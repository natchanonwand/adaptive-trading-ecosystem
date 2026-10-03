import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CandidateReadiness } from '../src/workbench/CandidateReadiness';

afterEach(() => vi.unstubAllGlobals());

const ready = {
  configuration_id: 'existing-config',
  status: 'CANDIDATE_EXECUTION_READY',
  authorization: 'VERIFIED_USER_ATTESTATION',
  artifact: 'VERIFIED',
  execution_strategy: 'INSTALLED_PROFILE_REFERENCE',
  profile_binding: 'VERIFIED',
  research_environment: 'READY_AS_OBSERVED',
  baseline_configuration: 'READY',
  native_config_dry_run: 'VERIFIED_DRY_RUN_NO_LAUNCH',
  license: 'UNKNOWN',
  tester_access: 'UNKNOWN',
  observed_tester_access: 'UNKNOWN',
  execution_available: false,
};

it('requires an explicitly selected persisted configuration', () => {
  render(<CandidateReadiness projectId="project" configurationId="" />);
  expect(screen.getByRole('button')).toBeDisabled();
});

it('checks readiness using only GET and keeps UNKNOWN distinct from READY', async () => {
  const fetcher = vi.fn(async () => ({ ok: true, json: async () => ready }));
  vi.stubGlobal('fetch', fetcher);
  render(<CandidateReadiness projectId="project" configurationId="existing-config" />);
  fireEvent.click(screen.getByRole('button'));
  expect(await screen.findByRole('status')).toHaveTextContent('CANDIDATE_EXECUTION_READY');
  expect(screen.getByText('INSTALLED_PROFILE_REFERENCE')).toBeInTheDocument();
  expect(screen.getAllByText('UNKNOWN')).toHaveLength(3);
  expect(screen.getByText(/does not enable the Run Baseline/)).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledExactlyOnceWith(
    '/workbench-api/baseline-candidate-readiness?project_id=project&configuration_id=existing-config',
    expect.objectContaining({ method: 'GET', body: undefined }),
  );
});

it('does not display readiness for a different configuration', async () => {
  const fetcher = vi.fn(async () => ({ ok: true, json: async () => ready }));
  vi.stubGlobal('fetch', fetcher);
  render(<CandidateReadiness projectId="project" configurationId="other-config" />);
  fireEvent.click(screen.getByRole('button'));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

it('shows precise blockers and no private runtime details', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        ...ready,
        status: 'BLOCKED_CANDIDATE_PROFILE_MISMATCH',
        expert_path: 'PRIVATE_PATH',
      }),
    })),
  );
  render(<CandidateReadiness projectId="project" configurationId="existing-config" />);
  fireEvent.click(screen.getByRole('button'));
  expect(await screen.findByRole('status')).toHaveTextContent('BLOCKED_CANDIDATE_PROFILE_MISMATCH');
  expect(screen.queryByText('PRIVATE_PATH')).not.toBeInTheDocument();
});

it('fails closed on unavailable proof without offering an execution action', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: false, status: 503 })),
  );
  render(<CandidateReadiness projectId="project" configurationId="existing-config" />);
  fireEvent.click(screen.getByRole('button'));
  expect(await screen.findByRole('alert')).toHaveTextContent('No execution started');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.getAllByRole('button')).toHaveLength(1);
});
