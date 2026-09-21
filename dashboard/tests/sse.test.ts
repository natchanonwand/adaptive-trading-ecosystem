import { describe, expect, it, vi } from 'vitest';
import { EventStream } from '../src/sse';
import { mockSnapshot, MOCK_STREAM } from '../src/mock';

class FakeSource extends EventTarget {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  emit(sequence: number) {
    const data = { ...mockSnapshot.events[0]!, sequence };
    this.dispatchEvent(new MessageEvent(data.event.event_type, { data: JSON.stringify(data) }));
  }
}
function setup(cursor = 9) {
  const sources: FakeSource[] = [],
    urls: string[] = [];
  const receive = vi.fn(),
    state = vi.fn(),
    invalid = vi.fn();
  const stream = new EventStream(MOCK_STREAM, cursor, receive, state, invalid, (url) => {
    urls.push(url);
    const fake = new FakeSource();
    sources.push(fake);
    return fake as unknown as EventSource;
  });
  stream.start();
  return { stream, sources, urls, receive, state, invalid };
}
describe('actual named Phase 3.5 SSE protocol', () => {
  it('subscribes after the initial atomic snapshot cursor', () => {
    const s = setup();
    expect(s.urls[0]).toContain('after=9');
    s.sources[0]!.onopen?.();
    expect(s.state).toHaveBeenCalledWith(true);
    s.stream.close();
  });
  it('accepts a contiguous named event update', () => {
    const s = setup();
    s.sources[0]!.emit(10);
    expect(s.receive).toHaveBeenCalledOnce();
    expect(s.stream.cursor).toBe(10);
    s.stream.close();
  });
  it('suppresses duplicate delivery', () => {
    const s = setup();
    s.sources[0]!.emit(10);
    s.sources[0]!.emit(10);
    expect(s.receive).toHaveBeenCalledOnce();
    s.stream.close();
  });
  it('reconnects with the latest cursor in the URL', async () => {
    vi.useFakeTimers();
    const s = setup();
    s.sources[0]!.emit(10);
    s.sources[0]!.onerror?.();
    expect(s.state).toHaveBeenLastCalledWith(false);
    await vi.advanceTimersByTimeAsync(2000);
    expect(s.urls[1]).toContain('after=10');
    s.stream.close();
  });
  it('fails closed on an impossible sequence instead of inventing ordering', () => {
    const s = setup();
    s.sources[0]!.emit(12);
    expect(s.receive).not.toHaveBeenCalled();
    expect(s.invalid).toHaveBeenCalledWith(expect.stringContaining('gap'));
    expect(s.sources[0]!.close).toHaveBeenCalled();
  });
  it('rejects malformed SSE', () => {
    const s = setup();
    s.sources[0]!.dispatchEvent(new MessageEvent('ACCOUNT_SNAPSHOT', { data: '{}' }));
    expect(s.invalid).toHaveBeenCalled();
  });
  it('stops reconnecting after cleanup', async () => {
    vi.useFakeTimers();
    const s = setup();
    s.sources[0]!.onerror?.();
    s.stream.close();
    await vi.advanceTimersByTimeAsync(10000);
    expect(s.sources).toHaveLength(1);
  });
});
