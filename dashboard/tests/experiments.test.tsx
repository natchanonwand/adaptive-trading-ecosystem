import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { ExperimentsPanel, type ExperimentRecord } from '../src/workbench/ExperimentsPanel';
import type { Detail } from '../src/workbench/api';

const detail: Detail = {
  project: {
    project_id: 'project',
    candidate_id: 'candidate',
    project_name: 'Synthetic',
    source_type: 'EXTERNAL_EA',
    status: 'BASELINE_READY',
    updated_at: '',
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
    product_name: 'Synthetic',
    version: '',
    vendor: '',
    source_reference: '',
    license_status: 'UNKNOWN',
    tester_access_status: 'UNKNOWN',
    known_magic_number: null,
    known_order_comments: '',
    notes: '',
    catalog_id: null,
    artifact_id: null,
    manual_id: null,
  },
  configurations: [
    {
      specification: { configuration_id: 'config', project_id: 'project', parameters: {} },
      configuration_identity: 'a'.repeat(64),
      exact_inputs_known: false,
      input_limitation: null,
    },
  ],
  verification: {},
  baseline_status: 'READY',
  execution_available: false,
};
const draft: ExperimentRecord = {
  id: 'draft',
  state: 'DRAFT',
  identity: 'b'.repeat(64),
  parameter_space_identity: 'c'.repeat(64),
  split_plan_identity: 'd'.repeat(64),
  campaign_identity: 'e'.repeat(64),
  definition: {
    project_id: 'project',
    candidate_id: 'candidate',
    baseline_configuration_id: 'config',
    baseline_identity: 'a'.repeat(64),
    hypothesis: 'Synthetic only',
    parameter_space: {
      parameters: [
        {
          parameter_name: 'Period',
          native_key: 'Period',
          kind: 'INTEGER',
          baseline: '2',
          minimum: '1',
          maximum: '3',
          step: '1',
          choices: [],
          transformation: 'IDENTITY',
          reason: 'Declared test',
          provenance: 'USER_DECLARATION',
          source_reference: 'Synthetic fixture',
          conditional: null,
          categorical: false,
          ordered: true,
        },
      ],
    },
    budget: {
      maximum_configurations: 3,
      maximum_native_executions: 3,
      method: 'GRID',
      random_seed: null,
      maximum_wall_seconds: 60,
      maximum_workers: 1,
      early_rejection: 'NONE',
    },
    split_plan: {
      splits: ['DEVELOPMENT', 'VALIDATION', 'LOCKED_OOS'].map((purpose, i) => ({
        purpose,
        start: `2020-0${i + 1}-01`,
        end: `2020-0${i + 2}-01`,
        locked: true,
      })),
    },
    objectives: [
      {
        metric: 'RETURN_R',
        direction: 'MAXIMIZE',
        definition: 'Declared risk return',
        null_policy: 'INELIGIBLE',
      },
    ],
    constraints: [
      {
        metric: 'TRADE_COUNT',
        comparator: 'AT_LEAST',
        threshold: '1',
        rationale: 'Minimum activity',
      },
    ],
  },
};
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vi.restoreAllMocks();
  fetcher = vi.fn(async (_url: string, init?: RequestInit) => ({
    ok: true,
    json: async () => (init?.method === 'POST' ? draft : { items: [draft] }),
  }));
  vi.stubGlobal('fetch', fetcher);
});
async function open(record = draft) {
  fetcher.mockResolvedValueOnce({ ok: true, json: async () => ({ items: [record] }) });
  render(<ExperimentsPanel detail={detail} />);
  await waitFor(() => expect(screen.getByLabelText('Review saved definition')).not.toBeDisabled());
  fireEvent.change(screen.getByLabelText('Review saved definition'), {
    target: { value: record.id },
  });
}
it('renders empty editor with baseline selection and no fabricated inputs', async () => {
  render(<ExperimentsPanel detail={detail} />);
  await waitFor(() =>
    expect(screen.getByLabelText('Existing baseline configuration')).not.toBeDisabled(),
  );
  fireEvent.change(screen.getByLabelText('Existing baseline configuration'), {
    target: { value: 'config' },
  });
  expect(screen.getByLabelText('baseline identity')).toHaveValue('a'.repeat(64));
  expect(screen.getByLabelText('parameter space parameters 1 native key')).toHaveValue('');
});
it('shows identity review, objectives, constraints and protected chronological splits', async () => {
  await open();
  for (const id of [
    draft.identity,
    draft.parameter_space_identity,
    draft.split_plan_identity,
    draft.campaign_identity,
  ])
    expect(screen.getByText(id)).toBeVisible();
  for (const purpose of ['DEVELOPMENT', 'VALIDATION', 'LOCKED_OOS'])
    expect(screen.getByDisplayValue(purpose)).toHaveAttribute('readonly');
  expect(screen.getByLabelText('objectives 1 metric')).toHaveValue('RETURN_R');
  expect(screen.getByLabelText('constraints 1 threshold')).toHaveValue('1');
  expect(screen.getByText(/READY for explicit freeze/)).toBeVisible();
});
it('edits draft inputs, saves exact declarations and invalidates freeze review', async () => {
  await open();
  fireEvent.change(screen.getByLabelText('parameter space parameters 1 baseline'), {
    target: { value: '3' },
  });
  fireEvent.change(screen.getByLabelText('budget maximum configurations'), {
    target: { value: '4' },
  });
  expect(screen.getByRole('button', { name: 'Freeze definition' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Register / save draft' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  const [url, init] = fetcher.mock.calls[1]!;
  expect(url).toBe('/workbench-api/experiments');
  const body = JSON.parse(init.body);
  expect(body.parameter_space.parameters[0].baseline).toBe('3');
  expect(body.budget.maximum_configurations).toBe(4);
  expect(init.headers['X-Workbench-Request']).toBe('1');
});
it.each([
  ['parameter space parameters 1 step', '0', 'INVALID_PARAMETER_RANGE_OR_STEP'],
  ['budget maximum configurations', '0', 'INVALID_EXPERIMENT_DEFINITION_OR_ACTION'],
  ['split plan splits 2 start', '2019-01-01', 'OVERLAPPING_SPLITS'],
])('surfaces backend rejection for %s verbatim', async (label, value, error) => {
  await open();
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fetcher.mockResolvedValueOnce({ ok: false, json: async () => ({ error }) });
  fireEvent.click(screen.getByRole('button', { name: 'Register / save draft' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(error);
  expect(screen.getByRole('button', { name: 'Freeze definition' })).toBeDisabled();
});
it('requires explicit confirmation and freezes into read-only state', async () => {
  await open();
  expect(screen.getByRole('button', { name: 'Freeze definition' })).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/I reviewed these identities/));
  fetcher.mockResolvedValueOnce({ ok: true, json: async () => ({ ...draft, state: 'FROZEN' }) });
  fireEvent.click(screen.getByRole('button', { name: 'Freeze definition' }));
  expect(await screen.findByText(/This definition is read-only/)).toBeVisible();
  expect(screen.getByLabelText('hypothesis')).toHaveAttribute('readonly');
  expect(screen.getByLabelText('budget method')).toBeDisabled();
  expect(screen.queryByRole('button', { name: 'Register / save draft' })).not.toBeInTheDocument();
  expect(fetcher.mock.calls[1]![0]).toBe('/workbench-api/experiments/draft/freeze');
  expect(JSON.parse(fetcher.mock.calls[1]![1].body)).toEqual({ confirmed: true });
  expect(screen.getByText(draft.identity)).toBeVisible();
});
it('loads frozen records without mutation controls and permits only a new blank definition', async () => {
  await open({ ...draft, state: 'FROZEN' });
  expect(screen.getByLabelText('hypothesis')).toBeDisabled();
  expect(screen.queryByRole('button', { name: 'Freeze definition' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'New definition' }));
  expect(screen.getByLabelText('hypothesis')).toHaveValue('');
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it('supports discrete choices and explicit conditional provenance editing', async () => {
  await open();
  fireEvent.click(screen.getByRole('button', { name: 'Add parameter space parameters 1 choices' }));
  fireEvent.change(screen.getByLabelText('parameter space parameters 1 choices 1'), {
    target: { value: '2' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Add parameter space parameters 1 conditional' }),
  );
  expect(screen.getByLabelText('parameter space parameters 1 conditional native key')).toHaveValue(
    '',
  );
  expect(screen.getByLabelText('parameter space parameters 1 source reference')).toHaveValue(
    'Synthetic fixture',
  );
});
it('has no campaign, OOS execution or unlock control and issues only list GET', async () => {
  await open();
  expect(
    screen.queryByRole('button', { name: /run|execute|unlock|tune|search/i }),
  ).not.toBeInTheDocument();
  expect(screen.getByText(/protected from parameter selection/)).toBeVisible();
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0]![1].method).toBe('GET');
});
it('shows list storage failures without claiming readiness', async () => {
  fetcher.mockResolvedValueOnce({
    ok: false,
    json: async () => ({ error: 'EXPERIMENT_STORAGE_UNAVAILABLE' }),
  });
  render(<ExperimentsPanel detail={detail} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('EXPERIMENT_STORAGE_UNAVAILABLE');
  expect(screen.queryByText(/READY for explicit freeze/)).not.toBeInTheDocument();
});
