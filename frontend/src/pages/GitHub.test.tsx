import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import App from '../App'
import { createDemoProductApi } from '../product/demo'
import type { JiraProject, ProductApi } from '../product/types'
import { unavailableProductApi } from '../product/unavailable'
import { ALICE, fakeAuth } from '../test/fakeAuth'

const NOW = Date.parse('2026-11-27T12:00:00Z')
const TOKEN = 'github_pat_valido_0000000000abcd'
const project: JiraProject = {
  key: 'LOJA',
  name: 'Projeto Loja',
  type: 'software',
  avatarUrl: null,
  openIssues: 1,
  totalIssues: 2,
  url: 'https://demo.atlassian.net/browse/LOJA',
}

function renderAt(api: ProductApi, path: string) {
  render(<App authClient={fakeAuth(ALICE).client} productApi={api} initialPath={path} />)
}

const panel = () => screen.findByRole('region', { name: 'GitHub connection' })

describe('F17-RF-01 F17-RT-01 conexão GitHub em Settings', () => {
  it('conecta com o token, mostra só os 4 últimos e remove', async () => {
    const api = createDemoProductApi(() => NOW)
    renderAt(api, '/settings')
    const p = await panel()

    await userEvent.type(await within(p).findByLabelText('Fine-grained token'), TOKEN)
    await userEvent.click(within(p).getByRole('button', { name: 'Connect GitHub' }))

    expect(await within(p).findByText('GitHub connected · acme-po')).toBeInTheDocument()
    expect(within(p).getByText('••••••••abcd')).toBeInTheDocument()
    expect(p.textContent).not.toContain(TOKEN)

    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await userEvent.click(within(p).getByRole('button', { name: 'Remove GitHub' }))
    expect(await within(p).findByLabelText('Fine-grained token')).toBeInTheDocument()
  })

  it('token recusado: mostra o erro e não salva', async () => {
    const api = createDemoProductApi(() => NOW)
    renderAt(api, '/settings')
    const p = await panel()

    await userEvent.type(
      await within(p).findByLabelText('Fine-grained token'),
      'github_pat_errado_x',
    )
    await userEvent.click(within(p).getByRole('button', { name: 'Connect GitHub' }))

    expect(await within(p).findByText(/GitHub rejected the token/)).toBeInTheDocument()
    expect(await api.getGitHubConnection()).toBeNull()
  })

  it('sem a feature, a seção não aparece', async () => {
    renderAt(unavailableProductApi, '/settings')
    await screen.findByRole('heading', { level: 1, name: 'Settings' })
    expect(screen.queryByRole('region', { name: 'GitHub connection' })).toBeNull()
  })
})

describe('F17-RF-01 F17-RF-04 repositório do projeto em Projects', () => {
  const card = () =>
    waitFor(
      () => screen.getByRole('heading', { name: 'Projeto Loja' }).closest('li') as HTMLElement,
    )

  it('sem GitHub conectado, manda para Settings', async () => {
    const api = createDemoProductApi(() => NOW)
    api.listProjects = async () => [project]
    renderAt(api, '/projects')
    const c = await card()
    await userEvent.click(within(c).getByRole('button', { name: 'Code repository' }))
    expect(
      await within(c).findByText(/Connect GitHub in Settings to link a repository/),
    ).toBeInTheDocument()
    expect(within(c).getByRole('link', { name: 'Open Settings' })).toHaveAttribute(
      'href',
      '/settings',
    )
  })

  it('vincula só depois do Link e desvincula', async () => {
    const api = createDemoProductApi(() => NOW)
    api.listProjects = async () => [project]
    await api.connectGitHub(TOKEN)
    const linkSpy = vi.spyOn(api, 'linkProjectRepo')
    renderAt(api, '/projects')
    const c = await card()
    await userEvent.click(within(c).getByRole('button', { name: 'Code repository' }))

    expect(await within(c).findByText(/No repository linked/)).toBeInTheDocument()
    expect(linkSpy).not.toHaveBeenCalled()
    await userEvent.click(await within(c).findByRole('button', { name: 'Link acme/loja-online' }))

    expect(linkSpy).toHaveBeenCalledWith('LOJA', 'acme/loja-online')
    expect(await within(c).findByRole('link', { name: 'acme/loja-online' })).toHaveAttribute(
      'href',
      'https://github.com/acme/loja-online',
    )
    await userEvent.click(within(c).getByRole('button', { name: 'Unlink' }))
    expect(await within(c).findByText(/No repository linked/)).toBeInTheDocument()
    expect((await api.getProjectRepo('LOJA')).link).toBeNull()
  })
})
