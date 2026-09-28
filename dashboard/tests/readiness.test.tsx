import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { ReadinessPanel } from '../src/workbench/ReadinessPanel';
import { type Detail } from '../src/workbench/api';

const detail: Detail = {
  baseline_enabled: true,
  readiness_enabled: true,
  baseline_status: 'READY',
  execution_available: false,
  verification: { ea: 'VERIFIED' },
  authorization: { provenance: 'UNKNOWN' },
  authorization_history: [],
  configurations: [],
  acceptance_readiness: {
    status: 'NOT_READY',
    reasons: ['BLOCKED_AUTHORIZATION_PROVENANCE', 'BASELINE_CONFIGURATION_REQUIRED'],
  },
  project: {
    project_id: 'project',
    candidate_id: 'candidate',
    project_name: 'Synthetic',
    source_type: 'EXTERNAL_EA',
    status: 'BASELINE_READY',
    updated_at: '2026-09-01',
    broker_binding: {
      broker_name: 'Demo',
      environment: 'DEMO',
      canonical_asset: 'XAUUSD',
      broker_symbol: 'XAUUSDm',
      timeframe: 'M5',
      symbol_confirmed: true,
    },
  },
  candidate: {
    product_name: 'Synthetic fixture',
    version: 'UNKNOWN',
    vendor: 'UNKNOWN',
    source_reference: 'UNKNOWN',
    license_status: 'UNKNOWN',
    tester_access_status: 'UNKNOWN',
    known_magic_number: null,
    known_order_comments: 'UNKNOWN',
    notes: 'UNKNOWN',
    catalog_id: null,
    artifact_id: 'artifact',
    manual_id: null,
    artifact_sha256: 'a'.repeat(64),
  },
};
beforeEach(() => {
  vi.restoreAllMocks();
});
it('keeps verified artifact distinct from unknown authorization and requires attestation', async () => {
  const fetcher = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => (url.includes('/baselines') ? { items: [] } : detail),
  }));
  vi.stubGlobal('fetch', fetcher);
  render(<ReadinessPanel detail={detail} source />);
  expect(screen.getByText(/not vendor verification/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save authorization attestation' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Authorization provenance'), {
    target: { value: 'FREE_VENDOR_DISTRIBUTION' },
  });
  fireEvent.change(screen.getByLabelText('source label'), {
    target: { value: 'Synthetic vendor' },
  });
  fireEvent.change(screen.getByLabelText('source reference'), {
    target: { value: 'Vendor terms reference' },
  });
  fireEvent.change(screen.getByLabelText('authorization basis'), {
    target: { value: 'Explicit tester permission' },
  });
  fireEvent.click(screen.getByLabelText(/I confirm this source/));
  fireEvent.click(screen.getByRole('button', { name: 'Save authorization attestation' }));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      '/workbench-api/authorization/project',
      expect.objectContaining({ method: 'POST' }),
    ),
  );
  expect(fetcher.mock.calls.some(([url]) => url.includes('/start'))).toBe(false);
});
it('saves a reviewed specification without creating an execution attempt', async () => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => ({
    ok: true,
    json: async () =>
      url.includes('/baseline-configurations')
        ? { specification: JSON.parse(String(options?.body)) }
        : url.includes('/baselines')
          ? { items: [] }
          : detail,
  }));
  vi.stubGlobal('fetch', fetcher);
  render(<ReadinessPanel detail={detail} />);
  expect(screen.getByText('BLOCKED_AUTHORIZATION_PROVENANCE')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Run Baseline' })).toBeDisabled();
  expect(screen.getByLabelText('from date')).toHaveValue('');
  fireEvent.change(screen.getByLabelText('from date'), { target: { value: '2026-09-01' } });
  fireEvent.change(screen.getByLabelText('to date'), { target: { value: '2026-09-02' } });
  fireEvent.click(screen.getByLabelText(/I reviewed all configuration/));
  fireEvent.click(screen.getByRole('button', { name: 'Save BaselineConfiguration' }));
  await waitFor(() =>
    expect(screen.getByText(/No execution attempt was created/)).toBeInTheDocument(),
  );
  const posts = fetcher.mock.calls.filter(([, o]) => o?.method === 'POST');
  expect(posts).toHaveLength(1);
  expect(posts[0]![0]).toBe('/workbench-api/baseline-configurations');
  expect(JSON.parse(String(posts[0]![1]?.body)).parameters).toMatchObject({
    symbol: 'XAUUSDm',
    timeframe: 'M5',
    tester_model: 'EVERY_TICK_BASED_ON_REAL_TICKS',
    input_provenance: 'TESTER_DEFAULTS',
    set_text: null,
  });
});

it('shows the research terminal blocker independently of candidate readiness', () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => ({ items: [] }) })),
  );
  render(
    <ReadinessPanel
      detail={{
        ...detail,
        acceptance_readiness: { status: 'READY', reasons: [] },
        research_environment: {
          status: 'BOOTSTRAP_UNVERIFIED',
          native_bootstrap: 'NOT_VERIFIED',
          symbol: 'XAUUSDm',
          binding: {
            terminal_executable: 'C:/Synthetic/terminal64.exe',
            terminal_data_root: 'C:/Synthetic/profile',
            company: 'Synthetic',
            terminal_build: '6230',
          },
        },
      }}
    />,
  );
  expect(screen.getByRole('region', { name: 'Research Environment' })).toBeInTheDocument();
  expect(screen.getByText('BOOTSTRAP_UNVERIFIED')).toBeInTheDocument();
  expect(screen.getByText(/native bootstrap: NOT_VERIFIED/)).toBeInTheDocument();
  expect(screen.getByText(/Build 6230/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Run Baseline' })).toBeDisabled();
});
