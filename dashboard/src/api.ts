import {
  viewNames,
  type Calendar,
  type Day,
  type Page,
  type Row,
  type Scope,
  type Snapshot,
  type Streams,
  type Telemetry,
  type Values,
} from './types';

export function object(value: unknown): Values {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Invalid response');
  return value as Values;
}
export function string(value: unknown): string {
  if (typeof value !== 'string') throw new Error('Invalid response');
  return value;
}
function nullableString(value: unknown): string | null {
  return value === null ? null : string(value);
}
export function integer(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0)
    throw new Error('Invalid response');
  return value;
}
function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error('Invalid response');
  return value;
}
function time(value: unknown): string {
  const result = string(value);
  if (!Number.isFinite(Date.parse(result)) || !/(Z|\+00:00)$/.test(result))
    throw new Error('Invalid UTC response');
  return result;
}
function scope(value: unknown): Scope {
  const s = object(value);
  const environment = string(s.environment);
  if (!['BACKTEST', 'PAPER_FORWARD', 'DEMO', 'LIVE'].includes(environment))
    throw new Error('Invalid environment');
  return {
    environment,
    account_id: nullableString(s.account_id),
    run_id: nullableString(s.run_id),
  };
}
function readonly(value: Values) {
  if (value.read_only !== true) throw new Error('Read-only contract required');
}
const moneyFields = [
  'balance',
  'equity',
  'realized_pnl',
  'unrealized_pnl',
  'used_margin',
  'free_margin',
  'daily_pnl',
  'drawdown',
  'open_risk',
  'net_pnl',
  'gross_pnl',
  'net_r',
  'commission',
  'spread_cost',
  'risk_per_trade',
  'portfolio_risk_limit',
  'daily_loss_limit',
  'drawdown_limit',
];
function values(value: unknown): Values {
  const result = object(value);
  for (const key of moneyFields)
    if (
      key in result &&
      result[key] !== null &&
      (typeof result[key] !== 'string' ||
        !/^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(String(result[key])))
    )
      throw new Error('Invalid financial value');
  if (result.account !== undefined) values(result.account);
  return result;
}
function row(value: unknown): Row {
  const r = object(value);
  return {
    sequence: integer(r.sequence),
    event_id: string(r.event_id),
    occurred_at: time(r.occurred_at),
    values: values(r.values),
  };
}
export function page(value: unknown): Page {
  const p = object(value);
  readonly(p);
  return {
    items: array(p.items).map(row),
    next_cursor: p.next_cursor === null ? null : integer(p.next_cursor),
    has_more: p.has_more === true,
    read_only: true,
  };
}
export function telemetry(value: unknown): Telemetry {
  const t = object(value),
    e = object(t.event);
  return {
    sequence: integer(t.sequence),
    event: {
      event_id: string(e.event_id),
      event_type: string(e.event_type),
      occurred_at: time(e.occurred_at),
      recorded_at: time(e.recorded_at),
      scope: scope(e.scope),
      payload: values(e.payload),
      source: string(e.source),
      symbol: nullableString(e.symbol),
      strategy_id: nullableString(e.strategy_id),
    },
  };
}
export function snapshot(value: unknown): Snapshot {
  const s = object(value);
  readonly(s);
  const raw = object(s.views),
    views = {} as Snapshot['views'],
    errors: Record<string, string> = {};
  for (const name of viewNames) {
    try {
      views[name] = raw[name] === null ? null : page(raw[name]);
    } catch {
      views[name] = null;
      errors[name] = 'Invalid response';
    }
  }
  for (const [key, error] of Object.entries(object(s.errors))) errors[key] = string(error);
  return {
    stream_id: string(s.stream_id),
    scope: s.scope === null ? null : scope(s.scope),
    cursor: integer(s.cursor),
    views,
    errors,
    events: array(s.events).map(telemetry),
    read_only: true,
  };
}
export function streams(value: unknown): Streams {
  const s = object(value);
  readonly(s);
  return {
    items: array(s.items).map((v) => {
      const r = object(v);
      return { stream_id: string(r.stream_id), scope: scope(r.scope), cursor: integer(r.cursor) };
    }),
    next_cursor: nullableString(s.next_cursor),
    read_only: true,
  };
}
export function calendar(value: unknown): Calendar {
  const c = object(value);
  readonly(c);
  if (typeof c.partial !== 'boolean') throw new Error('Invalid response');
  return {
    days: array(c.days).map((v): Day => {
      const d = values(v);
      return {
        ...d,
        date: string(d.date),
        coverage: string(d.coverage),
        trade_count: d.trade_count === null ? null : integer(d.trade_count),
        net_pnl: nullableString(d.net_pnl),
        gross_pnl: nullableString(d.gross_pnl),
        net_r: nullableString(d.net_r),
        commission: nullableString(d.commission),
        spread_cost: nullableString(d.spread_cost),
        max_intraday_drawdown: nullableString(d.max_intraday_drawdown),
        wins: d.wins === null ? null : integer(d.wins),
        losses: d.losses === null ? null : integer(d.losses),
      };
    }),
    partial: c.partial,
    reason: typeof c.reason === 'string' ? c.reason : undefined,
    read_only: true,
  };
}
export async function request<T>(
  path: string,
  parse: (value: unknown) => T,
  timeout = 8000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      method: 'GET',
      signal: controller.signal,
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`Backend unavailable (${response.status})`);
    let value: unknown;
    try {
      value = await response.json();
    } catch {
      throw new Error('Invalid response');
    }
    return parse(value);
  } catch (error) {
    if (controller.signal.aborted) throw new Error('API timeout', { cause: error });
    if (error instanceof TypeError) throw new Error('Backend unavailable', { cause: error });
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
export function url(
  route: string,
  params: Record<string, string | number | undefined> = {},
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value));
  }
  return `/api/v1/dashboard/${route}?${query}`;
}
