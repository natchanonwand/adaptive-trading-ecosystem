import { useState } from 'react';
import {
  Button,
  Checkbox,
  DataTable,
  MetricCard,
  MetricStrip,
  RetroPanel,
  StatusBadge,
} from './retro';
import { CopyValue } from './ResearchSurfaces';
import type { ExperimentRecord } from './ExperimentsPanel';

type Campaign = {
  id: string;
  status: string;
  consumed_executions: number;
  cancel_requested: boolean;
  plan_identity: string;
  plan: { candidates: { identity: string; assignments: Record<string, string> }[] };
  definition: { budget: { maximum_native_executions: number; maximum_wall_seconds: number } };
  runs: {
    id: string;
    configuration_identity: string;
    purpose: string;
    status: string;
    observation: {
      metrics: Record<string, string | null>;
      evidence_identity: string;
      result_identity: string;
    } | null;
  }[];
  selection: { selected: string[]; decisions: Record<string, string> } | null;
  selection_identity: string | null;
};
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/workbench-api/campaigns' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers:
      body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Workbench-Request': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok)
    throw new Error(
      'Campaign request rejected. Check frozen contract, supported metrics, migration and execution ownership.',
    );
  return response.json() as Promise<T>;
}
export function CampaignPanel({ definition }: { definition: ExperimentRecord }) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  async function inspect() {
    setBusy(true);
    setError('');
    try {
      const value = await api<{ items: Campaign[] }>('?definition_id=' + definition.id);
      setCampaign(value.items[0] ?? null);
      setLoaded(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function action(path: string, body?: unknown) {
    setBusy(true);
    setError('');
    try {
      setCampaign(await api<Campaign>(path, body));
      setConfirmed(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <RetroPanel
      title="Controlled campaign"
      status={campaign?.status ?? (loaded ? 'NOT_CREATED' : 'NOT_LOADED')}
    >
      <p>
        Creating a plan does not execute it. DEVELOPMENT selection is frozen before VALIDATION.
        LOCKED_OOS is unavailable.
      </p>
      <p>No real campaign is authorized by Phase 5C.1 implementation review.</p>
      {!loaded ? (
        <Button disabled={busy} onClick={() => void inspect()}>
          Inspect campaigns
        </Button>
      ) : !campaign ? (
        <Button
          disabled={busy}
          onClick={() =>
            void action('', {
              definition_id: definition.id,
              definition_identity: definition.identity,
              confirmed: true,
            })
          }
        >
          Create campaign plan
        </Button>
      ) : (
        <>
          <CopyValue label="campaign identity" value={campaign.id} />
          <CopyValue label="ordered plan identity" value={campaign.plan_identity} />
          <MetricStrip>
            <MetricCard label="Candidates" value={campaign.plan.candidates.length} />
            <MetricCard
              label="Execution reservations"
              value={campaign.consumed_executions}
              note={`Limit ${campaign.definition.budget.maximum_native_executions}`}
            />
            <MetricCard
              label="DEVELOPMENT recorded"
              value={
                campaign.runs.filter((r) => r.purpose === 'DEVELOPMENT' && r.status !== 'RESERVED')
                  .length
              }
            />
            <MetricCard
              label="VALIDATION recorded"
              value={
                campaign.runs.filter((r) => r.purpose === 'VALIDATION' && r.status !== 'RESERVED')
                  .length
              }
            />
          </MetricStrip>
          <p>
            Wall-time limit: {campaign.definition.budget.maximum_wall_seconds}s. Cancellation
            requested: {String(campaign.cancel_requested)}
          </p>
          <Button disabled={busy} onClick={() => void action('/' + campaign.id)}>
            Refresh campaign
          </Button>
          {['CREATED', 'RUNNING'].includes(campaign.status) && (
            <>
              <Checkbox
                label="I explicitly authorize this frozen campaign's bounded execution or resume."
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <Button
                disabled={busy || !confirmed || campaign.cancel_requested}
                onClick={() => void action('/' + campaign.id + '/start', { confirmed: true })}
              >
                Start / resume campaign
              </Button>
              <Button
                disabled={busy || campaign.cancel_requested}
                onClick={() => void action('/' + campaign.id + '/cancel', { confirmed: true })}
              >
                Cancel campaign
              </Button>
            </>
          )}
          <DataTable
            caption="Frozen candidate configurations"
            columns={['Identity', 'Assignments', 'Development selection']}
          >
            {campaign.plan.candidates.map((c) => (
              <tr key={c.identity}>
                <td>
                  <CopyValue label="configuration identity" value={c.identity} />
                </td>
                <td>
                  {Object.entries(c.assignments).map(([key, value]) => (
                    <div key={key}>
                      {key} = {value}
                    </div>
                  ))}
                </td>
                <td>{campaign.selection?.decisions[c.identity] ?? 'Not selected yet'}</td>
              </tr>
            ))}
          </DataTable>
          <CopyValue label="development selection identity" value={campaign.selection_identity} />
          <DataTable
            caption="Campaign run outcomes"
            columns={['Run', 'Purpose', 'Outcome', 'Evidence / metrics']}
          >
            {campaign.runs.map((r) => (
              <tr key={r.id}>
                <td>
                  <CopyValue label="experiment run identity" value={r.id} />
                </td>
                <td>{r.purpose}</td>
                <td>
                  <StatusBadge status={r.status} />
                </td>
                <td>
                  {r.observation ? (
                    <>
                      <CopyValue label="run evidence" value={r.observation.evidence_identity} />
                      <CopyValue label="result identity" value={r.observation.result_identity} />
                      {Object.entries(r.observation.metrics).map(([k, v]) => (
                        <div key={k}>
                          {k}: {v ?? '—'}
                        </div>
                      ))}
                    </>
                  ) : (
                    'No normalized observation'
                  )}
                </td>
              </tr>
            ))}
          </DataTable>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </RetroPanel>
  );
}
