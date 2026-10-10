import { ExperimentsPanel } from './ExperimentsPanel';
import { ReadinessPanel } from './ReadinessPanel';
import { useEffect, useState } from 'react';
import { BaselinePanel } from './BaselinePanel';
import {
  request,
  upload,
  type Artifact,
  type Binding,
  type Candidate,
  type Catalog,
  type Detail,
  type Project,
} from './api';

const stages = ['Source', 'Candidate', 'Artifacts', 'Broker binding', 'Metadata', 'Review'];
const sources = ['External EA', 'Strategy Idea', 'Quant Formula', 'Manual Trading'];
const mappings: Record<string, string> = {
  BTCUSD: 'BTCUSDm',
  XAUUSD: 'XAUUSDm',
  USTEC100: 'USTECm',
  US100: 'USTECm',
};
const initialCandidate: Candidate = {
  product_name: '',
  version: 'UNKNOWN',
  vendor: 'UNKNOWN',
  source_reference: 'UNKNOWN',
  license_status: 'UNKNOWN',
  tester_access_status: 'UNKNOWN',
  known_magic_number: null,
  known_order_comments: 'UNKNOWN',
  notes: '',
  catalog_id: null,
  artifact_id: null,
  manual_id: null,
};
const label = (value: string) => value.replaceAll('_', ' ');

function Evidence({ artifact, title }: { artifact: Artifact | null; title: string }) {
  return artifact ? (
    <div className="wb-evidence">
      <b>
        {title}: {artifact.filename}
      </b>
      <p>{artifact.size.toLocaleString()} bytes · Stored and hashed</p>
      <details>
        <summary>SHA-256 identity</summary>
        <code>{artifact.sha256}</code>
      </details>
    </div>
  ) : (
    <p className="muted">{title}: not provided</p>
  );
}

export function Workbench() {
  const [route, setRoute] = useState(window.location.hash || '#/projects');
  useEffect(() => {
    const change = () => setRoute(window.location.hash || '#/projects');
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  const go = (path: string) => {
    window.location.hash = path;
    setRoute('#' + path);
  };
  return (
    <div className="wb-shell">
      <header className="wb-header">
        <a href="#/projects" onClick={() => go('/projects')}>
          <b>ATE / Research Workbench</b>
        </a>
        <span className="wb-badge">DEMO research · No execution</span>
      </header>
      <main className="wb-main">
        {route === '#/projects/new' ? (
          <Wizard done={(id) => go('/projects/' + id)} cancel={() => go('/projects')} />
        ) : route.startsWith('#/projects/') ? (
          <ProjectDetail id={route.slice('#/projects/'.length)} back={() => go('/projects')} />
        ) : (
          <Projects open={(id) => go('/projects/' + id)} create={() => go('/projects/new')} />
        )}
      </main>
      <footer className="wb-footer">
        Evidence before conclusions. Artifacts are stored locally and never executed here.
      </footer>
    </div>
  );
}

function Projects({ open, create }: { open: (id: string) => void; create: () => void }) {
  const [items, setItems] = useState<Project[]>([]);
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    request<{ items: Project[]; next_offset: number | null }>('projects?offset=' + offset)
      .then((data) => {
        if (active) {
          setItems(data.items);
          setNext(data.next_offset);
          setLoading(false);
        }
      })
      .catch((e: Error) => {
        if (active) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [offset]);
  return (
    <>
      <div className="wb-title">
        <div>
          <p className="eyebrow">RESEARCH WORKSPACE</p>
          <h1>Projects</h1>
          <p className="muted">Bring an external EA into a traceable research project.</p>
        </div>
        <button className="wb-primary" onClick={create}>
          New Research Project
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {loading ? (
        <p role="status">Loading projects…</p>
      ) : !items.length && !error ? (
        <section className="wb-panel wb-empty">
          <h2>Your research starts here</h2>
          <p>No research projects yet. Register an EA and its evidence to begin.</p>
          <button onClick={create}>Create your first project</button>
        </section>
      ) : (
        <div className="wb-grid">
          {items.map((p) => (
            <article className="wb-panel" key={p.project_id}>
              <span className="wb-badge">{label(p.status)}</span>
              <h2>{p.project_name}</h2>
              <p>{p.product_name}</p>
              <p className="muted">
                {label(p.source_type)} · {p.broker_binding.canonical_asset} ·{' '}
                {p.broker_binding.timeframe}
              </p>
              <p className="small muted">Updated {new Date(p.updated_at).toLocaleString()}</p>
              <button onClick={() => open(p.project_id)}>Open Project</button>
            </article>
          ))}
        </div>
      )}
      {(offset > 0 || next !== null) && (
        <div className="wb-actions">
          <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>
            Previous
          </button>
          <button disabled={next === null} onClick={() => next !== null && setOffset(next)}>
            Next
          </button>
        </div>
      )}
    </>
  );
}

function Wizard({ done, cancel }: { done: (id: string) => void; cancel: () => void }) {
  const [step, setStep] = useState(0);
  const [projectId] = useState(() => crypto.randomUUID());
  const [name, setName] = useState('');
  const [candidate, setCandidate] = useState<Candidate>(initialCandidate);
  const [binding, setBinding] = useState<Binding>({
    broker_name: 'UNKNOWN',
    environment: 'DEMO',
    canonical_asset: 'UNKNOWN',
    broker_symbol: 'UNKNOWN',
    timeframe: 'UNKNOWN',
    symbol_confirmed: false,
  });
  const [catalog, setCatalog] = useState<Catalog[]>([]);
  const [ea, setEa] = useState<Artifact | null>(null);
  const [manual, setManual] = useState<Artifact | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    request<{ items: Catalog[] }>('catalog')
      .then((v) => {
        if (active) setCatalog(v.items);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  const update = (key: keyof Candidate, value: string | number | null) =>
    setCandidate((c) => ({ ...c, [key]: value }));
  async function add(file: File | undefined, role: 'EA' | 'MANUAL') {
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const result = await upload(file, role);
      if (role === 'EA') {
        setEa(result);
        update('artifact_id', result.artifact_id);
      } else {
        setManual(result);
        update('manual_id', result.artifact_id);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    if (
      candidate.known_magic_number !== null &&
      (!Number.isSafeInteger(candidate.known_magic_number) || candidate.known_magic_number < 0)
    ) {
      setError('Known magic number must be a nonnegative integer no larger than 9007199254740991.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await request<Project>('projects', {
        project_id: projectId,
        project_name: name,
        source_type: 'EXTERNAL_EA',
        candidate,
        broker_binding: binding,
      });
      done(result.project_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="wb-title">
        <div>
          <p className="eyebrow">NEW RESEARCH PROJECT</p>
          <h1>External EA onboarding</h1>
        </div>
        <button onClick={cancel} disabled={busy}>
          Cancel
        </button>
      </div>
      <ol className="wb-steps" aria-label="Project creation progress">
        {stages.map((s, i) => (
          <li key={s} aria-current={step === i ? 'step' : undefined}>
            {i + 1}. {s}
          </li>
        ))}
      </ol>
      <section className="wb-panel">
        <h2>{stages[step]}</h2>
        {step === 0 && (
          <>
            <div className="wb-grid">
              {sources.map((s, i) => (
                <button key={s} disabled={i > 0} aria-pressed={i === 0}>
                  {s}
                  {i > 0 ? ' — COMING SOON' : ' — selected'}
                </button>
              ))}
            </div>
            <p className="muted">
              Onboarding stores files and metadata. Baseline execution requires separate
              confirmation.
            </p>
          </>
        )}
        {step === 1 && (
          <>
            <label>
              Project name
              <input value={name} maxLength={150} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              Product name
              <input
                value={candidate.product_name}
                onChange={(e) => update('product_name', e.target.value)}
              />
            </label>
            <button
              onClick={() =>
                setCandidate((old) => ({
                  ...initialCandidate,
                  artifact_id: old.artifact_id,
                  manual_id: old.manual_id,
                }))
              }
            >
              Upload/Register EA · custom candidate
            </button>
            <h3>Candidate catalog</h3>
            <p className="muted">
              Metadata-only starting points. Selection is not an endorsement or a profitability
              claim. No license or file is included.
            </p>
            <div className="wb-grid">
              {catalog.map((c) => (
                <button
                  key={c.catalog_id}
                  aria-pressed={candidate.catalog_id === c.catalog_id}
                  onClick={() => {
                    setCandidate((old) => ({
                      ...old,
                      product_name: c.product_name,
                      catalog_id: c.catalog_id,
                      source_reference: c.source_reference,
                    }));
                    setBinding((old) => ({
                      ...old,
                      canonical_asset: c.asset,
                      broker_symbol: 'UNKNOWN',
                      symbol_confirmed: false,
                    }));
                  }}
                >
                  <strong>{c.product_name}</strong>
                  <span>
                    {c.asset} · {c.research_class}
                  </span>
                </button>
              ))}
            </div>
          </>
        )}
        {step === 2 && (
          <>
            <p>
              Choose files you are authorized to store. EX5 bytes remain opaque; only filename, size
              and SHA-256 are recorded.
            </p>
            <label>
              EA artifact (.ex5)
              <input
                type="file"
                accept=".ex5"
                disabled={busy}
                onChange={(e) => void add(e.target.files?.[0], 'EA')}
              />
            </label>

            <Evidence artifact={ea} title="EA artifact" />
            <label>
              Optional manual (.pdf)
              <input
                type="file"
                accept=".pdf"
                disabled={busy}
                onChange={(e) => void add(e.target.files?.[0], 'MANUAL')}
              />
            </label>
            <Evidence artifact={manual} title="Manual" />
            <p className="muted">
              You can create a draft without an EA file. An authorized artifact is required before
              baseline readiness.
            </p>
          </>
        )}
        {step === 3 && (
          <div className="wb-form">
            <label>
              Environment
              <input value="DEMO" readOnly />
            </label>
            <label>
              Broker
              <input
                value={binding.broker_name}
                onChange={(e) =>
                  setBinding({ ...binding, broker_name: e.target.value, symbol_confirmed: false })
                }
              />
            </label>
            <label>
              Canonical asset
              <select
                value={binding.canonical_asset}
                onChange={(e) =>
                  setBinding({
                    ...binding,
                    canonical_asset: e.target.value,
                    broker_symbol: 'UNKNOWN',
                    symbol_confirmed: false,
                  })
                }
              >
                {['UNKNOWN', ...Object.keys(mappings)].map((a) => (
                  <option key={a}>{a}</option>
                ))}
              </select>
            </label>
            <label>
              Broker symbol
              <input
                value={binding.broker_symbol}
                onChange={(e) =>
                  setBinding({ ...binding, broker_symbol: e.target.value, symbol_confirmed: false })
                }
              />
            </label>
            <p className="muted">
              Known mapping: {mappings[binding.canonical_asset] || 'UNKNOWN'}. Enter and confirm
              your broker symbol explicitly.
            </p>
            <label>
              Timeframe
              <select
                value={binding.timeframe}
                onChange={(e) => setBinding({ ...binding, timeframe: e.target.value })}
              >
                {['UNKNOWN', 'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label className="wb-check">
              <input
                type="checkbox"
                checked={binding.symbol_confirmed}
                onChange={(e) => setBinding({ ...binding, symbol_confirmed: e.target.checked })}
              />
              I confirm this DEMO broker/symbol mapping
            </label>
          </div>
        )}
        {step === 4 && (
          <div className="wb-form">
            {(
              [
                'product_name',
                'version',
                'vendor',
                'source_reference',
                'known_order_comments',
                'notes',
              ] as const
            ).map((key) => (
              <label key={key}>
                {label(key)}
                <input
                  value={candidate[key]}
                  maxLength={2000}
                  onChange={(e) => update(key, e.target.value)}
                />
              </label>
            ))}
            <label>
              License status
              <select
                value={candidate.license_status}
                onChange={(e) => update('license_status', e.target.value)}
              >
                <option value="UNKNOWN">UNKNOWN</option>
                <option value="USER_ATTESTED">I attest authorized use</option>
                <option value="NOT_AUTHORIZED">Not authorized</option>
              </select>
            </label>
            <label>
              Tester access
              <select
                value={candidate.tester_access_status}
                onChange={(e) => update('tester_access_status', e.target.value)}
              >
                <option value="UNKNOWN">UNKNOWN</option>
                <option value="USER_CONFIRMED">I confirm tester access</option>
                <option value="UNAVAILABLE">Unavailable</option>
              </select>
            </label>
            <label>
              Known magic number (optional)
              <input
                type="number"
                step="1"
                min="0"
                max="9007199254740991"
                value={candidate.known_magic_number ?? ''}
                onChange={(e) =>
                  update(
                    'known_magic_number',
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
              />
            </label>
            <p className="muted">
              Unknown metadata stays UNKNOWN. Never enter broker passwords, keys or license
              credentials.
            </p>
          </div>
        )}
        {step === 5 && (
          <>
            <h3>{name}</h3>
            <p>
              {candidate.product_name || 'UNKNOWN'} · {candidate.version}
            </p>
            <p>
              {binding.environment} · {binding.broker_name} · {binding.canonical_asset} →{' '}
              {binding.broker_symbol} · {binding.timeframe}
            </p>
            <p>
              License: {label(candidate.license_status)} · Tester:{' '}
              {label(candidate.tester_access_status)}
            </p>

            <Evidence artifact={ea} title="EA artifact" />
            <Evidence artifact={manual} title="Manual" />
            <details>
              <summary>Project identity</summary>
              <code>{projectId}</code>
              <p>Candidate identity is assigned when the project is created.</p>
            </details>
            <p className="muted">
              Creating a project stores research metadata only. No baseline run will start.
            </p>
          </>
        )}
        {busy && <p role="status">Saving and verifying…</p>}
        {error && <p role="alert">{error}</p>}
        <div className="wb-actions">
          <button disabled={step === 0 || busy} onClick={() => setStep(step - 1)}>
            Back
          </button>
          {step < 5 ? (
            <button
              className="wb-primary"
              disabled={busy || (step === 1 && !name.trim())}
              onClick={() => {
                setError('');
                setStep(step + 1);
              }}
            >
              Continue
            </button>
          ) : (
            <button className="wb-primary" disabled={busy} onClick={() => void save()}>
              Create Project
            </button>
          )}
        </div>
      </section>
    </>
  );
}

function ProjectDetail({ id, back }: { id: string; back: () => void }) {
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('Overview');
  const [notice, setNotice] = useState(false);
  useEffect(() => {
    let active = true;
    request<Detail>('projects/' + encodeURIComponent(id))
      .then((v) => {
        if (active) setData(v);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id]);
  if (error)
    return (
      <>
        <p role="alert">{error}</p>
        <button onClick={back}>Back to Projects</button>
      </>
    );
  if (!data) return <p role="status">Loading project…</p>;
  const { project: p, candidate: c } = data;
  const ea = c.artifact_sha256
    ? {
        artifact_id: c.artifact_id!,
        filename: c.artifact_filename!,
        sha256: c.artifact_sha256,
        size: c.artifact_size!,
      }
    : null;
  const manual = c.manual_sha256
    ? {
        artifact_id: c.manual_id!,
        filename: c.manual_filename!,
        sha256: c.manual_sha256,
        size: c.manual_size!,
      }
    : null;
  return (
    <>
      <button onClick={back}>← Projects</button>
      <div className="wb-title">
        <div>
          <h1>{p.project_name}</h1>
          <p>
            {c.product_name} · {c.version}
          </p>
        </div>
        <span className="wb-badge">{label(p.status)}</span>
      </div>
      {data.acceptance_readiness && (
        <p role="status">
          Acceptance execution: {data.acceptance_readiness.status} ·{' '}
          {data.acceptance_readiness.reasons.join(', ')}
        </p>
      )}
      <nav className="wb-tabs" aria-label="Project sections">
        {['Overview', 'Baseline', 'Experiments', 'Behavior', 'Forward', 'Evidence'].map((name) => (
          <button
            key={name}
            aria-current={tab === name ? 'page' : undefined}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </nav>
      <section className="wb-panel">
        <h2>{tab}</h2>
        {tab === 'Overview' && (
          <>
            <dl className="wb-facts">
              {Object.entries({
                Status: label(p.status),
                Candidate: c.product_name,
                Version: c.version,
                Asset: p.broker_binding.canonical_asset,
                Broker: p.broker_binding.broker_name,
                Symbol: p.broker_binding.broker_symbol,
                Timeframe: p.broker_binding.timeframe,
                Environment: p.broker_binding.environment,
                License: label(c.license_status),
                'Tester access': label(c.tester_access_status),
                'Artifact verification': data.verification.ea,
              }).map(([key, v]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <p className="muted">
              Readiness reflects registered metadata and artifact integrity. It is not a completed
              baseline or a license verification by the vendor.
            </p>
          </>
        )}
        {tab === 'Evidence' && (
          <>
            <p>
              Project ID: <code>{p.project_id}</code>
            </p>
            <p>
              Candidate ID: <code>{p.candidate_id}</code>
            </p>
            {data.readiness_enabled && <ReadinessPanel detail={data} source onChange={setData} />}
            <Evidence artifact={ea} title="EA artifact" />
            <Evidence artifact={manual} title="Manual" />
            <p>
              Verification: EA {data.verification.ea}; manual {data.verification.manual}
            </p>
            <p>
              {p.broker_binding.broker_name} · {p.broker_binding.environment} ·{' '}
              {p.broker_binding.canonical_asset} → {p.broker_binding.broker_symbol} ·{' '}
              {p.broker_binding.timeframe}
            </p>
            <p>Status: {label(p.status)}</p>
          </>
        )}
        {tab === 'Baseline' && data.readiness_enabled && (
          <ReadinessPanel detail={data} onChange={setData} />
        )}
        {tab === 'Baseline' && data.baseline_enabled && !data.readiness_enabled && (
          <BaselinePanel detail={data} />
        )}
        {tab === 'Baseline' && !data.baseline_enabled && (
          <>
            <span className="wb-badge">{data.baseline_status}</span>
            <p>No baseline results have been generated.</p>
            <button onClick={() => setNotice(true)}>Run Baseline</button>
            {notice && (
              <p role="status">
                Automated baseline execution will be available in Phase 5B. Nothing was executed.
              </p>
            )}
          </>
        )}
        {tab === 'Experiments' && <ExperimentsPanel key={id} detail={data} />}
        {['Behavior', 'Forward'].includes(tab) && (
          <>
            <h3>Coming soon</h3>
            <p>This stage is not enabled. No results or activity exist for this project.</p>
          </>
        )}
      </section>
    </>
  );
}
