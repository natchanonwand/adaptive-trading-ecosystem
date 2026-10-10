import { useEffect, useState } from 'react';
import type { Detail } from './api';

type Value = string | number | boolean | null | Value[] | { [key: string]: Value };
type Definition = { [key: string]: Value };
export type ExperimentRecord = {
  id: string;
  state: 'DRAFT' | 'FROZEN';
  identity: string;
  parameter_space_identity: string;
  split_plan_identity: string;
  campaign_identity: string;
  definition: Definition;
};
const parameter = {
  parameter_name: '',
  native_key: '',
  kind: 'INTEGER',
  baseline: '',
  minimum: null,
  maximum: null,
  step: null,
  choices: [],
  transformation: 'IDENTITY',
  reason: '',
  provenance: 'USER_DECLARATION',
  source_reference: '',
  conditional: null,
  categorical: false,
  ordered: true,
};
const objective = {
  metric: 'RETURN_R',
  direction: 'MAXIMIZE',
  definition: '',
  null_policy: 'INELIGIBLE',
};
const constraint = { metric: 'TRADE_COUNT', comparator: 'AT_LEAST', threshold: '', rationale: '' };
const metrics = [
  'RETURN_R',
  'NET_PROFIT',
  'PROFIT_FACTOR',
  'EXPECTANCY',
  'DRAWDOWN_ADJUSTED_RETURN',
  'STABILITY',
  'MAX_DRAWDOWN_PCT',
  'TRADE_COUNT',
  'ACTIVITY',
  'CONCENTRATION',
];
const options: Record<string, string[]> = {
  kind: ['INTEGER', 'DECIMAL', 'BOOLEAN', 'CATEGORY'],
  provenance: [
    'VENDOR_DOCUMENTATION',
    'USER_DECLARATION',
    'STRATEGY_SPECIFICATION',
    'REGISTERED_HYPOTHESIS',
  ],
  method: ['GRID', 'RANDOM_SEEDED'],
  early_rejection: ['NONE', 'PRE_REGISTERED_HARD_CONSTRAINTS'],
  metric: metrics,
  direction: ['MAXIMIZE', 'MINIMIZE'],
  comparator: ['AT_LEAST', 'AT_MOST'],
  evaluation_method: ['PARETO_REVIEW', 'DECLARED_LEXICOGRAPHIC'],
  evidence_classification: ['EXPLORATORY_GROSS', 'EXPLORATORY_COST_MODELED'],
};
const fixed = new Set([
  'schema_version',
  'project_id',
  'candidate_id',
  'baseline_configuration_id',
  'baseline_identity',
  'broker',
  'symbol',
  'timeframe',
  'tester_model',
  'broker_environment',
  'qualification_eligible',
  'purpose',
  'locked',
  'maximum_workers',
  'transformation',
  'null_policy',
]);
const title = (key: string) => key.replaceAll('_', ' ');

function Fields({
  value,
  path,
  name,
  change,
  frozen,
}: {
  value: Value;
  path: string;
  name: string;
  change: (v: Value) => void;
  frozen: boolean;
}) {
  const label = title(path);
  if (name === 'conditional' && value === null)
    return (
      <button
        type="button"
        disabled={frozen}
        onClick={() => change({ native_key: '', equals: '' })}
      >
        Add {label}
      </button>
    );
  if (Array.isArray(value)) {
    const template =
      name === 'parameters'
        ? parameter
        : name === 'objectives'
          ? objective
          : name === 'constraints'
            ? constraint
            : '';
    return (
      <fieldset>
        <legend>{title(name)}</legend>
        {value.map((v, i) => (
          <div key={i} className="wb-evidence">
            <Fields
              value={v}
              path={`${path} ${i + 1}`}
              name={String(i)}
              frozen={frozen}
              change={(next) => change(value.map((old, j) => (j === i ? next : old)))}
            />
            {name !== 'splits' && (
              <button
                type="button"
                disabled={frozen}
                onClick={() => change(value.filter((_, j) => j !== i))}
              >
                Remove {title(path)} {i + 1}
              </button>
            )}
          </div>
        ))}
        {name !== 'splits' && (
          <button
            type="button"
            disabled={frozen}
            onClick={() => change([...value, structuredClone(template)])}
          >
            Add {title(path)}
          </button>
        )}
      </fieldset>
    );
  }
  if (value !== null && typeof value === 'object')
    return (
      <fieldset>
        <legend>{title(name)}</legend>
        {Object.entries(value).map(([key, v]) => (
          <Fields
            key={key}
            value={v}
            path={`${path} ${key}`}
            name={key}
            frozen={frozen}
            change={(next) => change({ ...value, [key]: next })}
          />
        ))}
        {name === 'conditional' && (
          <button type="button" disabled={frozen} onClick={() => change(null)}>
            Remove {label}
          </button>
        )}
      </fieldset>
    );
  const disabled = frozen || fixed.has(name);
  if (typeof value === 'boolean')
    return (
      <label className="wb-check">
        <input
          type="checkbox"
          aria-label={label}
          checked={value}
          disabled={disabled}
          onChange={(e) => change(e.target.checked)}
        />
        {label}
      </label>
    );
  if (options[name])
    return (
      <label>
        {label}
        <select
          value={String(value ?? '')}
          disabled={disabled}
          onChange={(e) => change(e.target.value)}
        >
          {options[name].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </label>
    );
  const numeric =
    typeof value === 'number' || name === 'random_seed' || name.startsWith('maximum_');
  return (
    <label>
      {label}
      <input
        type={name === 'start' || name === 'end' ? 'date' : numeric ? 'number' : 'text'}
        step={numeric ? '1' : undefined}
        value={value ?? ''}
        readOnly={disabled}
        onChange={(e) =>
          change(
            numeric
              ? e.target.value === ''
                ? null
                : Number(e.target.value)
              : ['minimum', 'maximum', 'step'].includes(name)
                ? e.target.value || null
                : e.target.value,
          )
        }
      />
    </label>
  );
}

// Keep the backend's typed error verbatim instead of the generic onboarding message.
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/workbench-api/experiments' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers:
      body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Workbench-Request': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(typeof data.error === 'string' ? data.error : `HTTP ${response.status}`);
  return data as T;
}
function initial(detail: Detail): Definition {
  return {
    project_id: detail.project.project_id,
    candidate_id: detail.project.candidate_id,
    baseline_configuration_id: '',
    baseline_identity: '',
    hypothesis: '',
    parameter_space: { parameters: [structuredClone(parameter)] },
    budget: {
      maximum_configurations: 0,
      maximum_native_executions: 0,
      method: 'GRID',
      random_seed: null,
      maximum_wall_seconds: 0,
      maximum_workers: 1,
      early_rejection: 'NONE',
    },
    split_plan: {
      splits: ['DEVELOPMENT', 'VALIDATION', 'LOCKED_OOS'].map((purpose) => ({
        purpose,
        start: '',
        end: '',
        locked: true,
      })),
    },
    objectives: [structuredClone(objective)],
    evaluation_method: 'PARETO_REVIEW',
    constraints: [structuredClone(constraint)],
    tester_model: 'EVERY_TICK_BASED_ON_REAL_TICKS',
    cost_assumptions: '',
    broker_environment: 'DEMO_RESEARCH_TESTER',
    broker: detail.project.broker_binding.broker_name,
    symbol: detail.project.broker_binding.broker_symbol,
    timeframe: detail.project.broker_binding.timeframe,
    data_identity: '',
    evidence_classification: 'EXPLORATORY_GROSS',
    qualification_eligible: false,
  };
}
export function ExperimentsPanel({ detail }: { detail: Detail }) {
  const [items, setItems] = useState<ExperimentRecord[]>([]);
  const [form, setForm] = useState<Definition>(() => initial(detail));
  const [record, setRecord] = useState<ExperimentRecord | null>(null);
  const [dirty, setDirty] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api<{ items: ExperimentRecord[] }>(
      '?project_id=' + encodeURIComponent(detail.project.project_id),
    )
      .then((data) => {
        if (active) setItems(data.items);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [detail.project.project_id]);
  const frozen = record?.state === 'FROZEN';
  function review(next: ExperimentRecord) {
    setRecord(next);
    setForm(structuredClone(next.definition));
    setDirty(false);
    setConfirmed(false);
    setError('');
  }
  async function save(freeze: boolean) {
    setBusy(true);
    setError('');
    try {
      const next = freeze
        ? await api<ExperimentRecord>(`/${record!.id}/freeze`, { confirmed: true })
        : await api<ExperimentRecord>('', form);
      setItems((old) => [next, ...old.filter((r) => r.id !== next.id)]);
      review(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <p>
        Phase 5C.0: define, review and freeze only. No experiment execution or tuning is available.
      </p>
      <p>
        <strong>LOCKED_OOS</strong> is reserved and protected from parameter selection. No OOS
        results exist or can be unlocked here.
      </p>
      {loading && <p role="status">Loading experiment definitions…</p>}
      <label>
        Review saved definition
        <select
          disabled={busy || loading}
          value={record?.id ?? ''}
          onChange={(e) => {
            const found = items.find((r) => r.id === e.target.value);
            if (found) review(found);
          }}
        >
          <option value="">Select a definition</option>
          {items.map((r) => (
            <option key={r.id} value={r.id}>
              {r.state} · {r.id}
            </option>
          ))}
        </select>
      </label>
      <button
        disabled={busy || loading}
        onClick={() => {
          setRecord(null);
          setForm(initial(detail));
          setDirty(true);
          setConfirmed(false);
          setError('');
        }}
      >
        New definition
      </button>
      <p role="status">
        {frozen ? 'FROZEN' : 'DRAFT'}
        {record && !dirty && !frozen
          ? ' · READY for explicit freeze review (not execution)'
          : dirty
            ? ' · Unsaved changes'
            : ''}
      </p>
      <p>
        Saving revisions creates a new immutable identity; it never overwrites a saved definition.
        Explicit parameter provenance is required; hidden tester-default inputs are not inferred.
      </p>
      {record && (
        <dl className="wb-facts">
          {Object.entries({
            'Definition ID': record.id,
            'Definition identity': record.identity,
            'Parameter space identity': record.parameter_space_identity,
            'Split plan identity': record.split_plan_identity,
            'Campaign contract identity (no execution)': record.campaign_identity,
          }).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>
                <code>{value}</code>
              </dd>
            </div>
          ))}
        </dl>
      )}
      {dirty && record && (
        <p>
          Displayed identities belong to the saved version. Save revisions before reviewing a new
          identity.
        </p>
      )}
      <fieldset disabled={busy || loading || frozen}>
        <legend>Experiment definition</legend>
        <label>
          Existing baseline configuration
          <select
            value={String(form.baseline_configuration_id)}
            onChange={(e) => {
              const config = detail.configurations?.find(
                (c) => c.specification.configuration_id === e.target.value,
              );
              setForm({
                ...form,
                baseline_configuration_id: e.target.value,
                baseline_identity: config?.configuration_identity ?? '',
              });
              setDirty(true);
              setConfirmed(false);
            }}
          >
            <option value="">Select an existing configuration</option>
            {detail.configurations?.map((c) => (
              <option
                key={c.specification.configuration_id}
                value={c.specification.configuration_id}
              >
                {c.specification.configuration_id}
              </option>
            ))}
          </select>
        </label>
        <p>
          Numeric parameter domains require min/max/step OR choices. For BOOLEAN/CATEGORY, enable
          categorical; numeric parameters require ordered. Dates are half-open: start inclusive, end
          exclusive. Budget values must be positive; seeded random requires a seed and GRID requires
          an empty seed.
        </p>
        {Object.entries(form).map(([key, value]) => (
          <Fields
            key={key}
            name={key}
            path={key}
            value={value}
            frozen={!!frozen}
            change={(next) => {
              setForm({ ...form, [key]: next });
              setDirty(true);
              setConfirmed(false);
            }}
          />
        ))}
      </fieldset>
      {error && <p role="alert">{error}</p>}
      {busy && <p role="status">Saving definition…</p>}
      {!frozen && (
        <div className="wb-actions">
          <button disabled={busy || loading || !dirty} onClick={() => void save(false)}>
            Register / save draft
          </button>
        </div>
      )}
      {record && !frozen && (
        <>
          <label className="wb-check">
            <input
              type="checkbox"
              checked={confirmed}
              disabled={busy || dirty}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I reviewed these identities, parameter provenance, budget and locked splits; freeze this
            definition.
          </label>
          <button disabled={busy || dirty || !confirmed} onClick={() => void save(true)}>
            Freeze definition
          </button>
        </>
      )}
      {frozen && <p>This definition is read-only. Future changes require a new definition.</p>}
    </div>
  );
}
