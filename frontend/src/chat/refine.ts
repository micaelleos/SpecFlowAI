import { createContext } from 'react'

/**
 * Envia uma mensagem ao agente a partir de um cartão ("Refine with AI", F14-RF-04). O chat dá a
 * função; fora dele (ou com o agente respondendo) é `null` e o cartão esconde o botão.
 */
export const RefineContext = createContext<((text: string) => void) | null>(null)
