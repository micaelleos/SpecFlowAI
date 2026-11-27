import { useId, useState } from 'react'

import { t } from '../i18n/en'
import type { EditableSpec, EpicSpec, Scenario, WorkItemSpec } from '../product/types'
import { Button } from './ui'

type ScenarioKind = Scenario['kind']
const KINDS: ScenarioKind[] = ['principal', 'alternativo', 'erro', 'borda']

const input =
  'w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none'

/**
 * Editor da proposta por seção do `AgentReadySpec` (F14-RF-06): todas as seções aparecem, mesmo
 * vazias, e esvaziar uma obrigatória só derruba a prontidão (F14-RT-04). Listas: um item por linha.
 */
export function SpecEditor({
  spec,
  onChange,
}: {
  spec: EditableSpec
  onChange: (spec: EditableSpec) => void
}) {
  const e = t.chat.edit
  return (
    <div className="flex flex-col gap-4">
      <TextField
        label={e.title}
        value={spec.title}
        onChange={(title) => onChange({ ...spec, title })}
      />
      {spec.type === 'epic' ? (
        <EpicFields spec={spec} onChange={onChange} />
      ) : (
        <WorkItemFields spec={spec} onChange={onChange} />
      )}
    </div>
  )
}

function WorkItemFields({
  spec,
  onChange,
}: {
  spec: WorkItemSpec
  onChange: (spec: WorkItemSpec) => void
}) {
  const e = t.chat.edit
  const list = (key: keyof WorkItemSpec, label: string) => (
    <ListField
      label={label}
      items={(spec[key] as string[] | undefined) ?? []}
      onChange={(items) => onChange({ ...spec, [key]: items })}
    />
  )
  return (
    <>
      <TextField
        label={e.objective}
        multiline
        value={spec.objective ?? ''}
        onChange={(objective) => onChange({ ...spec, objective })}
      />
      {list('context', e.context)}
      <Scenarios
        items={spec.acceptance_criteria ?? []}
        onChange={(acceptance_criteria) => onChange({ ...spec, acceptance_criteria })}
      />
      {list('out_of_scope', e.outOfScope)}
      {list('constraints', e.constraints)}
      {list('where_to_change', e.whereToChange)}
      {list('how_to_verify', e.howToVerify)}
      {list('open_questions', e.openQuestions)}
    </>
  )
}

function EpicFields({ spec, onChange }: { spec: EpicSpec; onChange: (spec: EpicSpec) => void }) {
  const e = t.chat.edit
  const list = (key: keyof EpicSpec, label: string) => (
    <ListField
      label={label}
      items={(spec[key] as string[] | undefined) ?? []}
      onChange={(items) => onChange({ ...spec, [key]: items })}
    />
  )
  const decomposition = spec.decomposition ?? []
  return (
    <>
      <TextField
        label={e.problem}
        multiline
        value={spec.problem ?? ''}
        onChange={(problem) => onChange({ ...spec, problem })}
      />
      <TextField
        label={e.objective}
        multiline
        value={spec.objective ?? ''}
        onChange={(objective) => onChange({ ...spec, objective })}
      />
      {list('benefits', e.benefits)}
      {list('scope', e.scope)}
      {list('out_of_scope', e.outOfScope)}
      {list('acceptance_criteria', e.criteria)}
      <ListField
        label={e.decomposition}
        items={decomposition.map((d) => d.title)}
        // Título igual mantém a chave e as dependências da história (RA-11).
        onChange={(titles) =>
          onChange({
            ...spec,
            decomposition: titles.map(
              (title) => decomposition.find((d) => d.title === title) ?? { title },
            ),
          })
        }
      />
      {list('constraints', e.constraints)}
      {list('risks', e.risks)}
      {list('open_questions', e.openQuestions)}
    </>
  )
}

function Scenarios({
  items,
  onChange,
}: {
  items: Scenario[]
  onChange: (items: Scenario[]) => void
}) {
  const e = t.chat.edit
  const set = (i: number, patch: Partial<Scenario>) =>
    onChange(items.map((s, j) => (j === i ? { ...s, ...patch } : s)))
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-1 text-sm font-semibold">{e.criteria}</legend>
      {items.map((s, i) => (
        <div
          key={i}
          role="group"
          aria-label={e.criterion(i + 1)}
          className="flex flex-col gap-2 rounded-md border border-zinc-200 p-3"
        >
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-40 flex-1">
              <TextField
                label={e.criterionTitle}
                value={s.title}
                onChange={(title) => set(i, { title })}
              />
            </div>
            <KindSelect value={s.kind} onChange={(kind) => set(i, { kind })} />
            <Button
              type="button"
              variant="secondary"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
              aria-label={e.removeCriterion(i + 1)}
            >
              {e.remove}
            </Button>
          </div>
          <ListField label={e.given} items={s.given} onChange={(given) => set(i, { given })} />
          <ListField label={e.when} items={s.when} onChange={(when) => set(i, { when })} />
          <ListField label={e.then} items={s.then} onChange={(then) => set(i, { then })} />
        </div>
      ))}
      <div>
        <Button
          type="button"
          variant="secondary"
          onClick={() =>
            onChange([
              ...items,
              {
                // A API renumera os critérios (CA-01, CA-02…) ao salvar.
                id: `CA-${String(items.length + 1).padStart(2, '0')}`,
                kind: 'principal',
                title: '',
                given: [],
                when: [],
                then: [],
              },
            ])
          }
        >
          {e.addCriterion}
        </Button>
      </div>
    </fieldset>
  )
}

function KindSelect({
  value,
  onChange,
}: {
  value: ScenarioKind
  onChange: (kind: ScenarioKind) => void
}) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-zinc-600">
        {t.chat.edit.kind}
      </label>
      <select
        id={id}
        value={value}
        onChange={(ev) => onChange(ev.target.value as ScenarioKind)}
        className={`${input} min-h-9`}
      >
        {KINDS.map((k) => (
          <option key={k} value={k}>
            {k}
          </option>
        ))}
      </select>
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  multiline?: boolean
}) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-zinc-600">
        {label}
      </label>
      {multiline ? (
        <textarea
          id={id}
          rows={3}
          value={value}
          onChange={(ev) => onChange(ev.target.value)}
          className={input}
        />
      ) : (
        <input
          id={id}
          value={value}
          onChange={(ev) => onChange(ev.target.value)}
          className={input}
        />
      )}
    </div>
  )
}

/** Lista como texto, um item por linha; linhas vazias não viram item. */
function ListField({
  label,
  items,
  onChange,
}: {
  label: string
  items: string[]
  onChange: (items: string[]) => void
}) {
  const id = useId()
  // O texto cru fica aqui para a linha nova (ainda vazia) não sumir enquanto se digita.
  const [raw, setRaw] = useState(() => items.join('\n'))
  const parsed = (text: string) =>
    text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
  const shown = parsed(raw).join('\n') === items.join('\n') ? raw : items.join('\n')
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-zinc-600">
        {label} <span className="text-zinc-500">({t.chat.edit.onePerLine})</span>
      </label>
      <textarea
        id={id}
        rows={Math.min(Math.max(items.length + 1, 2), 8)}
        value={shown}
        onChange={(ev) => {
          setRaw(ev.target.value)
          onChange(parsed(ev.target.value))
        }}
        className={input}
      />
    </div>
  )
}
