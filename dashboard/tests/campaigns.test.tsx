import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { CampaignPanel } from '../src/workbench/CampaignPanel';
import type { ExperimentRecord } from '../src/workbench/ExperimentsPanel';

const definition: ExperimentRecord = {
  id: 'definition',
  state: 'FROZEN',
  identity: 'd'.repeat(64),
  parameter_space_identity: 'p',
  split_plan_identity: 's',
  campaign_identity: 'c',
  definition: {},
};
const campaign = {
  id: 'campaign',
  status: 'CREATED',
  consumed_executions: 0,
  cancel_requested: false,
  plan_identity: 'a'.repeat(64),
  plan: { candidates: [{ identity: 'b'.repeat(64), assignments: { Period: '10' } }] },
  definition: { budget: { maximum_native_executions: 2, maximum_wall_seconds: 60 } },
  runs: [],
  selection: null,
  selection_identity: null,
};
const fetcher = vi.fn();
const ok = (value: unknown) => ({ ok: true, json: async () => value });
beforeEach(() => {
  fetcher.mockReset();
  vi.stubGlobal('fetch', fetcher);
});
async function inspect(value: unknown = campaign) {
  fetcher.mockResolvedValueOnce(ok({ items: value ? [value] : [] }));
  render(<CampaignPanel definition={definition} />);
  fireEvent.click(screen.getByRole('button', { name: 'Inspect campaigns' }));
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Inspect campaigns' })).toBeNull(),
  );
}
it('does not fetch, create or execute automatically', () => {
  render(<CampaignPanel definition={definition} />);
  expect(fetcher).not.toHaveBeenCalled();
  expect(screen.getByText('NOT LOADED')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /start|OOS|unlock/i })).toBeNull();
});
it('creates only a plan with frozen definition identity', async () => {
  await inspect(null);
  fetcher.mockResolvedValueOnce(ok(campaign));
  fireEvent.click(screen.getByRole('button', { name: 'Create campaign plan' }));
  await screen.findByRole('button', { name: 'Start / resume campaign' });
  expect(JSON.parse(fetcher.mock.calls[1]![1].body)).toEqual({
    definition_id: definition.id,
    definition_identity: definition.identity,
    confirmed: true,
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it('requires explicit bounded execution confirmation', async () => {
  await inspect();
  const start = screen.getByRole('button', {
    name: 'Start / resume campaign',
  }) as HTMLButtonElement;
  expect(start.disabled).toBe(true);
  fireEvent.click(screen.getByRole('checkbox'));
  fetcher.mockResolvedValueOnce(ok({ ...campaign, status: 'RUNNING' }));
  fireEvent.click(start);
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect(fetcher.mock.calls[1]![0]).toBe('/workbench-api/campaigns/campaign/start');
});
it('shows budget, progress and deterministic selection separately', async () => {
  await inspect({
    ...campaign,
    status: 'COMPLETE',
    consumed_executions: 2,
    selection: {
      selected: ['b'.repeat(64)],
      decisions: { ['b'.repeat(64)]: 'DEVELOPMENT_SELECTED' },
    },
    selection_identity: 's'.repeat(64),
  });
  expect(screen.getByText('DEVELOPMENT_SELECTED')).toBeTruthy();
  expect(screen.getByText('Limit 2')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /start|OOS|unlock/i })).toBeNull();
});
it('preserves zero versus null and shows failed outcomes', async () => {
  await inspect({
    ...campaign,
    status: 'PARTIAL',
    runs: [
      {
        id: 'run1',
        configuration_identity: 'b',
        purpose: 'DEVELOPMENT',
        status: 'COMPLETE',
        observation: {
          metrics: { TRADE_COUNT: '0', PROFIT_FACTOR: null },
          evidence_identity: 'e',
          result_identity: 'r',
        },
      },
      {
        id: 'run2',
        configuration_identity: 'b',
        purpose: 'VALIDATION',
        status: 'TIMEOUT',
        observation: null,
      },
    ],
  });
  expect(screen.getByText('TRADE_COUNT: 0')).toBeTruthy();
  expect(screen.getByText('PROFIT_FACTOR: —')).toBeTruthy();
  expect(screen.getByText('TIMEOUT')).toBeTruthy();
  expect(screen.getByText('No normalized observation')).toBeTruthy();
});
it('requests cancellation without removing run evidence', async () => {
  await inspect();
  fetcher.mockResolvedValueOnce(ok({ ...campaign, cancel_requested: true, status: 'CANCELLED' }));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel campaign' }));
  await screen.findByText('CANCELLED');
  expect(fetcher.mock.calls[1]![0]).toBe('/workbench-api/campaigns/campaign/cancel');
});
it('fails closed on unavailable storage without offering plan creation', async () => {
  fetcher.mockResolvedValueOnce({ ok: false });
  render(<CampaignPanel definition={definition} />);
  fireEvent.click(screen.getByRole('button', { name: 'Inspect campaigns' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: 'Create campaign plan' })).toBeNull();
});
it('refreshes with GET and never schedules a run', async () => {
  await inspect();
  fetcher.mockResolvedValueOnce(ok(campaign));
  fireEvent.click(screen.getByRole('button', { name: 'Refresh campaign' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect(fetcher.mock.calls[1]![1].method).toBe('GET');
});
