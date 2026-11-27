import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useContext, useEffect, useState } from 'react'

import { RefineContext } from '../chat/refine'
import { errorMessage, t } from '../i18n/en'
import { ActionProblem } from '../product/actions'
import { useProduct } from '../product/context'
import type { EditableSpec, ProposedAction, Readiness, SpecSection } from '../product/types'
import { DocActionBody } from './DocActionCard'
import { Markdown } from './Markdown'
import { SpecEditor } from './SpecEditor'
import { Alert, Button } from './ui'

/** A versão mais nova entre a que a tela tem e a relida do histórico (F14). */
const newest = (a: ProposedAction, b: ProposedAction | null) => (b && b.version > a.version ? b : a)

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(timer)
  }, [value, ms])
  return debounced
}

/**
 * Cartão de ação proposta (F06-RF-01, F06-RF-06, F06-RF-08; F08-RF-04): mostra exatamente o que
 * vai ao Jira, por seção, com a prontidão para agente de código. Só "Confirmar" escreve; recusar
 * não envia nada. A prontidão avisa e não impede a confirmação.
 *
 * F14: "Edit" abre o editor por seção, com prévia e prontidão recalculadas pela API; "Save" grava
 * uma versão nova e a confirmação manda o hash da versão exibida.
 */
export function ActionCard({
  action: initial,
  conversationId,
}: {
  action: ProposedAction
  conversationId: string
}) {
  const product = useProduct()
  const queryClient = useQueryClient()
  const [edited, setEdited] = useState<ProposedAction | null>(null)
  const [draft, setDraft] = useState<EditableSpec | null>(null)
  const onSettled = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['messages', conversationId] }),
      queryClient.invalidateQueries({ queryKey: ['issues'] }),
      queryClient.invalidateQueries({ queryKey: ['documents'] }),
    ])
  const latest = newest(initial, edited)
  const confirm = useMutation({
    mutationFn: (current: ProposedAction) =>
      product.confirmAction(current.id, current.payloadHash || undefined),
    onSettled,
  })
  const reject = useMutation({ mutationFn: product.rejectAction, onSettled })
  const versionSettled = {
    onSuccess: (out: ProposedAction) => {
      setEdited(out)
      setDraft(null)
    },
    onError: (error: unknown) => {
      // 409 `action-changed`: a tela passa a mostrar a versão atual (F14-RT-01).
      if (error instanceof ActionProblem) setEdited(error.action)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['messages', conversationId] }),
  }
  const save = useMutation({
    mutationFn: (spec: EditableSpec) =>
      product.saveAction(latest.id, spec, latest.priority, latest.payloadHash),
    ...versionSettled,
  })
  const restore = useMutation({
    mutationFn: () => product.restoreAction(latest.id, latest.payloadHash),
    ...versionSettled,
  })
  const busy = confirm.isPending || reject.isPending || save.isPending || restore.isPending
  const failure = confirm.error ?? reject.error ?? save.error ?? restore.error
  // O estado mais novo vem da resposta (ou do erro que traz a ação), não só da lista.
  const action =
    confirm.data ??
    reject.data ??
    (failure instanceof ActionProblem && failure.action.version >= latest.version
      ? failure.action
      : null) ??
    latest
  const status = confirm.isPending ? 'executing' : action.status
  if (action.doc) {
    return (
      <DocActionBody
        action={action}
        status={status}
        busy={busy}
        failure={
          failure && (!(failure instanceof ActionProblem) || action.status === 'pending')
            ? problemText(failure)
            : null
        }
        onConfirm={() => confirm.mutate(action)}
        onReject={() => reject.mutate(action.id)}
      />
    )
  }
  const creating = action.kind === 'create_issue'
  const a = t.chat.action
  const e = t.chat.edit
  const heading = creating
    ? a.titleCreate(action.issueType ?? 'issue', action.projectKey ?? '')
    : a.titleUpdate(action.issueKey ?? '')
  const editable = status === 'pending' && action.spec !== null && action.payloadHash !== ''
  const editing = editable && draft !== null

  const fields: [string, string, string?][] = creating
    ? [
        [a.project, [action.projectKey, action.projectName].filter(Boolean).join(' · ')],
        [a.type, action.issueType ?? '—'],
        [a.priority, action.priority ?? a.projectDefault],
        [a.issueTitle, action.title, 'sm:col-span-2'],
        [a.parent, action.parentKey ?? '—'],
        [a.labels, action.labels.join(', ') || '—', 'sm:col-span-3'],
      ]
    : [[a.issue, action.issueKey ?? '—']]

  return (
    <section
      aria-label={heading}
      className="overflow-hidden rounded-xl border border-indigo-200 bg-white"
    >
      <header className="flex flex-wrap items-center gap-2 bg-indigo-50 px-5 py-3 text-sm font-semibold text-indigo-900">
        <h3 className="flex-1">
          <span className="font-normal text-indigo-700">{a.title} · </span>
          {heading}
        </h3>
        {action.editedBy === 'user' && (
          <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium">
            {a.editedByYou(action.version)}
          </span>
        )}
        {status === 'pending' && (
          <span className="font-normal">
            {a.expires(
              new Date(action.expiresAt).toLocaleString('en-US', {
                dateStyle: 'short',
                timeStyle: 'short',
              }),
            )}
          </span>
        )}
      </header>

      {editing ? (
        <EditPanel
          action={action}
          draft={draft}
          onDraft={setDraft}
          saving={save.isPending}
          onSave={() => save.mutate(draft)}
          onCancel={() => {
            setDraft(null)
            save.reset()
          }}
        />
      ) : (
        <>
          <dl className="grid gap-x-5 gap-y-3 px-5 py-4 text-sm sm:grid-cols-3">
            {fields.map(([label, value, span]) => (
              <div key={label} className={span}>
                <dt className="text-xs text-zinc-600">{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>

          <ReadinessBox readiness={action.readiness} labels={action.labels} />
          <Conflicts action={action} />
          {action.changes.length > 0 && <Changes action={action} />}
          {action.sections.length > 0 && (
            <details className="border-t border-zinc-100 px-5 py-3 text-sm" open={creating}>
              <summary className="cursor-pointer font-medium">{a.spec}</summary>
              <Sections
                sections={action.sections}
                refineFor={status === 'pending' && action.spec ? action.id : null}
              />
            </details>
          )}
        </>
      )}

      <div className="flex flex-col gap-3 border-t border-zinc-100 px-5 py-4">
        {failure != null &&
          (!(failure instanceof ActionProblem) || action.status === 'pending') && (
            <Alert kind="error">
              {failure instanceof ActionProblem && failure.code === 'action-changed'
                ? a.changed
                : problemText(failure)}
            </Alert>
          )}
        {status === 'pending' && !editing && (
          <div className="flex flex-wrap gap-2">
            <Button type="button" disabled={busy} onClick={() => confirm.mutate(action)}>
              {creating ? a.confirm : a.confirmUpdate}
            </Button>
            {editable && action.spec && (
              <Button
                type="button"
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setDraft(action.spec)
                  confirm.reset()
                }}
              >
                {e.edit}
              </Button>
            )}
            {editable && action.editedBy === 'user' && (
              <Button
                type="button"
                variant="secondary"
                disabled={busy}
                onClick={() => restore.mutate()}
              >
                {e.restore}
              </Button>
            )}
            <Button
              type="button"
              variant="secondary"
              className="text-red-700"
              disabled={busy}
              onClick={() => reject.mutate(action.id)}
            >
              {a.reject}
            </Button>
          </div>
        )}
        {status === 'executing' && (
          <p role="status" className="text-sm text-zinc-700">
            {a.executing}
          </p>
        )}
        {status === 'done' && action.resultKey && (
          <p role="status" className="text-sm text-green-800">
            {creating ? a.created(action.resultKey) : a.updated(action.resultKey)}
            {action.resultUrl && (
              <>
                {' · '}
                <a
                  href={action.resultUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-indigo-700 underline"
                >
                  {a.openInJira}
                </a>
              </>
            )}
          </p>
        )}
        {status === 'failed' && (
          <p role="status" className="text-sm text-red-800">
            {action.error ?? a.failed} {a.askAgent}
          </p>
        )}
        {status === 'rejected' && (
          <p role="status" className="text-sm text-zinc-700">
            {a.rejected}
          </p>
        )}
        {status === 'expired' && (
          <p role="status" className="text-sm text-zinc-700">
            {a.expired}
          </p>
        )}
      </div>
    </section>
  )
}

/** Editor + prévia ao vivo (F14-RF-01, F14-RT-03): a API recalcula a prévia sem gravar. */
function EditPanel({
  action,
  draft,
  onDraft,
  saving,
  onSave,
  onCancel,
}: {
  action: ProposedAction
  draft: EditableSpec
  onDraft: (spec: EditableSpec) => void
  saving: boolean
  onSave: () => void
  onCancel: () => void
}) {
  const product = useProduct()
  const e = t.chat.edit
  const debounced = useDebounced(draft, 400)
  const preview = useQuery({
    queryKey: ['action-preview', action.id, debounced],
    queryFn: () => product.previewAction(action.id, debounced, action.priority),
    retry: false,
    placeholderData: (previous) => previous,
  })
  const pending = debounced !== draft || preview.isFetching
  return (
    <div className="grid gap-5 border-t border-zinc-100 px-5 py-4 lg:grid-cols-2">
      <form
        aria-label={e.editing(action.title)}
        className="flex flex-col gap-4"
        onSubmit={(ev) => {
          ev.preventDefault()
          onSave()
        }}
      >
        <SpecEditor spec={draft} onChange={onDraft} />
        {preview.isError && <Alert kind="error">{e.invalid}</Alert>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={saving || pending || preview.isError}>
            {saving ? e.saving : e.save}
          </Button>
          <Button type="button" variant="secondary" disabled={saving} onClick={onCancel}>
            {e.cancel}
          </Button>
        </div>
      </form>
      <section aria-label={e.preview} className="flex flex-col gap-3 text-sm">
        <h4 className="font-semibold">
          {e.preview}
          {pending && <span className="ml-2 font-normal text-zinc-600">{e.previewUpdating}</span>}
        </h4>
        {preview.data && (
          <>
            <p className="font-medium">{preview.data.title}</p>
            <ReadinessBox readiness={preview.data.readiness} labels={preview.data.labels} />
            <Sections sections={preview.data.sections} refineFor={null} />
          </>
        )}
      </section>
    </div>
  )
}

/** As seções da spec; com `refineFor`, cada uma tem "Refine with AI" (F14-RF-04). */
function Sections({ sections, refineFor }: { sections: SpecSection[]; refineFor: string | null }) {
  return (
    <div className="mt-3 flex flex-col gap-4">
      {sections.map((s) => (
        <section key={s.title} aria-label={s.title}>
          <h4 className="mb-1 font-semibold">{s.title}</h4>
          <Markdown text={s.markdown} />
          {refineFor && <Refine section={s.title} actionId={refineFor} />}
        </section>
      ))}
    </div>
  )
}

function Refine({ section, actionId }: { section: string; actionId: string }) {
  const refine = useContext(RefineContext)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  if (!refine) return null
  const e = t.chat.edit
  if (!open)
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-1 text-xs font-medium text-indigo-700 underline"
        aria-label={e.refineSection(section)}
      >
        {e.refine}
      </button>
    )
  return (
    <form
      className="mt-2 flex flex-wrap items-end gap-2"
      onSubmit={(ev) => {
        ev.preventDefault()
        if (!text.trim()) return
        refine(e.refineMessage(section, actionId, text.trim()))
        setText('')
        setOpen(false)
      }}
    >
      <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-zinc-600">
        {e.refineLabel(section)}
        <input
          value={text}
          onChange={(ev) => setText(ev.target.value)}
          className="rounded-md border border-zinc-300 px-2 py-1.5 text-sm"
        />
      </label>
      <Button type="submit" disabled={!text.trim()}>
        {e.refineSend}
      </Button>
      <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
        {e.cancel}
      </Button>
    </form>
  )
}

/** Erros da API sobre ações trazem a mensagem já traduzida (F06-RF-07). */
function problemText(error: unknown): string {
  if (error instanceof ActionProblem) return error.message
  return errorMessage(error)
}

/** Prontidão para agente de código (F06-RF-08): avisa, não bloqueia. */
function ReadinessBox({ readiness, labels }: { readiness: Readiness | null; labels: string[] }) {
  if (!readiness) return null
  const a = t.chat.action
  const missing = readiness.rules.filter((r) => !r.passed && r.severity === 'obrigatória')
  const warnings = readiness.rules.filter((r) => !r.passed && r.severity !== 'obrigatória')
  const humanOnly = labels.includes('human-only')
  return (
    <div
      aria-label={a.readiness}
      role="group"
      className="border-t border-zinc-100 px-5 py-3 text-sm"
    >
      {readiness.ready ? (
        <p className="font-medium text-green-800">{a.ready}</p>
      ) : (
        <>
          <p className="font-medium text-amber-800">{a.notReady}</p>
          <ul className="mt-1 list-disc pl-5 text-amber-900">
            {missing.map((r) => (
              <li key={r.id}>{a.missing(r.label, r.id, r.detail)}</li>
            ))}
          </ul>
        </>
      )}
      {warnings.length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-zinc-700">
          {warnings.map((r) => (
            <li key={r.id}>{a.warning(r.label, r.id, r.detail)}</li>
          ))}
        </ul>
      )}
      {humanOnly && <p className="mt-1 text-zinc-700">{a.humanOnly}</p>}
    </div>
  )
}

/** Conflitos com a documentação do projeto (F19-RF-07): avisa; quem decide é o usuário. */
function Conflicts({ action }: { action: ProposedAction }) {
  if (action.conflicts.length === 0) return null
  const a = t.chat.action
  return (
    <div
      role="group"
      aria-label={a.conflicts}
      className="border-t border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-900"
    >
      <p className="font-medium">{a.conflicts}</p>
      <ul className="mt-1 list-disc pl-5">
        {action.conflicts.map((c) => (
          <li key={c.id}>{a.conflictWith(c.id, c.reason)}</li>
        ))}
      </ul>
    </div>
  )
}

/** Antes → depois dos campos que a atualização muda (F06-RF-06). */
function Changes({ action }: { action: ProposedAction }) {
  const a = t.chat.action
  return (
    <div className="border-t border-zinc-100 px-5 py-3 text-sm">
      <h4 className="mb-2 font-semibold">{a.changes}</h4>
      <dl className="flex flex-col gap-2">
        {action.changes.map((c) =>
          c.field === 'description' ? (
            <div key={c.field}>
              <dt className="text-xs text-zinc-600">{a.fields[c.field]}</dt>
              <dd>
                <details>
                  <summary className="cursor-pointer">{a.descriptionRewritten}</summary>
                  <div className="mt-2 rounded bg-zinc-50 p-2 text-zinc-700">
                    <Markdown text={c.before || '—'} />
                  </div>
                </details>
              </dd>
            </div>
          ) : (
            <div key={c.field}>
              <dt className="text-xs text-zinc-600">{a.fields[c.field]}</dt>
              <dd>
                <del className="text-zinc-500">{c.before || '—'}</del>
                {' → '}
                <ins className="no-underline font-medium">{c.after || '—'}</ins>
              </dd>
            </div>
          ),
        )}
      </dl>
    </div>
  )
}
