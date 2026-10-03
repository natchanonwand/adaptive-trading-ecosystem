import { useState } from 'react';
import { request } from './api';

type Summary = {
  configuration_id: string;
  status: string;
  authorization: string;
  artifact: string;
  execution_strategy: string;
  profile_binding: string;
  research_environment: string;
  baseline_configuration: string;
  native_config_dry_run: string;
  license: string;
  tester_access: string;
  observed_tester_access: string;
  execution_available: false;
};

export function CandidateReadiness({
  projectId,
  configurationId,
}: {
  projectId: string;
  configurationId: string;
}) {
  const [summary, setSummary] = useState<Summary>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return (
    <section aria-label="Candidate execution readiness">
      <h4>Candidate execution readiness</h4>
      <p>
        Check the selected configuration without starting MT5 or creating a run. Readiness does not
        verify license acceptance, tester access, initialization or performance.
      </p>
      <button
        disabled={!configurationId || busy}
        onClick={async () => {
          setBusy(true);
          setSummary(undefined);
          setError('');
          try {
            const value = await request<Summary>(
              'baseline-candidate-readiness?' +
                new URLSearchParams({ project_id: projectId, configuration_id: configurationId }),
            );
            setSummary(value);
          } catch {
            setError('Candidate readiness could not be verified. No execution started.');
          } finally {
            setBusy(false);
          }
        }}
      >
        Check candidate readiness (dry run)
      </button>
      {error && <p role="alert">{error}</p>}
      {summary && summary.configuration_id === configurationId && (
        <>
          <p role="status">{summary.status}</p>
          <dl>
            {(
              [
                ['Authorization', summary.authorization],
                ['Artifact', summary.artifact],
                ['Execution strategy', summary.execution_strategy],
                ['Profile binding', summary.profile_binding],
                ['Research environment', summary.research_environment],
                ['Baseline configuration', summary.baseline_configuration],
                ['Native configuration', summary.native_config_dry_run],
                ['Declared license', summary.license],
                ['Declared tester access', summary.tester_access],
                ['Observed tester access', summary.observed_tester_access],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <p>
            Environment evidence is historical. A later authorized acceptance requires fresh
            identity and account checks. This dry run does not enable the Run Baseline button.
          </p>
        </>
      )}
    </section>
  );
}
