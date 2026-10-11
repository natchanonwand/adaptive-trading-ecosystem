import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { CopyValue, Metrics, Timestamp } from '../src/workbench/ResearchSurfaces';

it('copies the complete long identity through a labeled keyboard control', async () => {
  const user = userEvent.setup();
  const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
  const value = 'abcdef0123456789'.repeat(4);
  render(<CopyValue label="report hash" value={value} />);
  expect(screen.getByText(value)).toBeVisible();
  await user.tab();
  expect(screen.getByRole('button', { name: 'Copy report hash' })).toHaveFocus();
  await user.keyboard('{Enter}');
  expect(write).toHaveBeenCalledExactlyOnceWith(value);
  expect(await screen.findByText('Copied')).toBeVisible();
});

it('keeps identities selectable when clipboard access is rejected', async () => {
  userEvent.setup();
  vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'));
  render(<CopyValue label="identity" value="full-identity" />);
  fireEvent.click(screen.getByRole('button', { name: 'Copy identity' }));
  expect(await screen.findByText('Copy unavailable; select the value')).toBeVisible();
  expect(screen.getByText('full-identity')).toBeVisible();
});

it('does not offer a copy action for an absent identity', () => {
  render(<CopyValue label="missing identity" value={null} />);
  expect(screen.getByLabelText('Unavailable')).toHaveTextContent('—');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

it('preserves full timestamp and explicit timezone offset', () => {
  const timestamp = '2026-10-09T17:01:02.123456+07:00';
  render(<Timestamp value={timestamp} />);
  expect(screen.getByText(timestamp)).toHaveAttribute('datetime', timestamp);
});

it('does not manufacture a timestamp when absent', () => {
  render(<Timestamp value={null} />);
  expect(screen.getByLabelText('Unavailable')).toHaveTextContent('—');
});

it('retains measured zero, precision, currency and undefined rate independently', () => {
  render(
    <Metrics
      currency="USD"
      metrics={{ total_trades: 0, net_profit: '0.00', equity_drawdown_pct: '0.00', win_rate: null }}
    />,
  );
  expect(screen.getByText('total trades').parentElement).toHaveTextContent('0');
  expect(screen.getByText('net profit').parentElement).toHaveTextContent('0.00USD');
  expect(screen.getByText('equity drawdown pct').parentElement).toHaveTextContent('0.00%');
  expect(screen.getByText('win rate').parentElement).toHaveTextContent(
    '—Undefined / not applicable',
  );
});
