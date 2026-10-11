import { useState } from 'react';
import type { BaselineRun, Publication } from './BaselinePanel';
import {
  Button,
  DataTable,
  MetricCard,
  MetricStrip,
  MonoValue,
  RetroPanel,
  StatusBadge,
} from './retro';

export function CopyValue({ label, value }: { label: string; value: string | null }) {
  const [feedback, setFeedback] = useState('');
  return (
    <span className="rt-copy-value">
      <MonoValue value={value} />
      {value !== null && (
        <Button
          type="button"
          variant="ghost"
          aria-label={`Copy ${label}`}
          onClick={() => {
            void Promise.resolve()
              .then(() => navigator.clipboard.writeText(value))
              .then(
                () => setFeedback('Copied'),
                () => setFeedback('Copy unavailable; select the value'),
              );
          }}
        >
          Copy
        </Button>
      )}
      <span className="rt-help" role="status">
        {feedback}
      </span>
    </span>
  );
}

export function Timestamp({ value }: { value: string | null }) {
  return value ? (
    <time className="rt-mono" dateTime={value}>
      {value}
    </time>
  ) : (
    <MonoValue value={null} />
  );
}

function ShortIdentity({ value }: { value: string | null }) {
  return value ? (
    <code className="rt-mono" title={value} aria-label={value}>
      {value.slice(0, 8)}…{value.slice(-4)}
    </code>
  ) : (
    <MonoValue value={null} />
  );
}

export function RunTable({
  runs,
  selected,
  publication,
  disabled,
  onSelect,
}: {
  runs: BaselineRun[];
  selected: BaselineRun | null;
  publication: Publication | null;
  disabled: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <DataTable
      caption="Baseline run register"
      columns={[
        'Run / candidate',
        'Configuration',
        'Execution outcome',
        'Strategy / environment',
        'Started / ended',
        'Result / publication',
      ]}
    >
      {runs.map((saved) => {
        const r =
          selected?.config.baseline_run_id === saved.config.baseline_run_id ? selected : saved;
        const p = r === selected ? publication : null;
        return (
          <tr key={r.config.baseline_run_id} aria-selected={r === selected}>
            <td>
              <Button
                disabled={disabled}
                onClick={() => onSelect(r.config.baseline_run_id)}
                aria-label={`Inspect run ${r.config.baseline_run_id}`}
              >
                <ShortIdentity value={r.config.baseline_run_id} />
              </Button>
              <br />
              <ShortIdentity value={r.candidate_id} />
            </td>
            <td>
              <ShortIdentity value={r.config.configuration_id ?? null} />
              <br />
              {r.config.symbol} · {r.config.timeframe}
            </td>
            <td>
              <StatusBadge status={r.status} />
            </td>
            <td>
              {p?.execution_strategy ?? 'Not exposed in run record'}
              <br />
              <StatusBadge status={r.config.environment} />
            </td>
            <td>
              <Timestamp value={r.started_at} />
              <br />
              <Timestamp value={r.completed_at} />
            </td>
            <td>
              {r.result_identity ? 'Normalized result recorded' : 'No normalized result recorded'}
              <br />
              {p
                ? 'Derived publication available'
                : r === selected
                  ? 'No derived publication'
                  : 'Inspect to check publication'}
            </td>
          </tr>
        );
      })}
    </DataTable>
  );
}

export function Facts({ values }: { values: Record<string, string | number | null | undefined> }) {
  return (
    <dl className="wb-facts">
      {Object.entries(values).map(([label, value]) => (
        <div key={label}>
          <dt>{label.replaceAll('_', ' ')}</dt>
          <dd>
            <MonoValue value={value ?? null} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function RunHeader({
  run,
  publication,
  elapsed,
}: {
  run: BaselineRun;
  publication: Publication | null;
  elapsed: number;
}) {
  return (
    <>
      <RetroPanel title="Run identity" status={run.status}>
        <CopyValue label="run identity" value={run.config.baseline_run_id} />
        <Facts
          values={{
            candidate: run.candidate_id,
            environment: run.config.environment,
            execution_strategy: publication?.execution_strategy ?? 'Not exposed in run record',
          }}
        />
        <p className="rt-help">
          Execution-time outcome is retained. Later assessments are shown separately below.
        </p>
      </RetroPanel>
      <RetroPanel title="Execution">
        <dl className="wb-facts">
          <div>
            <dt>Started (full timestamp)</dt>
            <dd>
              <Timestamp value={run.started_at} />
            </dd>
          </div>
          <div>
            <dt>Ended (full timestamp)</dt>
            <dd>
              <Timestamp value={run.completed_at} />
            </dd>
          </div>
        </dl>
        <Facts
          values={{
            elapsed: run.started_at ? `${elapsed}s` : null,
            native_exit_code: run.exit_code,
            terminal_build: run.terminal_build,
            observed_tester_status: run.observed_tester_status,
            diagnostic: run.diagnostic,
          }}
        />
      </RetroPanel>
    </>
  );
}

export function Metrics({
  metrics,
  currency,
}: {
  metrics: Record<string, string | number | null>;
  currency: string;
}) {
  const primary = [
    'total_trades',
    'net_profit',
    'balance_drawdown',
    'equity_drawdown',
    'balance_drawdown_pct',
    'equity_drawdown_pct',
    'win_rate',
  ];
  const additional = Object.entries(metrics).filter(([key]) => !primary.includes(key));
  return (
    <>
      <MetricStrip>
        {primary
          .filter((key) => key in metrics)
          .map((key) => (
            <MetricCard
              key={key}
              label={key.replaceAll('_', ' ')}
              value={metrics[key] ?? null}
              note={
                metrics[key] === null
                  ? 'Undefined / not applicable'
                  : key === 'net_profit'
                    ? currency
                    : key.endsWith('_pct')
                      ? '%'
                      : undefined
              }
            />
          ))}
      </MetricStrip>
      {additional.length > 0 && (
        <DataTable caption="Additional reported metrics" columns={['Metric', 'Value']}>
          {additional.map(([key, value]) => (
            <tr key={key}>
              <th scope="row">{key.replaceAll('_', ' ')}</th>
              <td
                className="rt-numeric"
                aria-label={value === null ? 'Undefined / not applicable' : undefined}
              >
                {value ?? '—'}
              </td>
            </tr>
          ))}
        </DataTable>
      )}
    </>
  );
}

export function PublicationPanel({
  run,
  publication: p,
}: {
  run: BaselineRun;
  publication: Publication;
}) {
  return (
    <RetroPanel title="Reconciled publication" status={p.state ?? 'PUBLISHED'}>
      <h4>Published result — post-run reconciliation</h4>
      <div className="rt-assessments">
        <section aria-label="Immutable execution outcome">
          <h4>Execution-time outcome</h4>
          <StatusBadge status={run.status} />
          <p>Execution outcome (unchanged): {run.status}</p>
        </section>
        <section aria-label="Later reconciliation">
          <h4>Later evidence assessment</h4>
          <StatusBadge status={p.reconciliation_status} />
          <p>Reconciliation: {p.reconciliation_status}</p>
        </section>
        <section aria-label="Derived publication">
          <h4>Derived publication</h4>
          <StatusBadge status={p.state ?? 'PUBLISHED'} />
          <p>{p.provenance ?? 'POST_RUN_RECONCILIATION'}</p>
          <p>Publication: PUBLISHED · {p.id}</p>
        </section>
      </div>
      <Metrics metrics={p.metrics} currency={run.config.currency} />
      <p>Zero trades is a valid observation; undefined rates remain unavailable.</p>
      <EvidenceLineage run={run} publication={p} />
    </RetroPanel>
  );
}

export function EvidenceLineage({
  run,
  publication: p,
}: {
  run: BaselineRun;
  publication: Publication | null;
}) {
  const rows: [string, string, string | null, string][] = [
    [
      'Authorization',
      'Authorization event',
      run.authorization_event_id ?? null,
      'Recorded declaration event; not inferred permission',
    ],
    ['Artifact', 'Candidate', run.candidate_id, 'Persisted run candidate'],
    ['Artifact', 'Artifact SHA-256', run.ea_sha256, 'Persisted run artifact'],
    [
      'Configuration',
      'Configuration identity',
      p?.configuration_identity ?? null,
      'Immutable execution configuration',
    ],
    [
      'Execution plan',
      'Execution plan identity',
      p?.execution_plan_identity ?? null,
      p?.execution_strategy ?? 'Not exposed in run record',
    ],
    [
      'Native evidence',
      'BaselineRun',
      run.config.baseline_run_id,
      `Immutable execution outcome: ${run.status}`,
    ],
    ['Native evidence', 'Manifest identity', run.evidence_identity, 'Execution evidence manifest'],
  ];
  if (p)
    rows.push(
      [
        'Native evidence',
        'Native source identity (manifest provenance only)',
        p.native_source_identity,
        'Original native encoding bytes were not retained.',
      ],
      [
        'Native evidence',
        'Verified stored UTF-8 report',
        p.stored_utf8_report_identity,
        'Verified parser source bytes',
      ],
      [
        'Reconciliation',
        'Reconciliation identity',
        p.reconciliation_identity,
        p.reconciliation_status,
      ],
      [
        'Publication',
        'Publication identity',
        p.identity,
        p.provenance ?? 'POST_RUN_RECONCILIATION',
      ],
    );
  return (
    <DataTable
      caption="Evidence provenance"
      columns={['Category', 'Identity', 'Source / qualification']}
    >
      {rows.map(([category, label, identity, source]) => (
        <tr key={label}>
          <th scope="row">{category}</th>
          <td>
            <span className="rt-label">{label}</span>
            <CopyValue label={label} value={identity} />
          </td>
          <td>
            {source}
            {identity === null && <p>Not exposed by this record.</p>}
          </td>
        </tr>
      ))}
    </DataTable>
  );
}
