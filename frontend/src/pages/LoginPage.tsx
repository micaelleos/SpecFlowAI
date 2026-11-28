import { type FormEvent, useState } from 'react'
import { Link } from 'react-router'

import { useAuth } from '../auth/context'
import { Mark } from '../components/Mark'
import { Alert, Button, Field } from '../components/ui'
import { errorMessage, t } from '../i18n/en'

const L = t.login

/** O que o SpecFlow faz hoje, ao lado do formulário (embaixo dele no celular). */
function Highlights() {
  return (
    <aside
      aria-labelledby="login-highlights"
      className="relative isolate flex flex-col gap-6 overflow-hidden rounded-2xl bg-zinc-900 p-8 text-white shadow-xl shadow-indigo-950/20"
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-24 -right-20 size-72 animate-glow rounded-full bg-indigo-600/40 blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(rgb(255_255_255/0.06)_1px,transparent_1px)] [background-size:22px_22px]" />
      </div>
      <Mark className="size-8" />
      <h2 id="login-highlights" className="text-xl leading-snug font-bold text-balance">
        {L.asideTitle}
      </h2>
      <ul className="flex flex-col gap-4">
        {L.asideItems.map((item, i) => (
          <li
            key={item.title}
            className="flex animate-fade-up gap-3"
            style={{ animationDelay: `${150 + i * 100}ms` }}
          >
            <span
              aria-hidden="true"
              className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-xs text-emerald-300"
            >
              ✓
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">{item.title}</h3>
              <p className="text-sm text-zinc-300">{item.body}</p>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-auto border-t border-zinc-700 pt-4 text-xs text-zinc-400">{L.asideNote}</p>
    </aside>
  )
}

export function LoginPage() {
  const { client } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action() // o GuestRoute redireciona quando o estado do Auth muda
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void run(() => client.signInWithEmail(email, password))
  }

  return (
    <main className="mx-auto grid min-h-[80vh] max-w-5xl grid-cols-1 items-center gap-8 px-4 py-10 md:grid-cols-[1fr_1.05fr] md:gap-12 md:px-8">
      <div className="flex flex-col gap-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-zinc-900">{L.title}</h1>
          <p className="text-sm text-zinc-600">{L.subtitle}</p>
        </div>
        {error && <Alert kind="error">{error}</Alert>}
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => void run(() => client.signInWithGoogle())}
        >
          {L.google}
        </Button>
        <div className="flex items-center gap-3 text-sm text-zinc-500">
          <span aria-hidden="true" className="h-px flex-1 bg-zinc-200" />
          <span>{L.or}</span>
          <span aria-hidden="true" className="h-px flex-1 bg-zinc-200" />
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <Field
            id="email"
            label={L.email}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Field
            id="password"
            label={L.password}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Link to="/reset-password" className="self-end text-sm text-indigo-700 underline">
            {L.forgot}
          </Link>
          <Button type="submit" disabled={busy}>
            {L.submit}
          </Button>
        </form>
        <p className="text-sm text-zinc-600">
          {L.noAccount}{' '}
          <Link to="/signup" className="font-medium text-indigo-700 underline">
            {L.signUp}
          </Link>
        </p>
        <p className="border-t border-zinc-100 pt-4 text-xs text-zinc-500">{L.sharedLogin}</p>
      </div>
      <Highlights />
    </main>
  )
}
