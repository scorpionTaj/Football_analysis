import { expect, test, type Page } from '@playwright/test';

const source = { source: 'test fixture', coverage: 'published window', freshness: null };
const arsenal = { team_id: 'arsenal', name: 'Arsenal', badge_url: null, logo_url: null };
const liverpool = { team_id: 'liverpool', name: 'Liverpool', badge_url: null, logo_url: null };
const chelsea = { team_id: 'chelsea', name: 'Chelsea', badge_url: null, logo_url: null };
const match = {
  competition: 'E0', season: 2026, match_date: '2026-09-27', kickoff_time: '19:45',
  home: arsenal, away: liverpool, home_goals: null, away_goals: null,
  venue: null, stage: null, referee: null, source: 'Football-Data.co.uk fixtures',
  home_shots: null, away_shots: null, home_shots_on_target: null, away_shots_on_target: null,
  half_time_home_goals: null, half_time_away_goals: null, home_corners: null, away_corners: null,
  home_fouls: null, away_fouls: null, home_yellows: null, away_yellows: null,
  home_reds: null, away_reds: null,
};
const otherMatch = { ...match, match_date: '2026-09-22', kickoff_time: null, home: chelsea, away: arsenal, home_goals: 1, away_goals: 0 };

async function mockApi(page: Page, onMatchSearch?: (query: string) => void, forecastRows: unknown[] = [], matchRows?: typeof match[]) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };
    if (request.method() === 'OPTIONS') {
      await route.fulfill({ status: 204, headers: corsHeaders });
      return;
    }
    const url = new URL(request.url());
    const path = url.pathname;
    let payload: unknown = {};
    if (path === '/api/v1/catalog') payload = {
      competitions: [{ code: 'E0', name: 'Premier League', kind: 'domestic', group: 'Domestic leagues', seasons: [{ season: 2026, label: '2026/27', status: 'live_partial', match_count: 2, latest_match: '2026-09-22' }], source }],
      current_season: 2026, generated_at: '2026-09-23T12:00:00', source,
    };
    else if (path === '/api/v1/teams') payload = { teams: [arsenal, chelsea, liverpool], source };
    else if (path === '/api/v1/matches') {
      const query = url.searchParams.get('q') || '';
      onMatchSearch?.(query);
      const matches = matchRows ?? (query ? query.toLowerCase().includes('livrpool') ? [match] : [] : [otherMatch]);
      payload = { matches, page: { next_cursor: null, limit: 20, returned: matches.length }, source };
    } else if (path === '/api/v1/match-detail') payload = {
      match, status: 'Scheduled', stadium: null, attendance: null,
      home_coach: null, away_coach: null, home_formation: null, away_formation: null,
      narrative: [], statistics: [], timeline: [], lineups: [], coverage_notes: ['Only the published fixture is known.'],
      lineup_complete: false, source,
    };
    else if (path === '/api/v1/refresh') payload = {
      job_id: null, status: 'idle', current_step: 0, target_step: 4,
      completed_steps: [], step_name: 'Ready', message: 'Choose a refresh depth to begin.',
      started_at: null, finished_at: null, error: null,
    };
    else if (path === '/api/v1/health') payload = { status: 'ok', database: 'test', read_only: true };
    else if (path === '/api/v1/predictions') payload = {
      model_id: 'test-model', model_name: 'Test model', trained_at: '2026-09-23T12:00:00',
      validation_cutoff: '2025-01-01', metrics: {
        accuracy: 0.51, baseline_accuracy: 0.43, log_loss: 0.997, validation_matches: 100,
        high_confidence_threshold: 0.75, high_confidence_matches: 4,
        high_confidence_accuracy: 0.75, high_confidence_coverage: 0.04,
        outcome_backtest: [{ outcome: 'Draw', matches: 25, predicted: 5, correct: 2, recall: 0.08, precision: 0.4 }],
        walk_forward: [{ season: 2025, matches: 50, accuracy: 0.5, baseline_accuracy: 0.43, log_loss: 1.01 }],
      }, calibration: [], forecasts: forecastRows, league_outlooks: [],
      forecast_history: [], forecast_record: { issued: 0, resolved: 0, correct: 0, accuracy: null }, source,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', headers: corsHeaders, body: JSON.stringify(payload) });
  });
}

test('searches beyond the current page and preserves a match detail link', async ({ page }) => {
  let lastQuery = '';
  await mockApi(page, (query) => { lastQuery = query; });
  await page.goto('/matches?competition=E0&season=2026');
  await page.getByPlaceholder('Search club or referee...').fill('Livrpool');
  await expect(page.getByRole('button', { name: /Open Arsenal versus Liverpool match centre/ })).toBeVisible();
  expect(lastQuery).toBe('Livrpool');
  await page.getByRole('button', { name: /Open Arsenal versus Liverpool match centre/ }).click();
  await expect(page).toHaveURL(/match_date=2026-09-27/);
  await expect(page.getByRole('heading', { name: 'Fixture preview' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Match timeline' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Match statistics' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Technical area' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Fixture preview' })).toBeVisible();
});

test('keeps Match Centre search focused while debounced results update', async ({ page }) => {
  const searches: string[] = [];
  await mockApi(page, (query) => { searches.push(query); });
  await page.goto('/matches?competition=E0&season=2026');
  await expect(page.getByRole('button', { name: /Open Chelsea versus Arsenal match centre/ })).toBeVisible();
  const search = page.getByRole('textbox', { name: 'Search matches by club or referee' });
  await search.pressSequentially('Livrpool', { delay: 10 });
  await expect(page.getByRole('button', { name: /Open Arsenal versus Liverpool match centre/ })).toBeVisible();
  await expect(search).toBeFocused();
  await expect(search).toHaveValue('Livrpool');
  expect(searches.filter(Boolean)).toEqual(['Livrpool']);
});

test('missing match detail offers a way back to the fixture list', async ({ page }) => {
  await mockApi(page);
  await page.route('**/api/v1/match-detail**', (route) => route.fulfill({
    status: 404,
    contentType: 'application/json',
    headers: { 'Access-Control-Allow-Origin': '*' },
    body: JSON.stringify({ detail: 'Match not found' }),
  }));
  await page.goto('/matches?competition=E0&season=2026&match_date=2026-09-27&home=Arsenal&away=Liverpool');
  await expect(page.getByText('Match detail could not load')).toBeVisible();
  await page.getByRole('button', { name: 'Back to matches' }).click();
  await expect(page.getByRole('heading', { name: 'Match Centre' })).toBeVisible();
});

test('global search finds a misspelled club without broad short-fragment matches', async ({ page }) => {
  await mockApi(page);
  await page.goto('/matches?competition=E0&season=2026');
  const search = page.getByRole('combobox', { name: 'Search clubs, players and competitions' });
  await search.fill('Chelsa');
  await expect(page.getByRole('option', { name: /Chelsea Club \/ nation/ })).toBeVisible();
  await expect(search).toHaveAttribute('aria-expanded', 'true');
  await search.press('ArrowDown');
  await expect(search).toHaveAttribute('aria-activedescendant', 'global-search-option-0');
  await search.press('Escape');
  await expect(search).toHaveAttribute('aria-expanded', 'false');
  await search.fill('he');
  await expect(page.getByRole('option', { name: /Chelsea Club \/ nation/ })).toHaveCount(0);
  await search.fill('Chelsa');
  await expect(page.getByRole('option', { name: /Chelsea Club \/ nation/ })).toBeVisible();
  await search.press('ArrowDown');
  await search.press('Enter');
  await expect(page).toHaveURL(/\/clubs\?team=Chelsea/);
});

test('mobile navigation fits a narrow screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto('/matches?competition=E0&season=2026');
  const trigger = page.getByRole('button', { name: 'Open navigation menu' });
  await expect(trigger).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Quick navigation' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Football Analysis home' })).toBeHidden();
  await trigger.focus();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Refresh visible data' })).toBeFocused();
  await trigger.click();
  await expect(page.getByRole('dialog', { name: 'Primary navigation' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Football Analysis home' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button', { name: 'Toggle color mode' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Football Analysis home' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
  await expect(page.getByRole('dialog', { name: 'Primary navigation' })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('long club names remain readable in mobile fixture rows', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const longMatch = {
    ...match,
    home: { ...arsenal, name: 'Borussia Mönchengladbach' },
    away: { ...liverpool, name: 'Athletic Club Bilbao' },
  };
  await mockApi(page, undefined, [], [longMatch]);
  await page.goto('/matches?competition=E0&season=2026');
  const row = page.getByRole('button', { name: /Open Borussia Mönchengladbach versus Athletic Club Bilbao match centre/ });
  await expect(row).toBeVisible();
  const name = row.getByText('Borussia Mönchengladbach');
  expect(await name.evaluate((element) => element.getBoundingClientRect().height)).toBeGreaterThan(28);
  expect(await name.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('muted text tokens retain readable contrast across themes', async ({ page }) => {
  await mockApi(page);
  await page.goto('/matches?competition=E0&season=2026');
  const values = await page.evaluate(() => {
    const themes = ['mocha', 'latte', 'tokyo-night', 'nord', 'dracula', 'github-light'];
    return themes.map((theme) => {
      document.documentElement.dataset.theme = theme;
      const style = getComputedStyle(document.documentElement);
      return {
        theme,
        surface: style.getPropertyValue('--surface0').trim(),
        muted: ['--overlay0', '--overlay1', '--subtext0'].map((token) => style.getPropertyValue(token).trim()),
      };
    });
  });
  const luminance = (hex: string) => {
    const [red, green, blue] = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255)
      .map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  for (const { theme, surface, muted } of values) {
    for (const color of muted) {
      const [lighter, darker] = [luminance(surface), luminance(color)].sort((a, b) => b - a);
      expect((lighter + 0.05) / (darker + 0.05), `${theme}: ${color} on ${surface}`).toBeGreaterThanOrEqual(4.5);
    }
  }
});

test('overview exposes the competition catalog through fuzzy search', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Football intelligence, from fixture to forecast' })).toBeVisible();
  await page.getByRole('button', { name: 'Browse all 1' }).click();
  const search = page.getByRole('searchbox', { name: 'Find a league or cup' });
  await search.fill('Premir');
  await expect(page.locator('#competition-browser').getByRole('button', { name: /Premier League/ })).toBeVisible();
  await search.fill('No such competition');
  await expect(page.getByText('No competition matches that search.')).toBeVisible();
});

test('refresh depth and model diagnostics render', async ({ page }) => {
  await mockApi(page);
  await page.goto('/settings');
  await page.getByRole('button', { name: /Results and fixtures/ }).click();
  await expect(page.getByText('Step 1 of 4')).toBeVisible();
  await page.goto('/predictions');
  await expect(page.getByRole('heading', { name: 'Home, draw and away audit' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Published forecast record' })).toBeVisible();
});

test('full-season forecasts stay browsable without rendering the whole calendar', async ({ page }) => {
  const rows = Array.from({ length: 65 }, (_, index) => ({
    competition: index < 40 ? 'E0' : 'SP1', season: 2026,
    match_date: new Date(Date.UTC(2026, 9, index + 1)).toISOString().slice(0, 10),
    home: arsenal, away: liverpool, predicted_result: 'Home',
    home_probability: 0.5, draw_probability: 0.25, away_probability: 0.25,
  }));
  await mockApi(page, undefined, rows);
  await page.goto('/predictions');
  await expect(page.getByText('Showing 30 of 65 forecasts')).toBeVisible();
  await page.getByRole('button', { name: 'Show 30 more forecasts' }).click();
  await expect(page.getByText('Showing 60 of 65 forecasts')).toBeVisible();
  await page.getByLabel('League').selectOption('SP1');
  await expect(page.getByText('Showing 25 of 25 forecasts')).toBeVisible();
});
