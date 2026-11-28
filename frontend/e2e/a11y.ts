import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'

/**
 * Violações sérias ou críticas (WCAG 2 A/AA). Antes de medir, espera as animações finitas da tela
 * (entrada da página, painéis) terminarem: no meio da transição a opacidade derruba o contraste.
 */
export async function serious(page: Page): Promise<string[]> {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  )
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.help}`)
}
