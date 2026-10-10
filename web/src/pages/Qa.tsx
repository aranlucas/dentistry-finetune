import { useMutation, useQuery } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import { useState } from 'react';
import { api, generation, postJSON, type Qa as QaData, type QaOutput } from '../api';
import { Sheet } from '../components/Folder';
import { Answer, Answers, Evidence, Inspector, Prompt, SourceLink } from '../components/Inspector';
import { Alert, Finding, Lead, RunPicker, Section } from '../components/Lead';
import { KeyItem, ResultChart, type Mark } from '../components/ResultChart';
import { TrainingRun } from '../components/Training';
import { Field, TryPanel } from '../components/TryPanel';
import { Button, Raw, Search } from '../components/ui';
import { mib, pad, pct } from '../format';
import { useCaseFocus, within } from '../useCaseFocus';

const route = getRouteApi('/qa');
const labels = { base: 'Base model', adapter: 'Fine-tuned model' } as const;
type Key = keyof typeof labels;
const mean = (rows: NonNullable<QaOutput>[]) => (rows.length ? rows.reduce((s, r) => s + r.reference_word_f1, 0) / rows.length : null);

export function Qa() {
  const { run = 'long' } = route.useSearch(), navigate = route.useNavigate();
  const qa = useQuery(api.qa(run));
  const d = qa.data;
  const saved = (key: Key) => d?.cases.map(e => e.outputs[key]).filter((r): r is NonNullable<QaOutput> => !!r) ?? [];
  const base = saved('base'), tuned = saved('adapter'), complete = !!d && base.length === d.cases.length && tuned.length === d.cases.length;
  const delta = (mean(tuned) ?? 0) - (mean(base) ?? 0);

  return (
    <Sheet title="Dental Q&A" footer="Authored, source-linked answers are study aids, not official answer keys. Held-out topics were excluded from training and the questions were frozen before generation. Source data, weights, and raw outputs stay on this Mac.">
      <Alert error={qa.error} hint="Point .local/qa-run-history.json at the local run directories, then reload." />
      <Lead
        headline={!d ? (qa.error ? 'Results unavailable' : 'Answering study questions without notes')
          : complete
            // Twelve questions can't support a fine distinction, so small differences read as no change.
            ? (delta > 0.03 ? 'The fine-tuned answers share more words with the references' : 'Fine-tuning didn’t bring the answers closer to the references')
            : d.status.status === 'resource_blocked' ? 'This run is paused for memory' : 'This run is still in progress'}
        lede="A small Qwen3 model is fine-tuned on authored answers to AAPD flashcard questions, then asked twelve questions from topics it never trained on. No excerpts are supplied. Each answer sits beside the authored reference so you can judge it yourself."
        run={<RunPicker legend="Training run" value={run} onChange={v => navigate({ search: { run: v as 'long' | 'short' }, replace: true })}
          options={[{ value: 'long', label: 'Three passes' }, { value: 'short', label: 'Short pilot' }]}
          note={d && (d.schedule === 'qa-long-v1' ? `${d.planned_steps} updates over three passes, resumed across short bounded jobs.` : `${d.planned_steps} updates in one bounded job.`)} />}
      />
      {d && <Results key={run} d={d} complete={complete} base={base} tuned={tuned} reload={() => qa.refetch()} reloading={qa.isFetching} />}
      <Section title="Ask a study question" intro="Runs one question on this Mac with the selected training run. Nothing is saved. Check any answer against a source.">
        <Ask run={run} trained={!!d?.training} />
      </Section>
    </Sheet>
  );
}

function Results({ d, complete, base, tuned, reload, reloading }: {
  d: QaData; complete: boolean; base: NonNullable<QaOutput>[]; tuned: NonNullable<QaOutput>[]; reload: () => void; reloading: boolean;
}) {
  const focus = useCaseFocus();
  const [term, setTerm] = useState('');
  const filtered = d.cases.filter(e => (e.question + ' ' + e.source_title).toLowerCase().includes(term.toLowerCase()));
  const selected = within(filtered, focus.selected);
  const number = (id: string) => d.cases.findIndex(e => e.id === id) + 1;
  const e = d.cases.find(e => e.id === selected);

  return (
    <>
      <ResultChart title="Word overlap with the reference, per question" cellMin={40} selected={selected} onSelect={id => { setTerm(''); focus.open(id); }}
        groups={[{ label: 'Questions from held-out topics', columns: d.cases.map((e, i) => ({ id: e.id, number: i + 1, title: e.source_title })) }]}
        rows={(['base', 'adapter'] as const).map(key => {
          const rows = key === 'base' ? base : tuned;
          return {
            key, label: labels[key], tally: { value: pct(mean(rows)), unit: rows.length ? '%' : 'pending' },
            marks: Object.fromEntries(d.cases.map((e, i) => {
              const r = e.outputs[key];
              const mark: Mark = r
                ? { state: 'measure', value: r.reference_word_f1, text: pct(r.reference_word_f1),
                    flags: (r.repeated_fourgram ? 'R' : '') + (r.finish_reason === 'length' ? 'L' : ''),
                    label: `Question ${pad(i + 1)}, ${labels[key]}: ${pct(r.reference_word_f1)}% word overlap${r.repeated_fourgram ? ', repeated phrase' : ''}${r.finish_reason === 'length' ? ', hit token limit' : ''}` }
                : { state: 'none', label: `Question ${pad(i + 1)}, ${labels[key]}: not generated yet` };
              return [e.id, mark];
            })),
          };
        })}
        legend={<>
          <KeyItem>Numbers are word overlap with the reference, in percent. Overlap is not accuracy.</KeyItem>
          <KeyItem><b className="text-xs text-fail">R</b> repeated phrase</KeyItem>
          <KeyItem><b className="text-xs text-fail">L</b> hit the token limit</KeyItem>
          <KeyItem mark="none">Not generated yet</KeyItem>
        </>} />

      <Finding
        showsTitle={complete ? 'Answers saved, clinical review pending' : 'Progress so far'}
        shows={complete
          ? `Mean word overlap was ${pct(mean(base))}% for the base model and ${pct(mean(tuned))}% after fine-tuning. The fine-tuned model repeated itself in ${tuned.filter(r => r.repeated_fourgram).length} answers and hit the token limit in ${tuned.filter(r => r.finish_reason === 'length').length}. ${d.status.detail ?? ''}`
          : `${d.committed_steps} of ${d.planned_steps} training updates are committed, and ${base.length} base and ${tuned.length} fine-tuned answers are saved. ${d.status.detail ?? ''}`}
        limits={`Word overlap counts shared vocabulary; it can’t tell a correct answer from a fluent wrong one. ${d.evaluation_limit ?? ''}`} />

      <TrainingRun title="Training loss" loss={d.loss}
        model={`${d.model}, 4-bit, with thinking disabled. Rank-8 LoRA on the last four layers.`}
        facts={[['Training examples', d.dataset_counts.train], ['Validation examples', d.dataset_counts.valid],
                ['Updates', `${d.committed_steps}/${d.planned_steps}`], ...(d.training ? [['Training time', `${d.training.wall_seconds.toFixed(0)} s`] as [string, string]] : [])]}
        note={d.training
          ? `Peak MLX memory ${Math.round(d.training.mlx_peak_mib)} MiB, adapter ${mib(d.training.adapter_bytes)}. Model revision ${d.revision}.`
          : `Training hasn’t finished. ${d.status.detail ?? ''}`} />

      <Section id="cases" title="Read every answer" intro="The reference answer was withheld while the models generated. Open it below each pair."
        action={<Button onClick={reload} disabled={reloading}>Reload results</Button>}>
        <Inspector ref={focus.inspector} noun="questions" total={d.cases.length} selected={selected} onSelect={focus.setSelected}
          items={filtered.map(e => ({ id: e.id, number: number(e.id), text: e.question, sub: e.source_title }))}
          heading={item => `Question ${pad(item.number)} of ${d.cases.length}, asked with no excerpts`}
          tools={<Search aria-label="Search questions" placeholder="Search questions or sources" value={term} onChange={e => setTerm(e.target.value)} className="bg-sheet" />}>
          {e && <>
            <Prompt>{e.question}</Prompt>
            <Answers>
              {(['base', 'adapter'] as const).map(key => {
                const r = e.outputs[key];
                return (
                  <Answer key={key} title={labels[key]} prose raw={r?.raw}
                    verdict={{ state: 'none', text: r ? `${pct(r.reference_word_f1)}% overlap` : 'Not generated yet' }}
                    missing={{ title: 'No saved answer yet', detail: 'This question hasn’t been generated in this run.' }}
                    foot={r ? [`${r.seconds.toFixed(2)} s`, `${r.generation_tokens} tokens`, ...(r.finish_reason === 'length' ? ['hit the token limit'] : []),
                               ...(r.repeated_fourgram ? ['repeated phrase'] : [])].join(', ') : undefined} />
                );
              })}
            </Answers>
            <Evidence summary="Authored reference answer">
              <Raw prose className="mt-3.5 mb-2 min-h-0">{e.reference}</Raw>
              <SourceLink title={e.source_title} url={e.publisher_url} detail={e.source_revision ? `revision ${e.source_revision}` : undefined} />
            </Evidence>
          </>}
        </Inspector>
      </Section>
    </>
  );
}

function Ask({ run, trained }: { run: string; trained: boolean }) {
  const [question, setQuestion] = useState(''), [model, setModel] = useState<Key>('base');
  const ask = useMutation({ mutationFn: () => postJSON('/api/qa/predict', { question, condition: model, run }, generation) });
  const r = ask.data;
  return (
    <TryPanel prose model={model} onModel={v => setModel(v as Key)} action="Answer the question" busy={ask.isPending} disabled={!question.trim()}
      onRun={() => ask.mutate()} output={r?.raw}
      models={[{ value: 'base', label: labels.base }, { value: 'adapter', label: trained ? labels.adapter : 'Fine-tuned model (not trained yet)', disabled: !trained }]}
      status={ask.error ? ask.error.message : r && `${r.seconds.toFixed(2)} s, ${r.generation_tokens} tokens${r.finish_reason === 'length' ? ', hit the token limit' : ''}. Experimental answer; check it against a source.`}
      fields={<Field id="question" label="Question" value={question} onChange={setQuestion} maxLength={500}
                     placeholder="When is silver diamine fluoride appropriate for a young child?" />} />
  );
}
