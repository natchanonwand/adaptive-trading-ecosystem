import { useState, type ReactNode } from 'react';
import * as f from './format';
import type { Calendar as CalendarData, Row, Telemetry, Values } from './types';

export function Badge({ value, live = false }: { value: unknown; live?: boolean }) {
  const text = f.label(value);
  const variant = ['HALT_AND_FLATTEN', 'ERROR', 'DISCONNECTED', 'LIVE'].includes(text)
    ? 'danger'
    : ['STALE', 'DEGRADED', 'PAUSE_ENTRIES'].includes(text)
      ? 'warning'
      : ['ACTIVE', 'HEALTHY', 'CONNECTED'].includes(text)
        ? 'good'
        : 'neutral';
  return (
    <span className={`badge ${variant} ${live ? 'live' : ''}`}>
      <span aria-hidden="true">
        {variant === 'danger' ? '■' : variant === 'warning' ? '▲' : '◆'}
      </span>{' '}
      {text.replaceAll('_', ' ')}
    </span>
  );
}
export function Panel({
  title,
  note,
  children,
  className = '',
}: {
  title: string;
  note?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <h2>{title}</h2>
        {note && <span className="muted small">{note}</span>}
      </div>
      {children}
    </section>
  );
}
export function Empty({ children = 'No observations available.' }: { children?: ReactNode }) {
  return (
    <div className="empty">
      <span aria-hidden="true">▤</span>
      <p>{children}</p>
    </div>
  );
}
export function ErrorNotice({ message }: { message: string | null }) {
  return message ? (
    <p className="notice error" role="alert">
      ! {message}
    </p>
  ) : null;
}
export function Metric({
  title,
  value,
  note,
  accent = false,
  tone = '',
}: {
  title: string;
  value: string;
  note?: string;
  accent?: boolean;
  tone?: string;
}) {
  return (
    <div className={`metric ${accent ? 'accent' : ''}`}>
      <span className="eyebrow">{title}</span>
      <strong className={tone}>{value}</strong>
      <span className="muted small">
        {note ?? (value === f.unavailable ? 'Unavailable from source' : 'Reported observation')}
      </span>
    </div>
  );
}
export function AccountSummary({ account, portfolio }: { account: Values; portfolio: Values }) {
  return (
    <div className="metrics">
      <Metric title="Balance" value={f.money(account.balance)} accent note="Account cash · USD" />
      <Metric title="Equity" value={f.money(account.equity)} note="Marked account value · USD" />
      <Metric
        title="Today P/L"
        value={f.money(portfolio.daily_pnl)}
        tone={f.tone(portfolio.daily_pnl)}
        note="Authoritative UTC risk day"
      />
      <Metric
        title="Floating P/L"
        value={f.money(account.unrealized_pnl)}
        tone={f.tone(account.unrealized_pnl)}
      />
      <Metric title="Realized P/L" value={f.money(account.realized_pnl)} />
      <Metric title="Current drawdown" value={f.percent(portfolio.drawdown)} />
      <Metric title="Peak drawdown" value={f.unavailable} />
      <Metric title="Open risk" value={f.money(portfolio.open_risk)} note="Reported risk · USD" />
      <Metric title="Open positions" value={f.count(portfolio.open_positions)} />
      <Metric title="Free margin" value={f.money(account.free_margin)} />
      <Metric title="Used margin" value={f.money(account.used_margin)} />
    </div>
  );
}
export function EquityChart({ rows }: { rows: Row[] }) {
  const [selected, select] = useState<number | null>(null);
  if (!rows.length)
    return <Empty>No account snapshot history. The chart never fabricates a curve.</Empty>;
  const numbers = rows
    .flatMap((r) => [r.values.balance, r.values.equity])
    .filter((v): v is string => typeof v === 'string')
    .map(Number)
    .filter(Number.isFinite);
  if (!numbers.length) return <Empty>Balance and equity are unavailable.</Empty>;
  const low = Math.min(...numbers),
    high = Math.max(...numbers),
    span = high - low || 1;
  const first = Date.parse(rows[0]!.occurred_at),
    last = Date.parse(rows[rows.length - 1]!.occurred_at);
  const x = (r: Row) => 45 + ((Date.parse(r.occurred_at) - first) / (last - first || 1)) * 855;
  const y = (v: number) => 180 - ((v - low) / span) * 145;
  const path = (key: string) => {
    let pen = false,
      previous = 0;
    return rows
      .map((r) => {
        const raw = r.values[key],
          time = Date.parse(r.occurred_at);
        if (raw === null || raw === undefined || !Number.isFinite(Number(raw))) {
          pen = false;
          return '';
        }
        const next = `${pen && time - previous <= 300_000 ? 'L' : 'M'}${x(r)},${y(Number(raw))}`;
        pen = true;
        previous = time;
        return next;
      })
      .join(' ');
  };
  const current = rows[Math.min(selected ?? rows.length - 1, rows.length - 1)]!;
  return (
    <div className="chart">
      <div className="chart-legend">
        <span className="line-key equity">Equity</span>
        <span className="line-key balance">Balance</span>
        <span className="muted">Last {rows.length} samples · UTC</span>
      </div>
      <svg
        viewBox="0 0 930 225"
        role="img"
        aria-label="Reported balance and equity over time, with missing samples and gaps left disconnected"
      >
        {[35, 83, 131, 180].map((line) => (
          <line key={line} x1="45" x2="900" y1={line} y2={line} className="gridline" />
        ))}
        <path d={path('balance')} className="balance-path" />
        <path d={path('equity')} className="equity-path" />
        <line x1={x(current)} x2={x(current)} y1="25" y2="185" className="crosshair" />
        {rows.map(
          (r, i) =>
            typeof r.values.equity === 'string' && (
              <circle
                key={r.sequence}
                cx={x(r)}
                cy={y(Number(r.values.equity))}
                r="3"
                className="chart-dot"
                onMouseEnter={() => select(i)}
              >
                <title>
                  {f.timestamp(r.occurred_at)} · Equity {f.money(r.values.equity)}
                </title>
              </circle>
            ),
        )}
        <text x="45" y="213">
          {new Date(first).toISOString().slice(11, 16)}
        </text>
        <text x="855" y="213">
          {new Date(last).toISOString().slice(11, 16)}
        </text>
      </svg>
      <label className="chart-scrubber">
        Inspect snapshot
        <input
          type="range"
          min="0"
          max={rows.length - 1}
          value={selected ?? rows.length - 1}
          onChange={(e) => select(Number(e.target.value))}
        />
      </label>
      <div className="chart-tooltip" aria-live="polite">
        <span>{f.timestamp(current.occurred_at)}</span>
        <span>
          Balance <b>{f.money(current.values.balance)}</b>
        </span>
        <span>
          Equity <b>{f.money(current.values.equity)}</b>
        </span>
      </div>
      <p className="muted small">
        Missing values and intervals over 5 minutes break the line. Observed samples only.
      </p>
    </div>
  );
}
export function AssetCards({ rows, complete }: { rows: Row[]; complete: boolean }) {
  const symbols = [
    ...new Set(['BTCUSD', 'XAUUSD', 'USTEC100', ...rows.map((r) => f.label(r.values.symbol))]),
  ];
  return (
    <div className="asset-grid">
      {symbols.map((symbol) => {
        const positions = rows.filter(
          (r) => r.values.symbol === symbol && r.values.state === 'OPEN',
        );
        return (
          <article className="asset" key={symbol}>
            <div className="asset-title">
              <h3>{symbol}</h3>
              <Badge value={positions.length ? 'OPEN' : complete ? 'FLAT' : 'UNKNOWN'} />
            </div>
            {!positions.length ? (
              <p className="muted small">
                {complete ? 'No open position observed' : 'Position data unavailable or incomplete'}
              </p>
            ) : (
              positions.map((r) => (
                <div key={r.event_id}>
                  <div className="asset-pnl">
                    <Badge value={r.values.side} />
                    <strong className={f.tone(r.values.unrealized_pnl)}>
                      {f.money(r.values.unrealized_pnl)}
                    </strong>
                  </div>
                  <dl className="compact-details">
                    <dt>Quantity</dt>
                    <dd>{f.quantity(r.values.quantity)}</dd>
                    <dt>Entry / Mark</dt>
                    <dd>
                      {f.price(r.values.average_entry)} / {f.price(r.values.mark_price)}
                    </dd>
                    <dt>SL / TP</dt>
                    <dd>
                      {f.price(r.values.stop_loss)} / {f.price(r.values.take_profit)}
                    </dd>
                    <dt>Strategy / EA</dt>
                    <dd>{f.label(r.values.strategy_id ?? r.values.source_instance_id)}</dd>
                    <dt>Updated</dt>
                    <dd>{f.timestamp(r.values.updated_at)}</dd>
                  </dl>
                </div>
              ))
            )}
          </article>
        );
      })}
    </div>
  );
}
export function PortfolioTable({ rows }: { rows: Row[] }) {
  const [filter, setFilter] = useState(''),
    [sort, setSort] = useState('symbol');
  const filtered = rows
    .filter((r) =>
      JSON.stringify([
        r.values.symbol,
        r.values.strategy_id,
        r.values.source_instance_id,
        r.values.side,
      ])
        .toLowerCase()
        .includes(filter.toLowerCase()),
    )
    .sort((a, b) =>
      sort === 'updated_at'
        ? Date.parse(f.label(a.values.updated_at)) - Date.parse(f.label(b.values.updated_at))
        : f.label(a.values[sort]).localeCompare(f.label(b.values[sort])),
    );
  return (
    <>
      <div className="toolbar">
        <label>
          Filter loaded positions
          <input
            placeholder="Symbol, strategy, EA or side"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
        <label>
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="symbol">Symbol</option>
            <option value="side">Side</option>
            <option value="updated_at">Updated at</option>
          </select>
        </label>
      </div>
      {!filtered.length ? (
        <Empty>No matching open positions.</Empty>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {[
                  'Symbol',
                  'Strategy / EA',
                  'Side',
                  'Quantity',
                  'Entry',
                  'Mark',
                  'SL',
                  'TP',
                  'Floating P/L',
                  'Realized P/L',
                  'Risk',
                  'Opened UTC',
                  'Updated UTC',
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.event_id}>
                  <td>
                    <b>{f.label(r.values.symbol)}</b>
                  </td>
                  <td
                    title={f.label(r.values.strategy_id ?? r.values.source_instance_id)}
                    className="identifier"
                  >
                    {f.label(r.values.strategy_id ?? r.values.source_instance_id)}
                    <small>{f.source(r.values.source)}</small>
                  </td>
                  <td>
                    <Badge value={r.values.side} />
                  </td>
                  <td>{f.quantity(r.values.quantity)}</td>
                  <td>{f.price(r.values.average_entry)}</td>
                  <td>{f.price(r.values.mark_price)}</td>
                  <td>{f.price(r.values.stop_loss)}</td>
                  <td>{f.price(r.values.take_profit)}</td>
                  <td className={f.tone(r.values.unrealized_pnl)}>
                    {f.money(r.values.unrealized_pnl)}
                  </td>
                  <td>{f.money(r.values.realized_pnl)}</td>
                  <td>{f.unavailable}</td>
                  <td>{f.timestamp(r.values.opened_at)}</td>
                  <td>{f.timestamp(r.values.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
export function RiskPanel({ risk, portfolio }: { risk: Values; portfolio: Values }) {
  return (
    <>
      <div className="risk-state">
        <div>
          <span className="eyebrow">Authoritative risk state</span>
          <h3>{f.label(risk.policy_id)}</h3>
        </div>
        <Badge value={risk.risk_state} />
      </div>
      <div className="metrics risk-metrics">
        <Metric title="Risk / Trade" value={f.percent(risk.risk_per_trade)} />
        <Metric title="Open risk · USD" value={f.money(risk.open_risk)} />
        <Metric title="Portfolio risk limit" value={f.percent(risk.portfolio_risk_limit)} />
        <Metric title="Daily P/L" value={f.money(portfolio.daily_pnl)} />
        <Metric title="Daily loss limit" value={f.percent(risk.daily_loss_limit)} />
        <Metric title="Current drawdown" value={f.percent(risk.drawdown)} />
        <Metric title="Max DD limit" value={f.percent(risk.drawdown_limit)} />
        <Metric title="Open positions" value={f.count(portfolio.open_positions)} />
        <Metric title="Max positions" value={f.unavailable} />
      </div>
      <dl className="risk-notes">
        <dt>Last rejection</dt>
        <dd>
          {Array.isArray(risk.last_rejection_reason) && risk.last_rejection_reason.length
            ? risk.last_rejection_reason.map(f.label).join(' · ')
            : f.unavailable}
        </dd>
        <dt>Last state change</dt>
        <dd>{f.timestamp(risk.last_state_change)}</dd>
      </dl>
      <p className="muted small">
        Limits are displayed as percentages. Open risk is a USD amount. Monitoring cannot change
        risk state.
      </p>
    </>
  );
}
export function SystemHealth({ rows, connection }: { rows: Row[]; connection: string }) {
  const expected = [
    'database',
    'broker',
    'market_data',
    'portfolio',
    'risk_engine',
    'strategy',
    'ea',
    'reconciliation',
  ];
  return (
    <div className="health-grid">
      {[...new Set([...expected, ...rows.map((r) => f.label(r.values.component))])].flatMap(
        (component) => {
          const found = rows.filter((r) => r.values.component === component);
          return (found.length ? found : [null]).map((row, index) => (
            <article className="health-card" key={`${component}-${index}`}>
              <div>
                <h3>{component.replaceAll('_', ' ')}</h3>
                <Badge value={row?.values.state ?? 'UNKNOWN'} />
              </div>
              <p className="muted small">{f.label(row?.values.detail)}</p>
              <span className="small">Last observation: {f.timestamp(row?.occurred_at)}</span>
              <small className="muted identifier">{f.label(row?.values.source_instance_id)}</small>
            </article>
          ));
        },
      )}
      <article className="health-card">
        <div>
          <h3>Monitoring UI</h3>
          <Badge value={connection} />
        </div>
        <p className="muted small">Local transport status; does not alter domain health.</p>
      </article>
    </div>
  );
}
export function EventFeed({ events }: { events: Telemetry[] }) {
  return !events.length ? (
    <Empty>No recent events for this stream.</Empty>
  ) : (
    <ol className="event-feed">
      {[...events].reverse().map((record) => (
        <li key={record.sequence}>
          <span
            className={`event-marker ${record.event.event_type.includes('REJECT') || record.event.event_type.includes('DISCONNECT') ? 'warning' : ''}`}
            aria-hidden="true"
          >
            ◆
          </span>
          <div>
            <b>{record.event.event_type.replaceAll('_', ' ').toLowerCase()}</b>
            <span className="muted small">
              {record.event.symbol ?? 'System'} · {f.source(record.event.source)} · #
              {record.sequence}
            </span>
            <details>
              <summary>Event details</summary>
              <pre>{JSON.stringify(record, null, 2)}</pre>
            </details>
          </div>
          <time className="small" dateTime={record.event.occurred_at}>
            {f.timestamp(record.event.occurred_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
export function Calendar({
  data,
  month,
  onMonth,
}: {
  data: CalendarData | null;
  month: string;
  onMonth: (month: string) => void;
}) {
  const [selected, select] = useState<string | null>(null);
  const day = data?.days.find((d) => d.date === selected);
  const offset = (new Date(`${month}-01T00:00:00Z`).getUTCDay() + 6) % 7;
  return (
    <>
      <div className="toolbar">
        <label>
          Month · UTC
          <input
            type="month"
            value={month}
            onChange={(e) => {
              if (e.target.value) {
                select(null);
                onMonth(e.target.value);
              }
            }}
          />
        </label>
        <span className="muted small">Reported closed-trade P/L · not account daily P/L</span>
      </div>
      {data?.partial && <ErrorNotice message={data.reason ?? 'Calendar data incomplete'} />}
      {!data?.days.length ? (
        <Empty>No calendar observations available.</Empty>
      ) : (
        <div className="calendar-grid">
          <div className="calendar-weekdays">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
              <span key={d}>{d}</span>
            ))}
          </div>
          <div className="calendar-days">
            {Array.from({ length: offset }, (_, i) => (
              <span key={`blank-${i}`} aria-hidden="true" />
            ))}
            {data.days.map((d) => (
              <button
                key={d.date}
                className={`calendar-day ${f.tone(d.net_pnl)} ${selected === d.date ? 'selected' : ''}`}
                onClick={() => select(d.date)}
                aria-label={`${d.date}: ${f.money(d.net_pnl)}, ${f.count(d.trade_count)} trades`}
              >
                <span>{Number(d.date.slice(-2))}</span>
                <strong>{f.money(d.net_pnl)}</strong>
                <small>
                  {d.trade_count === null ? 'No observations' : `${f.count(d.trade_count)} trades`}
                </small>
              </button>
            ))}
          </div>
        </div>
      )}
      {day && (
        <section className="day-detail" aria-label="Daily trade details">
          <h3>{day.date} · UTC</h3>
          <div className="metrics">
            <Metric title="Net P/L" value={f.money(day.net_pnl)} />
            <Metric title="Gross P/L" value={f.money(day.gross_pnl)} />
            <Metric title="Net R" value={f.multiple(day.net_r)} />
            <Metric title="Wins / Losses" value={`${f.count(day.wins)} / ${f.count(day.losses)}`} />
            <Metric title="Commission" value={f.money(day.commission)} />
            <Metric title="Spread cost" value={f.money(day.spread_cost)} />
            <Metric title="Max intraday DD" value={f.percent(day.max_intraday_drawdown)} />
          </div>
          <p className="muted small">
            {day.coverage.replaceAll('_', ' ')}. Unknown values and unobserved days are not zero.
          </p>
        </section>
      )}
    </>
  );
}
