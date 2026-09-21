import { telemetry } from './api';
import { eventTypes, type Connection, type Telemetry } from './types';
export const STALE_MS = 30_000;
export function connectionState(
  connected: boolean,
  updated: number | null,
  now: number,
): Connection {
  if (!connected) return 'DISCONNECTED';
  return updated === null || now - updated > STALE_MS ? 'STALE' : 'CONNECTED';
}
export class EventStream {
  private source: EventSource | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  constructor(
    private stream: string,
    public cursor: number,
    private onEvent: (event: Telemetry) => void,
    private onState: (connected: boolean) => void,
    private onInvalid: (reason: string) => void,
    private factory: (url: string) => EventSource = (url) => new EventSource(url),
  ) {}
  start() {
    if (this.stopped) return;
    this.source = this.factory(
      `/api/v1/stream?stream_id=${encodeURIComponent(this.stream)}&after=${this.cursor}`,
    );
    this.source.onopen = () => this.onState(true);
    this.source.onerror = () => {
      this.source?.close();
      this.onState(false);
      if (!this.stopped) this.timer = setTimeout(() => this.start(), 2000);
    };
    for (const kind of eventTypes)
      this.source.addEventListener(kind, (raw) => {
        try {
          const event = telemetry(JSON.parse((raw as MessageEvent<string>).data));
          if (event.event.event_type !== kind) throw new Error('SSE type mismatch');
          if (event.sequence <= this.cursor) return;
          if (event.sequence !== this.cursor + 1)
            throw new Error('SSE sequence gap; reload required');
          this.cursor = event.sequence;
          this.onEvent(event);
        } catch (error) {
          this.close();
          this.onState(false);
          this.onInvalid(error instanceof Error ? error.message : 'Invalid SSE');
        }
      });
    this.source.addEventListener('monitoring_error', () => {
      this.close();
      this.onState(false);
      this.onInvalid('SSE data unavailable; reload required');
    });
  }
  close() {
    this.stopped = true;
    this.source?.close();
    if (this.timer) clearTimeout(this.timer);
  }
}
