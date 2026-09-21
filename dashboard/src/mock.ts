/** Explicit synthetic preview only. Never selected after a real API failure. */
import { calendar, page, snapshot, streams } from './api';
import type { Values } from './types';
export const MOCK_STREAM = '00000000-0000-0000-0000-000000003600';
const scope = {
  environment: 'DEMO',
  account_id: '00000000-0000-0000-0000-000000000036',
  run_id: null,
};
const at = new Date().toISOString();
const meta = {
  environment: 'DEMO',
  source: 'EXTERNAL_EA',
  source_instance_id: 'ea-observer-07',
  strategy_id: null,
  magic_number: 7401,
  broker_ticket: 'DEMO-1824',
  comment: 'Synthetic preview',
};
const account = {
  kind: 'ACCOUNT',
  balance: '128450.00',
  equity: '129284.75',
  realized_pnl: '8450',
  unrealized_pnl: '834.75',
  used_margin: '2400',
  free_margin: '126884.75',
  complete: true,
  stale: false,
};
function row(sequence: number, values: Values, time = at) {
  return {
    sequence,
    event_id: `mock-${sequence}`,
    occurred_at: time,
    values: { ...meta, ...values },
  };
}
const positions = [
  row(4, {
    kind: 'POSITION',
    episode_id: 'preview-btc',
    symbol: 'BTCUSD',
    side: 'LONG',
    quantity: '0.15',
    average_entry: '62410.50',
    mark_price: '62875.25',
    stop_loss: '61200',
    take_profit: null,
    unrealized_pnl: '697.12',
    realized_pnl: null,
    opened_at: at,
    updated_at: at,
    state: 'OPEN',
  }),
  row(5, {
    kind: 'POSITION',
    episode_id: 'preview-xau',
    symbol: 'XAUUSD',
    side: 'SHORT',
    quantity: '0.10',
    average_entry: '2684.50',
    mark_price: '2670.73',
    stop_loss: '2698',
    take_profit: '2655',
    unrealized_pnl: '137.63',
    realized_pnl: null,
    opened_at: at,
    updated_at: at,
    state: 'OPEN',
  }),
];
const tradeRows = [
  row(6, {
    ...positions[0]?.values,
    kind: 'POSITION',
    symbol: 'BTCUSD',
    side: 'LONG',
    quantity: '0',
    state: 'CLOSED',
    closed_at: at,
    net_pnl: '326.80',
    gross_pnl: '331.80',
    net_r: '1.24',
    commission: '5',
    financing: '0',
    spread_cost: null,
    outcome: 'WIN',
    complete: false,
  }),
];
const makePage = (items: ReturnType<typeof row>[]) => ({
  items,
  next_cursor: null,
  read_only: true,
});
export const mockSnapshot = snapshot({
  stream_id: MOCK_STREAM,
  scope,
  cursor: 9,
  read_only: true,
  errors: {},
  views: {
    account: makePage([row(7, account)]),
    portfolio: makePage([
      row(8, {
        kind: 'PORTFOLIO',
        account,
        daily_pnl: '1158.65',
        drawdown: '0.0124',
        peak_nav: '1.31',
        peak_equity: null,
        open_risk: '421.50',
        reserved_risk: '0',
        open_positions: 2,
        reserved_positions: 0,
        risk_state: 'ACTIVE',
      }),
    ]),
    positions: makePage(positions),
    trades: makePage(tradeRows),
    risk: makePage([
      row(9, {
        kind: 'RISK',
        risk_state: 'ACTIVE',
        policy_id: 'V0_CONSERVATIVE',
        risk_per_trade: '0.0025',
        open_risk: '421.50',
        portfolio_risk_limit: '0.0075',
        daily_loss: '0',
        daily_loss_limit: '0.02',
        drawdown: '0.0124',
        drawdown_limit: '0.10',
        last_rejection_reason: ['INSUFFICIENT_REMAINING_RISK'],
        last_state_change: at,
      }),
    ]),
    system: makePage(
      [
        'database',
        'broker',
        'market_data',
        'portfolio',
        'risk_engine',
        'strategy',
        'ea',
        'reconciliation',
      ].map((component, i) =>
        row(i + 10, {
          kind: 'HEALTH',
          component,
          state: component === 'market_data' ? 'STALE' : 'HEALTHY',
          detail:
            component === 'market_data'
              ? 'Synthetic quote age exceeds observation threshold'
              : 'Synthetic health observation',
        }),
      ),
    ),
    activity: makePage([
      row(20, {
        kind: 'ACTIVITY',
        status: 'EA_STARTED',
        trades: 14,
        pnl: '1284.75',
        net_r: '3.82',
        drawdown: null,
      }),
    ]),
  },
  events: ['RISK_APPROVED', 'POSITION_OPENED', 'BROKER_CONNECTED'].map((event_type, i) => ({
    sequence: i + 7,
    event: {
      event_id: `preview-event-${i}`,
      event_type,
      occurred_at: at,
      recorded_at: at,
      scope,
      payload: { kind: 'ACTIVITY', status: 'SYNTHETIC_PREVIEW' },
      source: 'EXTERNAL_EA',
      symbol: i === 1 ? 'BTCUSD' : null,
      strategy_id: null,
    },
  })),
});
export const mockStreams = streams({
  items: [{ stream_id: MOCK_STREAM, scope, cursor: 9 }],
  next_cursor: null,
  read_only: true,
});
export const mockHistory = page(
  makePage(
    Array.from({ length: 24 }, (_, i) =>
      row(
        i + 1,
        {
          ...account,
          balance: i === 23 ? account.balance : String(127800 + i * 28),
          equity:
            i === 23
              ? account.equity
              : i === 11
                ? null
                : String(127800 + i * 57 + [20, -70, 45][i % 3]!),
        },
        new Date(Date.parse(at) - (23 - i) * 60_000).toISOString(),
      ),
    ),
  ),
);
export function mockCalendar(month: string) {
  const [year, mon] = month.split('-').map(Number);
  const count = new Date(Date.UTC(year!, mon!, 0)).getUTCDate();
  return calendar({
    read_only: true,
    partial: false,
    days: Array.from({ length: count }, (_, i) => ({
      date: `${month}-${String(i + 1).padStart(2, '0')}`,
      trade_count: i % 5 ? 3 : null,
      net_pnl: i % 5 ? String([326.8, -148.2, 214.5, 87.25][i % 4]) : null,
      gross_pnl: null,
      net_r: i % 5 ? '1.24' : null,
      commission: i % 5 ? '5.00' : null,
      spread_cost: null,
      max_intraday_drawdown: null,
      wins: i % 5 ? 2 : null,
      losses: i % 5 ? 1 : null,
      coverage: i % 5 ? 'OBSERVED_TRADES_ONLY' : 'NO_OBSERVATIONS',
    })),
  });
}
export const mockTrades = page(makePage(tradeRows));
