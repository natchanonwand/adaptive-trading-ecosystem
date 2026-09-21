import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import App from '../src/App';
import { mockClient, type Client } from '../src/client';
import { useDashboard } from '../src/hooks';
import { mockSnapshot, MOCK_STREAM } from '../src/mock';

class BrowserSource extends EventTarget {
  static instances: BrowserSource[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    super();
    BrowserSource.instances.push(this);
  }
  close() {}
}
it('marks an old initial snapshot stale immediately instead of making old data look fresh', async () => {
  BrowserSource.instances = [];
  vi.stubGlobal('EventSource', BrowserSource);
  const old = structuredClone(mockSnapshot);
  old.events = old.events.map((e) => ({
    ...e,
    event: { ...e.event, recorded_at: '2020-01-01T00:00:00Z' },
  }));
  const client: Client = { ...mockClient, mock: false, snapshot: async () => old };
  const hook = renderHook(() => useDashboard(client));
  await waitFor(() => expect(hook.result.current.snapshot).not.toBeNull());
  act(() => BrowserSource.instances[0]!.onopen?.());
  expect(hook.result.current.connection).toBe('STALE');
});
it('browser refresh rehydrates authoritative state and subscribes after its cursor', async () => {
  BrowserSource.instances = [];
  vi.stubGlobal('EventSource', BrowserSource);
  localStorage.setItem('adaptive-stream', MOCK_STREAM);
  const client: Client = { ...mockClient, mock: false };
  const hook = renderHook(() => useDashboard(client));
  await waitFor(() => expect(hook.result.current.snapshot?.cursor).toBe(9));
  expect(BrowserSource.instances[0]?.url).toContain('after=9');
});
it('one failed history query leaves the authoritative account summary usable', async () => {
  render(
    <App
      client={{
        ...mockClient,
        collection: async () => {
          throw new Error('API timeout');
        },
      }}
    />,
  );
  expect(await screen.findByText('$128,450.00')).toBeInTheDocument();
  expect(await screen.findByRole('alert')).toHaveTextContent('API timeout');
});
it('backend failure never silently enables mock data', async () => {
  render(
    <App
      client={{
        ...mockClient,
        mock: false,
        streams: async () => {
          throw new Error('Backend unavailable');
        },
      }}
    />,
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('Backend unavailable');
  expect(screen.queryByText(/MOCK DATA/)).not.toBeInTheDocument();
  expect(screen.queryByText('$128,450.00')).not.toBeInTheDocument();
});
