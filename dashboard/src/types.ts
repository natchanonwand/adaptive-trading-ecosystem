export const viewNames = [
  'account',
  'portfolio',
  'positions',
  'trades',
  'risk',
  'system',
  'activity',
] as const;
export type ViewName = (typeof viewNames)[number];
export type Values = Record<string, unknown>;
export interface Row {
  sequence: number;
  event_id: string;
  occurred_at: string;
  values: Values;
}
export interface Page {
  items: Row[];
  next_cursor: number | null;
  has_more?: boolean;
  read_only: true;
}
export interface Scope {
  environment: string;
  account_id: string | null;
  run_id: string | null;
}
export interface Stream {
  stream_id: string;
  scope: Scope;
  cursor: number;
}
export interface Streams {
  items: Stream[];
  next_cursor: string | null;
  read_only: true;
}
export interface Telemetry {
  sequence: number;
  event: {
    event_id: string;
    event_type: string;
    occurred_at: string;
    recorded_at: string;
    scope: Scope;
    payload: Values;
    source: string;
    symbol: string | null;
    strategy_id: string | null;
  };
}
export interface Snapshot {
  stream_id: string;
  scope: Scope | null;
  cursor: number;
  views: Record<ViewName, Page | null>;
  events: Telemetry[];
  errors: Record<string, string>;
  read_only: true;
}
export interface Day extends Values {
  date: string;
  trade_count: number | null;
  net_pnl: string | null;
  gross_pnl: string | null;
  net_r: string | null;
  commission: string | null;
  spread_cost: string | null;
  max_intraday_drawdown: string | null;
  wins: number | null;
  losses: number | null;
  coverage: string;
}
export interface Calendar {
  days: Day[];
  partial: boolean;
  read_only: true;
  reason?: string;
}
export type Connection = 'CONNECTED' | 'STALE' | 'DISCONNECTED' | 'CONNECTING';
export const eventTypes = [
  'ACCOUNT_SNAPSHOT',
  'PORTFOLIO_SNAPSHOT',
  'POSITION_OPENED',
  'POSITION_UPDATED',
  'POSITION_CLOSED',
  'ORDER_INTENT_CREATED',
  'ORDER_INTENT_REJECTED',
  'RISK_APPROVED',
  'RISK_REJECTED',
  'RISK_STATE_CHANGED',
  'BROKER_CONNECTED',
  'BROKER_DISCONNECTED',
  'BROKER_STALE',
  'RECONCILIATION_STARTED',
  'RECONCILIATION_OK',
  'RECONCILIATION_MISMATCH',
  'STRATEGY_STARTED',
  'STRATEGY_STOPPED',
  'STRATEGY_SIGNAL',
  'EA_STARTED',
  'EA_STOPPED',
  'EA_HEALTH',
  'EXECUTION_INCIDENT',
  'SYSTEM_STARTED',
  'SYSTEM_STOPPED',
  'SYSTEM_HEALTH',
] as const;
