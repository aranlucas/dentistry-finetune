import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { useState, type RefObject } from "react";
import {
  api,
  generation,
  postJSON,
  READER_MODE,
  type QuestionPredictionRequest,
  type DevCase,
  type Development as DevData,
} from "../api";
import { Sheet } from "../components/folder";
import {
  Answer,
  Answers,
  Evidence,
  Excerpt,
  Inspector,
  Prompt,
  SourceLink,
} from "../components/inspector";
import { Alert, Finding, Lead, RunPicker, Section } from "../components/lead";
import { KeyItem, ResultChart, type Glyph } from "../components/result-chart";
import { TrainingRun, type TrainingFact } from "../components/training";
import { Field, FieldActions, TryPanel } from "../components/try-panel";
import { Button, Raw, Search } from "../components/ui";
import { mib, pad } from "../format";
import { useCaseFocus, within } from "../use-case-focus";

type ResultsProps = {
  d: DevData;
  focusedCase: string | undefined;
  inspectorRef: RefObject<HTMLElement | null>;
  onOpen: (id: string) => void;
  onSelect: (id: string) => void;
  reload: () => void;
  reloading: boolean;
};

type AskProps = { d: DevData; run: string | undefined; current?: DevCase };

const route = getRouteApi("/development");

const labels = { base: "Base model", adapter: "Fine-tuned model" } as const;

type Key = keyof typeof labels;

const verdictText: Record<Glyph, string> = {
  pass: "Pass",
  partial: "Partial",
  fail: "Fail",
  none: "Review pending",
};

const glyph = (e: DevCase, key: Key): Glyph => e.outputs[key]?.judgment?.decision ?? "none";

export function Development() {
  const { run } = route.useSearch();
  const navigate = route.useNavigate();
  const [navigationError, setNavigationError] = useState<Error | null>(null);
  const dev = useQuery({ ...api.development(run), placeholderData: keepPreviousData });
  const d = dev.data;
  const n = d?.cases.length ?? 0;
  const base = d?.counts.base;
  const tuned = d?.counts.adapter;
  const pending = (base?.pending ?? 0) + (tuned?.pending ?? 0);
  const { selected: focusedCase, inspectorRef, open, setSelected } = useCaseFocus();

  return (
    <Sheet
      title="Reviewed answers"
      footer="Everything shown is read from files on this Mac. Questions, source text, raw answers, judgments and model weights remain local. The earlier pilot and held-out results are preserved."
    >
      <Alert error={navigationError ?? dev.error} />
      <Lead
        headline={
          !d || !base || !tuned
            ? dev.error
              ? "Results unavailable"
              : "Reading the reviewed answers…"
            : pending
              ? "Review is still in progress"
              : `The fine-tuned model passed review on ${tuned.pass} of ${n} questions`
        }
        lede={`The base model passed on ${base?.pass ?? "–"} of the same questions. Each question asks about a fact the model trained on, in new wording. Both models answer; the assistant judges each answer against the source-supported study answer. Read the answers, the judgments, and the reasons below.`}
        run={
          d && (
            <RunPicker
              legend="Development run"
              value={run ?? d.runs.find((r) => r.label === d.label)?.id ?? d.runs[0]?.id}
              onChange={(value) => {
                setNavigationError(null);
                void navigate({ search: { run: value }, replace: true }).catch((error) => {
                  setNavigationError(
                    error instanceof Error
                      ? error
                      : new Error("Unable to change the selected run."),
                  );
                });
              }}
              options={d.runs.map((r) => ({ value: r.id, label: r.label }))}
              note={dev.isFetching ? "Reading this run…" : d.input_mode}
            />
          )
        }
      />
      {d && (
        <Results
          key={run ?? "default"}
          d={d}
          focusedCase={focusedCase}
          inspectorRef={inspectorRef}
          onOpen={open}
          onSelect={setSelected}
          reload={() => {
            dev.refetch().catch((error) => {
              setNavigationError(
                error instanceof Error ? error : new Error("Unable to reload local results."),
              );
            });
          }}
          reloading={dev.isFetching}
        />
      )}
      {d && (d.input_mode === "Question alone" || d.input_mode === READER_MODE) && (
        <Section
          title={
            d.input_mode === READER_MODE ? "Ask with a reference" : "Try another study question"
          }
          intro="Uses the selected run’s completed adapter on this Mac. This narrow experiment needs source checking. Questions and answers here are not saved."
        >
          <Ask
            d={d}
            run={run ?? d.runs[0]?.id}
            current={d.cases.find((q) => q.id === focusedCase) ?? d.cases[0]}
          />
        </Section>
      )}
    </Sheet>
  );
}

function Results({
  d,
  focusedCase,
  inspectorRef,
  onOpen,
  onSelect,
  reload,
  reloading,
}: ResultsProps) {
  const [term, setTerm] = useState("");
  const [failures, setFailures] = useState(false);

  const filtered = d.cases.filter(
    (q) =>
      (q.question + " " + q.publisher_references.map((r) => r.title).join(" "))
        .toLowerCase()
        .includes(term.toLowerCase()) &&
      (!failures || glyph(q, "base") === "fail" || glyph(q, "adapter") === "fail"),
  );

  const selected = within(filtered, focusedCase);
  const number = (id: string) => d.cases.findIndex((q) => q.id === id) + 1;
  const selectedCase = d.cases.find((q) => q.id === selected);
  const count = (key: Key) => d.counts[key];

  return (
    <>
      <ResultChart
        title="Review result by question and model"
        selected={selected}
        onSelect={(id) => {
          setTerm("");
          setFailures(false);
          onOpen(id);
        }}
        groups={[
          {
            label: "Development questions on facts seen in training",
            columns: d.cases.map((q, i) => ({ id: q.id, number: i + 1 })),
          },
        ]}
        rows={(["base", "adapter"] as const).map((key) => ({
          key,
          label: labels[key],
          tally: { value: count(key).pass, unit: `/${d.cases.length}` },
          marks: Object.fromEntries(
            d.cases.map((q, i) => [
              q.id,
              {
                state: glyph(q, key),
                label: `Question ${i + 1}, ${labels[key]}: ${verdictText[glyph(q, key)].toLowerCase()}`,
              },
            ]),
          ),
        }))}
        legend={
          <>
            <KeyItem mark="pass">Pass</KeyItem>
            <KeyItem mark="partial">Partial: misses a fact or qualifier</KeyItem>
            <KeyItem mark="fail">Fail</KeyItem>
            <KeyItem mark="none">Review pending</KeyItem>
          </>
        }
      />

      <Finding
        showsTitle="What a pass means"
        limitsTitle="Development, with known facts"
        shows={`The answer addresses the required facts, preserves the relevant conditions, and adds no unsupported claims. Partial answers miss facts or qualifiers; wrong or unusable answers fail. Base model: ${count("base").partial} partial, ${count("base").fail} fail. Fine-tuned model: ${count("adapter").partial} partial, ${count("adapter").fail} fail.`}
        limits={d.limits}
      />

      <TrainingRun
        title="Training run"
        model={d.label}
        facts={[
          ["Updates", `${d.steps}/${d.planned_steps}`],
          ["Questions", d.cases.length],
          ["Sampling temperature", d.temperature],
          ...(d.training
            ? [["Training time", `${d.training.wall_seconds.toFixed(0)} s`] satisfies TrainingFact]
            : []),
        ]}
        note={
          d.training
            ? `Peak MLX memory ${Math.round(d.training.mlx_peak_mib)} MiB, adapter ${mib(d.training.adapter_bytes)}. Input: ${d.input_mode}.`
            : "Training hasn’t finished in this run."
        }
      />

      <Section
        id="cases"
        title="Read every answer"
        intro="Each answer sits beside the assistant’s judgment and its reason. The source-supported study answer is below each pair."
        action={
          <Button onClick={reload} disabled={reloading}>
            Reload results
          </Button>
        }
      >
        <Inspector
          ref={inspectorRef}
          noun="questions"
          total={d.cases.length}
          selected={selected}
          onSelect={onSelect}
          items={filtered.map((q) => ({
            id: q.id,
            number: number(q.id),
            text: q.question,
            sub: q.publisher_references[0]?.title ?? "",
          }))}
          heading={(item) => `Question ${pad(item.number)} of ${d.cases.length}`}
          tools={
            <>
              <Search
                aria-label="Find a question"
                placeholder="Find a question or topic"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                className="bg-sheet"
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={failures}
                  onChange={(e) => setFailures(e.target.checked)}
                  className="accent-pass"
                />
                Only questions with a failed answer
              </label>
            </>
          }
        >
          {selectedCase && (
            <>
              <Prompt>{selectedCase.question}</Prompt>
              <p className="-mt-3 mb-6 max-w-[70ch] text-sm text-muted">
                Review criteria: {selectedCase.criteria}
              </p>
              <Answers>
                {(["base", "adapter"] as const).map((key) => {
                  const r = selectedCase.outputs[key];

                  return (
                    <Answer
                      key={key}
                      title={labels[key]}
                      prose
                      raw={r?.raw}
                      verdict={{
                        state: glyph(selectedCase, key),
                        text: verdictText[glyph(selectedCase, key)],
                      }}
                      reason={
                        r
                          ? (r.judgment?.reason ??
                            "No assistant judgment has been logged for this answer yet.")
                          : undefined
                      }
                      missing={{
                        title: "Not generated yet",
                        detail: "This answer hasn’t been generated in this run.",
                      }}
                      foot={
                        r
                          ? `${r.generation_tokens} tokens, ${r.seconds.toFixed(2)} s, finished by ${r.finish_reason}`
                          : undefined
                      }
                    />
                  );
                })}
              </Answers>
              <Evidence summary="Source-supported study answer and references">
                <Raw prose className="mt-3.5 mb-2 min-h-0">
                  {selectedCase.reference}
                </Raw>
                {selectedCase.publisher_references.map((ref) => (
                  <SourceLink
                    key={ref.url}
                    title={ref.title}
                    url={ref.url}
                    detail={`revision ${ref.revision?.length ? ref.revision : "unspecified"}`}
                  />
                ))}
              </Evidence>
              {!!selectedCase.retrieved_passages?.length && (
                <Evidence
                  summary={`Publisher excerpts supplied to both models (${selectedCase.retrieved_passages.length})`}
                >
                  {selectedCase.retrieved_passages.map((p, i) => (
                    <Excerpt
                      key={`${p.url}:${p.text}`}
                      tag={`S${i + 1}`}
                      text={p.text}
                      title={p.title}
                      url={p.url}
                    />
                  ))}
                </Evidence>
              )}
            </>
          )}
        </Inspector>
      </Section>
    </>
  );
}

function Ask({ d, run, current }: AskProps) {
  const reader = d.input_mode === READER_MODE;
  const [question, setQuestion] = useState("");
  const [reference, setReference] = useState("");
  const [model, setModel] = useState<Key>("adapter");

  const ask = useMutation({
    mutationFn: () => {
      const request: QuestionPredictionRequest = { question, condition: model, run };

      if (reader) {
        request.reference = reference;
      }

      return postJSON("/api/development/predict", request, generation);
    },
  });

  const r = ask.data;

  return (
    <TryPanel
      prose
      model={model}
      onModel={(value) => {
        if (value === "base" || value === "adapter") {
          setModel(value);
        }
      }}
      action="Answer locally"
      busy={ask.isPending}
      disabled={!d.training || !question.trim()}
      onRun={() => ask.mutate()}
      output={r?.raw}
      models={[
        { value: "adapter", label: labels.adapter },
        { value: "base", label: labels.base },
      ]}
      status={
        ask.error
          ? ask.error.message
          : r &&
            `${r.seconds.toFixed(2)} s, ${r.generation_tokens} tokens, temperature ${r.temperature ?? "not recorded"}. Experimental study answer; verify it against a source.`
      }
      fields={
        <>
          <Field
            id="dev-question"
            label="Study question"
            value={question}
            onChange={setQuestion}
            maxLength={500}
            placeholder="Ask about one of the reviewed study topics"
          />
          {reader && (
            <>
              <Field
                id="dev-reference"
                label="Publisher reference excerpt"
                rows={5}
                value={reference}
                onChange={setReference}
                maxLength={2000}
                placeholder="Paste a short publisher excerpt supporting your question"
              />
              <p className="mt-2 text-sm text-muted">
                Use a short excerpt. The complete input must fit the local model’s token budget.
              </p>
              <FieldActions>
                <Button
                  onClick={() => {
                    if (current) {
                      setQuestion(current.question);
                      setReference(
                        (current.retrieved_passages ?? []).map((p) => p.text).join("\n\n"),
                      );
                    }
                  }}
                >
                  Use the selected question’s excerpts
                </Button>
              </FieldActions>
            </>
          )}
        </>
      }
    />
  );
}
