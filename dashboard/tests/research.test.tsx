import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ResearchPage, parseResearch } from '../src/ResearchPage';

const metric = { n: 12, known_count: 10, missing_count: 2, median: '1.5' };
const fixture = {
  read_only: true,
  verification: 'VERIFIED_OFFLINE',
  dataset_type: 'SYNTHETIC_QUALIFICATION',
  status: 'SOFTWARE_VALIDATION_ONLY',
  run_id: 'fixture-research',
  feature_set_id: 'fixture-set',
  selected_candidates: ['fixture-EA'],
  selected_session_ids: ['fixture-session'],
  hypotheses: [],
  fingerprint: {
    fingerprint_schema_version: 'BEHAVIOR_FINGERPRINT_V1',
    measurements: {
      sample: { n: 12, sufficiency: 'INSUFFICIENT' },
      temporal: { hour: metric },
      stops: { has_SL: metric },
      volume: { entry_volume: metric },
      spacing: { time: metric },
      market_context: { ema: metric },
    },
  },
};
afterEach(() => vi.unstubAllGlobals());
describe('offline Research Lab', () => {
  it('renders provenance, sample counts and prominent synthetic guard', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture))));
    render(<ResearchPage />);
    expect(
      await screen.findByText(/SYNTHETIC QUALIFICATION — NO REAL BEHAVIOR CONCLUSION/),
    ).toBeInTheDocument();
    expect(screen.getByText('fixture-research')).toBeInTheDocument();
    expect(screen.getByText('Sessions').nextElementSibling).toHaveTextContent('1');
    expect(screen.getByText('Episodes').nextElementSibling).toHaveTextContent('12');
    expect(screen.getAllByText('Known').length).toBe(5);
    expect(screen.getAllByText('Missing').length).toBe(5);
    expect(screen.queryByRole('button', { name: /GPT|AI|Clone|Generate/ })).not.toBeInTheDocument();
  });
  it('has no fake research fallback when offline', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<ResearchPage />);
    expect(await screen.findByText(/Research unavailable/)).toBeInTheDocument();
    expect(screen.queryByText('fixture-research')).not.toBeInTheDocument();
  });
  it('keeps general mock separate from research data', () => {
    render(<ResearchPage mock />);
    expect(screen.getByText(/General dashboard mock is not/)).toBeInTheDocument();
  });
  it('rejects synthetic hypotheses and misleading status', () => {
    expect(() =>
      parseResearch({ ...fixture, hypotheses: [{ status: 'SUPPORTED_BY_CURRENT_SAMPLE' }] }),
    ).toThrow();
    expect(() => parseResearch({ ...fixture, status: 'REAL_QUALIFIED' })).toThrow();
  });
  it('rejects unknown provenance or writable data', () => {
    expect(() => parseResearch({ ...fixture, dataset_type: 'UNKNOWN' })).toThrow();
    expect(() => parseResearch({ ...fixture, read_only: false })).toThrow();
  });
  it('accepts insufficient real-type responses without qualification claim', () => {
    expect(
      parseResearch({
        ...fixture,
        dataset_type: 'REAL_DEMO_OBSERVATION',
        status: 'INSUFFICIENT_DATA',
      }).status,
    ).toBe('INSUFFICIENT_DATA');
  });
});
