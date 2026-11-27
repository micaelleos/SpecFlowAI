import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

import { createAccount, EMULATORS, seedDoc } from './emulators'

// AT-F18-01..03 com o modelo real (API local com LLM_PROVIDER=google_vertexai) e o Jira sandbox.
// O histórico (um épico e duas histórias "criados pelo SpecFlow") é semeado no emulador, então nada é
// escrito no Jira para preparar o teste.
// - AT-F18-03: sem repositório, não precisa de GitHub.
// - AT-F18-02: E2E_GITHUB_TOKEN e E2E_GITHUB_REPO (`dono/nome`); o cartão é recusado, nada é escrito.
// - AT-F18-01: E2E_GITHUB_WRITE=1, autorizado pelo PO: abre um PR de verdade (token com escrita).
//   E2E_JIRA_EPIC (opcional) é um épico real do sandbox que recebe o link do PR.
const SITE = process.env.JIRA_SANDBOX_URL ?? ''
const EMAIL = process.env.JIRA_SANDBOX_EMAIL ?? ''
const JIRA_TOKEN = process.env.JIRA_SANDBOX_API_TOKEN ?? ''
const PROJECT = process.env.JIRA_SANDBOX_PROJECT_KEY ?? ''
const GITHUB_TOKEN = process.env.E2E_GITHUB_TOKEN ?? ''
const REPO = process.env.E2E_GITHUB_REPO ?? ''
const EPIC = process.env.E2E_JIRA_EPIC ?? `${PROJECT}-9010`

test.skip(!EMULATORS, 'precisa dos emuladores: E2E_EMULATORS=1 com `make dev`')
test.skip(process.env.E2E_REAL_LLM !== '1', 'precisa do modelo real: E2E_REAL_LLM=1')
test.skip(!SITE || !EMAIL || !JIRA_TOKEN || !PROJECT, 'precisa de JIRA_SANDBOX_*')
test.setTimeout(300_000)

const story = (title: string) => ({
  type: 'story',
  title,
  objective: `${title} no checkout.`,
  acceptance_criteria: [
    {
      id: 'CA-01',
      kind: 'principal',
      title: title,
      given: ['um carrinho com itens'],
      when: ['a pessoa escolhe o meio de pagamento'],
      then: ['o pedido é pago'],
    },
  ],
  out_of_scope: ['Parcelamento.'],
})

/** Um épico com duas histórias no histórico do usuário (F10), como o Confirm teria gravado. */
async function seedEpic(request: APIRequestContext, uid: string) {
  const at = new Date()
  const done = (key: string, payload: Record<string, unknown>) => ({
    kind: 'create_issue',
    status: 'done',
    payload,
    result: { issue_key: key, url: `${SITE}/browse/${key}` },
    conversationId: 'c-e2e',
    createdAt: at,
  })
  const epic = {
    type: 'epic',
    title: 'Pagamentos no checkout (E2E F18)',
    objective: 'Pix e boleto.',
  }
  await seedDoc(
    request,
    `users/${uid}/pending_actions/e2e-epic`,
    done(EPIC, { project_key: PROJECT, spec: epic }),
  )
  await seedDoc(request, `users/${uid}/jira_issues/${EPIC}`, {
    specActionId: 'e2e-epic',
    issueType: 'Epic',
    summary: epic.title,
    projectKey: PROJECT,
    createdAt: at,
  })
  for (const [i, title] of ['Pagar com Pix', 'Pagar com boleto'].entries())
    await seedDoc(
      request,
      `users/${uid}/pending_actions/e2e-story-${i}`,
      done(`${PROJECT}-${9011 + i}`, {
        project_key: PROJECT,
        parent_key: EPIC,
        spec: story(title),
      }),
    )
}

async function signIn(page: Page, request: APIRequestContext) {
  const account = await createAccount(request, { verified: true, name: 'Pessoa das Specs' })
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Chat' })).toBeVisible()
  await page.goto('/settings')
  await page.getByLabel('Site URL').fill(SITE)
  await page.getByLabel('Atlassian account email').fill(EMAIL)
  await page.getByLabel('API token', { exact: true }).fill(JIRA_TOKEN)
  await page.getByRole('button', { name: 'Validate and save', exact: true }).click()
  await expect(page.getByText(/Jira connected ·/)).toBeVisible({ timeout: 30_000 })
  await seedEpic(request, account.uid)
  return account
}

async function linkRepo(page: Page) {
  await page.goto('/settings')
  const panel = page.getByRole('region', { name: 'GitHub connection' })
  await panel.getByLabel('Fine-grained token').fill(GITHUB_TOKEN)
  await panel.getByRole('button', { name: 'Connect GitHub' }).click()
  await expect(panel.getByText(/^GitHub connected · /)).toBeVisible({ timeout: 30_000 })
  await page.goto('/projects')
  const card = page.locator('li', { has: page.getByText(new RegExp(`^${PROJECT} · `)) })
  await card.getByRole('button', { name: 'Code repository' }).click()
  await card.getByLabel('Search repositories').fill(REPO.split('/')[1])
  await card.getByRole('button', { name: `Link ${REPO}` }).click({ timeout: 30_000 })
  await expect(card.getByRole('link', { name: REPO })).toBeVisible({ timeout: 30_000 })
}

/** Pelo botão de Created issues (F18-RF-01): abre o chat com o pedido escrito. */
async function askExport(page: Page) {
  await page.goto('/issues')
  await page
    .getByRole('link', { name: `Export ${EPIC} and its stories to the code repository` })
    .click()
  await expect(page.getByLabel('Message')).toHaveValue(new RegExp(EPIC))
  await page.getByLabel('Message').press('Enter')
  await expect(page.getByRole('button', { name: 'Stop' })).toBeHidden({ timeout: 240_000 })
}

const branchExists = async (request: APIRequestContext, branch: string) =>
  (
    await request.get(`https://api.github.com/repos/${REPO}/git/ref/heads/${branch}`, {
      headers: { Authorization: `Bearer ${GITHUB_TOKEN}`, Accept: 'application/vnd.github+json' },
    })
  ).status() === 200

test('F18-RF-05 AT-F18-03 sem repositório vinculado não há cartão', async ({ page, request }) => {
  await signIn(page, request)
  await askExport(page)
  // A resposta do agente (não o menu "Projects"): pede para vincular um repositório.
  await expect(page.getByText(/vincul/i).last()).toBeVisible()
  await expect(page.getByRole('region', { name: /^Open a pull request in / })).toHaveCount(0)
})

test.describe('com o repositório do PO', () => {
  test.skip(!GITHUB_TOKEN || !REPO, 'precisa de E2E_GITHUB_TOKEN e E2E_GITHUB_REPO')

  test('F18-RF-01 F18-RT-01 AT-F18-02 recusar não escreve', async ({ page, request }) => {
    await signIn(page, request)
    await linkRepo(page)
    await askExport(page)
    const card = page.getByRole('region', { name: `Open a pull request in ${REPO}` })
    await expect(card).toBeVisible({ timeout: 60_000 })
    await expect(card.getByText(/spec\.md$/)).toBeVisible()
    await expect(card.getByText(/tasks\.md$/)).toBeVisible()
    const branch = ((await card.getByText(/^specflow\//).textContent()) ?? '').split(' ')[0]
    await card.getByRole('button', { name: 'Reject' }).click()
    await expect(card.getByText(/Rejected/i)).toBeVisible({ timeout: 30_000 })
    expect(await branchExists(request, branch)).toBe(false)
  })

  test('F18-RF-02 F18-RF-03 F18-RF-04 AT-F18-01 exportar épico como PR', async ({
    page,
    request,
  }) => {
    test.skip(process.env.E2E_GITHUB_WRITE !== '1', 'abre um PR de verdade: E2E_GITHUB_WRITE=1')
    await signIn(page, request)
    await linkRepo(page)
    await askExport(page)
    const card = page.getByRole('region', { name: `Open a pull request in ${REPO}` })
    await expect(card).toBeVisible({ timeout: 60_000 })
    await card.getByRole('button', { name: 'Confirm and open pull request' }).click()
    await expect(card.getByText(/Opened pull request #\d+/)).toBeVisible({ timeout: 60_000 })
    const url = await card.getByRole('link', { name: 'Open on GitHub' }).getAttribute('href')
    const number = url?.split('/').pop()
    const files = await request.get(`https://api.github.com/repos/${REPO}/pulls/${number}/files`, {
      headers: { Authorization: `Bearer ${GITHUB_TOKEN}`, Accept: 'application/vnd.github+json' },
    })
    const names = ((await files.json()) as { filename: string }[]).map((f) => f.filename)
    expect(names.some((n) => /^specs\/\d{3}-[\w-]+\/spec\.md$/.test(n))).toBe(true)
    expect(names.some((n) => /^specs\/\d{3}-[\w-]+\/tasks\.md$/.test(n))).toBe(true)
  })
})
