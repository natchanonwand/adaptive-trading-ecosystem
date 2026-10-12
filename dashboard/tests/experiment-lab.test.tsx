import { render, screen, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import { BudgetMeter, ExperimentLab } from '../src/workbench/ExperimentLab';
import type { ExperimentRecord } from '../src/workbench/ExperimentsPanel';

const definition = {
  candidate_id: 'synthetic-candidate',
  hypothesis: 'Explicit synthetic protocol',
  evidence_classification: 'EXPLORATORY_GROSS',
  budget: {
    method: 'RANDOM_SEEDED',
    random_seed: 42,
    maximum_configurations: 4,
    maximum_native_executions: 8,
    maximum_wall_seconds: 60,
    maximum_workers: 1,
  },
  parameter_space: {
    parameters: [
      {
        parameter_name: 'Period',
        native_key: 'Period',
        kind: 'INTEGER',
        baseline: '2',
        minimum: '1',
        maximum: '3',
        step: '1',
        choices: [],
        provenance: 'USER_DECLARATION',
        source_reference: 'Synthetic fixture',
        conditional: null,
      },
    ],
  },
  split_plan: {
    splits: [
      { purpose: 'DEVELOPMENT', start: '2020-01-01', end: '2020-02-01' },
      { purpose: 'VALIDATION', start: '2020-02-01', end: '2020-03-01' },
      { purpose: 'LOCKED_OOS', start: '2020-03-01', end: '2020-04-01' },
    ],
  },
  objectives: [{ metric: 'NET_PROFIT', direction: 'MAXIMIZE', definition: 'Reported result' }],
  constraints: [
    { metric: 'TRADE_COUNT', comparator: 'AT_LEAST', threshold: '0', rationale: 'Explicit floor' },
  ],
  evaluation_method: 'DECLARED_LEXICOGRAPHIC',
};
const frozen: ExperimentRecord = {
  id: 'definition',
  state: 'FROZEN',
  identity: 'a'.repeat(64),
  parameter_space_identity: 'p',
  split_plan_identity: 's',
  campaign_identity: 'c',
  definition,
};
it('renders a research dossier with actual identity and classification', () => {
  render(<ExperimentLab definition={definition} record={frozen} dirty={false} />);
  expect(screen.getByRole('region', { name: 'Experiment Lab' })).toBeTruthy();
  expect(screen.getByText('synthetic-candidate')).toBeTruthy();
  expect(screen.getByText('RANDOM_SEEDED')).toBeTruthy();
  expect(screen.getByText(frozen.identity)).toBeTruthy();
});
it('marks frozen parameter space immutable without edit controls', () => {
  render(<ExperimentLab definition={definition} record={frozen} dirty={false} />);
  expect(screen.getByText(/FROZEN parameter space — immutable/)).toBeTruthy();
  const table = screen.getByRole('table', { name: 'Declared parameter space' });
  expect(within(table).getByText('2')).toBeTruthy();
  expect(within(table).getByText('1 → 3 / step 1')).toBeTruthy();
  expect(screen.queryByRole('textbox')).toBeNull();
});
it('distinguishes editable draft from execution authorization', () => {
  render(<ExperimentLab definition={definition} record={null} dirty />);
  expect(screen.getByText(/DRAFT remains editable/)).toBeTruthy();
  expect(screen.queryByText(frozen.identity)).toBeNull();
});
it('labels saved identities when the visible draft has changed', () => {
  render(<ExperimentLab definition={definition} record={{ ...frozen, state: 'DRAFT' }} dirty />);
  expect(screen.getByText(/Identity refers to the saved version/)).toBeTruthy();
});
it('shows chronological protocol without suggesting actual progress', () => {
  render(<ExperimentLab definition={definition} record={frozen} dirty={false} />);
  const protocol = screen.getByRole('list', { name: 'Research phase sequence' });
  expect(within(protocol).getByText('DEVELOPMENT')).toBeTruthy();
  expect(within(protocol).getByText('SELECTION FROZEN')).toBeTruthy();
  expect(within(protocol).getByText('VALIDATION')).toBeTruthy();
  expect(screen.getByText(/registered protocol, not live execution progress/)).toBeTruthy();
});
it('seals OOS without performance or execution controls', () => {
  render(<ExperimentLab definition={definition} record={frozen} dirty={false} />);
  expect(screen.getByText('🔒 LOCKED OOS · SEALED')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /run|unlock|preview/i })).toBeNull();
  expect(screen.getByText(/Reserved final evaluation data/)).toBeTruthy();
});
it('does not invent campaign usage before it is loaded', () => {
  render(<ExperimentLab definition={definition} record={frozen} dirty={false} />);
  expect(screen.queryByRole('meter')).toBeNull();
  expect(screen.getAllByText('Campaign usage not loaded')).toHaveLength(2);
});
it.each([
  [0, 10, 10],
  [3, 10, 7],
  [10, 10, 0],
])('budget meter uses %i / %i with %i remaining', (used, maximum, remaining) => {
  render(<BudgetMeter label="Execution capacity" used={used} maximum={maximum} />);
  expect(screen.getByRole('meter', { name: 'Execution capacity' })).toHaveAttribute(
    'value',
    String(used),
  );
  expect(screen.getByRole('meter')).toHaveAttribute('max', String(maximum));
  expect(screen.getByText('Remaining').nextElementSibling).toHaveTextContent(String(remaining));
  expect(screen.getByText(/not an execution target/)).toBeTruthy();
});
it('unknown budgets remain unavailable, not zero or animated progress', () => {
  render(<BudgetMeter label="Missing budget" used={null} maximum={null} />);
  expect(screen.getAllByText('—')).toHaveLength(3);
  expect(screen.queryByRole('meter')).toBeNull();
});
it('qualified metrics do not relabel gross evidence as production performance', () => {
  render(<ExperimentLab definition={definition} record={frozen} dirty={false} />);
  expect(screen.getByText('NET_PROFIT · TRADE_COUNT · PROFIT_FACTOR')).toBeTruthy();
  expect(screen.getByText(/Not cost-modeled or production-qualified/)).toBeTruthy();
  expect(screen.getByText('EXPLORATORY_GROSS')).toBeTruthy();
});
it('preserves unqualified stored objective values with a clear limitation', () => {
  render(
    <ExperimentLab
      definition={{ ...definition, objectives: [{ metric: 'RETURN_R' }] }}
      record={frozen}
      dirty={false}
    />,
  );
  expect(screen.getByText('RETURN_R')).toBeTruthy();
  expect(screen.getByText('Unqualified — execution fails closed')).toBeTruthy();
});
it('renders absent parameters without synthesizing ranges', () => {
  render(<ExperimentLab definition={{}} record={null} dirty />);
  expect(screen.getByText('No parameter values declared.')).toBeTruthy();
  expect(screen.queryByText('Period')).toBeNull();
});
it('shows categorical choices and declared conditional provenance', () => {
  render(
    <ExperimentLab
      definition={{
        ...definition,
        parameter_space: {
          parameters: [
            {
              parameter_name: 'Mode',
              native_key: 'Mode',
              kind: 'CATEGORY',
              baseline: 'A',
              choices: ['A', 'B'],
              provenance: 'USER_DECLARATION',
              source_reference: 'Declared fixture',
              conditional: { native_key: 'Enabled', equals: 'true' },
            },
          ],
        },
      }}
      record={frozen}
      dirty={false}
    />,
  );
  expect(screen.getByText('A · B')).toBeTruthy();
  expect(screen.getByText('Enabled = true')).toBeTruthy();
  expect(screen.getByText('Declared fixture')).toBeTruthy();
});
