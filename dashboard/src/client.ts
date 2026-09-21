import * as api from './api';
import { mockCalendar, mockHistory, mockSnapshot, mockStreams, mockTrades } from './mock';
import type { Calendar, Page, Snapshot, Streams } from './types';
export interface Client {
  mock: boolean;
  streams(after?: string): Promise<Streams>;
  snapshot(stream: string): Promise<Snapshot>;
  collection(
    name: 'history' | 'trades' | 'positions',
    stream: string,
    filters?: Record<string, string | number | undefined>,
  ): Promise<Page>;
  calendar(stream: string, month: string): Promise<Calendar>;
}
export function monthWindow(month: string) {
  const next = new Date(`${month}-01T00:00:00Z`);
  next.setUTCMonth(next.getUTCMonth() + 1);
  return { start: `${month}-01`, end: next.toISOString().slice(0, 10) };
}
export const realClient: Client = {
  mock: false,
  streams: (after) => api.request(api.url('streams', { after, limit: 100 }), api.streams),
  snapshot: (stream_id) => api.request(api.url('snapshot', { stream_id }), api.snapshot),
  collection: (name, stream_id, filters = {}) =>
    api.request(
      api.url(name, { stream_id, limit: name === 'history' ? 200 : 50, ...filters }),
      api.page,
    ),
  calendar: (stream_id, month) =>
    api.request(api.url('calendar', { stream_id, ...monthWindow(month) }), api.calendar),
};
export const mockClient: Client = {
  mock: true,
  streams: async () => mockStreams,
  snapshot: async () => mockSnapshot,
  collection: async (name) =>
    name === 'history'
      ? mockHistory
      : name === 'positions'
        ? mockSnapshot.views.positions!
        : mockTrades,
  calendar: async (_, month) => mockCalendar(month),
};
