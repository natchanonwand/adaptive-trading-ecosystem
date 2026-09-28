import { BaselinePanel } from './BaselinePanel';
import { useState } from 'react';
import { request, type Detail } from './api';

type Saved = {
  specification: {
    configuration_id: string;
    project_id: string;
    parameters: Record<string, unknown>;
  };
  configuration_identity: string;
  exact_inputs_known: boolean;
  input_limitation: string | null;
};
type Authorization = {
  event_id?: string;
  provenance: string;
  source_reference?: string;
  source_label?: string;
  authorization_basis?: string;
  authorization_attested_at?: string;
};
export type Readiness = {
  authorization: Authorization;
  authorization_history: Authorization[];
  configurations: Saved[];
  acceptance_readiness: { status: string; reasons: string[] };
};
const provenances = [
  'UNKNOWN',
  'USER_SUPPLIED_AUTHORIZED',
  'FREE_VENDOR_DISTRIBUTION',
  'MARKETPLACE_AUTHORIZED',
  'VENDOR_TRIAL_AUTHORIZED',
  'OTHER_EXPLICIT_AUTHORIZATION',
  'PROHIBITED_OR_UNVERIFIED',
];

export function ReadinessPanel({
  detail,
  source = false,
  onChange,
}: {
  detail: Detail;
  source?: boolean;
  onChange?: (value: Detail) => void;
}) {
  const [data, setData] = useState(detail);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [auth, setAuth] = useState({
    provenance: detail.authorization?.provenance ?? 'UNKNOWN',
    source_reference: detail.authorization?.source_reference ?? '',
    source_label: detail.authorization?.source_label ?? '',
    authorization_basis: detail.authorization?.authorization_basis ?? '',
  });
  const [form, setForm] = useState({
    from_date: '',
    to_date: '',
    initial_deposit: '10000',
    currency: 'USD',
    leverage: 100,
    timeout_seconds: 600,
    input_provenance: 'TESTER_DEFAULTS',
    input_reference: '',
    set_text: '',
  });
  const [selected, setSelected] = useState('');
  const [runConfirmed, setRunConfirmed] = useState(false);
  const [notice, setNotice] = useState('');
  const project = data.project;
  const candidate = data.candidate;
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await work();
      const refreshed = await request<Detail>('projects/' + project.project_id);
      setData(refreshed);
      onChange?.(refreshed);
    } catch {
      setError(
        'Request rejected. Check the source, confirmation, configuration and current readiness. Reload before retrying a stale authorization edit.',
      );
    } finally {
      setBusy(false);
    }
  }
  if (source)
    return (
      <section aria-label="Source and Authorization">
        <h3>Source &amp; Authorization</h3>
        <p>
          Product: {candidate.product_name}; vendor: {candidate.vendor}
        </p>
        <p>
          Artifact {data.verification.ea} · SHA-256: <code>{candidate.artifact_sha256}</code>
        </p>
        <p>
          Declared license: {candidate.license_status}; declared tester access:{' '}
          {candidate.tester_access_status}. UNKNOWN means not yet verified.
        </p>
        <p>
          Authorization: {data.authorization?.provenance ?? 'UNKNOWN'}. Artifact verification does
          not establish use authorization.
        </p>
        <p>
          User-attested authorization only; not vendor verification. Do not enter credentials or
          license secrets.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action(async () => {
              await request('authorization/' + project.project_id, {
                ...auth,
                event_id: crypto.randomUUID(),
                previous_event_id: data.authorization?.event_id ?? null,
                confirmed,
              });
              setConfirmed(false);
              setNotice('Authorization attestation recorded. Previous declarations are retained.');
            });
          }}
        >
          <label>
            Authorization provenance
            <select
              value={auth.provenance}
              onChange={(e) => {
                setConfirmed(false);
                setAuth({ ...auth, provenance: e.target.value });
              }}
            >
              {provenances.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          {(['source_label', 'source_reference', 'authorization_basis'] as const).map((key) => (
            <label key={key}>
              {key.replaceAll('_', ' ')}
              <input
                required
                value={auth[key]}
                onChange={(e) => {
                  setConfirmed(false);
                  setAuth({ ...auth, [key]: e.target.value });
                }}
              />
            </label>
          ))}
          <label>
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I confirm this source and authorization declaration is accurate.
          </label>
          <button disabled={!confirmed || busy}>Save authorization attestation</button>
        </form>
        <h4>Attestation history</h4>
        <ul>
          {data.authorization_history?.map((a) => (
            <li key={a.event_id}>
              {a.authorization_attested_at}: {a.provenance} — {a.source_label}; {a.source_reference}
              ; {a.authorization_basis} (user-attested)
            </li>
          ))}
        </ul>
        <BaselinePanel key={notice} detail={data} existingOnly />
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
      </section>
    );
  return (
    <section aria-label="Baseline configuration">
      <h3>Acceptance readiness: {data.acceptance_readiness?.status}</h3>
      {data.research_environment && (
        <section aria-label="Research Environment">
          <h4>Research Environment</h4>
          <p>{data.research_environment.status}</p>
          {data.research_environment.last_probe && (
            <p>Last Probe: {data.research_environment.last_probe}</p>
          )}
          <p>
            Symbol: {data.research_environment.symbol ?? project.broker_binding.broker_symbol};
            native bootstrap: {data.research_environment.native_bootstrap ?? 'NOT_VERIFIED'}
          </p>
          <p>
            MT5 Terminal:{' '}
            {data.research_environment.binding?.terminal_executable ?? 'Not configured'}
          </p>
          <p>
            {data.research_environment.binding?.company} · Build{' '}
            {data.research_environment.binding?.terminal_build ?? 'UNKNOWN'}
          </p>
          <p>Research/tester binding only. This is not broker-order execution authorization.</p>
        </section>
      )}
      <ul>
        {data.acceptance_readiness?.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      <p>
        License: {candidate.license_status}; tester access: {candidate.tester_access_status}.
        UNKNOWN declarations are not prohibitions.
      </p>
      <p>
        DEMO/research only · {project.broker_binding.canonical_asset} →{' '}
        {project.broker_binding.broker_symbol} · {project.broker_binding.timeframe} ·
        EVERY_TICK_BASED_ON_REAL_TICKS
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action(async () => {
            const exact = ['USER_SUPPLIED_SET', 'USER_CONFIRMED_VALUES'].includes(
              form.input_provenance,
            );
            const saved = await request<Saved>('baseline-configurations', {
              configuration_id: crypto.randomUUID(),
              project_id: project.project_id,
              confirmed: reviewed,
              parameters: {
                ...form,
                symbol: project.broker_binding.broker_symbol,
                timeframe: project.broker_binding.timeframe,
                tester_model: 'EVERY_TICK_BASED_ON_REAL_TICKS',
                environment: 'DEMO_RESEARCH_TESTER',
                set_text: exact ? form.set_text : null,
                input_reference: form.input_reference || null,
              },
            });
            setSelected(saved.specification.configuration_id);
            setReviewed(false);
            setNotice(
              'Immutable configuration saved. No execution attempt was created or started.',
            );
          });
        }}
      >
        {(['from_date', 'to_date', 'initial_deposit', 'leverage', 'timeout_seconds'] as const).map(
          (key) => (
            <label key={key}>
              {key.replaceAll('_', ' ')}
              <input
                required
                type={key.endsWith('date') ? 'date' : 'number'}
                value={form[key]}
                onChange={(e) => {
                  setReviewed(false);
                  setForm({
                    ...form,
                    [key]: ['leverage', 'timeout_seconds'].includes(key)
                      ? Number(e.target.value)
                      : e.target.value,
                  });
                }}
              />
            </label>
          ),
        )}
        <p>
          Currency: USD. Existing defaults: deposit 10000, leverage 100, timeout 600 seconds. Review
          before saving; dates are required.
        </p>
        <label>
          EA input provenance
          <select
            value={form.input_provenance}
            onChange={(e) => {
              setReviewed(false);
              setForm({ ...form, input_provenance: e.target.value });
            }}
          >
            {[
              'TESTER_DEFAULTS',
              'VENDOR_DOCUMENTED_DEFAULTS',
              'USER_SUPPLIED_SET',
              'USER_CONFIRMED_VALUES',
            ].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label>
          Input documentation reference
          <input
            value={form.input_reference}
            onChange={(e) => {
              setReviewed(false);
              setForm({ ...form, input_reference: e.target.value });
            }}
          />
        </label>
        {['USER_SUPPLIED_SET', 'USER_CONFIRMED_VALUES'].includes(form.input_provenance) ? (
          <label>
            Exact .set values (optimization prohibited)
            <textarea
              required
              value={form.set_text}
              onChange={(e) => {
                setReviewed(false);
                setForm({ ...form, set_text: e.target.value });
              }}
            />
          </label>
        ) : (
          <p>
            Exact default inputs are unavailable before initialization. No hidden parameters are
            invented.
          </p>
        )}
        <label>
          <input
            type="checkbox"
            checked={reviewed}
            onChange={(e) => setReviewed(e.target.checked)}
          />
          I reviewed all configuration values and input limitations.
        </label>
        <button disabled={!reviewed || busy}>Save BaselineConfiguration</button>
      </form>
      <label>
        Persisted configuration
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setRunConfirmed(false);
          }}
        >
          <option value="">Select an immutable configuration</option>
          {data.configurations?.map((c) => (
            <option key={c.specification.configuration_id} value={c.specification.configuration_id}>
              {c.specification.configuration_id}
            </option>
          ))}
        </select>
      </label>
      {data.configurations
        ?.filter((c) => c.specification.configuration_id === selected)
        .map((c) => (
          <pre key={c.configuration_identity}>{JSON.stringify(c, null, 2)}</pre>
        ))}
      <label>
        <input
          type="checkbox"
          checked={runConfirmed}
          onChange={(e) => setRunConfirmed(e.target.checked)}
        />
        Explicitly start one tester execution attempt of the selected configuration.
      </label>
      <button
        disabled={
          busy ||
          !selected ||
          !runConfirmed ||
          data.acceptance_readiness?.status !== 'READY' ||
          (data.research_environment !== undefined && data.research_environment.status !== 'READY')
        }
        onClick={() =>
          void action(async () => {
            const cfg = data.configurations?.find(
              (c) => c.specification.configuration_id === selected,
            );
            if (!cfg) throw new Error('Select a configuration');
            const id = crypto.randomUUID();
            await request('baselines', {
              ...cfg.specification.parameters,
              project_id: project.project_id,
              configuration_id: selected,
              baseline_run_id: id,
            });
            await request('baselines/' + id + '/start', { confirmed: true });
            setRunConfirmed(false);
            setNotice('Execution attempt started: ' + id);
          })
        }
      >
        Run Baseline
      </button>
      <BaselinePanel key={notice} detail={data} existingOnly />
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
