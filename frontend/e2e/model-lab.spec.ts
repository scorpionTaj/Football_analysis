import { expect, test } from '@playwright/test';

const source = { source: 'model-leaderboard', coverage: 'walk-forward', freshness: '2026-10-03T02:40:27' };
const run = (model: string, rps: number, extra: Record<string, unknown> = {}) => ({
  model, rps, log_loss: 0.97, brier: 0.57, accuracy: 0.533, ece: 0.004, matches: 13061,
  independent: true, is_champion: false, trained_at: '2026-10-03T02:40:27', params: {},
  seasons: [{ season: 2024, rps, log_loss: 0.97, brier: 0.57, accuracy: 0.53, ece: 0.01, n: 3000 }],
  calibration: [{ outcome: 'Home', bin: 4, predicted: 0.45, observed: 0.46, n: 900 }],
  ...extra,
});

test('model lab ranks models between the base rate and the closing line', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path === '/api/v1/models' ? {
      champion: 'ensemble', targets: { log_loss: 0.975, rps: 0.2, accuracy: 0.535, ece: 0.02 }, source,
      runs: [
        run('market_closing', 0.19, { independent: false }),
        run('ensemble', 0.194, { is_champion: true }),
        run('elo_logit', 0.198),
        run('prevalence_baseline', 0.23, { independent: false }),
      ],
    } : { source, competitions: [], current_season: 2026, generated_at: null };
    await route.fulfill({ json: body, headers: { 'Access-Control-Allow-Origin': '*' } });
  });
  await page.goto('/models');
  await expect(page.getByRole('heading', { name: /bookmaker.s edge each model recovers/ })).toBeVisible();
  await expect(page.getByText('90.0%')).toBeVisible(); // (0.23 - 0.194) / (0.23 - 0.19)
  await expect(page.getByText('Below target · goal ≥ 53.5%')).toBeVisible();
  await page.getByRole('button', { name: 'Show scores' }).click();
  await expect(page.getByRole('rowheader', { name: /Ensemble/ })).toBeVisible();
});
