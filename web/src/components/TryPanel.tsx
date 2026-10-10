import type { ReactNode } from 'react';
import type { RunOption } from './Lead';
import { Button, Label, Raw, Select, TextArea } from './ui';

/** Run one request on this Mac. Inputs on the left; model choice, action, and result on the right. */
export function TryPanel({ fields, models, model, onModel, action, busy, disabled, onRun, output, prose, status }: {
  fields: ReactNode; models: RunOption[]; model: string; onModel: (v: string) => void;
  action: string; busy: boolean; disabled?: boolean; onRun: () => void;
  output?: string; prose?: boolean; status?: ReactNode;
}) {
  return (
    <div className="grid gap-6 md:grid-cols-2 md:gap-12">
      <div className="min-w-0">{fields}</div>
      <div className="min-w-0">
        <Label htmlFor="try-model">Answer with</Label>
        <Select id="try-model" value={model} onChange={e => onModel(e.target.value)}>
          {models.map(m => <option key={m.value} value={m.value} disabled={m.disabled}>{m.label}</option>)}
        </Select>
        <div className="mt-4 flex flex-wrap items-center gap-2.5">
          <Button primary disabled={busy || disabled} onClick={onRun}>{busy ? 'Running on this Mac…' : action}</Button>
        </div>
        <Raw prose={prose} className="mt-4">{output ?? 'The response appears here.'}</Raw>
        <div role="status" className="mt-2.5 min-h-[22px] text-sm text-muted">{status}</div>
      </div>
    </div>
  );
}

export function Field({ id, label, value, onChange, rows = 3, maxLength, placeholder }: {
  id: string; label: string; value: string; onChange: (v: string) => void; rows?: number; maxLength: number; placeholder?: string;
}) {
  return (
    <>
      <Label htmlFor={id}>{label}</Label>
      <TextArea id={id} rows={rows} maxLength={maxLength} placeholder={placeholder} value={value} onChange={e => onChange(e.target.value)} />
    </>
  );
}

/** Secondary actions under the inputs, such as loading an example. */
export const FieldActions = ({ children }: { children: ReactNode }) =>
  <div className="mt-4 flex flex-wrap items-center gap-2.5">{children}</div>;
