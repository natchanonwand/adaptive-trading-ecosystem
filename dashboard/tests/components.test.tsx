import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '../src/App';
import { mockClient } from '../src/client';
import {
  AccountSummary,
  AssetCards,
  Badge,
  Calendar,
  EquityChart,
  EventFeed,
  PortfolioTable,
  RiskPanel,
  SystemHealth,
} from '../src/components';
import { mockCalendar, mockHistory, mockSnapshot } from '../src/mock';

describe('read-only dashboard components', () => {
  it('shows authoritative summary values and unavailable metrics', () => {
    render(
      <AccountSummary
        account={mockSnapshot.views.account!.items[0]!.values}
        portfolio={mockSnapshot.views.portfolio!.items[0]!.values}
      />,
    );
    expect(screen.getByText('$128,450.00')).toBeInTheDocument();
    expect(screen.getByText('Peak drawdown').parentElement).toHaveTextContent('—');
  });
  it.each(['ACTIVE', 'PAUSE_ENTRIES', 'HALT_AND_FLATTEN'])(
    'renders risk state %s as text, not color alone',
    (risk_state) => {
      render(<RiskPanel risk={{ risk_state }} portfolio={{}} />);
      expect(screen.getByText(risk_state.replaceAll('_', ' '))).toBeInTheDocument();
    },
  );
  it.each(['BACKTEST', 'PAPER_FORWARD', 'DEMO', 'LIVE'])(
    'renders environment %s explicitly',
    (environment) => {
      render(<Badge value={environment} live={environment === 'LIVE'} />);
      expect(screen.getByText(environment.replaceAll('_', ' '))).toBeInTheDocument();
      if (environment === 'LIVE') expect(screen.getByText('LIVE')).toHaveClass('live');
    },
  );
  it('filters positions without financial recalculation', () => {
    render(<PortfolioTable rows={mockSnapshot.views.positions!.items} />);
    fireEvent.change(screen.getByPlaceholderText('Symbol, strategy, EA or side'), {
      target: { value: 'XAU' },
    });
    expect(screen.getByText('XAUUSD')).toBeInTheDocument();
    expect(screen.queryByText('BTCUSD')).not.toBeInTheDocument();
  });
  it('supports unknown assets and does not claim flat when data is incomplete', () => {
    const rows = [
      {
        ...mockSnapshot.views.positions!.items[0]!,
        values: { ...mockSnapshot.views.positions!.items[0]!.values, symbol: 'FUTURE_ASSET' },
      },
    ];
    render(<AssetCards rows={rows} complete={false} />);
    expect(screen.getByText('FUTURE_ASSET')).toBeInTheDocument();
    expect(screen.queryByText('FLAT')).not.toBeInTheDocument();
  });
  it('renders all required health components and unknown states', () => {
    render(<SystemHealth rows={[]} connection="DISCONNECTED" />);
    expect(screen.getByText('market data')).toBeInTheDocument();
    expect(screen.getAllByText('UNKNOWN')).toHaveLength(8);
  });
  it('summarizes events, retaining optional debug detail', () => {
    render(<EventFeed events={mockSnapshot.events} />);
    expect(screen.getByText('position opened')).toBeInTheDocument();
    expect(screen.getAllByText('Event details')).toHaveLength(3);
  });
  it('shows calendar nulls and opens accessible day detail', () => {
    render(<Calendar data={mockCalendar('2026-09')} month="2026-09" onMonth={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /^2026-09-01:/ }));
    expect(screen.getByRole('region', { name: 'Daily trade details' })).toHaveTextContent(
      'Unknown values and unobserved days are not zero',
    );
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
  it('supports chart keyboard inspection and disconnected null samples', () => {
    render(<EquityChart rows={mockHistory.items} />);
    fireEvent.change(screen.getByRole('slider'), { target: { value: '11' } });
    expect(screen.getByText('Equity', { selector: '.chart-tooltip span' })).toHaveTextContent('—');
    expect(screen.getByRole('img')).toBeInTheDocument();
  });
  it('renders chart no-data state', () => {
    render(<EquityChart rows={[]} />);
    expect(screen.getByText(/never fabricates/)).toBeInTheDocument();
  });
  it('requires explicit mock mode and provides every navigation page without trading controls', async () => {
    render(<App client={mockClient} />);
    expect(await screen.findByText('$128,450.00', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText(/MOCK DATA/)).toBeInTheDocument();
    const nav = screen.getByRole('navigation');
    expect(
      within(nav)
        .getAllByRole('button')
        .map((button) => button.title),
    ).toEqual(['Overview', 'Portfolio', 'Trades', 'Risk', 'Systems', 'Research', 'EA Observer']);
    fireEvent.click(within(nav).getByText('Risk'));
    expect(screen.getByText('Risk control room')).toBeInTheDocument();
    for (const name of ['Buy', 'Sell', 'Close position', 'Reset halt', 'Enable live'])
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    fireEvent.click(within(nav).getByText('EA Observer'));
    expect(screen.getByText(/No external EA observations/)).toBeInTheDocument();
    for (const name of ['Buy', 'Sell', 'Close position', 'Reset halt', 'Enable live'])
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
  });
});
