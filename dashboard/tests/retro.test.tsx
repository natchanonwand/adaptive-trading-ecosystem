import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import {
  Button,
  StatusBadge,
  Field,
  Select,
  Checkbox,
  MetricCard,
  MetricStrip,
  MonoValue,
  DataTable,
  RetroPanel,
  Tabs,
} from '../src/workbench/retro';
import { Workbench } from '../src/workbench/Workbench';

it.each([
  'VERIFIED',
  'READY',
  'RUNNING',
  'COMPLETE',
  'BLOCKED',
  'FAILED',
  'UNKNOWN',
  'DRAFT',
  'FROZEN',
  'PUBLISHED',
  'DEMO',
])('renders %s as explicit text, not color alone', (status) => {
  render(<StatusBadge status={status} />);
  expect(screen.getByText(status, { exact: false })).toBeVisible();
});
it('keeps unknown and blocked treatments distinct without deriving readiness', () => {
  const { container } = render(
    <>
      <StatusBadge status="UNKNOWN" />
      <StatusBadge status="BLOCKED_LICENSE" />
    </>,
  );
  expect(container.querySelector('[data-tone="unknown"]')).toHaveTextContent('UNKNOWN');
  expect(container.querySelector('[data-tone="danger"]')).toHaveTextContent('BLOCKED LICENSE');
});
it('supports keyboard focus/activation and prevents disabled button activation', async () => {
  const click = vi.fn();
  render(
    <>
      <Button variant="primary" onClick={click}>
        Review
      </Button>
      <Button disabled onClick={click}>
        Unavailable
      </Button>
    </>,
  );
  await userEvent.tab();
  expect(screen.getByRole('button', { name: 'Review' })).toHaveFocus();
  await userEvent.keyboard('{Enter}');
  expect(click).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: 'Unavailable' }));
  expect(click).toHaveBeenCalledTimes(1);
});
it('preserves labeled native form controls, readonly and error state', async () => {
  const change = vi.fn();
  render(
    <>
      <Field label="Identity" value="immutable" readOnly />
      <Field label="Budget" type="number" defaultValue={0} error="Positive value required" />
      <Select label="Method" defaultValue="GRID" onChange={change}>
        <option>GRID</option>
        <option>RANDOM_SEEDED</option>
      </Select>
      <Checkbox label="Explicit confirmation" onChange={change} />
    </>,
  );
  expect(screen.getByLabelText('Identity')).toHaveAttribute('readonly');
  expect(screen.getByRole('spinbutton')).toHaveAttribute('aria-invalid', 'true');
  expect(screen.getByRole('alert')).toHaveTextContent('Positive value required');
  await userEvent.selectOptions(screen.getByLabelText('Method'), 'RANDOM_SEEDED');
  await userEvent.click(screen.getByLabelText('Explicit confirmation'));
  expect(change).toHaveBeenCalledTimes(2);
});
it('distinguishes numeric and decimal zero from null without fabricated metrics', () => {
  render(
    <MetricStrip>
      <MetricCard label="Trades" value={0} />
      <MetricCard label="Profit" value="0.00" />
      <MetricCard label="Win rate" value={null} />
    </MetricStrip>,
  );
  expect(screen.getByText('0', { exact: true })).toBeVisible();
  expect(screen.getByText('0.00', { exact: true })).toBeVisible();
  expect(screen.getByLabelText('Unavailable')).toHaveTextContent('—');
});
it('provides a named scrollable table and mono identities', () => {
  render(
    <DataTable caption="Evidence" columns={['Identity', 'Trades']}>
      <tr>
        <td>
          <MonoValue value="abc123" />
        </td>
        <td className="rt-numeric">0</td>
      </tr>
    </DataTable>,
  );
  expect(screen.getByRole('region', { name: 'Evidence' })).toHaveAttribute('tabindex', '0');
  expect(screen.getAllByRole('columnheader')).toHaveLength(2);
  expect(screen.getByText('abc123').tagName).toBe('CODE');
});
it('provides panel title, status, actions and footer without synthetic behavior', () => {
  render(
    <RetroPanel
      title="Read-only evidence"
      status="FROZEN"
      actions={<Button>Details</Button>}
      footer="Immutable"
    >
      Contents
    </RetroPanel>,
  );
  expect(screen.getByRole('region', { name: 'Read-only evidence' })).toBeVisible();
  expect(screen.getByText('Immutable')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Details' })).toBeVisible();
});
it('keeps navigation semantic and keyboard accessible', async () => {
  const change = vi.fn();
  render(<Tabs items={['Overview', 'Evidence']} current="Overview" onChange={change} />);
  expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-current', 'page');
  await userEvent.tab();
  await userEvent.tab();
  await userEvent.keyboard('{Enter}');
  expect(change).toHaveBeenCalledWith('Evidence');
});
it('renders actual Overview metadata and identities through the retro shell', async () => {
  window.history.replaceState(null, '', '/workbench#/projects/synthetic');
  const fetcher = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      project: {
        project_id: 'synthetic',
        candidate_id: 'candidate',
        project_name: 'Synthetic research',
        source_type: 'EXTERNAL_EA',
        status: 'BASELINE_READY',
        broker_binding: {
          canonical_asset: 'XAUUSD',
          broker_name: 'Demo',
          broker_symbol: 'XAUUSDm',
          timeframe: 'M5',
          environment: 'DEMO',
        },
      },
      candidate: {
        product_name: 'Synthetic EA',
        version: 'UNKNOWN',
        license_status: 'UNKNOWN',
        tester_access_status: 'UNKNOWN',
        artifact_size: 12,
        artifact_sha256: 'a'.repeat(64),
      },
      verification: { ea: 'VERIFIED' },
      configurations: [],
    }),
  }));
  vi.stubGlobal('fetch', fetcher);
  render(<Workbench />);
  expect(await screen.findByRole('heading', { name: 'Synthetic research' })).toBeVisible();
  expect(screen.getByText('ADAPTIVE TRADING ECOSYSTEM')).toBeVisible();
  expect(screen.getByRole('region', { name: 'Project dossier' })).toBeVisible();
  expect(screen.getByText('a'.repeat(64))).toBeVisible();
  expect(screen.getByText('12', { exact: true })).toBeVisible();
  expect(screen.getByText('0', { exact: true })).toBeVisible();
  expect(screen.getByLabelText('Unavailable')).toHaveTextContent('—');
  fireEvent.click(screen.getByRole('button', { name: 'Behavior' }));
  expect(screen.getByRole('heading', { name: 'Coming soon' })).toBeVisible();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
