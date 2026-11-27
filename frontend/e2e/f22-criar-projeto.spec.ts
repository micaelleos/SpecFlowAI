import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

import { createAccount, EMULATORS } from './emulators'

// AT-F22-01..03 com o modelo real (API local com LLM_PROVIDER=google_vertexai) e o Jira sandbox.
// AT-F22-02 e 03 não criam nada (chave em uso; cartão recusado). ESCREVE NO JIRA só o AT-F22-01,
// que cria um projeto de teste (a conta precisa ser administradora do Jira) e roda só com
// E2E_JIRA_WRITE=1, que o PO autoriza; o projeto é apagado à mão no Jira depois.
const SITE = process.env.JIRA_SANDBOX_URL ?? ''
const EMAIL = process.env.JIRA_SANDBOX_EMAIL ?? ''
const TOKEN = process.env.JIRA_SANDBOX_API_TOKEN ?? ''
const PROJECT = process.env.JIRA_SANDBOX_PROJECT_KEY ?? ''

test.skip(!EMULATORS, 'precisa dos emuladores: E2E_EMULATORS=1 com `make dev`')
test.skip(process.env.E2E_REAL_LLM !== '1', 'precisa do modelo real: E2E_REAL_LLM=1')
test.skip(!SITE || !EMAIL || !TOKEN || !PROJECT, 'precisa de JIRA_SANDBOX_*')
test.setTimeout(300_000)

async function connected(page: Page, request: APIRequestContext) {
  const account = await createAccount(request, { verified: true, name: 'Pessoa dos Projetos' })
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Chat' })).toBeVisible()
  await page.goto('/settings')
  await page.getByLabel('Site URL').fill(SITE)
  await page.getByLabel('Atlassian account email').fill(EMAIL)
  await page.getByLabel('API token', { exact: true }).fill(TOKEN)
  await page.getByRole('button', { name: 'Validate and save', exact: true }).click()
  await expect(page.getByText(/Jira connected ·/)).toBeVisible({ timeout: 30_000 })
}

async function ask(page: Page, text: string) {
  await page.goto('/chat')
  await page.getByLabel('Message').fill(text)
  await page.getByLabel('Message').press('Enter')
  await expect(page.getByRole('button', { name: 'Stop' })).toBeHidden({ timeout: 240_000 })
}

const projectCard = (page: Page) =>
  page.getByRole('region', { name: /^Create Jira project [A-Z][A-Z0-9]+$/ }).first()

/** Chave única por execução: o Jira não deixa reaproveitar a de um projeto apagado logo depois. */
const stamp = () => `T${Date.now().toString(36).toUpperCase().slice(-6)}`

test('F22-RF-01 F22-RF-03 AT-F22-01 criar e seguir com o projeto', async ({ page, request }) => {
  test.skip(process.env.E2E_JIRA_WRITE !== '1', 'escreve no Jira: E2E_JIRA_WRITE=1')
  await connected(page, request)
  const key = stamp()
  await ask(page, `Crie um projeto Scrum chamado Teste SpecFlow ${key} com a chave ${key}.`)
  const card = projectCard(page)
  await expect(card).toBeVisible({ timeout: 60_000 })
  await expect(card.getByText('Scrum', { exact: true })).toBeVisible()
  await expect(card.getByText(/\(your account\)$/)).toBeVisible()

  await card.getByRole('button', { name: 'Confirm and create project' }).click()

  await expect(card.getByText(`Created project ${key}`)).toBeVisible({ timeout: 60_000 })
  const auth = Buffer.from(`${EMAIL}:${TOKEN}`).toString('base64')
  const created = await request.get(`${SITE}/rest/api/3/project/${key}`, {
    headers: { Authorization: `Basic ${auth}`, Accept: 'application/json' },
  })
  expect(created.ok()).toBe(true)
  await page.reload()
  await expect(page.getByText(new RegExp(`\\b${key}\\b`)).first()).toBeVisible()
})

test('F22-RF-02 AT-F22-02 chave em uso não vira cartão', async ({ page, request }) => {
  await connected(page, request)
  await ask(page, `Crie um projeto Kanban chamado Outro Projeto com a chave ${PROJECT}.`)
  await expect(page.getByRole('region', { name: `Create Jira project ${PROJECT}` })).toHaveCount(0)
  await expect(page.getByText(/em uso|already|existe/i).last()).toBeVisible()
})

test('F22-RF-01 F22-RF-05 AT-F22-03 recusar não cria nada', async ({ page, request }) => {
  await connected(page, request)
  const key = stamp()
  await ask(page, `Crie um projeto Scrum chamado Recusado ${key} com a chave ${key}.`)
  const card = projectCard(page)
  await expect(card).toBeVisible({ timeout: 60_000 })
  await card.getByRole('button', { name: 'Reject' }).click()
  await expect(card.getByRole('button', { name: 'Confirm and create project' })).toBeHidden({
    timeout: 30_000,
  })
  const auth = Buffer.from(`${EMAIL}:${TOKEN}`).toString('base64')
  const missing = await request.get(`${SITE}/rest/api/3/project/${key}`, {
    headers: { Authorization: `Basic ${auth}`, Accept: 'application/json' },
  })
  expect(missing.status()).toBe(404)
})
