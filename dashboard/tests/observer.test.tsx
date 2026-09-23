import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ObserverPage, parseObserver } from '../src/ObserverPage';

afterEach(() => vi.unstubAllGlobals());
const session = {
  session_id: 'observer-session',
  environment: 'DEMO',
  config: { symbols: ['BTCUSDm'], candidates: [] },
};
describe('external observer', () => {
  it('keeps general mock data separate', () => {
    render(<ObserverPage mock />);
    expect(screen.getByText(/No external EA observations/)).toBeInTheDocument();
  });
  it('rejects malformed or non-demo responses', () => {
    expect(() =>
      parseObserver({
        sessions: [{ session: { ...session, environment: 'LIVE' } }],
        selected: null,
      }),
    ).toThrow();
    expect(() => parseObserver({ sessions: [], selected: { read_only: false } })).toThrow();
  });
  it('loads a read-only session with explicitly unknown attribution and empty exposure', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ sessions: [{ session, status: 'OBSERVING' }], selected: null }),
        ),
      )
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            sessions: [{ session, status: 'OBSERVING' }],
            selected: {
              session,
              status: 'OBSERVING',
              heartbeat: { at: '2026-09-23T00:00:00Z' },
              read_only: true,
              positions: [],
              activity: [],
              summary: { completed_episodes: 0, excluded_episodes: 1 },
              observed_deals: 1,
              metrics_complete: true,
            },
          }),
        ),
      );
    vi.stubGlobal('fetch', fetch);
    render(<ObserverPage />);
    await screen.findByText(/observer-session/);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'observer-session' } });
    await screen.findByText('UNKNOWN / not registered');
    expect(screen.getByText('No open positions observed.')).toBeInTheDocument();
    expect(screen.getByText('No execution controls')).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  });
  it('reports unavailable source without synthetic fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<ObserverPage />);
    expect(await screen.findByText(/Observer unavailable/)).toBeInTheDocument();
  });
});
