import { useEffect, useState } from 'react';
import { type Detail } from './api';

type Config = {
  baseline_run_id: string;
  project_id: string;
  symbol: string;
  timeframe: string;
  from_date: string;
  to_date: string;
  initial_deposit: string;
  leverage: number;
  currency: 'USD';
  tester_model: 'EVERY_TICK_BASED_ON_REAL_TICKS';
  environment: 'DEMO_RESEARCH_TESTER';
  timeout_seconds: number;
  input_provenance: 'TESTER_DEFAULTS' | 'USER_SET';
  set_text: string | null;
};
export type BaselineRun = {
  config: Config;
  candidate_id: string;
  artifact_id: string;
  ea_sha256: string;
  input_sha256: string | null;
  status: string;
  diagnostic: string;
  started_at: string | null;
  completed_at: string | null;
  terminal_build: string;
  observed_tester_status: string;
  declared_license_status: string;
  declared_tester_access: string;
  evidence_identity: string | null;
  result_identity: string | null;
};
type Result = {
  metrics: Record<string, string | number | null>;
  metadata: Record<string, string>;
  report_identity: string;
  result_identity: string;
};
const active = ['QUEUED', 'PREPARING', 'RUNNING', 'PARSING'];
const messages: Record<string, string> = {
  BLOCKED_SYMBOL:
    'The configured symbol is unavailable in this tester environment. Check the explicit broker binding and cached history.',
  BLOCKED_TESTER_ACCESS:
    'The EA did not permit Strategy Tester execution. No license bypass was attempted.',
  BLOCKED_LICENSE:
    'Authorized tester use could not be established. Check the license with the vendor.',
  BLOCKED_ARTIFACT_IDENTITY_MISMATCH:
    'The registered EA is missing or its bytes changed. Register the authorized artifact in a new project.',
  BLOCKED_REAL_TICKS_UNAVAILABLE:
    'Real ticks were unavailable or could not be verified. The model was not downgraded.',
  INITIALIZATION_FAILED:
    'The isolated tester could not initialize. Ask the operator to check the pinned terminal and cache configuration.',
  TESTER_FAILED:
    'The tester failed or its previous owner was interrupted. Review retained diagnostics; this run will not retry.',
  TIMEOUT: 'The tester exceeded its bounded timeout. Its owned process tree was stopped.',
  REPORT_MISSING: 'The tester did not generate a report. Review the retained diagnostics.',
  REPORT_PARSE_FAILED:
    'The report could not be normalized or did not match the requested configuration. Review retained evidence.',
  CANCELLED: 'This run was cancelled. Partial diagnostics are not a baseline result.',
};
async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/workbench-api/baselines' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers:
      body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Workbench-Request': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok)
    throw new Error(
      response.status === 409
        ? 'Another baseline is active. Wait for it to finish before explicitly starting this run.'
        : response.status === 503
          ? 'Baseline storage is unavailable. Ask the operator to check migrations and the local service.'
          : 'Baseline request rejected. Check dates (1–366 days), positive deposit, leverage (1–2000), timeout (30–3600 seconds), inputs and project readiness.',
    );
  return response.json() as Promise<T>;
}

export function BaselinePanel({ detail }: { detail: Detail }) {
  const [form, setForm] = useState<Config>(() => ({
    baseline_run_id: crypto.randomUUID(),
    project_id: detail.project.project_id,
    symbol: detail.project.broker_binding.broker_symbol,
    timeframe: detail.project.broker_binding.timeframe,
    from_date: '',
    to_date: '',
    initial_deposit: '10000',
    currency: 'USD',
    leverage: 100,
    environment: 'DEMO_RESEARCH_TESTER',
    tester_model: 'EVERY_TICK_BASED_ON_REAL_TICKS',
    timeout_seconds: 600,
    input_provenance: 'TESTER_DEFAULTS',
    set_text: null,
  }));
  const [runs, setRuns] = useState<BaselineRun[]>([]);
  const [run, setRun] = useState<BaselineRun | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [confirmed, setConfirmed] = useState(false);
  const running = !!run && active.includes(run.status);
  useEffect(() => {
    let mounted = true;
    call<{ items: BaselineRun[] }>('?project_id=' + detail.project.project_id)
      .then((v) => {
        if (mounted) setRuns(v.items);
      })
      .catch((e: Error) => {
        if (mounted) setError(e.message);
      });
    return () => {
      mounted = false;
    };
  }, [detail.project.project_id]);
  useEffect(() => {
    if (!running || !run) return;
    let mounted = true;
    const timer = setInterval(() => {
      setNow(Date.now());
      call<{ run: BaselineRun; result: Result | null }>('/' + run.config.baseline_run_id)
        .then((v) => {
          if (mounted) {
            setRun(v.run);
            setResult(v.result);
          }
        })
        .catch((e: Error) => {
          if (mounted) setError(e.message);
        });
    }, 1000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, [running, run]);
  async function action(task: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const elapsed = run?.started_at
    ? Math.max(
        0,
        Math.floor(
          ((run.completed_at ? Date.parse(run.completed_at) : now) - Date.parse(run.started_at)) /
            1000,
        ),
      )
    : 0;
  return (
    <>
      <p>
        Strategy Tester research only · {detail.project.broker_binding.broker_name} · {form.symbol}{' '}
        · {form.timeframe}
      </p>
      <p>
        Candidate: {detail.candidate.product_name} · {detail.project.candidate_id}
      </p>
      <p>
        Declared license: {detail.candidate.license_status} · Declared tester access:{' '}
        {detail.candidate.tester_access_status}
      </p>
      {(detail.candidate.license_status === 'UNKNOWN' ||
        detail.candidate.tester_access_status === 'UNKNOWN') && (
        <p className="muted">
          UNKNOWN means not yet verified. Readiness does not establish license or tester permission;
          execution evidence is recorded separately.
        </p>
      )}
      <p className="small">
        Artifact SHA-256: <code>{detail.candidate.artifact_sha256 || 'UNAVAILABLE'}</code>
      </p>
      {runs.length > 0 && (
        <label>
          Saved baseline runs
          <select
            aria-label="Saved baseline runs"
            value={run?.config.baseline_run_id || ''}
            disabled={busy || running}
            onChange={(e) => {
              const id = e.target.value;
              if (id)
                void action(async () => {
                  const v = await call<{ run: BaselineRun; result: Result | null }>('/' + id);
                  setRun(v.run);
                  setResult(v.result);
                  setConfirmed(false);
                });
            }}
          >
            <option value="">Select a run</option>
            {runs.map((r) => (
              <option key={r.config.baseline_run_id} value={r.config.baseline_run_id}>
                {r.config.baseline_run_id} · {r.status}
              </option>
            ))}
          </select>
        </label>
      )}
      {!run && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action(async () => {
              const saved = await call<BaselineRun>('', form);
              setRun(saved);
              setRuns((old) => [saved, ...old]);
              setConfirmed(false);
            });
          }}
        >
          <p>Every tick based on real ticks · USD · one explicit input configuration</p>
          <div className="wb-form">
            <label>
              From date
              <input
                type="date"
                required
                value={form.from_date}
                onChange={(e) => setForm({ ...form, from_date: e.target.value })}
              />
            </label>
            <label>
              To date (exclusive)
              <input
                type="date"
                required
                value={form.to_date}
                onChange={(e) => setForm({ ...form, to_date: e.target.value })}
              />
            </label>
            <label>
              Initial deposit
              <input
                type="number"
                min="0.01"
                max="100000000"
                step="0.01"
                required
                value={form.initial_deposit}
                onChange={(e) => setForm({ ...form, initial_deposit: e.target.value })}
              />
            </label>
            <label>
              Leverage (1:N)
              <input
                type="number"
                min="1"
                max="2000"
                required
                value={form.leverage}
                onChange={(e) => setForm({ ...form, leverage: Number(e.target.value) })}
              />
            </label>
            <label>
              Timeout seconds
              <input
                type="number"
                min="30"
                max="3600"
                required
                value={form.timeout_seconds}
                onChange={(e) => setForm({ ...form, timeout_seconds: Number(e.target.value) })}
              />
            </label>
            <label>
              Input provenance
              <select
                value={form.input_provenance}
                onChange={(e) =>
                  setForm({
                    ...form,
                    input_provenance: e.target.value as Config['input_provenance'],
                    set_text: e.target.value === 'USER_SET' ? '' : null,
                  })
                }
              >
                <option value="TESTER_DEFAULTS">Tester defaults (opaque binary defaults)</option>
                <option value="USER_SET">Explicit .set contents</option>
              </select>
            </label>
            {form.input_provenance === 'USER_SET' && (
              <label>
                Set contents
                <textarea
                  required
                  maxLength={65536}
                  value={form.set_text || ''}
                  onChange={(e) => setForm({ ...form, set_text: e.target.value })}
                />
              </label>
            )}
          </div>
          <p className="muted">
            Use a historical interval of at most 366 days. Inputs must contain no credentials and no
            enabled optimization ranges.
          </p>
          <button className="wb-primary" disabled={busy || detail.baseline_status !== 'READY'}>
            Run Baseline
          </button>
          {detail.baseline_status !== 'READY' && (
            <p>NOT_READY — provide an authorized EA, tester access and confirmed broker binding.</p>
          )}
        </form>
      )}
      {run && (
        <>
          <h3>{run.status === 'READY' ? 'Review and confirm baseline' : 'Baseline status'}</h3>
          <p role="status">
            {run.status} · Elapsed {elapsed}s
          </p>
          <dl className="wb-facts">
            {Object.entries({
              ...run.config,
              set_text:
                run.config.set_text === null
                  ? 'Not supplied'
                  : 'Captured in immutable configuration',
              input_sha256: run.input_sha256 || 'Not applicable',
              candidate_id: run.candidate_id,
              artifact_id: run.artifact_id,
              ea_sha256: run.ea_sha256,
            }).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll('_', ' ')}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
          <p>
            Declared license: {run.declared_license_status} · Declared tester access:{' '}
            {run.declared_tester_access} · Observed: {run.observed_tester_status}
          </p>
          {run.status === 'READY' && (
            <>
              <label className="wb-check">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                I confirm this exact configuration and authorized tester use.
              </label>
              <button
                disabled={busy || !confirmed}
                onClick={() =>
                  void action(async () => {
                    setRun(
                      await call<BaselineRun>('/' + run.config.baseline_run_id + '/start', {
                        confirmed: true,
                      }),
                    );
                  })
                }
              >
                Confirm and start tester
              </button>
            </>
          )}
          {(running || run.status === 'READY') && (
            <button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  setRun(
                    await call<BaselineRun>('/' + run.config.baseline_run_id + '/cancel', {
                      confirmed: true,
                    }),
                  );
                })
              }
            >
              Cancel baseline
            </button>
          )}
          {messages[run.status] && <p role="alert">{messages[run.status]}</p>}
          {run.status === 'COMPLETE' && result && (
            <>
              <h3>Result Summary</h3>
              <dl className="wb-facts">
                {Object.entries(result.metrics).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll('_', ' ')}</dt>
                    <dd>{value === null ? 'UNAVAILABLE' : String(value)}</dd>
                  </div>
                ))}
              </dl>
              <h3>Tester Metadata</h3>
              <dl className="wb-facts">
                {Object.entries(result.metadata).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <p>
                Raw report SHA-256: <code>{result.report_identity}</code>
              </p>
              <p>
                Normalized result identity: <code>{result.result_identity}</code>
              </p>
            </>
          )}
          <h3>Execution Evidence</h3>
          <p>
            Run ID: <code>{run.config.baseline_run_id}</code>
          </p>
          <p>
            Manifest identity: <code>{run.evidence_identity || 'UNAVAILABLE'}</code>
          </p>
          <p>Terminal build (operator configured): {run.terminal_build}</p>
          {!running && run.status !== 'READY' && (
            <button
              disabled={busy}
              onClick={() => {
                setRun(null);
                setResult(null);
                setConfirmed(false);
                setForm({ ...form, baseline_run_id: crypto.randomUUID() });
              }}
            >
              Configure another explicit run
            </button>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </>
  );
}
