import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from '../App'
import { fakeAuth } from '../test/fakeAuth'

describe('F03-RF-02 F03-RF-03 página de login', () => {
  it('tem o formulário e, ao lado, o que o SpecFlow faz hoje', async () => {
    render(<App authClient={fakeAuth().client} initialPath="/login" />)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sign in to SpecFlow AI' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Forgot your password?' })).toHaveAttribute(
      'href',
      '/reset-password',
    )
    const aside = screen.getByRole('complementary', {
      name: 'Specs grounded in your docs and your code',
    })
    for (const name of ['Reads your Confluence', 'Knows your repository', 'Specs in your repo'])
      expect(within(aside).getByRole('heading', { name })).toBeInTheDocument()
    expect(within(aside).getByText(/until you confirm/)).toBeInTheDocument()
  })
})
