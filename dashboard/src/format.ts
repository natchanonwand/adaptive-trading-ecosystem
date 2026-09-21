export const unavailable = '—';
function scaled(value: unknown, digits: number, shift = 0): string | null {
  if (typeof value !== 'string' && typeof value !== 'number') return null;
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(String(value));
  if (!match) return null;
  const exponent = Number(match[4] ?? 0) + shift + digits - (match[3]?.length ?? 0);
  if (Math.abs(exponent) > 100 || String(value).length > 100) return null;
  let coefficient = BigInt((match[2] ?? '0') + (match[3] ?? ''));
  if (exponent >= 0) coefficient *= 10n ** BigInt(exponent);
  else {
    const divisor = 10n ** BigInt(-exponent);
    coefficient = (coefficient + divisor / 2n) / divisor;
  }
  const raw = coefficient.toString().padStart(digits + 1, '0');
  const whole = (digits ? raw.slice(0, -digits) : raw).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${match[1] && coefficient !== 0n ? '-' : ''}${whole}${digits ? '.' + raw.slice(-digits) : ''}`;
}
export const money = (v: unknown) => {
  const result = scaled(v, 2);
  return result === null
    ? unavailable
    : `${result.startsWith('-') ? '-$' + result.slice(1) : '$' + result}`;
};
export const price = (v: unknown) => scaled(v, 2) ?? unavailable;
export const quantity = (v: unknown) => scaled(v, 4) ?? unavailable;
export const percent = (v: unknown) => {
  const result = scaled(v, 2, 2);
  return result === null ? unavailable : `${result}%`;
};
export const multiple = (v: unknown) => {
  const result = scaled(v, 2);
  return result === null ? unavailable : `${result}R`;
};
export const count = (v: unknown) =>
  typeof v === 'number' && Number.isSafeInteger(v) && v >= 0 ? String(v) : unavailable;
export const label = (v: unknown) => (typeof v === 'string' && v.length ? v : unavailable);
export const timestamp = (v: unknown) =>
  typeof v === 'string' && Number.isFinite(Date.parse(v))
    ? new Date(v).toISOString().replace('T', ' ').replace('.000Z', ' UTC')
    : unavailable;
export const tone = (v: unknown) =>
  typeof v === 'string' && Number.isFinite(Number(v))
    ? Number(v) < 0
      ? 'negative'
      : Number(v) > 0
        ? 'positive'
        : ''
    : '';
export const source = (v: unknown) =>
  v === 'DOMAIN'
    ? 'INTERNAL_STRATEGY'
    : v === 'EXTERNAL_EA'
      ? 'EXTERNAL_EA'
      : v === 'MANUAL'
        ? 'MANUAL'
        : 'UNKNOWN';
