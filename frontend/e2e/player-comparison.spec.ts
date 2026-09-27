import { expect, test, type Page } from '@playwright/test';

const source = { source: 'Transfermarkt Open Dataset', coverage: '2025/26 snapshot', freshness: null };
const team = { team_id: 'club', name: 'Example FC', badge_url: null, logo_url: null };
const players = [
  { player_id: 'alice', name: 'Alice Forward', team, position: 'Attack', nationality: 'England', image_url: null, market_value_eur: null, source: source.source },
  { player_id: 'bob', name: 'Bob Midfielder', team, position: 'Midfield', nationality: 'France', image_url: null, market_value_eur: null, source: source.source },
];
const seasonStat = (season: number, competition: string, appearances: number | null, goals: number | null, assists: number | null, minutes_played: number | null) => ({
  season, competition, statistic: 'season', value: null, appearances, goals, assists, minutes_played, yellow_cards: null, red_cards: null,
});
const profiles = {
  alice: { ...players[0], sub_position: null, date_born: null, height_cm: null, foot: null, stats: [
    seasonStat(2025, 'Bundesliga', 20, 9, null, 900),
    seasonStat(2025, 'Cup', 1, null, 0, 0),
  ], coverage: source },
  bob: { ...players[1], sub_position: null, date_born: null, height_cm: null, foot: null, stats: [
    seasonStat(2025, 'Bundesliga', 15, 3, 5, 450),
  ], coverage: source },
};

async function mockPlayers(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const payload = url.pathname === '/api/v1/players'
      ? { players, page: { next_cursor: null, limit: 10, returned: 2 }, total_count: 2, teams: [team], positions: ['Attack', 'Midfield'], average_age: null, nationality_count: 2, total_market_value_eur: 0, source }
      : url.pathname === '/api/v1/players/alice' ? profiles.alice
        : url.pathname === '/api/v1/players/bob' ? profiles.bob : {};
    await route.fulfill({ status: 200, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify(payload) });
  });
}

test('compares matching historical competition seasons and keeps profile selection', async ({ page }) => {
  await mockPlayers(page);
  await page.goto('/players');
  const comparison = page.getByRole('region', { name: 'Player comparison' });
  await expect(page.getByRole('heading', { name: 'Alice Forward' })).toBeVisible();

  await page.getByRole('button', { name: 'Add Alice Forward to comparison' }).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Add Bob Midfielder to comparison' }).click();
  await expect(page.getByRole('heading', { name: 'Alice Forward' })).toBeVisible();
  await expect(comparison).toContainText('2025/26 snapshot, through July 2026');
  await expect(comparison).toContainText('not current 2026/27 squads');

  const choice = comparison.getByRole('combobox', { name: 'Season and competition' });
  await expect(choice).toHaveValue(JSON.stringify(['2025', 'Bundesliga']));
  const table = comparison.getByRole('table');
  await expect(table.getByRole('rowheader', { name: 'Appearances' }).locator('..').getByRole('cell')).toHaveText(['20', '15']);
  await expect(table.getByRole('rowheader', { name: 'Goals', exact: true }).locator('..').getByRole('cell')).toHaveText(['9', '3']);
  await expect(table.getByRole('rowheader', { name: 'Assists', exact: true }).locator('..').getByRole('cell')).toHaveText(['—', '5']);
  await expect(table.getByRole('rowheader', { name: 'Minutes' }).locator('..').getByRole('cell')).toHaveText(['900', '450']);
  await expect(table.getByRole('rowheader', { name: 'Goals / 90' }).locator('..').getByRole('cell')).toHaveText(['0.90', '0.60']);
  await expect(table.getByRole('rowheader', { name: 'Assists / 90' }).locator('..').getByRole('cell')).toHaveText(['—', '1.00']);

  await choice.selectOption(JSON.stringify(['2025', 'Cup']));
  await expect(table.getByRole('rowheader', { name: 'Goals', exact: true }).locator('..').getByRole('cell')).toHaveText(['—', '—']);
  await expect(table.getByRole('rowheader', { name: 'Assists', exact: true }).locator('..').getByRole('cell')).toHaveText(['0', '—']);
  await expect(table.getByRole('rowheader', { name: 'Minutes' }).locator('..').getByRole('cell')).toHaveText(['0', '—']);
  await expect(table.getByRole('rowheader', { name: 'Goals / 90' }).locator('..').getByRole('cell')).toHaveText(['—', '—']);

  await page.getByRole('button', { name: 'View profile for Bob Midfielder' }).click();
  await expect(page.getByRole('heading', { name: 'Bob Midfielder' })).toBeVisible();
  await expect(table.getByRole('rowheader', { name: 'Assists', exact: true }).locator('..').getByRole('cell')).toHaveText(['0', '—']);
});

test('comparison fits a narrow screen and remains keyboard operable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPlayers(page);
  await page.goto('/players');
  await page.getByRole('button', { name: 'Add Alice Forward to comparison' }).click();
  await page.getByRole('button', { name: 'Add Bob Midfielder to comparison' }).focus();
  await page.keyboard.press('Enter');
  const comparison = page.getByRole('region', { name: 'Player comparison' });
  await expect(comparison.getByRole('table')).toBeVisible();
  expect(await comparison.evaluate((element) => element.getBoundingClientRect().right)).toBeLessThanOrEqual(390);
  await comparison.getByRole('button', { name: 'Remove Bob Midfielder from comparison' }).focus();
  await page.keyboard.press('Enter');
  await expect(comparison.getByRole('table')).toHaveCount(0);
  await expect(comparison).toContainText('Choose from the list below');
});
