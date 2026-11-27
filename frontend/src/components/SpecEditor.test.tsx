import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { EditableSpec, EpicSpec, WorkItemSpec } from '../product/types'
import { SpecEditor } from './SpecEditor'

const story: WorkItemSpec = {
  type: 'story',
  title: 'Login',
  objective: 'Como cliente, quero entrar.',
  context: [],
  acceptance_criteria: [
    {
      id: 'CA-01',
      kind: 'principal',
      title: 'Entrar',
      given: ['tenho conta'],
      when: ['envio a senha'],
      then: ['vejo a home'],
    },
  ],
  out_of_scope: ['SSO.'],
  human_only: false,
  human_only_reason: '',
}

function Harness({
  initial,
  onChange,
}: {
  initial: EditableSpec
  onChange: (s: EditableSpec) => void
}) {
  const [spec, setSpec] = useState(initial)
  return (
    <SpecEditor
      spec={spec}
      onChange={(next) => {
        setSpec(next)
        onChange(next)
      }}
    />
  )
}

const last = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls[fn.mock.calls.length - 1]?.[0] as EditableSpec

describe('F14-RF-06 editor por seção do AgentReadySpec', () => {
  it('mostra todas as seções da história, mesmo vazias, e edita lista um item por linha', async () => {
    const onChange = vi.fn()
    render(<Harness initial={story} onChange={onChange} />)
    const user = userEvent.setup()

    for (const label of [
      'Title',
      'Objective',
      /^Context/,
      /^Out of scope/,
      /^Constraints and contracts/,
      /^Where to change/,
      /^How to verify/,
      /^Open questions/,
    ])
      expect(screen.getByLabelText(label)).toBeInTheDocument()

    const out = screen.getByLabelText(/^Out of scope/)
    await user.type(out, '{Enter}{Enter}Pix.')
    expect((last(onChange) as WorkItemSpec).out_of_scope).toEqual(['SSO.', 'Pix.'])

    await user.clear(screen.getByLabelText('Objective'))
    expect(last(onChange).objective).toBe('') // F14-RT-04: esvaziar pode; a seção continua
    expect(screen.getByLabelText('Objective')).toBeInTheDocument()
  })

  it('critérios de aceite: Dado/Quando/Então, tipo, acrescentar e remover', async () => {
    const onChange = vi.fn()
    render(<Harness initial={story} onChange={onChange} />)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Add criterion' }))
    const second = screen.getByRole('group', { name: 'Criterion 2' })
    await user.type(within(second).getByLabelText('Criterion title'), 'Senha expirada')
    await user.selectOptions(within(second).getByLabelText('Kind'), 'erro')
    await user.type(within(second).getByLabelText(/^Given/), 'minha senha expirou')
    await user.type(within(second).getByLabelText(/^When/), 'tento entrar')
    await user.type(within(second).getByLabelText(/^Then/), 'vejo trocar senha')

    const criteria = (last(onChange) as WorkItemSpec).acceptance_criteria ?? []
    expect(criteria[1]).toMatchObject({
      title: 'Senha expirada',
      kind: 'erro',
      given: ['minha senha expirou'],
      when: ['tento entrar'],
      then: ['vejo trocar senha'],
    })

    await user.click(screen.getByRole('button', { name: 'Remove criterion 1' }))
    const left = (last(onChange) as WorkItemSpec).acceptance_criteria ?? []
    expect(left.map((c) => c.title)).toEqual(['Senha expirada'])
  })

  it('épico: problema, escopo e decomposição que mantém a chave da história', async () => {
    const epic: EpicSpec = {
      type: 'epic',
      title: 'Pagamentos',
      objective: '',
      problem: '',
      decomposition: [{ title: 'Pix', key: 'PAG-1', depends_on: [] }],
      human_only: false,
      human_only_reason: '',
    }
    const onChange = vi.fn()
    render(<Harness initial={epic} onChange={onChange} />)
    const user = userEvent.setup()

    for (const label of ['Problem', /^Benefits/, /^Scope/, /^Risks/, /^Acceptance criteria/])
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    await user.type(screen.getByLabelText(/^Stories/), '{Enter}Boleto')

    expect((last(onChange) as EpicSpec).decomposition).toEqual([
      { title: 'Pix', key: 'PAG-1', depends_on: [] },
      { title: 'Boleto' },
    ])
  })
})
