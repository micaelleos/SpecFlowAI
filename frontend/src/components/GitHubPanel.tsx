import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { errorMessage, t } from '../i18n/en'
import { useProduct } from '../product/context'
import { Alert, Button, Field, Panel } from './ui'

const TOKENS_URL = 'https://github.com/settings/personal-access-tokens/new'

/** Settings › GitHub (F17-RF-01, F17-RF-04): token fine-grained só de leitura, nunca mostrado. */
export function GitHubPanel() {
  const product = useProduct()
  const queryClient = useQueryClient()
  const [token, setToken] = useState('')
  const key = ['github-connection']
  const connection = useQuery({
    queryKey: key,
    queryFn: product.getGitHubConnection,
    enabled: !!product.features.github,
  })
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: key }),
      queryClient.invalidateQueries({ queryKey: ['project-repo'] }),
    ])
  const connect = useMutation({
    mutationFn: product.connectGitHub,
    onSuccess: async () => {
      setToken('')
      await invalidate()
    },
  })
  const validate = useMutation({
    mutationFn: product.validateGitHub,
    onSuccess: (data) => queryClient.setQueryData(key, data),
  })
  const disconnect = useMutation({ mutationFn: product.disconnectGitHub, onSuccess: invalidate })
  if (!product.features.github) return null

  const g = t.github
  const data = connection.data
  const invalid = data?.status === 'invalid'
  const submit = (event: FormEvent) => {
    event.preventDefault()
    connect.mutate(token)
  }

  return (
    <Panel label={g.panel} className="flex min-w-0 flex-col gap-4">
      <h2 className="text-lg font-semibold">{g.panel}</h2>
      <p className="text-sm text-zinc-700">{g.intro}</p>
      {connection.isPending && <p className="text-zinc-600">{t.common.loading}</p>}
      {disconnect.isError && <Alert kind="error">{errorMessage(disconnect.error)}</Alert>}
      {data && (
        <>
          {validate.isError && <Alert kind="error">{errorMessage(validate.error)}</Alert>}
          {validate.isSuccess && !invalid && <Alert kind="info">{g.testOk}</Alert>}
          <p className="flex flex-wrap items-center gap-3 text-sm">
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 font-medium ${
                invalid ? 'bg-red-100 text-red-900' : 'bg-green-100 text-green-900'
              }`}
            >
              <span
                aria-hidden="true"
                className={`size-2 rounded-full ${invalid ? 'bg-red-600' : 'bg-green-600'}`}
              />
              {invalid ? g.invalid : g.connectedAs(data.login)}
            </span>
            <span className="text-zinc-600">
              {g.validatedAt(
                new Date(data.validatedAt).toLocaleString('en-US', {
                  dateStyle: 'short',
                  timeStyle: 'short',
                }),
              )}
            </span>
          </p>
          <p className="text-sm">
            <span className="text-zinc-600">{g.token}: </span>
            {`••••••••${data.tokenLast4}`}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={validate.isPending}
              onClick={() => validate.mutate()}
            >
              {g.test}
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="text-red-700"
              disabled={disconnect.isPending}
              onClick={() => {
                if (window.confirm(g.removeConfirm)) disconnect.mutate()
              }}
            >
              {g.remove}
            </Button>
          </div>
        </>
      )}
      {connection.isSuccess && !data && (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field
            id="github-token"
            label={g.tokenLabel}
            type="password"
            required
            autoComplete="off"
            aria-describedby="github-token-hint"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <p id="github-token-hint" className="-mt-2 text-sm text-zinc-600">
            {g.tokenHint}{' '}
            <a
              href={TOKENS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-indigo-700 underline"
            >
              {g.howLink}
            </a>
          </p>
          {connect.isError && <Alert kind="error">{errorMessage(connect.error)}</Alert>}
          <div>
            <Button type="submit" disabled={connect.isPending}>
              {g.save}
            </Button>
          </div>
        </form>
      )}
    </Panel>
  )
}
