import { describe, expect, it, vi } from 'vitest';
import { page, request, snapshot, streams, url } from '../src/api';
import { mockSnapshot, mockStreams } from '../src/mock';

describe('read-only API boundary', () => {
  it('parses a successful response and sends GET', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(mockStreams)));
    vi.stubGlobal('fetch', fetcher);
    expect((await request('/api', streams)).items).toHaveLength(1);
    expect(fetcher).toHaveBeenCalledWith(
      '/api',
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });
  it('reports a timeout', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      (_: string, options: RequestInit) =>
        new Promise((_, reject) => {
          options.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          );
        }),
    );
    const result = expect(request('/api', streams, 50)).rejects.toThrow('API timeout');
    await vi.advanceTimersByTimeAsync(51);
    await result;
  });
  it('reports unavailable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(request('/api', streams)).rejects.toThrow('Backend unavailable');
  });
  it('reports HTTP errors without falling back to fixtures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })));
    await expect(request('/api', streams)).rejects.toThrow('503');
  });
  it('rejects malformed JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not json')));
    await expect(request('/api', streams)).rejects.toThrow('Invalid response');
  });
  it.each([{}, { read_only: true }, { read_only: false, items: [], next_cursor: null }])(
    'rejects missing or writable contracts',
    (value) => expect(() => streams(value)).toThrow(),
  );
  it('rejects numeric money instead of silently accepting float semantics', () => {
    const data = structuredClone(mockSnapshot.views.account!);
    data.items[0]!.values.balance = 0.1;
    expect(() => page(data)).toThrow('financial');
  });
  it('isolates a malformed view without crashing all views', () => {
    const data = { ...mockSnapshot, views: { ...mockSnapshot.views, risk: {} } };
    const result = snapshot(data);
    expect(result.views.risk).toBeNull();
    expect(result.errors.risk).toBe('Invalid response');
    expect(result.views.account).not.toBeNull();
  });
  it('URL encodes filters and never interpolates raw query syntax', () =>
    expect(url('trades', { symbol: 'A&B', after: 0 })).toContain('symbol=A%26B&after=0'));
});
