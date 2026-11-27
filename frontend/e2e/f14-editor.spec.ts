import {
  type APIRequestContext,
  type BrowserContext,
  expect,
  type Page,
  test,
} from '@playwright/test'

import { createAccount, EMULATORS } from './emulators'

// AT-F14-01..04 com o modelo real (API local com LLM_PROVIDER=google_vertexai) e o Jira sandbox.
// AT-F14-02..04 só leem o Jira: o cartão é editado, mas não confirmado (o AT-04 confirma uma
// versão antiga, que a API recusa antes de escrever). ESCREVE NO JIRA só o AT-F14-01, que cria 1
// issue e roda com E2E_JIRA_WRITE=1, que o PO autoriza. E2E_REAL_LLM=1 liga estes testes.
const SITE = process.env.JIRA_SANDBOX_URL ?? ''
const EMAIL = process.env.JIRA_SANDBOX_EMAIL ?? ''
const TOKEN = process.env.JIRA_SANDBOX_API_TOKEN ?? ''
const PROJECT = process.env.JIRA_SANDBOX_PROJECT_KEY ?? ''

test.skip(!EMULATORS, 'precisa dos emuladores: E2E_EMULATORS=1 com `make dev`')
test.skip(process.env.E2E_REAL_LLM !== '1', 'precisa do modelo real: E2E_REAL_LLM=1')
test.skip(!SITE || !EMAIL || !TOKEN || !PROJECT, 'precisa de JIRA_SANDBOX_*')
test.setTimeout(300_000)

const REQUEST =
  'Crie uma story: login com e-mail e senha na loja. Quem tem conta informa e-mail e senha e cai ' +
  'na página inicial; com senha errada vê "E-mail ou senha incorretos" e continua na tela de ' +
  'login. Fora do escopo: login social. Verificação: testes de unidade do formulário e E2E do ' +
  'login. Já está completo, pode propor sem perguntar mais nada.'

/** Conta nova com o Jira conectado e uma proposta de story pendente; devolve o cartão. */
async function proposal(page: Page, request: APIRequestContext) {
  const account = await createAccount(request, { verified: true, name: 'Pessoa Editora' })
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Chat' })).toBeVisible()
  await page.goto('/settings')
  await page.getByLabel('Site URL').fill(SITE)
  await page.getByLabel('Atlassian account email').fill(EMAIL)
  await page.getByLabel('API token', { exact: true }).fill(TOKEN)
  await page.getByRole('button', { name: 'Validate and save' }).click()
  await expect(page.getByText(/Jira connected ·/)).toBeVisible({ timeout: 30_000 })
  await page.goto(`/chat?projeto=${PROJECT}`)
  await send(page, REQUEST)
  const card = cardOf(page)
  await expect(card.getByRole('button', { name: 'Confirm and create' })).toBeVisible({
    timeout: 240_000,
  })
  await idle(page)
  // O histórico relido traz a spec e o hash: só então o cartão edita.
  await expect(card.getByRole('button', { name: 'Edit' })).toBeVisible({ timeout: 30_000 })
  return card
}

const cardOf = (page: Page) =>
  page.getByRole('region', { name: new RegExp(`^Create (Story|Task) in ${PROJECT}$`) }).first()

async function send(page: Page, text: string) {
  await page.getByLabel('Message').fill(text)
  await expect(page.getByRole('button', { name: 'Send' })).toBeEnabled({ timeout: 240_000 })
  await page.getByLabel('Message').press('Enter')
}

const idle = (page: Page) =>
  expect(page.getByRole('button', { name: 'Stop' })).toBeHidden({ timeout: 240_000 })

async function editTitle(page: Page, title: string) {
  const card = cardOf(page)
  await card.getByRole('button', { name: 'Edit' }).click()
  const form = card.getByRole('form', { name: /^Editing/ })
  await form.getByLabel('Title', { exact: true }).fill(title)
  return form
}

async function save(page: Page) {
  const card = cardOf(page)
  await card.getByRole('button', { name: 'Save' }).click({ timeout: 30_000 })
  await expect(card.getByText(/^Edited by you · version \d+$/)).toBeVisible({ timeout: 30_000 })
}

test('F14-RF-01 F14-RF-02 F14-RF-06 AT-F14-01 editar e confirmar cria o conteúdo editado', async ({
  page,
  request,
}) => {
  test.skip(process.env.E2E_JIRA_WRITE !== '1', 'escreve no Jira: E2E_JIRA_WRITE=1')
  const card = await proposal(page, request)
  const form = await editTitle(page, 'Login com SSO')
  await form.getByRole('button', { name: 'Add criterion' }).click()
  const added = form.getByRole('group', { name: /^Criterion \d+$/ }).last()
  await added.getByLabel('Criterion title').fill('Senha expirada')
  await added.getByLabel('Kind').selectOption('erro')
  await added.getByLabel(/^Given/).fill('minha senha expirou')
  await added.getByLabel(/^When/).fill('tento entrar')
  await added.getByLabel(/^Then/).fill('vejo o pedido para trocar a senha')

  // A prévia muda antes de salvar (F14-RT-03).
  const preview = card.getByRole('region', { name: 'Preview' })
  await expect(preview.getByText('Login com SSO')).toBeVisible({ timeout: 30_000 })
  await expect(preview.getByText(/Senha expirada/)).toBeVisible({ timeout: 30_000 })

  await save(page)
  await card.getByRole('button', { name: 'Confirm and create' }).click()
  const created = card.getByRole('status').filter({ hasText: /^Created as / })
  await expect(created).toBeVisible({ timeout: 60_000 })
  const key = ((await created.textContent()) ?? '').match(/Created as ([A-Z][A-Z0-9_]+-\d+)/)?.[1]
  expect(key).toBeTruthy()

  const auth = Buffer.from(`${EMAIL}:${TOKEN}`).toString('base64')
  const issue = await request.get(`${SITE}/rest/api/3/issue/${key}?fields=summary,description`, {
    headers: { Authorization: `Basic ${auth}`, Accept: 'application/json' },
  })
  expect(issue.ok()).toBe(true)
  const fields = (await issue.json()).fields
  expect(fields.summary).toBe('Login com SSO')
  expect(JSON.stringify(fields.description)).toContain('Senha expirada')
})

test('F14-RF-03 AT-F14-02 restaurar a versão do agente', async ({ page, request }) => {
  const card = await proposal(page, request)
  const agentTitle = await card.locator('div:has(> dt:text-is("Title")) > dd').textContent()
  expect(agentTitle).toBeTruthy()
  await editTitle(page, 'Login com SSO')
  await save(page)
  await expect(card.getByText('Login com SSO', { exact: true })).toBeVisible()

  await card.getByRole('button', { name: 'Restore agent version' }).click()

  await expect(card.getByText(agentTitle ?? '', { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(card.getByText(/^Edited by you/)).toBeHidden()
})

test('F14-RF-04 F14-RF-05 AT-F14-03 refinar uma seção com IA na mesma proposta', async ({
  page,
  request,
}) => {
  const card = await proposal(page, request)
  await editTitle(page, 'Login com SSO')
  await save(page)

  await card.getByRole('button', { name: 'Refine “Critérios de aceite” with AI' }).click()
  await card
    .getByLabel('What should change in “Critérios de aceite”?')
    .fill('adicione o cenário de senha expirada: o usuário vê o pedido para trocar a senha')
  await card.getByRole('button', { name: 'Ask the agent' }).click()
  await idle(page)
  await page.reload()

  await expect(page.getByRole('region', { name: /^Create (Story|Task) in / })).toHaveCount(1)
  const again = cardOf(page)
  await expect(again.getByRole('region', { name: 'Critérios de aceite' })).toContainText(
    /senha expirada/i,
    { timeout: 30_000 },
  )
  await expect(again.getByText('Login com SSO', { exact: true })).toBeVisible()
})

test('F14-RT-01 AT-F14-04 confirmar uma versão desatualizada é recusado', async ({
  page,
  request,
  context,
}) => {
  await proposal(page, request)
  const other = await openSameConversation(context, page)

  await editTitle(page, 'Login com SSO')
  await save(page)

  await expect(cardOf(other).getByText('Login com SSO', { exact: true })).toHaveCount(0)
  await cardOf(other).getByRole('button', { name: 'Confirm and create' }).click()

  await expect(cardOf(other).getByText(/This proposal changed after you opened it/)).toBeVisible({
    timeout: 30_000,
  })
  await expect(cardOf(other).getByText('Login com SSO', { exact: true })).toBeVisible()
  await expect(cardOf(other).getByRole('button', { name: 'Confirm and create' })).toBeVisible()
})

/** A mesma conversa noutra aba (mesma sessão), com o cartão na versão de antes da edição. */
async function openSameConversation(context: BrowserContext, page: Page): Promise<Page> {
  const other = await context.newPage()
  await other.goto(page.url())
  await expect(cardOf(other).getByRole('button', { name: 'Edit' })).toBeVisible({
    timeout: 30_000,
  })
  // Esta aba não relê o histórico: o cartão fica na versão antiga e o Confirm manda o hash dela
  // (a API recusa sem escrever no Jira).
  await other.route(/\/api\/v1\/conversations\//, (route) => route.abort())
  return other
}
