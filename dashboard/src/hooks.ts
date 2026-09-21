import { useCallback, useEffect, useState } from 'react';
import type { Client } from './client';
import { connectionState, EventStream } from './sse';
import type { Snapshot, Streams, Telemetry } from './types';

export function useResource<T>(load: () => Promise<T>, enabled = true) {
  const [state, set] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });
  useEffect(() => {
    let active = true;
    set({ data: null, error: null, loading: enabled });
    if (enabled)
      void load()
        .then((data) => {
          if (active) set({ data, error: null, loading: false });
        })
        .catch((error: unknown) => {
          if (active)
            set({
              data: null,
              error: error instanceof Error ? error.message : 'Invalid response',
              loading: false,
            });
        });
    return () => {
      active = false;
    };
  }, [load, enabled]);
  return state;
}
export function useDashboard(client: Client) {
  const [catalog, setCatalog] = useState<Streams | null>(null);
  const [stream, setStream] = useState('');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [events, setEvents] = useState<Telemetry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [updated, setUpdated] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let active = true;
    void client
      .streams()
      .then((result) => {
        if (!active) return;
        setCatalog(result);
        setError(null);
        let saved: string | null = null;
        try {
          saved = localStorage.getItem('adaptive-stream');
        } catch {
          /* Storage is optional. */
        }
        setStream(
          (current) =>
            current ||
            (result.items.find((item) => item.stream_id === saved)?.stream_id ??
              result.items[0]?.stream_id ??
              ''),
        );
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : 'Backend unavailable');
      });
    return () => {
      active = false;
    };
  }, [client, reload]);
  useEffect(() => {
    let active = true,
      busy = false,
      dirty = false;
    let session: EventStream | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    setSnapshot(null);
    setEvents([]);
    setConnected(false);
    setUpdated(null);
    if (!stream) return;
    try {
      localStorage.setItem('adaptive-stream', stream);
    } catch {
      /* Storage is optional. */
    }
    const refresh = async (initial: boolean) => {
      if (!active) return;
      if (busy) {
        dirty = true;
        return;
      }
      busy = true;
      try {
        const data = await client.snapshot(stream);
        if (!active) return;
        setSnapshot(data);
        setError(null);
        if (initial) {
          setEvents(data.events);
          setUpdated(
            data.events.reduce<number | null>(
              (latest, event) => Math.max(latest ?? 0, Date.parse(event.event.recorded_at)),
              null,
            ),
          );
          if (client.mock) setConnected(true);
          else {
            session = new EventStream(
              stream,
              data.cursor,
              (event) => {
                if (!active) return;
                setUpdated(Date.parse(event.event.recorded_at));
                setEvents((old) =>
                  [...old.filter((v) => v.sequence !== event.sequence), event].slice(-50),
                );
                if (!timer)
                  timer = setTimeout(() => {
                    timer = null;
                    void refresh(false);
                  }, 1000);
              },
              (value) => {
                if (active) setConnected(value);
              },
              (reason) => {
                if (active) setError(reason);
              },
            );
            session.start();
          }
        }
      } catch (e) {
        if (active) {
          setError(e instanceof Error ? e.message : 'Backend unavailable');
          setConnected(false);
        }
      } finally {
        busy = false;
        if (dirty && active) {
          dirty = false;
          timer = setTimeout(() => {
            timer = null;
            void refresh(false);
          }, 1000);
        }
      }
    };
    void refresh(true);
    return () => {
      active = false;
      session?.close();
      if (timer) clearTimeout(timer);
    };
  }, [client, stream, reload]);
  const moreStreams = useCallback(async () => {
    if (!catalog?.next_cursor) return;
    try {
      const next = await client.streams(catalog.next_cursor);
      setCatalog({ ...next, items: [...catalog.items, ...next.items] });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Backend unavailable');
    }
  }, [catalog, client]);
  return {
    catalog,
    stream,
    setStream,
    snapshot,
    events,
    error,
    connection: client.mock ? ('CONNECTED' as const) : connectionState(connected, updated, now),
    updated,
    now,
    refresh: () => setReload((v) => v + 1),
    moreStreams,
  };
}
