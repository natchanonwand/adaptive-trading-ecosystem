/** Invoked by the PostgreSQL pytest fixture against its real loopback HTTP server. */
import { expect, it } from 'vitest';
import { request, snapshot, streams, telemetry } from '../src/api';
const root = process.env.DASHBOARD_TEST_API;
const stream = process.env.DASHBOARD_TEST_STREAM;
if (!root || !stream || !root.startsWith('http://127.0.0.1:'))
  throw new Error('Local fixture API required');
it('loads real migrated PostgreSQL snapshots through the actual TypeScript client', async () => {
  const catalog = await request(`${root}/api/v1/dashboard/streams?limit=500`, streams);
  expect(catalog.items.some((item) => item.stream_id === stream)).toBe(true);
  const result = await request(`${root}/api/v1/dashboard/snapshot?stream_id=${stream}`, snapshot);
  expect(result.views.account?.items[0]?.values.balance).toBe('10000');
  expect(result.cursor).toBe(1);
  expect(result.errors).toEqual({});
});
it('parses the real Phase 3.5 SSE frame without a browser-side accounting reducer', async () => {
  const response = await fetch(`${root}/api/v1/stream?stream_id=${stream}&after=0&follow=false`);
  const raw = await response.text();
  expect(response.status).toBe(200);
  expect(raw).toContain('event: ACCOUNT_SNAPSHOT');
  const json = raw
    .split('\n')
    .find((line) => line.startsWith('data: '))
    ?.slice(6);
  expect(json).toBeDefined();
  expect(telemetry(JSON.parse(json!)).sequence).toBe(1);
});
