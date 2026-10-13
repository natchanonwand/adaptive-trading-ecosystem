import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { CampaignAuthorization } from '../src/workbench/CampaignAuthorization';
import { CampaignPanel } from '../src/workbench/CampaignPanel';

it('shows budget and refuses authorization without environment readiness', () => {
  const authorize = vi.fn();
  render(
    <CampaignAuthorization
      busy={false}
      authorize={authorize}
      review={{
        state: 'NOT_AUTHORIZED',
        start_eligible: false,
        authorization_eligible: false,
        review_identity: 'a'.repeat(64),
        blocker: 'INITIALIZATION_FAILED',
      }}
    />,
  );
  expect(screen.getByText(/Native maximum 11/)).toBeTruthy();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: 'Authorize campaign' }));
  expect(authorize).not.toHaveBeenCalled();
  expect(screen.getByText(/INITIALIZATION_FAILED/)).toBeTruthy();
});

it('requires explicit review and submits identity without starting', () => {
  const authorize = vi.fn().mockResolvedValue(undefined);
  render(
    <CampaignAuthorization
      busy={false}
      authorize={authorize}
      review={{
        state: 'NOT_AUTHORIZED',
        start_eligible: false,
        authorization_eligible: true,
        review_identity: 'b'.repeat(64),
      }}
    />,
  );
  const button = screen.getByRole('button', { name: 'Authorize campaign' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(button);
  expect(authorize).toHaveBeenCalledExactlyOnceWith('b'.repeat(64));
  expect(screen.queryByRole('button', { name: /start/i })).toBeNull();
});

it('keeps existing authorization immutable and OOS sealed', () => {
  render(
    <CampaignAuthorization
      busy={false}
      authorize={vi.fn()}
      review={{
        state: 'AUTHORIZED',
        start_eligible: true,
        authorization_eligible: true,
        review_identity: 'c'.repeat(64),
      }}
    />,
  );
  fireEvent.click(screen.getByRole('checkbox'));
  expect(
    (screen.getByRole('button', { name: 'Authorize campaign' }) as HTMLButtonElement).disabled,
  ).toBe(true);
  expect(screen.getByText(/LOCKED_OOS SEALED/)).toBeTruthy();
});

it.each(['NOT_AUTHORIZED', 'AUTHORIZED'])(
  'Start eligibility requires backend authorization state %s without auto-start',
  async (state) => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [
          {
            id: 'reference',
            status: 'CREATED',
            consumed_executions: 0,
            cancel_requested: false,
            plan_identity: 'a'.repeat(64),
            plan: { candidates: [] },
            definition: {
              budget: {
                maximum_configurations: 9,
                maximum_native_executions: 11,
                maximum_wall_seconds: 6600,
              },
            },
            runs: [],
            selection: null,
            selection_identity: null,
            authorization_review: { state, start_eligible: true },
          },
        ],
      }),
    });
    vi.stubGlobal('fetch', fetcher);
    try {
      render(
        <CampaignPanel
          definition={{
            id: 'd',
            state: 'FROZEN',
            identity: 'd'.repeat(64),
            parameter_space_identity: 'p',
            split_plan_identity: 's',
            campaign_identity: 'c',
            definition: {},
          }}
        />,
      );
      fireEvent.click(screen.getByRole('button', { name: 'Inspect campaigns' }));
      const start = (await screen.findByRole('button', {
        name: 'Start / resume campaign',
      })) as HTMLButtonElement;
      expect(start.disabled).toBe(state !== 'AUTHORIZED');
      expect(fetcher).toHaveBeenCalledTimes(1);
      expect(fetcher.mock.calls[0]![1].method).toBe('GET');
    } finally {
      vi.unstubAllGlobals();
    }
  },
);
