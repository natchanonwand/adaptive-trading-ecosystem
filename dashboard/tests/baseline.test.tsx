import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { BaselinePanel, type BaselineRun } from '../src/workbench/BaselinePanel';
import { type Detail } from '../src/workbench/api';
import { Workbench } from '../src/workbench/Workbench';

const detail: Detail = {
  baseline_enabled: true,
  baseline_status: 'READY',
  execution_available: false,
  verification: { ea: 'VERIFIED' },
  project: {
    project_id: 'project',
    candidate_id: 'candidate',
    project_name: 'Synthetic',
    source_type: 'EXTERNAL_EA',
    status: 'BASELINE_READY',
    updated_at: '2026-09-01',
    broker_binding: {
      broker_name: 'Synthetic demo',
      environment: 'DEMO',
      canonical_asset: 'XAUUSD',
      broker_symbol: 'XAUUSDm',
      timeframe: 'H1',
      symbol_confirmed: true,
    },
  },
  candidate: {
    product_name: 'Synthetic fixture',
    version: 'UNKNOWN',
    vendor: 'UNKNOWN',
    source_reference: 'UNKNOWN',
    license_status: 'USER_ATTESTED',
    tester_access_status: 'USER_CONFIRMED',
    known_magic_number: null,
    known_order_comments: 'UNKNOWN',
    notes: 'UNKNOWN',
    catalog_id: null,
    artifact_id: 'artifact',
    manual_id: null,
    artifact_sha256: 'a'.repeat(64),
  },
};
const saved: BaselineRun = {
  config: {
    baseline_run_id: 'run',
    project_id: 'project',
    symbol: 'XAUUSDm',
    timeframe: 'H1',
    from_date: '2026-09-01',
    to_date: '2026-09-08',
    initial_deposit: '10000',
    currency: 'USD',
    leverage: 100,
    tester_model: 'EVERY_TICK_BASED_ON_REAL_TICKS',
    environment: 'DEMO_RESEARCH_TESTER',
    timeout_seconds: 600,
    input_provenance: 'TESTER_DEFAULTS',
    set_text: null,
  },
  candidate_id: 'candidate',
  artifact_id: 'artifact',
  ea_sha256: 'a'.repeat(64),
  input_sha256: null,
  status: 'READY',
  diagnostic: 'READY_FOR_EXPLICIT_START',
  started_at: null,
  completed_at: null,
  terminal_build: 'UNKNOWN',
  observed_tester_status: 'UNKNOWN',
  declared_license_status: 'USER_ATTESTED',
  declared_tester_access: 'USER_CONFIRMED',
  evidence_identity: null,
  result_identity: null,
};
beforeEach(() => {
  vi.restoreAllMocks();
});

it('shows baseline ready with unknown declarations and never automatically starts', async () => {
  const unknown: Detail = {
    ...detail,
    candidate: { ...detail.candidate, license_status: 'UNKNOWN', tester_access_status: 'UNKNOWN' },
  };
  const fetcher = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => (url.includes('/projects/') ? unknown : { items: [] }),
  }));
  vi.stubGlobal('fetch', fetcher);
  window.history.replaceState(null, '', '/workbench#/projects/project');
  render(<Workbench />);
  expect(await screen.findByText('BASELINE READY', { selector: '.wb-badge' })).toBeVisible();
  expect(screen.queryByText('BLOCKED LICENSE')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Baseline' }));
  expect(await screen.findByText(/UNKNOWN means not yet verified/)).toBeVisible();
  expect(screen.getByText(/Declared license: UNKNOWN/)).toHaveTextContent(
    'Declared tester access: UNKNOWN',
  );
  expect(screen.getByRole('button', { name: 'Run Baseline' })).toBeEnabled();
  expect(fetcher.mock.calls.some(([url]) => url.endsWith('/start'))).toBe(false);
});
function mock(status = 'READY', list = false) {
  const run = { ...saved, status };
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    const value = url.includes('?')
      ? { items: list ? [run] : [] }
      : options?.method === 'POST'
        ? {
            ...run,
            status: url.endsWith('/start')
              ? 'QUEUED'
              : url.endsWith('/cancel')
                ? 'CANCELLED'
                : status,
          }
        : {
            run,
            result:
              status === 'COMPLETE'
                ? {
                    metrics: {
                      net_profit: '250.50',
                      total_trades: 10,
                      win_rate: '0.6',
                      average_holding_time: null,
                    },
                    metadata: { Build: 'UNAVAILABLE' },
                    report_identity: 'raw-hash',
                    result_identity: 'result-hash',
                  }
                : null,
          };
    return { ok: true, json: async () => value };
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
async function selectRun() {
  await screen.findByRole('combobox', { name: 'Saved baseline runs' });
  fireEvent.change(screen.getByRole('combobox', { name: 'Saved baseline runs' }), {
    target: { value: 'run' },
  });
}
it('requires readiness and performs no automatic execution', async () => {
  const fetcher = mock();
  render(<BaselinePanel detail={{ ...detail, baseline_status: 'NOT_READY' }} />);
  expect(screen.getByRole('button', { name: 'Run Baseline' })).toBeDisabled();
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  expect(fetcher.mock.calls.every(([, options]) => !options || options.method === 'GET')).toBe(
    true,
  );
});
it('persists explicit config then requires a separate confirmation to start', async () => {
  const fetcher = mock();
  render(<BaselinePanel detail={detail} />);
  fireEvent.change(screen.getByLabelText('From date'), { target: { value: '2026-09-01' } });
  fireEvent.change(screen.getByLabelText('To date (exclusive)'), {
    target: { value: '2026-09-08' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Run Baseline' }));
  const start = await screen.findByRole('button', { name: 'Confirm and start tester' });
  expect(start).toBeDisabled();
  expect(fetcher.mock.calls.some(([url]) => url.endsWith('/start'))).toBe(false);
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(start);
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(
        ([url, options]) => url.endsWith('/start') && options?.body === '{"confirmed":true}',
      ),
    ).toBe(true),
  );
});
it('shows real stages and elapsed time without a progress percentage', async () => {
  mock('RUNNING', true);
  render(<BaselinePanel detail={detail} />);
  await selectRun();
  expect(await screen.findByText(/RUNNING · Elapsed/)).toBeInTheDocument();
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Cancel baseline' })).toBeEnabled();
});
it('shows normalized metrics, unavailable values and evidence after completion', async () => {
  mock('COMPLETE', true);
  render(<BaselinePanel detail={detail} />);
  await selectRun();
  expect(await screen.findByText('Result Summary')).toBeInTheDocument();
  expect(screen.getByText('250.50')).toBeInTheDocument();
  expect(screen.getByText('raw-hash')).toBeInTheDocument();
  expect(screen.getByText('result-hash')).toBeInTheDocument();
  expect(screen.getAllByText('UNAVAILABLE').length).toBeGreaterThan(0);
  expect(
    screen.queryByRole('button', { name: 'Confirm and start tester' }),
  ).not.toBeInTheDocument();
});
it.each([
  'BLOCKED_SYMBOL',
  'BLOCKED_LICENSE',
  'BLOCKED_TESTER_ACCESS',
  'BLOCKED_REAL_TICKS_UNAVAILABLE',
  'TIMEOUT',
  'REPORT_PARSE_FAILED',
  'TESTER_FAILED',
  'CANCELLED',
])('renders actionable %s without fabricated results', async (status) => {
  mock(status, true);
  render(<BaselinePanel detail={detail} />);
  await selectRun();
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(screen.queryByText('Result Summary')).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Confirm and start tester' }),
  ).not.toBeInTheDocument();
});
it('supports cancellation without treating it as success', async () => {
  const fetcher = mock('RUNNING', true);
  render(<BaselinePanel detail={detail} />);
  await selectRun();
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel baseline' }));
  await waitFor(() =>
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/cancel'))).toBe(true),
  );
  expect(await screen.findByText(/This run was cancelled/)).toBeInTheDocument();
});
it('shows an explicit busy error and never retries start automatically', async () => {
  const fetcher = mock('READY', true);
  render(<BaselinePanel detail={detail} />);
  await selectRun();
  await screen.findByRole('checkbox');
  fetcher.mockResolvedValueOnce({ ok: false, json: async () => ({}) } as never);
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm and start tester' }));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/start'))).toHaveLength(1);
});
