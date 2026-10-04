import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { Workbench } from '../src/workbench/Workbench';
import { upload } from '../src/workbench/api';

const binding = {
  broker_name: 'Demo',
  environment: 'DEMO',
  canonical_asset: 'XAUUSD',
  broker_symbol: 'XAUUSDm',
  timeframe: 'H1',
  symbol_confirmed: true,
};
const project = {
  project_id: 'project-1',
  candidate_id: 'candidate-1',
  project_name: 'Gold research',
  source_type: 'EXTERNAL_EA',
  status: 'BASELINE_READY',
  updated_at: '2026-09-26T00:00:00Z',
  broker_binding: binding,
  product_name: 'Gold pilot',
};
const artifact = {
  artifact_id: 'artifact-1',
  filename: 'synthetic.ex5',
  sha256: 'a'.repeat(64),
  size: 12,
};
const detail = {
  project,
  candidate: {
    product_name: 'Gold pilot',
    version: 'UNKNOWN',
    license_status: 'USER_ATTESTED',
    tester_access_status: 'USER_CONFIRMED',
    artifact_id: artifact.artifact_id,
    artifact_filename: artifact.filename,
    artifact_sha256: artifact.sha256,
    artifact_size: artifact.size,
  },
  verification: { ea: 'VERIFIED', manual: 'NOT_PROVIDED' },
  baseline_status: 'READY',
  execution_available: false,
};
const catalog = [
  {
    catalog_id: 'gold-scalper',
    product_name: 'Gold Scalper for MT5 EA',
    asset: 'XAUUSD',
    research_class: 'transparent/simple pilot',
    source_reference: 'UNKNOWN',
  },
];

function mockFetch(items: unknown[] = []) {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    let value: unknown = { items, next_offset: null };
    if (url.endsWith('/catalog')) value = { items: catalog };
    else if (url.endsWith('/artifacts')) value = artifact;
    else if (options?.method === 'POST') value = project;
    else if (url.endsWith('/project-1')) value = detail;
    return { ok: true, json: async () => value };
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

beforeEach(() => {
  window.history.replaceState(null, '', '/workbench#/projects');
});

it('shows the empty projects state', async () => {
  mockFetch();
  render(<Workbench />);
  expect(await screen.findByRole('button', { name: 'Create your first project' })).toBeVisible();
});

it('lists persisted project metadata and opens its detail', async () => {
  mockFetch([project]);
  render(<Workbench />);
  expect(await screen.findByText('Gold research')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Open Project' }));
  expect(await screen.findByRole('heading', { name: 'Overview' })).toBeVisible();
  expect(screen.getByText('VERIFIED')).toBeVisible();
});

it('creates a catalog draft through all six steps with explicit DEMO metadata', async () => {
  const fetcher = mockFetch();
  render(<Workbench />);
  await userEvent.click(await screen.findByRole('button', { name: 'New Research Project' }));
  expect(screen.getByRole('button', { name: /Strategy Idea/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: /Quant Formula/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: /Manual Trading/ })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  await userEvent.type(screen.getByLabelText('Project name'), 'Demo draft');
  await userEvent.click(await screen.findByRole('button', { name: /Gold Scalper/ }));
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByLabelText('Optional manual (.pdf)')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByLabelText('Environment')).toHaveValue('DEMO');
  expect(screen.getByLabelText('Broker symbol')).toHaveValue('UNKNOWN');
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  await userEvent.click(screen.getByRole('button', { name: 'Create Project' }));
  await screen.findByRole('heading', { name: 'Overview' });
  const call = fetcher.mock.calls.find(
    ([url, options]) => url.endsWith('/projects') && options?.method === 'POST',
  );
  const body = JSON.parse(call![1]!.body as string);
  expect(body).toMatchObject({
    project_name: 'Demo draft',
    source_type: 'EXTERNAL_EA',
    candidate: { catalog_id: 'gold-scalper', artifact_id: null, manual_id: null },
    broker_binding: {
      environment: 'DEMO',
      canonical_asset: 'XAUUSD',
      broker_symbol: 'UNKNOWN',
      symbol_confirmed: false,
    },
  });
  expect(body.project_id).toMatch(/^[a-f0-9-]{36}$/);
});

it('keeps uploaded artifact identity when switching back to custom candidate', async () => {
  const fetcher = mockFetch();
  window.history.replaceState(null, '', '/workbench#/projects/new');
  render(<Workbench />);
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  await userEvent.type(screen.getByLabelText('Project name'), 'Upload test');
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const file = new File(['opaque fixture'], 'synthetic.ex5');
  Object.defineProperty(file, 'arrayBuffer', {
    value: async () => new Uint8Array([1, 2, 3]).buffer,
  });
  fireEvent.change(screen.getByLabelText('EA artifact (.ex5)'), { target: { files: [file] } });
  await screen.findByText(/EA artifact: synthetic.ex5/);
  await userEvent.click(screen.getByRole('button', { name: 'Back' }));
  await userEvent.click(screen.getByRole('button', { name: /custom candidate/ }));
  for (let i = 0; i < 4; i++)
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByText(artifact.sha256)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Create Project' }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(
        ([url, options]) => url.endsWith('/projects') && options?.method === 'POST',
      ),
    ).toBe(true),
  );
  const call = fetcher.mock.calls.find(
    ([url, options]) => url.endsWith('/projects') && options?.method === 'POST',
  );
  expect(JSON.parse(call![1]!.body as string).candidate.artifact_id).toBe('artifact-1');
  await screen.findByRole('heading', { name: 'Overview' });
});

it('shows identities and baseline placeholder without an execution request', async () => {
  const fetcher = mockFetch();
  window.history.replaceState(null, '', '/workbench#/projects/project-1');
  render(<Workbench />);
  await screen.findByRole('heading', { name: 'Overview' });
  await userEvent.click(screen.getByRole('button', { name: 'Evidence' }));
  expect(screen.getByText('candidate-1')).toBeVisible();
  expect(screen.getByText(artifact.sha256)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Baseline' }));
  await userEvent.click(screen.getByRole('button', { name: 'Run Baseline' }));
  expect(screen.getByRole('status')).toHaveTextContent('available in Phase 5B');
  for (const stage of ['Experiments', 'Behavior', 'Forward']) {
    await userEvent.click(screen.getByRole('button', { name: stage }));
    expect(screen.getByRole('heading', { name: 'Coming soon' })).toBeVisible();
  }
  expect(fetcher.mock.calls.every(([, options]) => options?.method === 'GET')).toBe(true);
});

it('rejects invalid files before a network request', async () => {
  const fetcher = mockFetch();
  await expect(upload(new File(['x'], 'file.exe'), 'EA')).rejects.toThrow('EX5');
  await expect(upload(new File([], 'file.ex5'), 'EA')).rejects.toThrow('non-empty');
  await expect(upload(new File(['x'], 'file.ex5'), 'MANUAL')).rejects.toThrow('PDF');
  expect(fetcher).not.toHaveBeenCalled();
});

it('displays a safe error instead of backend error details', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({ password: 'never display' }), // pragma: allowlist secret - synthetic error fixture
    })),
  );
  render(<Workbench />);
  expect(await screen.findByRole('alert')).toHaveTextContent('storage is unavailable');
  expect(screen.queryByText('never display')).not.toBeInTheDocument();
});
