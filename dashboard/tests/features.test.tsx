import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FeaturePage, parseFeatures } from '../src/FeaturePage';

afterEach(() => vi.unstubAllGlobals());
describe('offline feature quality', () => {
  it('does not invent datasets from general mock', () => {
    render(<FeaturePage mock />);
    expect(screen.getByText(/General dashboard mock/)).toBeInTheDocument();
  });
  it('rejects mutable and unknown-provenance responses', () => {
    expect(() => parseFeatures({ read_only: false })).toThrow();
    expect(() =>
      parseFeatures({ read_only: true, status: 'VERIFIED_OFFLINE', dataset_type: 'UNKNOWN' }),
    ).toThrow();
  });
  it('shows synthetic provenance and explicit missingness', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            read_only: true,
            status: 'VERIFIED_OFFLINE',
            dataset_type: 'SYNTHETIC_QUALIFICATION',
            feature_set_id: 'fixture-v1',
            sessions: 1,
            causal_feature_count: 74,
            outcome_field_count: 26,
            real_ea_qualification: 'NOT_PROVIDED',
            datasets: { episode_features: { rows: 2, columns: 86 } },
            missingness: { h1_ema200: 2 },
            source_confidence: { counts: { KNOWN: 2 } },
          }),
        ),
      ),
    );
    render(<FeaturePage />);
    expect(await screen.findByText('SYNTHETIC_QUALIFICATION')).toBeInTheDocument();
    expect(screen.getByText('h1_ema200')).toBeInTheDocument();
    expect(screen.getByText('NOT_PROVIDED')).toBeInTheDocument();
  });
  it('shows unavailable status without fabricated values', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<FeaturePage />);
    expect(await screen.findByText(/Feature dataset unavailable/)).toBeInTheDocument();
  });
});
