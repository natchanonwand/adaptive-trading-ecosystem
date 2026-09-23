import { useEffect, useState } from 'react';
import { object, request } from './api';
import { Badge, Empty, ErrorNotice, Panel } from './components';
import * as f from './format';
import type { Values } from './types';

type ObserverData = { sessions: Values[]; selected: Values | null };
function records(value: unknown): Values[] {
  if (!Array.isArray(value)) throw new Error('Invalid observer records');
  return value.map(object);
}
export function parseObserver(value: unknown): ObserverData {
  const data = object(value);
  const sessions = records(data.sessions);
  for (const row of sessions) {
    const session = object(row.session);
    if (typeof session.session_id !== 'string' || session.environment !== 'DEMO')
      throw new Error('Invalid DEMO session');
  }
  const selected = data.selected === null ? null : object(data.selected);
  if (selected) {
    if (selected.read_only !== true) throw new Error('Read-only observer required');
    records(selected.positions);
    records(selected.activity);
    object(selected.summary);
    object(selected.session);
  }
  return { sessions, selected };
}
export async function loadObserver(session: string): Promise<ObserverData> {
  const query = session ? `?session_id=${encodeURIComponent(session)}` : '';
  return request(`/api/v1/observer${query}`, parseObserver);
}

export function ObserverPage({ mock = false }: { mock?: boolean }) {
  const [session, setSession] = useState('');
  const [data, setData] = useState<ObserverData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (mock) return;
    let active = true;
    let busy = false;
    const refresh = async () => {
      if (busy) return;
      busy = true;
      try {
        const next = await loadObserver(session);
        if (active) {
          setData(next);
          setError(null);
        }
      } catch {
        if (active) setError('Observer unavailable. Existing values may be stale.');
      } finally {
        busy = false;
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [session, mock]);
  const selected = data?.selected;
  const summary = selected ? object(selected.summary) : {};
  const info = selected ? object(selected.session) : {};
  const config = info.config ? object(info.config) : {};
  const candidates = config.candidates ? records(config.candidates) : [];
  const positions = selected ? records(selected.positions) : [];
  const activity = selected ? records(selected.activity) : [];
  return (
    <>
      <Panel title="EA OBSERVER" note="External observations · DEMO · read only">
        <p className="notice">
          Attribution follows recorded evidence. Unknown sources are excluded from EA-specific
          metrics.
        </p>
        {mock ? (
          <Empty>No external EA observations are represented by the general dashboard mock.</Empty>
        ) : (
          <>
            <ErrorNotice message={error} />
            <label>
              Observation session{' '}
              <select
                value={session}
                onChange={(e) => {
                  setSession(e.target.value);
                  setData(null);
                }}
              >
                <option value="">Select a session</option>
                {data?.sessions.map((row) => {
                  const item = object(row.session);
                  return (
                    <option key={String(item.session_id)} value={String(item.session_id)}>
                      {String(item.session_id)} · {String(row.status)}
                    </option>
                  );
                })}
              </select>
            </label>
            {!data?.sessions.length && <Empty>No observation sessions available.</Empty>}
          </>
        )}
      </Panel>
      {selected && (
        <>
          <Panel title="Session status" note="No execution controls">
            <Badge value={selected.status} />
            <dl className="compact-details">
              <dt>Broker / server scope</dt>
              <dd>
                {f.label(info.broker)} / {f.label(info.server_scope)}
              </dd>
              <dt>Candidates</dt>
              <dd>
                {candidates.map((c) => f.label(c.display_name)).join(', ') ||
                  'UNKNOWN / not registered'}
              </dd>
              <dt>Magic numbers</dt>
              <dd>
                {candidates
                  .map((c) =>
                    Array.isArray(c.magic_numbers) ? c.magic_numbers.join(', ') : 'Unknown',
                  )
                  .join(' · ') || 'Unknown'}
              </dd>
              <dt>Symbols</dt>
              <dd>{Array.isArray(config.symbols) ? config.symbols.join(', ') : 'Unknown'}</dd>
              <dt>Observed positions</dt>
              <dd>{positions.length}</dd>
              <dt>Observed deals</dt>
              <dd>{f.count(selected.observed_deals)}</dd>
              <dt>Completed EA episodes</dt>
              <dd>{f.count(summary.completed_episodes)}</dd>
              <dt>Excluded episodes</dt>
              <dd>{f.count(summary.excluded_episodes)}</dd>
              <dt>Last observation</dt>
              <dd>{f.timestamp(object(selected.heartbeat).at)}</dd>
              <dt>Source confidence</dt>
              <dd>
                {[...new Set(activity.map((e) => f.label(object(e.attribution).confidence)))].join(
                  ', ',
                ) || '—'}
              </dd>
              <dt>Last action</dt>
              <dd>{f.label(activity.at(-1)?.kind)}</dd>
              <dt>Last activity</dt>
              <dd>{f.timestamp(activity.at(-1)?.observed_at)}</dd>
              <dt>Gross observed P/L</dt>
              <dd>{f.money(summary.gross_pnl)}</dd>
              <dt>Commission</dt>
              <dd>{f.money(summary.commission)}</dd>
              <dt>Fee</dt>
              <dd>{f.money(summary.fee)}</dd>
              <dt>Swap</dt>
              <dd>{f.money(summary.swap)}</dd>
            </dl>
            {selected.metrics_complete !== true && (
              <p className="notice">
                Metrics cover a bounded subset. Export the session for full replay.
              </p>
            )}
          </Panel>
          <Panel
            title="Current observed exposure"
            note="Broker quantities; no inferred risk percentage"
          >
            {!positions.length ? (
              <Empty>No open positions observed.</Empty>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      {['Symbol', 'Position', 'Side', 'Lots', 'Entry', 'SL', 'TP', 'Magic'].map(
                        (h) => (
                          <th key={h}>{h}</th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => (
                      <tr key={String(p.identifier ?? p.ticket)}>
                        <td>{f.label(p.symbol)}</td>
                        <td>{f.label(String(p.identifier ?? p.ticket))}</td>
                        <td>{p.type === 0 ? 'BUY' : p.type === 1 ? 'SELL' : 'UNKNOWN'}</td>
                        <td>{f.quantity(p.volume)}</td>
                        <td>{f.price(p.price_open)}</td>
                        <td>{f.price(p.sl)}</td>
                        <td>{f.price(p.tp)}</td>
                        <td>{String(p.magic ?? 'Unknown')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <Panel
            title="External observer activity"
            note="Last 50 observations · separate from internal intents"
          >
            {!activity.length ? (
              <Empty>No behavior events observed.</Empty>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      {[
                        'First observed UTC',
                        'Action',
                        'Symbol',
                        'Source confidence',
                        'Quality',
                      ].map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {activity
                      .slice()
                      .reverse()
                      .map((e) => (
                        <tr key={String(e.event_id)}>
                          <td>{f.timestamp(e.observed_at)}</td>
                          <td>
                            <Badge value={e.kind} />
                          </td>
                          <td>{f.label(e.symbol)}</td>
                          <td>{f.label(object(e.attribution).confidence)}</td>
                          <td>
                            {f.label(e.quality)}
                            {e.recovered_state === true ? ' · RECOVERED STATE' : ''}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  );
}
