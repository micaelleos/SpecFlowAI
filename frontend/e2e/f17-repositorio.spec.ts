import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

import { createAccount, EMULATORS } from './emulators'

// AT-F17-01..03 com o modelo real (API local com LLM_PROVIDER=google_vertexai), o Jira sandbox e
// um repositório GitHub real do PO, lido com um token fine-grained só de leitura. Nada é escrito no
// GitHub nem no Jira (o cartão não é confirmado). O AT-F17-03 só precisa dos emuladores; E2E_GITHUB_TOKEN
// e E2E_GITHUB_REPO (`dono/nome`) ligam os outros; E2E_GITHUB_REQUEST (opcional) troca o pedido pelo de um módulo do repositório.
const SITE = process.env.JIRA_SANDBOX_URL ?? ''
const EMAIL = process.env.JIRA_SANDBOX_EMAIL ?? ''
const JIRA_TOKEN = process.env.JIRA_SANDBOX_API_TOKEN ?? ''
const PROJECT = process.env.JIRA_SANDBOX_PROJECT_KEY ?? ''
const GITHUB_TOKEN = process.env.E2E_GITHUB_TOKEN ?? ''
const REPO = process.env.E2E_GITHUB_REPO ?? ''
const REQUEST =
  process.env.E2E_GITHUB_REQUEST ??
  'Crie uma tarefa técnica: adicionar um teste de unidade para o módulo principal deste repositório. ' +
    'Fora do escopo: mudar o comportamento. Já está completo, pode propor sem perguntar mais nada.'

test.skip(!EMULATORS, 'precisa dos emuladores: E2E_EMULATORS=1 com `make dev`')
test.setTimeout(300_000)

async function signIn(page: Page, request: APIRequestContext) {
  const account = await createAccount(request, { verified: true, name: 'Pessoa do Código' })
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Chat' })).toBeVisible()
}

async function connectGitHub(page: Page, token: string) {
  await page.goto('/settings')
  const panel = page.getByRole('region', { name: 'GitHub connection' })
  await panel.getByLabel('Fine-grained token').fill(token)
  await panel.getByRole('button', { name: 'Connect GitHub' }).click()
  return panel
}

test('F17-RF-01 F17-RT-01 AT-F17-03 token recusado não é salvo', async ({ page, request }) => {
  await signIn(page, request)
  const panel = await connectGitHub(page, 'github_pat_invalido_000000000000000000')
  await expect(panel.getByText(/GitHub rejected the token/)).toBeVisible({ timeout: 30_000 })
  await page.reload()
  await expect(
    page.getByRole('region', { name: 'GitHub connection' }).getByLabel('Fine-grained token'),
  ).toBeVisible()
})

test.describe('com o Jira sandbox e o modelo real', () => {
  test.skip(process.env.E2E_REAL_LLM !== '1', 'precisa do modelo real: E2E_REAL_LLM=1')
  test.skip(!SITE || !EMAIL || !JIRA_TOKEN || !PROJECT, 'precisa de JIRA_SANDBOX_*')
  test.skip(!GITHUB_TOKEN || !REPO, 'precisa de E2E_GITHUB_TOKEN e E2E_GITHUB_REPO')

  async function linked(page: Page, request: APIRequestContext) {
    await signIn(page, request)
    await page.goto('/settings')
    await page.getByLabel('Site URL').fill(SITE)
    await page.getByLabel('Atlassian account email').fill(EMAIL)
    await page.getByLabel('API token', { exact: true }).fill(JIRA_TOKEN)
    await page.getByRole('button', { name: 'Validate and save', exact: true }).click()
    await expect(page.getByText(/Jira connected ·/)).toBeVisible({ timeout: 30_000 })
    const panel = await connectGitHub(page, GITHUB_TOKEN)
    await expect(panel.getByText(/^GitHub connected · /)).toBeVisible({ timeout: 30_000 })

    await page.goto('/projects')
    const card = page.locator('li', { has: page.getByText(new RegExp(`^${PROJECT} · `)) })
    await card.getByRole('button', { name: 'Code repository' }).click()
    await card.getByLabel('Search repositories').fill(REPO.split('/')[1])
    await card.getByRole('button', { name: `Link ${REPO}` }).click({ timeout: 30_000 })
    await expect(card.getByRole('link', { name: REPO })).toBeVisible({ timeout: 30_000 })
    return card
  }

  async function ask(page: Page) {
    await page.goto(`/chat?projeto=${PROJECT}`)
    await page.getByLabel('Message').fill(REQUEST)
    await page.getByLabel('Message').press('Enter')
    await expect(page.getByRole('button', { name: 'Stop' })).toBeHidden({ timeout: 240_000 })
  }

  test('F17-RF-02 F17-RF-03 AT-F17-01 "Onde mexer" a partir do repositório', async ({
    page,
    request,
  }) => {
    await linked(page, request)
    const tree = request.get(`https://api.github.com/repos/${REPO}/git/trees/HEAD?recursive=1`, {
      headers: { Authorization: `Bearer ${GITHUB_TOKEN}`, Accept: 'application/vnd.github+json' },
    })
    await ask(page)

    const card = page.getByRole('region', { name: /^Create (Story|Task) in / }).first()
    await expect(card).toBeVisible({ timeout: 60_000 })
    const where = card.getByRole('region', { name: 'Onde mexer' })
    await expect(where).toBeVisible()
    const text = (await where.textContent()) ?? ''
    const paths = new Set(
      ((await (await tree).json()).tree as { path: string }[]).map((e) => e.path),
    )
    const cited = [...text.matchAll(/([\w.-]+(?:\/[\w.-]+)+|[\w-]+\.\w{1,5})/g)].map((m) => m[1])
    expect(cited.length).toBeGreaterThan(0)
    expect(cited.some((p) => paths.has(p))).toBe(true)
    await expect(card.getByRole('region', { name: 'Como verificar' })).toBeVisible()
  })

  test('F17-RF-04 F17-RF-05 AT-F17-02 desvincular: a conversa não lê o repositório', async ({
    page,
    request,
  }) => {
    const card = await linked(page, request)
    await card.getByRole('button', { name: 'Unlink' }).click()
    await expect(card.getByText(/No repository linked/)).toBeVisible({ timeout: 30_000 })
    const reads: string[] = []
    page.on('response', async (r) => {
      if (r.url().includes('/messages')) reads.push(await r.text().catch(() => ''))
    })
    await ask(page)
    await expect(page.getByText('Lendo o repositório…')).toHaveCount(0)
    expect(reads.join('').includes('_do_repositorio')).toBe(false)
  })
})
