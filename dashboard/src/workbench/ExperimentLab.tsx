import { CopyValue } from './ResearchSurfaces';
import { DataTable, RetroPanel, StatusBadge } from './retro';
import type { ExperimentRecord } from './ExperimentsPanel';

export const qualifiedMetrics = ['NET_PROFIT', 'TRADE_COUNT', 'PROFIT_FACTOR'];
const object = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
const rows = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value) ? value.map(object) : [];
const scalar = (value: unknown): string =>
  value === null || value === undefined || value === '' ? '—' : String(value);

export function BudgetMeter({
  label,
  used,
  maximum,
}: {
  label: string;
  used: number | null;
  maximum: number | null;
}) {
  const valid = maximum !== null && maximum > 0;
  const remaining = valid && used !== null ? Math.max(0, maximum - used) : null;
  return (
    <div className="lab-budget-meter">
      <h4>{label}</h4>
      <dl>
        <div>
          <dt>Used</dt>
          <dd>{scalar(used)}</dd>
        </div>
        <div>
          <dt>Remaining</dt>
          <dd>{scalar(remaining)}</dd>
        </div>
        <div>
          <dt>Max</dt>
          <dd>{scalar(maximum)}</dd>
        </div>
      </dl>
      {valid && used !== null ? (
        <meter aria-label={label} min={0} max={maximum} value={used} />
      ) : (
        <p className="rt-help">
          {used === null ? 'Campaign usage not loaded' : 'Set a positive budget'}
        </p>
      )}
      <p className="rt-help">Unused capacity is a limit, not an execution target.</p>
    </div>
  );
}

export function ExperimentLab({
  definition,
  record,
  dirty,
}: {
  definition: Record<string, unknown>;
  record: ExperimentRecord | null;
  dirty: boolean;
}) {
  const budget = object(definition.budget);
  const parameters = rows(object(definition.parameter_space).parameters);
  const splits = rows(object(definition.split_plan).splits);
  const objectives = rows(definition.objectives);
  const constraints = rows(definition.constraints);
  const frozen = record?.state === 'FROZEN';
  return (
    <div className="lab-overview">
      <RetroPanel title="Experiment Lab" status={record?.state ?? 'DRAFT'}>
        <p className="rt-label">Controlled research / experiment dossier</p>
        <p>
          {scalar(definition.hypothesis) === '—'
            ? 'Define a research hypothesis before freezing the protocol.'
            : scalar(definition.hypothesis)}
        </p>
        <dl className="lab-header-facts">
          <div>
            <dt>Candidate</dt>
            <dd>
              <CopyValue
                label="Lab candidate identity"
                value={typeof definition.candidate_id === 'string' ? definition.candidate_id : null}
              />
            </dd>
          </div>
          <div>
            <dt>Search method</dt>
            <dd>{scalar(budget.method)}</dd>
          </div>
          <div>
            <dt>Evidence classification</dt>
            <dd>{scalar(definition.evidence_classification)}</dd>
          </div>
        </dl>
        <CopyValue label="Lab definition identity" value={record?.identity ?? null} />
        {dirty && record && (
          <p>Identity refers to the saved version. The current draft has unsaved changes.</p>
        )}
        <p>
          {frozen
            ? 'FROZEN parameter space — immutable; a revision requires a new definition.'
            : 'DRAFT remains editable. READY is freeze-review readiness, not permission to execute.'}
        </p>
      </RetroPanel>
      <RetroPanel title="Research protocol" status="LOCKED_OOS">
        <ol className="lab-protocol" aria-label="Research phase sequence">
          <li>
            <strong>DEVELOPMENT</strong>
            <span>Declared search and constraint evaluation</span>
          </li>
          <li>
            <strong>SELECTION FROZEN</strong>
            <span>Required checkpoint before validation</span>
          </li>
          <li>
            <strong>VALIDATION</strong>
            <span>Selected configurations only; no search feedback</span>
          </li>
          <li className="lab-oos">
            <strong>🔒 LOCKED OOS · SEALED</strong>
            <span>
              Reserved final evaluation data. No performance preview or execution control.
            </span>
          </li>
        </ol>
        <div className="lab-split-register">
          {splits.map((split, i) => (
            <div key={i}>
              <strong>{scalar(split.purpose)}</strong>
              <span>
                {scalar(split.start)} → {scalar(split.end)}
              </span>
              <small>Start inclusive · end exclusive</small>
            </div>
          ))}
        </div>
        <p className="rt-help">This is the registered protocol, not live execution progress.</p>
      </RetroPanel>
      <RetroPanel title="Parameter space register" status={frozen ? 'FROZEN' : 'DRAFT'}>
        <DataTable
          caption="Declared parameter space"
          columns={[
            'Name / native key',
            'Type',
            'Baseline',
            'Range / choices',
            'Provenance',
            'Condition',
          ]}
        >
          {parameters.map((p, i) => (
            <tr key={i}>
              <td>
                {scalar(p.parameter_name)}
                <br />
                <code>{scalar(p.native_key)}</code>
              </td>
              <td>{scalar(p.kind)}</td>
              <td>{scalar(p.baseline)}</td>
              <td>
                {Array.isArray(p.choices) && p.choices.length
                  ? p.choices.map(scalar).join(' · ')
                  : `${scalar(p.minimum)} → ${scalar(p.maximum)} / step ${scalar(p.step)}`}
              </td>
              <td>
                <span>{scalar(p.provenance)}</span>
                <br />
                <span>{scalar(p.source_reference)}</span>
              </td>
              <td>
                {p.conditional
                  ? `${scalar(object(p.conditional).native_key)} = ${scalar(object(p.conditional).equals)}`
                  : p.conditional === null
                    ? 'Unconditional'
                    : '—'}
              </td>
            </tr>
          ))}
        </DataTable>
        {!parameters.length && <p>No parameter values declared.</p>}
      </RetroPanel>
      <RetroPanel title="Research budget">
        <div className="lab-budget-grid">
          <BudgetMeter
            label="Candidate configurations"
            used={null}
            maximum={
              typeof budget.maximum_configurations === 'number'
                ? budget.maximum_configurations
                : null
            }
          />
          <BudgetMeter
            label="Native execution reservations"
            used={null}
            maximum={
              typeof budget.maximum_native_executions === 'number'
                ? budget.maximum_native_executions
                : null
            }
          />
        </div>
        <p>
          Seed: {scalar(budget.random_seed)} · Wall-time limit:{' '}
          {scalar(budget.maximum_wall_seconds)} seconds · Workers: {scalar(budget.maximum_workers)}
        </p>
        <p>
          Usage appears only after inspecting persisted campaign evidence. Reservations may include
          blocked preparations.
        </p>
      </RetroPanel>
      <RetroPanel title="Objectives and hard constraints">
        <p>
          Qualified adapter metrics: <strong>NET_PROFIT · TRADE_COUNT · PROFIT_FACTOR</strong>
        </p>
        <p>
          <StatusBadge status="EXPLORATORY_GROSS" /> only. Not cost-modeled or production-qualified.
          NET_PROFIT is the native report metric name; it does not change the evidence
          classification.
        </p>
        <DataTable
          caption="Declared objectives"
          columns={['Metric', 'Direction', 'Definition', 'Adapter support']}
        >
          {objectives.map((o, i) => (
            <tr key={i}>
              <td>{scalar(o.metric)}</td>
              <td>{scalar(o.direction)}</td>
              <td>{scalar(o.definition)}</td>
              <td>
                {qualifiedMetrics.includes(String(o.metric))
                  ? 'Qualified for EXPLORATORY_GROSS'
                  : 'Unqualified — execution fails closed'}
              </td>
            </tr>
          ))}
        </DataTable>
        <DataTable
          caption="Declared hard constraints"
          columns={['Metric', 'Comparator', 'Threshold', 'Rationale']}
        >
          {constraints.map((c, i) => (
            <tr key={i}>
              <td>{scalar(c.metric)}</td>
              <td>{scalar(c.comparator)}</td>
              <td>{scalar(c.threshold)}</td>
              <td>{scalar(c.rationale)}</td>
            </tr>
          ))}
        </DataTable>
        <p>
          Evaluation: {scalar(definition.evaluation_method)}. Constraints precede objective ranking.
          Zero is measured; — is unavailable.
        </p>
      </RetroPanel>
    </div>
  );
}
