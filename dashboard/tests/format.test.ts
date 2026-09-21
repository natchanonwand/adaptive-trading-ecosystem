import { describe, expect, it } from 'vitest';
import * as f from '../src/format';
import { connectionState } from '../src/sse';

describe('formatting observes null, units and exact decimal display', () => {
  it.each([null, undefined, '', 'invalid', NaN])('keeps unavailable %s distinct from zero', (v) => {
    expect(f.money(v)).toBe('—');
    expect(f.percent(v)).toBe('—');
  });
  it.each([
    ['0', '$0.00'],
    ['1234.5', '$1,234.50'],
    ['-12.34', '-$12.34'],
    ['9007199254740993.12', '$9,007,199,254,740,993.12'],
    ['1e3', '$1,000.00'],
    ['-0.001', '$0.00'],
  ])('formats %s as %s without binary rounding', (input, output) =>
    expect(f.money(input)).toBe(output),
  );
  it('uses explicit fractional policy units', () => {
    expect(f.percent('0.0025')).toBe('0.25%');
    expect(f.multiple('1.25')).toBe('1.25R');
    expect(f.quantity('0.01')).toBe('0.0100');
  });
  it('preserves observed zero counts', () => {
    expect(f.count(0)).toBe('0');
    expect(f.count(null)).toBe('—');
  });
  it('uses UTC timestamps', () =>
    expect(f.timestamp('2026-09-17T05:00:00+07:00')).toBe('2026-09-16 22:00:00 UTC'));
  it.each([
    ['DOMAIN', 'INTERNAL_STRATEGY'],
    ['EXTERNAL_EA', 'EXTERNAL_EA'],
    ['MANUAL', 'MANUAL'],
    ['ADAPTER', 'UNKNOWN'],
    [null, 'UNKNOWN'],
  ])('maps source %s honestly', (value, expected) => expect(f.source(value)).toBe(expected));
});
describe('UI staleness is distinct from domain risk', () => {
  it('shows fresh observations as connected', () =>
    expect(connectionState(true, 1000, 2000)).toBe('CONNECTED'));
  it('shows old data as stale even on an open transport', () =>
    expect(connectionState(true, 1000, 32000)).toBe('STALE'));
  it('shows disconnect irrespective of data age', () =>
    expect(connectionState(false, 1000, 2000)).toBe('DISCONNECTED'));
  it('never treats missing freshness as fresh', () =>
    expect(connectionState(true, null, 0)).toBe('STALE'));
});
