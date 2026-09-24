import { useCallback, useState } from 'react';
import {
  AccountSummary,
  AssetCards,
  Badge,
  Calendar,
  Empty,
  EquityChart,
  ErrorNotice,
  EventFeed,
  Panel,
  PortfolioTable,
  RiskPanel,
  SystemHealth,
} from './components';
import type { Client } from './client';
import { ObserverPage } from './ObserverPage';
import { FeaturePage } from './FeaturePage';
import { ResearchPage } from './ResearchPage';
import * as f from './format';
import { useDashboard, useResource } from './hooks';
import type { Row, Values } from './types';

const pages = [
  'Overview',
  'Portfolio',
  'Trades',
  'Risk',
  'Systems',
  'Research',
  'EA Observer',
  'Feature Data',
] as const;
type PageName = (typeof pages)[number];
const descriptions: Record<PageName, string> = {
  Overview: 'Your ecosystem, at a glance. Every number traces back to an observation.',
  Portfolio: 'Open exposure across assets, strategies and external EAs.',
  Trades: 'Reported trade history and a UTC calendar of observed outcomes.',
  Risk: 'Authoritative policy, current state and the reasons behind it.',
  Systems: 'Component health, observation age and connection visibility.',
  Research: 'Offline behavioral measurements, sample sufficiency and evidence.',
  'EA Observer': 'External EA sessions, broker observations and attribution confidence.',
  'Feature Data': 'Versioned offline features, outcome separation and data quality.',
};
const icons = ['▦', '▥', '⇄', '◇', '▣', '⌕', '◉', '▤'];
function values(value: unknown): Values {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Values) : {};
}

function PositionPage({
  client,
  stream,
  revision,
}: {
  client: Client;
  stream: string;
  revision: number;
}) {
  const [after, setAfter] = useState(0);
  const load = useCallback(() => {
    void revision;
    return client.collection('positions', stream, { after });
  }, [client, stream, after, revision]);
  const data = useResource(load, !!stream);
  return (
    <Panel title="Open positions" note="50 rows per page · sort/filter applies to this page">
      <ErrorNotice message={data.error} />
      {data.loading ? (
        <Empty>Loading positions…</Empty>
      ) : (
        <PortfolioTable rows={data.data?.items ?? []} />
      )}
      <Pager after={after} next={data.data?.next_cursor ?? null} set={setAfter} />
    </Panel>
  );
}
function Pager({
  after,
  next,
  set,
}: {
  after: number;
  next: number | null;
  set: (v: number) => void;
}) {
  return (
    <div className="pager">
      <button onClick={() => set(0)} disabled={!after}>
        First page
      </button>
      <span className="muted small">Cursor {after} · bounded query</span>
      <button onClick={() => next !== null && set(next)} disabled={next === null}>
        Next page →
      </button>
    </div>
  );
}
function TradesTable({ rows }: { rows: Row[] }) {
  return !rows.length ? (
    <Empty>No matching completed trade observations.</Empty>
  ) : (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {[
              'Timestamp UTC',
              'Symbol',
              'Strategy / EA',
              'Side',
              'Entry',
              'Exit',
              'Quantity',
              'Net P/L',
              'Net R',
              'Commission',
              'Source',
              'Environment',
            ].map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.event_id}>
              <td>{f.timestamp(r.values.closed_at)}</td>
              <td>
                <b>{f.label(r.values.symbol)}</b>
              </td>
              <td
                className="identifier"
                title={f.label(r.values.strategy_id ?? r.values.source_instance_id)}
              >
                {f.label(r.values.strategy_id ?? r.values.source_instance_id)}
                <small>
                  Magic {f.count(r.values.magic_number)} · Ticket {f.label(r.values.broker_ticket)}
                </small>
              </td>
              <td>
                <Badge value={r.values.side} />
              </td>
              <td>{f.price(r.values.average_entry)}</td>
              <td>{f.unavailable}</td>
              <td>{f.unavailable}</td>
              <td className={f.tone(r.values.net_pnl)}>{f.money(r.values.net_pnl)}</td>
              <td>{f.multiple(r.values.net_r)}</td>
              <td>{f.money(r.values.commission)}</td>
              <td>{f.source(r.values.source)}</td>
              <td>
                <Badge value={r.values.environment} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function TradesPage({
  client,
  stream,
  revision,
}: {
  client: Client;
  stream: string;
  revision: number;
}) {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [filterError, setFilterError] = useState<string | null>(null);
  const [after, setAfter] = useState(0);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const load = useCallback(() => {
    void revision;
    return client.collection('trades', stream, { after, ...filters });
  }, [client, stream, after, filters, revision]);
  const daily = useCallback(() => {
    void revision;
    return client.calendar(stream, month);
  }, [client, stream, month, revision]);
  const trades = useResource(load, !!stream),
    calendar = useResource(daily, !!stream);
  return (
    <>
      <Panel title="Daily P/L calendar" note="UTC · reported trade summaries">
        <ErrorNotice message={calendar.error} />
        {calendar.loading ? (
          <Empty>Loading calendar…</Empty>
        ) : (
          <Calendar data={calendar.data} month={month} onMonth={setMonth} />
        )}
      </Panel>
      <Panel title="Trade history" note="50 rows per page">
        <form
          className="toolbar filters"
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            const parsed = Object.fromEntries([...data.entries()].map(([k, v]) => [k, String(v)]));
            if (
              !!parsed.start !== !!parsed.end ||
              (parsed.start && parsed.end && parsed.end <= parsed.start)
            ) {
              setFilterError('Choose both UTC dates; Before must be later than From.');
              return;
            }
            setFilterError(null);
            setAfter(0);
            setFilters(parsed);
          }}
        >
          <label>
            From · UTC
            <input type="date" name="start" />
          </label>
          <label>
            Before · UTC
            <input type="date" name="end" />
          </label>
          <label>
            Symbol
            <input name="symbol" placeholder="All symbols" />
          </label>
          <label>
            Strategy ID
            <input name="strategy_id" placeholder="All strategies" />
          </label>
          <label>
            Environment
            <select name="environment">
              <option value="">Current stream</option>
              {['BACKTEST', 'PAPER_FORWARD', 'DEMO', 'LIVE'].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit">
            Apply filters
          </button>
        </form>
        <p className="muted small">
          Date filters require both bounds. Exit fill price and total traded quantity are
          unavailable in the current telemetry contract.
        </p>
        <ErrorNotice message={filterError ?? trades.error} />
        {trades.loading ? (
          <Empty>Loading trades…</Empty>
        ) : (
          <TradesTable rows={trades.data?.items ?? []} />
        )}
        <Pager after={after} next={trades.data?.next_cursor ?? null} set={setAfter} />
      </Panel>
    </>
  );
}

export default function App({ client }: { client: Client }) {
  const [page, setPage] = useState<PageName>('Overview');
  const state = useDashboard(client);
  const revision = state.snapshot?.cursor ?? 0;
  const loadHistory = useCallback(() => {
    void revision;
    return client.collection('history', state.stream);
  }, [client, state.stream, revision]);
  const history = useResource(loadHistory, page === 'Overview' && !!state.stream);
  const portfolio = state.snapshot?.views.portfolio?.items[0]?.values ?? {};
  const account = state.snapshot?.views.account?.items[0]?.values ?? values(portfolio.account);
  const risk = state.snapshot?.views.risk?.items[0]?.values ?? {};
  const positionPage = state.snapshot?.views.positions;
  const positions = positionPage?.items ?? [];
  const health = state.snapshot?.views.system?.items ?? [];
  const catalogScope = state.catalog?.items.find((s) => s.stream_id === state.stream)?.scope;
  const environment = state.snapshot?.scope?.environment ?? catalogScope?.environment;
  const riskState = risk.risk_state ?? portfolio.risk_state;
  return (
    <div className="app">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <aside className="sidebar">
        <a className="brand" href="./" aria-label="Adaptive Trading Ecosystem home">
          <span className="pixel-logo" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>
            ADAPTIVE<small>TRADING ECOSYSTEM</small>
          </span>
        </a>
        <div className="workspace-label">
          MISSION CONTROL <span>3.6</span>
        </div>
        <nav aria-label="Main navigation">
          {pages.map((name, i) => (
            <button
              key={name}
              className={page === name ? 'active' : ''}
              aria-current={page === name ? 'page' : undefined}
              title={name}
              onClick={() => setPage(name)}
            >
              <span aria-hidden="true">{icons[i]}</span>
              {name}
              {page === name && <i aria-hidden="true">▪</i>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="read-only">
            <span aria-hidden="true">▣</span> READ ONLY
          </div>
          <p>
            Observe. Understand.
            <br />
            Keep authority in the core.
          </p>
          <a href={client.mock ? './' : '?mock=1'}>
            {client.mock ? 'Return to real telemetry →' : 'Open labeled mock preview →'}
          </a>
          <span className="small muted">LOCAL INSTANCE / 127.0.0.1</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="global-header">
          <div className="header-context">
            <span className="eyebrow">LOCAL MONITORING</span>
            <span className="header-title">ADAPTIVE TRADING ECOSYSTEM</span>
          </div>
          {page === 'Feature Data' || page === 'Research' ? (
            <div className="global-status">
              <Badge value="OFFLINE DATASET" />
            </div>
          ) : (
            <div className="global-status">
              <div>
                <span className="eyebrow">Environment</span>
                <Badge value={environment ?? 'UNKNOWN'} live={environment === 'LIVE'} />
              </div>
              <div>
                <span className="eyebrow">Connection</span>
                <Badge value={state.connection} />
              </div>
              <div>
                <span className="eyebrow">Risk state</span>
                <Badge value={riskState} />
              </div>
              <div className="last-update">
                <span className="eyebrow">Last telemetry</span>
                <time>
                  {state.updated === null
                    ? f.unavailable
                    : `${Math.max(0, Math.floor((state.now - state.updated) / 1000))}s ago`}
                </time>
                <small>
                  {state.updated === null
                    ? f.unavailable
                    : f.timestamp(new Date(state.updated).toISOString())}
                </small>
              </div>
            </div>
          )}
        </header>
        {client.mock && (
          <div className="mock-banner" role="status">
            ◆ MOCK DATA — synthetic preview · no broker or account connection
          </div>
        )}
        {environment === 'LIVE' && (
          <div className="live-banner">■ LIVE OBSERVATIONS · READ ONLY · No trading controls</div>
        )}
        <main id="main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                OBSERVABILITY <span>/ {page.toUpperCase()}</span>
              </div>
              <h1>{page}</h1>
              <p className="muted">{descriptions[page]}</p>
            </div>
            {page !== 'Feature Data' && page !== 'Research' && (
              <button onClick={state.refresh} className="refresh">
                ↻ Refresh observations
              </button>
            )}
          </div>
          {page !== 'Feature Data' && page !== 'Research' && (
            <>
              <div className="stream-bar">
                <label>
                  Observation stream
                  <select value={state.stream} onChange={(e) => state.setStream(e.target.value)}>
                    <option value="">Select a stream</option>
                    {state.catalog?.items.map((s) => (
                      <option key={s.stream_id} value={s.stream_id}>
                        {s.scope.environment} · Account {s.scope.account_id ?? 'System'} ·{' '}
                        {s.stream_id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </label>
                <span className="muted small">
                  UTC timestamps · USD amounts · read-only telemetry
                </span>
                {state.catalog?.next_cursor && (
                  <button onClick={() => void state.moreStreams()}>More streams</button>
                )}
              </div>
              <ErrorNotice message={state.error} />
              {state.connection === 'STALE' && !client.mock && (
                <p className="notice warning" role="status">
                  ▲ STALE — the latest telemetry timestamp is over 30 seconds old. Displayed
                  observations may be old.
                </p>
              )}
              {!!Object.keys(state.snapshot?.errors ?? {}).length && (
                <p className="notice warning" role="alert">
                  Partial data: {Object.keys(state.snapshot?.errors ?? {}).join(', ')} unavailable.
                  Other sections remain usable.
                </p>
              )}
              {!state.stream && (
                <Panel title="Connect your local telemetry">
                  <Empty>
                    {state.error
                      ? 'Start the local read-only API and refresh. No mock fallback is used.'
                      : 'No stream selected. Choose an existing observation stream or use the explicitly labeled mock preview.'}
                  </Empty>
                </Panel>
              )}
            </>
          )}
          {page === 'Overview' && (
            <>
              <p className="muted small">
                Account observation:{' '}
                {f.timestamp(
                  state.snapshot?.views.account?.items[0]?.occurred_at ??
                    state.snapshot?.views.portfolio?.items[0]?.occurred_at,
                )}{' '}
                ·{' '}
                {account.stale === true
                  ? 'SOURCE REPORTS STALE'
                  : account.complete === false
                    ? 'PARTIAL SOURCE VALUES'
                    : 'Reported source values'}
              </p>
              <AccountSummary account={account} portfolio={portfolio} />
              <div className="overview-grid">
                <Panel
                  title="Account trajectory"
                  note={
                    <>
                      <span className="signal-dot" /> Reported snapshots
                    </>
                  }
                >
                  <ErrorNotice message={history.error} />
                  <EquityChart rows={history.data?.items ?? []} />
                </Panel>
                <Panel title="Risk watch" note="Authoritative state">
                  <Badge value={riskState} />
                  <dl className="compact-details risk-watch">
                    <dt>Policy</dt>
                    <dd>{f.label(risk.policy_id)}</dd>
                    <dt>Risk / trade</dt>
                    <dd>{f.percent(risk.risk_per_trade)}</dd>
                    <dt>Portfolio limit</dt>
                    <dd>{f.percent(risk.portfolio_risk_limit)}</dd>
                    <dt>Daily loss limit</dt>
                    <dd>{f.percent(risk.daily_loss_limit)}</dd>
                    <dt>Max DD limit</dt>
                    <dd>{f.percent(risk.drawdown_limit)}</dd>
                  </dl>
                  <button className="text-button" onClick={() => setPage('Risk')}>
                    Inspect risk state →
                  </button>
                  <p className="muted small">
                    Observation only. Authority stays with the Risk Engine.
                  </p>
                </Panel>
              </div>
              <Panel title="Asset radar" note="Default watchlist + all observed symbols">
                <AssetCards rows={positions} complete={!!positionPage && !positionPage.has_more} />
              </Panel>
              <Panel title="Recent activity" note="Last 50 events maximum">
                <EventFeed events={state.events} />
              </Panel>
            </>
          )}
          {page === 'Portfolio' && (
            <PositionPage
              key={state.stream}
              client={client}
              stream={state.stream}
              revision={revision}
            />
          )}
          {page === 'Trades' && (
            <TradesPage
              key={state.stream}
              client={client}
              stream={state.stream}
              revision={revision}
            />
          )}
          {page === 'Risk' && (
            <Panel title="Risk control room" note="Read-only policy observations">
              <RiskPanel risk={risk} portfolio={portfolio} />
            </Panel>
          )}
          {page === 'Systems' && (
            <>
              <Panel title="System health" note="Unknown is never treated as healthy">
                <SystemHealth rows={health} connection={state.connection} />
              </Panel>
              <Panel title="Event feed">
                <EventFeed events={state.events} />
              </Panel>
            </>
          )}
          {page === 'Research' && <ResearchPage mock={client.mock} />}
          {page === 'EA Observer' && <ObserverPage mock={client.mock} />}
          {page === 'Feature Data' && <FeaturePage mock={client.mock} />}
          <footer>
            <span>ADAPTIVE / TELEMETRY CONSOLE</span>
            <span>Read-only · Local-first · Phase 3.6</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
