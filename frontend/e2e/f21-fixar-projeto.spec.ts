import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

import { createAccount, EMULATORS } from './emulators'

// AT-F21-01..04 com o modelo real e o Jira/Confluence do sandbox. Só lê: a proposta da página não é
// confirmada. Precisa da API local com CONFLUENCE_WRITE_ENABLED=true e das páginas de teste
// (`scripts/confluence_fixture.py`). E2E_REAL_LLM=1 liga estes testes.
const SITE = process.env.JIRA_SANDBOX_URL ?? ''
const EMAIL = process.env.JIRA_SANDBOX_EMAIL ?? ''
const TOKEN = process.env.JIRA_SANDBOX_API_TOKEN ?? ''
const PROJECT = process.env.JIRA_SANDBOX_PROJECT_KEY ?? ''

test.skip(!EMULATORS, 'precisa dos emuladores: E2E_EMULATORS=1 com `make dev`')
test.skip(process.env.E2E_REAL_LLM !== '1', 'precisa do modelo real: E2E_REAL_LLM=1')
test.skip(!SITE || !EMAIL || !TOKEN || !PROJECT, 'precisa de JIRA_SANDBOX_*')
test.setTimeout(300_000)

/** Conta nova com o Jira conectado e o projeto vinculado ao espaço; termina numa conversa nova. */
async function setup(page: Page, request: APIRequestContext) {
  const account = await createAccount(request, { verified: true, name: 'Pessoa Fixa Projeto' })
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
  await page.goto('/projects')
  const card = page
    .getByRole('listitem')
    .filter({ has: page.getByText(new RegExp(`^${PROJECT} · `)) })
  await card.getByRole('button', { name: 'Project docs' }).click()
  await card.getByRole('button', { name: 'Link', exact: true }).click()
  await expect(card.getByText('The agent reads this space before proposing issues:')).toBeVisible()
  await page.goto('/chat')
  await expect(page.getByLabel('Message')).toBeVisible()
}

async function send(page: Page, text: string) {
  await page.getByLabel('Message').fill(text)
  // Durante a resposta o composer mostra "Stop" e ignora o Enter: espera o turno anterior acabar.
  await expect(page.getByRole('button', { name: 'Send' })).toBeEnabled({ timeout: 240_000 })
  await page.getByLabel('Message').press('Enter')
}

const idle = (page: Page) =>
  expect(page.getByRole('button', { name: 'Stop' })).toBeHidden({ timeout: 240_000 })

test('F21-RF-01 F21-RF-02 F21-RF-04 AT-F21-01 pedido de documentação numa conversa nova', async ({
  page,
  request,
}) => {
  await setup(page, request)
  await expect(page.getByText(/^Pinned project:/)).toBeHidden()
  await send(
    page,
    `No projeto ${PROJECT}, adicione ao glossário o termo Cupom: código que dá desconto no ` +
      'pedido. Proponha sem perguntas.',
  )
  const card = page.getByRole('region', { name: /^(Create|Update) page “Glossário”$/ }).last()
  await expect(card).toBeVisible({ timeout: 240_000 })
  await expect(card.getByRole('button', { name: 'Confirm and write' })).toBeVisible()
  await idle(page)
  await expect(page.getByText(`Pinned project: ${PROJECT}`)).toBeVisible()
})

test('F21-RF-03 AT-F21-02 o agente não troca o projeto', async ({ page, request }) => {
  await setup(page, request)
  await send(page, `Esta conversa é sobre o projeto ${PROJECT}.`)
  await idle(page)
  await expect(page.getByText(`Pinned project: ${PROJECT}`)).toBeVisible()
  await send(page, 'Agora fixe esta conversa no projeto VEND.')
  await idle(page)
  await page.reload()
  await expect(page.getByText(`Pinned project: ${PROJECT}`)).toBeVisible()
})

test('F21-RF-01 AT-F21-03 projeto que a conta não vê', async ({ page, request }) => {
  await setup(page, request)
  await send(page, 'Fixe esta conversa no projeto XYZQ e me diga o que tem no roadmap.')
  await idle(page)
  await page.reload()
  await expect(page.getByLabel('Message')).toBeVisible()
  await expect(page.getByText(/^Pinned project:/)).toBeHidden()
  await expect(page.getByLabel('Pin a project')).toBeVisible()
})

test('F21-RF-05 AT-F21-04 pin manual', async ({ page, request }) => {
  await setup(page, request)
  await send(page, 'Oi! Em uma frase: o que você faz?')
  await idle(page)
  await page.getByLabel('Pin a project').selectOption(PROJECT)
  await expect(page.getByText(`Pinned project: ${PROJECT}`)).toBeVisible()
  await send(page, 'Quais páginas existem na documentação deste projeto? Liste só os títulos.')
  await idle(page)
  await expect(page.getByText('Glossário').last()).toBeVisible()
})
