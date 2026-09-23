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

async function mockApi(page: Page, onMatchSearch?: (query: string) => void, forecastRows: unknown[] = []) {
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
      const matches = query ? query.toLowerCase().includes('livrpool') ? [match] : [] : [otherMatch];
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
  await expect(page.getByRole('heading', { name: 'Match overview' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Match overview' })).toBeVisible();
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

test('global search finds a misspelled club without broad short-fragment matches', async ({ page }) => {
  await mockApi(page);
  await page.goto('/matches?competition=E0&season=2026');
  const search = page.getByRole('textbox', { name: 'Search clubs, players and competitions' });
  await search.fill('Chelsa');
  await expect(page.getByRole('link', { name: /Chelsea Club \/ nation/ })).toBeVisible();
  await search.fill('he');
  await expect(page.getByRole('link', { name: /Chelsea Club \/ nation/ })).toHaveCount(0);
});

test('mobile navigation fits a narrow screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto('/matches?competition=E0&season=2026');
  await expect(page.getByRole('button', { name: 'Open navigation menu' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Quick navigation' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
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
