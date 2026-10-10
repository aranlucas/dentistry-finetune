// Typed access to the local Python server. Every response is parsed with zod, so a missing or
// reshaped local file shows as an error instead of a half-drawn page. Nothing is invented client-side.
import { queryOptions } from '@tanstack/react-query';
import { z } from 'zod';

export class LocalDataError extends Error {}

async function read<S extends z.ZodType>(schema: S, response: Response, fallback: string): Promise<z.infer<S>> {
  const body: unknown = await response.json().catch(() => undefined);
  if (!response.ok) {
    const message = z.object({ error: z.string() }).safeParse(body);
    throw new LocalDataError(message.success ? message.data.error : fallback);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    const where = parsed.error.issues[0]?.path.join('.') || 'response';
    throw new LocalDataError(`The local server answered ${response.url ? new URL(response.url).pathname : ''} in an unexpected shape (at ${where}).`);
  }
  return parsed.data;
}

export const getJSON = async <S extends z.ZodType>(url: string, schema: S) =>
  read(schema, await fetch(url), `Local data unavailable at ${url}.`);

export const postJSON = async <S extends z.ZodType>(url: string, body: unknown, schema: S) =>
  read(schema, await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
       'Local inference stopped.');

const tally = z.object({ count: z.number(), total: z.number(), rate: z.number() });
export type Tally = z.infer<typeof tally>;

const lossRow = z.object({
  kind: z.enum(['train', 'validation']), iteration: z.number(),
  train_loss: z.number().optional(), val_loss: z.number().optional(),
});
export type LossRow = z.infer<typeof lossRow>;

const training = z.object({
  steps: z.number(), wall_seconds: z.number(), mlx_peak_mib: z.number(), adapter_bytes: z.number().optional(),
});

// Sentence-completion pilot
export const PILOT_KEYS = ['retrieval', 'base_rag', 'adapter_rag'] as const;
export type PilotKey = (typeof PILOT_KEYS)[number];
const metrics = z.object({ n: z.number(), json_valid: tally, schema_valid: tally, semantic_exact: tally });
const condition = z.object({ metrics, abstention_cases: metrics });
const report = z.object({
  conditions: z.object({ retrieval: condition, base_rag: condition, adapter_rag: condition }),
  training: training.optional(),
  reproduction_status: z.string().optional(),
  reproduction_detail: z.string().optional(),
  qualitative_failures: z.object({
    base_rag: z.object({ categories: z.record(z.string(), z.number()), target_ending_in_unstructured_output: z.number() }).optional(),
    adapter_rag: z.object({ schema_failure_reasons: z.record(z.string(), z.number()).optional() }).optional(),
  }).optional(),
});
export type Report = z.infer<typeof report>;

const pilotOutput = z.object({
  raw: z.string(), json_valid: z.boolean(), schema_valid: z.boolean(), semantic_exact: z.boolean(),
  seconds: z.number().nullish(),
}).nullable();
export type PilotOutput = z.infer<typeof pilotOutput>;
const pilotOutputs = z.partialRecord(z.enum(PILOT_KEYS), pilotOutput);
const passage = z.object({ citation: z.string(), text: z.string(), title: z.string(), url: z.string() });
const pilotCase = z.object({
  id: z.string(), kind: z.enum(['supported', 'missing_context', 'unsupported_or_malformed']), note: z.string(),
  expected: z.object({ answer: z.string(), citation: z.string() }),
  outputs: pilotOutputs, original_outputs: pilotOutputs, passages: z.array(passage),
});
export type PilotCase = z.infer<typeof pilotCase>;
const available = z.object({ base_rag: z.number(), adapter_rag: z.number() });
const comparison = z.object({
  cases: z.array(pilotCase), loss: z.array(lossRow), original_loss: z.array(lossRow),
  reproduction: z.boolean(), report: report.optional(),
  available_outputs: available, original_available_outputs: available,
  demo_model_available: z.boolean(), demo_adapter_available: z.boolean(),
});
export type Comparison = z.infer<typeof comparison>;
const practice = z.array(z.object({ id: z.string(), note: z.string(), passages: z.array(z.object({ citation: z.string(), text: z.string() })) }));
export const pilotPrediction = z.object({ raw: z.string(), seconds: z.number(), schema_valid: z.boolean(), supported_quote: z.boolean() });

// Dental Q&A without excerpts
const qaOutput = z.object({
  raw: z.string(), reference_word_f1: z.number(), repeated_fourgram: z.boolean(), finish_reason: z.string(),
  seconds: z.number(), generation_tokens: z.number(),
}).nullish();
export type QaOutput = z.infer<typeof qaOutput>;
const qaCase = z.object({
  id: z.string(), question: z.string(), reference: z.string(), source_title: z.string(), publisher_url: z.string(),
  source_revision: z.string().nullish(), outputs: z.object({ base: qaOutput, adapter: qaOutput }),
});
const qa = z.object({
  model: z.string(), revision: z.string(), dataset_counts: z.object({ train: z.number(), valid: z.number(), test: z.number() }),
  training: training.nullable(), loss: z.array(lossRow), status: z.object({ status: z.string(), detail: z.string().nullish() }),
  cases: z.array(qaCase), schedule: z.string(), planned_steps: z.number(), committed_steps: z.number(),
  evaluation_limit: z.string().nullish(),
});
export type Qa = z.infer<typeof qa>;
export const generation = z.object({
  raw: z.string(), seconds: z.number(), generation_tokens: z.number(),
  finish_reason: z.string().nullish(), temperature: z.number().nullish(),
});

// Reviewed development answers
export const DECISIONS = ['pass', 'partial', 'fail'] as const;
export type Decision = (typeof DECISIONS)[number];
const devOutput = z.object({
  raw: z.string(), judgment: z.object({ decision: z.enum(DECISIONS), reason: z.string() }).nullish(),
  generation_tokens: z.number(), seconds: z.number(), finish_reason: z.string(),
}).nullish();
export type DevOutput = z.infer<typeof devOutput>;
export type DevCase = z.infer<typeof devCase>;
const devCase = z.object({
  id: z.string(), question: z.string(), reference: z.string(), criteria: z.string(),
  publisher_references: z.array(z.object({ title: z.string(), url: z.string(), revision: z.string().nullish() })),
  retrieved_passages: z.array(z.object({ title: z.string(), url: z.string(), text: z.string() })).nullish(),
  outputs: z.object({ base: devOutput, adapter: devOutput }),
});
const counts = z.object({ pass: z.number(), partial: z.number(), fail: z.number(), pending: z.number() });
const development = z.object({
  runs: z.array(z.object({ id: z.string(), label: z.string() })), label: z.string(), limits: z.string(), input_mode: z.string(),
  counts: z.object({ base: counts, adapter: counts }), temperature: z.number(), training: training.nullable(),
  steps: z.number(), planned_steps: z.number(), cases: z.array(devCase),
});
export type Development = z.infer<typeof development>;
export const READER_MODE = 'Question with reviewer-selected publisher excerpts';

export const api = {
  results: () => queryOptions({ queryKey: ['results'], queryFn: () => getJSON('/api/results', report) }),
  comparison: () => queryOptions({ queryKey: ['comparison'], queryFn: () => getJSON('/api/comparison', comparison) }),
  practice: () => queryOptions({ queryKey: ['practice'], queryFn: () => getJSON('/api/practice', practice), staleTime: Infinity }),
  qa: (run: string) => queryOptions({ queryKey: ['qa', run], queryFn: () => getJSON('/api/qa?run=' + encodeURIComponent(run), qa) }),
  development: (run: string | undefined) => queryOptions({
    queryKey: ['development', run ?? 'default'],
    queryFn: () => getJSON('/api/development' + (run ? '?run=' + encodeURIComponent(run) : ''), development),
  }),
};
