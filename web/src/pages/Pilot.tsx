import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import { useState } from 'react';
import { api, pilotPrediction, postJSON, PILOT_KEYS, type Comparison, type PilotCase, type PilotKey, type PilotOutput, type Report } from '../api';
import { Sheet } from '../components/Folder';
import { Answer, Answers, Evidence, Excerpt, Inspector, Prompt, Target } from '../components/Inspector';
import { Alert, Finding, Lead, RunPicker, Section } from '../components/Lead';
import { KeyItem, ResultChart, type Mark } from '../components/ResultChart';
import { TrainingRun } from '../components/Training';
import { Field, FieldActions, TryPanel } from '../components/TryPanel';
import { Button, H3, Search, Select } from '../components/ui';
import { mib, tally } from '../format';
import { useCaseFocus, within } from '../useCaseFocus';

const route = getRouteApi('/');
const names: Record<PilotKey, string> = { retrieval: 'Keyword baseline', base_rag: 'Base model', adapter_rag: 'Fine-tuned model' };
const kinds: Record<PilotCase['kind'], string> = {
  supported: 'Answer is in the excerpts', missing_context: 'No excerpts supplied', unsupported_or_malformed: 'Unsupported or malformed',
};

export function Pilot() {
  const results = useQuery(api.results()), comparison = useQuery(api.comparison());
  const search = route.useSearch(), navigate = route.useNavigate();
  const c = comparison.data;
  const canReplay = !!(c?.reproduction && c.report);
  const replay = (search.run ?? (canReplay ? 'replay' : 'original')) === 'replay' && canReplay;
  const report = replay ? c?.report : results.data;
  const error = results.error ?? comparison.error;

  return (
    <Sheet title="Sentence completion" footer="Source excerpts and model answers are read from this Mac; no external model service is called. The questions were generated mechanically from publisher references and frozen before any evaluation. No clinician has reviewed them.">
      <Alert error={error} hint="Start the local server with make dev and keep the frozen experiment files in place." />
      <Lead
        headline={headline(report, error)}
        lede="Each of the 24 held-out cases asks a model to finish a sentence from a dental reference, cite the excerpt it came from, or abstain when the excerpts don’t contain it. A keyword baseline that copies the matching sentence is shown for comparison."
        run={<RunPicker legend="Run" value={replay ? 'replay' : 'original'} onChange={run => navigate({ search: { run: run as 'original' | 'replay' }, replace: true })}
          options={[{ value: 'original', label: 'Original' },
                    { value: 'replay', label: c?.report?.reproduction_status ? (c.report.reproduction_status === 'resource_blocked' ? 'Reproduction (paused)' : 'Reproduction (running)') : 'Reproduction', disabled: !canReplay }]}
          note={!c ? 'Checking for local answer files.' : replay ? 'New generations from the same frozen recipe. The original results are unchanged.' : 'Scores from the saved report. Per-case answer files may be absent.'} />}
      />
      {c && report && <Results c={c} report={report} replay={replay} />}
      <Section title="Try a note" intro="Runs one request on this Mac. It doesn’t change either run’s results, and nothing you type is saved.">
        <Try c={c} />
      </Section>
    </Sheet>
  );
}

function headline(r: Report | undefined, error: unknown) {
  if (error) return 'Results unavailable';
  if (!r) return 'Reading the saved results…';
  if (r.reproduction_status) return r.reproduction_status === 'resource_blocked' ? 'The reproduction is paused for memory.' : 'The reproduction is still running.';
  const base = r.conditions.base_rag.metrics.semantic_exact, tuned = r.conditions.adapter_rag.metrics.semantic_exact;
  return tuned.count === 0 ? 'The fine-tuned model produced no usable answers.'
    : tuned.rate > base.rate ? 'The fine-tune improved exact answers.' : 'The fine-tune did not improve exact answers.';
}

function Results({ c, report: r, replay }: { c: Comparison; report: Report; replay: boolean }) {
  const focus = useCaseFocus();
  const [term, setTerm] = useState(''), [kind, setKind] = useState<'all' | PilotCase['kind']>('all');
  const outputOf = (e: PilotCase, key: PilotKey) => (replay ? e.outputs : e.original_outputs)[key] ?? null;
  const number = (e: PilotCase) => c.cases.indexOf(e) + 1;
  const m = (k: PilotKey) => r.conditions[k].metrics.semantic_exact;
  const supported = c.cases.filter(e => e.kind === 'supported'), abstain = c.cases.filter(e => e.kind !== 'supported');
  const column = (e: PilotCase) => ({ id: e.id, number: number(e) });
  const filtered = c.cases.filter(e => (kind === 'all' || e.kind === kind) && (e.note.toLowerCase().includes(term.toLowerCase()) || e.id.includes(term)));
  const selected = within(filtered, focus.selected);
  const have = replay ? c.available_outputs : c.original_available_outputs;
  const failures = r.qualitative_failures, why = failures?.adapter_rag?.schema_failure_reasons ?? {};

  return (
    <>
      <ResultChart title="Results for every held-out case" selected={selected} onSelect={id => { setTerm(''); setKind('all'); focus.open(id); }}
        groups={[{ label: 'Answer is in the excerpts', columns: supported.map(column) }, { label: 'Correct response is to abstain', columns: abstain.map(column) }]}
        rows={PILOT_KEYS.map(key => ({
          key, label: names[key], tally: m(key).total ? { value: m(key).count, unit: `/${m(key).total}` } : { value: '–', unit: 'pending' },
          marks: Object.fromEntries(c.cases.map(e => {
            const out = outputOf(e, key), state = out ? (out.semantic_exact ? 'pass' : 'fail') : 'none';
            return [e.id, { state, label: `Case ${number(e)}, ${names[key]}: ${state === 'pass' ? 'correct' : state === 'fail' ? 'failed' : 'answer not saved'}` } satisfies Mark];
          })),
        }))}
        legend={<>
          <KeyItem mark="pass">Exact answer and citation</KeyItem>
          <KeyItem mark="fail">Failed the answer contract</KeyItem>
          <KeyItem mark="none">Answer text not saved on this Mac</KeyItem>
          <KeyItem>Select a mark to read that answer.</KeyItem>
        </>} />

      {r.reproduction_status
        ? <Finding showsTitle="Progress so far" shows={`${r.conditions.base_rag.metrics.n} base and ${r.conditions.adapter_rag.metrics.n} fine-tuned answers are saved. Answers already generated are kept when the resource guard stops a job. ${r.reproduction_detail ?? ''}`} limits={limits} />
        : <Finding shows={`The keyword baseline scored ${tally(m('retrieval'))}. The base model scored ${tally(m('base_rag'))} and the fine-tuned model ${tally(m('adapter_rag'))}. Lower validation loss did not translate into better generated answers. Prefer the deterministic baseline for this task; these results don’t justify scaling the fine-tune.`} limits={limits} />}

      <Section title="The answer contract" intro="A usable answer is valid JSON, follows the schema, quotes the right ending, and cites the right excerpt. Abstaining when the evidence is missing counts as correct.">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[15px] tabular-nums">
            <thead>
              <tr className="border-b-2 border-form text-sm text-form">
                {['Condition', 'Parseable JSON', 'Valid schema', 'Exact answer and citation', 'Correct abstentions'].map((h, i) =>
                  <th key={h} scope="col" className={`px-3 pb-3 align-bottom font-normal ${i ? 'text-right' : 'pl-0 text-left'}`}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {PILOT_KEYS.map(key => {
                const v = r.conditions[key];
                return (
                  <tr key={key} className="border-b border-rule">
                    <th scope="row" className="py-3 pr-3 text-left font-semibold whitespace-nowrap">{names[key]}</th>
                    {[v.metrics.json_valid, v.metrics.schema_valid, v.metrics.semantic_exact, v.abstention_cases.semantic_exact].map((t, i) =>
                      <td key={i} className={`px-3 py-3 text-right font-num text-[17px] ${t.total && t.count === t.total ? 'text-pass' : 'text-fail'}`}>{tally(t)}</td>)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-6 grid gap-6 text-[15px] text-muted md:grid-cols-2 md:gap-12">
          <div>
            <H3 className="text-ink">How the base model failed</H3>
            {failures?.base_rag ? <>
              <p>{failures.base_rag.categories.unstructured_prose_or_echo ?? 0} answers were free text or echoed the prompt instead of JSON.</p>
              <p className="mt-1.5">The expected ending appeared somewhere in {failures.base_rag.target_ending_in_unstructured_output} of them. That doesn’t meet the contract, so they count as failures.</p>
            </> : <p>Failure categories are not available for this run.</p>}
          </div>
          <div>
            <H3 className="text-ink">How the fine-tuned model failed</H3>
            {failures?.adapter_rag ? <>
              <p>{why['JSON parse failure'] ?? 0} answers attempted JSON that didn’t parse.</p>
              <p className="mt-1.5">{(why['Invalid citation label'] ?? 0) + (why['Inconsistent abstention/citation'] ?? 0)} parsed but broke the schema: a made-up citation label, or an abstention that also cited an excerpt.</p>
            </> : <p>Failure categories are not available for this run.</p>}
          </div>
        </div>
      </Section>

      <TrainingRun title="Loss fell; answers didn’t improve" loss={replay ? c.loss : c.original_loss}
        model="SmolLM2-135M-Instruct with a rank-8 LoRA on its last four layers, trained on an Apple M5 with 16 GiB of shared memory."
        facts={r.training ? [['Updates', r.training.steps], ['Training time', `${r.training.wall_seconds.toFixed(1)} s`],
                             ['Peak MLX memory', `${Math.round(r.training.mlx_peak_mib)} MiB`], ['Adapter size', mib(r.training.adapter_bytes)]] : []}
        note={!r.training ? 'Adapter training hasn’t finished in this run.' : replay
          ? 'This reproduction is a separate run of the same recipe; its numbers are not merged with the original.'
          : 'An earlier 120-update attempt stopped at 59 updates on the swap guard before saving. This 40-update run is the one evaluated; no checkpoint was chosen using held-out results.'} />

      <Section id="cases" title="Read every answer" intro={replay
        ? `Showing the reproduction’s own answers: ${have.base_rag} from the base model and ${have.adapter_rag} from the fine-tuned model. These are new generations, not the original outputs.`
        : `${have.base_rag} base and ${have.adapter_rag} fine-tuned answers from the original run are on this Mac. Missing answers are marked, never filled in.`}>
        <Inspector ref={focus.inspector} noun="cases" total={c.cases.length} selected={selected} onSelect={focus.setSelected}
          items={filtered.map(e => ({ id: e.id, number: number(e), text: e.note, sub: kinds[e.kind] }))}
          heading={item => `Case ${String(item.number).padStart(2, '0')}, ${kinds[c.cases[item.number - 1].kind].toLowerCase()}`}
          tools={<>
            <Search aria-label="Search study notes" placeholder="Search notes" value={term} onChange={e => setTerm(e.target.value)} className="bg-sheet" />
            <Select aria-label="Case type" value={kind} onChange={e => setKind(e.target.value as typeof kind)} className="bg-sheet">
              <option value="all">All cases</option>
              {Object.entries(kinds).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </Select>
          </>}>
          {selected && <PilotCaseDetail e={c.cases.find(e => e.id === selected)!} outputOf={outputOf} />}
        </Inspector>
      </Section>
    </>
  );
}

const limits = 'This is a narrow extraction task. It doesn’t test dental question answering, oral-board reasoning, or clinical reliability. The keyword baseline wins because the question quotes the start of the target sentence.';

function PilotCaseDetail({ e, outputOf }: { e: PilotCase; outputOf: (e: PilotCase, key: PilotKey) => PilotOutput }) {
  return (
    <>
      <Prompt>{e.note || '(Empty study note)'}</Prompt>
      <Target title="Expected answer" answer={e.expected.answer} note={`Cites ${e.expected.citation}. This is the frozen reference, not a model answer.`} />
      <Answers>
        {(['base_rag', 'adapter_rag'] as const).map(key => {
          const out = outputOf(e, key), state = !out ? 'none' : out.semantic_exact ? 'pass' : 'fail';
          return (
            <Answer key={key} title={names[key]} raw={out?.raw}
              verdict={{ state, text: { pass: 'Correct', fail: 'Failed', none: 'Not saved' }[state] }}
              missing={{ title: 'No answer text on this Mac', detail: 'This run’s prediction file isn’t present. Nothing has been substituted.' }}
              foot={out ? [out.json_valid ? 'JSON parses' : 'JSON doesn’t parse', out.schema_valid ? 'schema valid' : 'schema invalid',
                           ...(out.seconds != null ? [`${out.seconds.toFixed(2)} s`] : [])].join(', ') : undefined} />
          );
        })}
      </Answers>
      <Evidence open summary={e.passages.length ? `Excerpts given to the models (${e.passages.length})` : 'No excerpts were given'}>
        {!e.passages.length && <p className="pt-2 text-sm text-muted">With no evidence, the correct response is to abstain.</p>}
        {e.passages.map(p => <Excerpt key={p.citation} tag={p.citation} text={p.text} title={p.title} url={p.url} />)}
      </Evidence>
    </>
  );
}

function Try({ c }: { c?: Comparison }) {
  const client = useQueryClient();
  const [note, setNote] = useState('Supply the exact missing ending for review: The blue lamp');
  const [s1, setS1] = useState('The blue lamp is on the desk.'), [s2, setS2] = useState('The red coat is by the door.');
  const [model, setModel] = useState('retrieval'), [sample, setSample] = useState(0), [hint, setHint] = useState<string>();
  const run = useMutation({
    mutationFn: () => postJSON('/api/predict', {
      condition: model, note, passages: [s1, s2].filter(Boolean).map((text, i) => ({ citation: `S${i + 1}`, text })),
    }, pilotPrediction),
    onMutate: () => setHint(undefined),
  });
  const ready = (key: PilotKey) => key === 'retrieval' || (!!c?.demo_model_available && (key === 'base_rag' || c.demo_adapter_available));
  const loadSample = async () => {
    try {
      const rows = await client.fetchQuery(api.practice()), e = rows[sample % rows.length];
      setSample(sample + 1); setNote(e.note); setS1(e.passages[0]?.text ?? ''); setS2(e.passages[1]?.text ?? '');
      setHint('Loaded a held-out example.');
    } catch { setHint('The local study corpus isn’t on this Mac. The synthetic example still works.'); }
  };
  const r = run.data;
  return (
    <TryPanel model={model} onModel={setModel} action="Complete the note" busy={run.isPending} onRun={() => run.mutate()}
      models={PILOT_KEYS.map(k => ({ value: k, label: ready(k) ? names[k] : `${names[k]} (weights not on this Mac)`, disabled: !ready(k) }))}
      output={r?.raw}
      status={run.error ? run.error.message : hint ?? (r && `${r.seconds.toFixed(2)} s. Schema ${r.schema_valid ? 'valid' : 'invalid'}. ${r.supported_quote ? 'The quote appears in the cited excerpt.' : 'No supported quote; check the response.'}`)}
      fields={<>
        <Field id="note" label="Study note" value={note} onChange={setNote} maxLength={240} />
        <Field id="s1" label="Excerpt S1" value={s1} onChange={setS1} maxLength={450} />
        <Field id="s2" label="Excerpt S2" value={s2} onChange={setS2} maxLength={450} />
        <FieldActions>
          <Button onClick={loadSample}>Load a held-out example</Button>
          <Button onClick={() => { setS1(''); setS2(''); setHint('With no excerpts, the correct response is to abstain.'); }}>Clear excerpts</Button>
        </FieldActions>
      </>} />
  );
}
