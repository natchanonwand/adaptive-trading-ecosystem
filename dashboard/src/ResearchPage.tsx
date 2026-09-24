import { useEffect, useState } from 'react';
import { object, request } from './api';
import { Badge, Empty, ErrorNotice, Panel } from './components';
import * as f from './format';
import type { Values } from './types';

export function parseResearch(value: unknown): Values {
  const data = object(value);
  if (
    data.read_only !== true ||
    data.verification !== 'VERIFIED_OFFLINE' ||
    !['SYNTHETIC_QUALIFICATION', 'REAL_DEMO_OBSERVATION'].includes(String(data.dataset_type))
  )
    throw new Error('Invalid research provenance');
  if (
    !Array.isArray(data.hypotheses) ||
    !Array.isArray(data.selected_candidates) ||
    !Array.isArray(data.selected_session_ids)
  )
    throw new Error('Invalid research schema');
  if (
    data.dataset_type === 'SYNTHETIC_QUALIFICATION' &&
    (data.status !== 'SOFTWARE_VALIDATION_ONLY' || data.hypotheses.length !== 0)
  )
    throw new Error('Synthetic conclusions are forbidden');
  const measurements = object(object(data.fingerprint).measurements);
  for (const key of ['sample', 'temporal', 'stops', 'volume', 'spacing', 'market_context'])
    object(measurements[key]);
  return data;
}

function Metrics({ data }: { data: Values }) {
  const rows: [string, Values][] = [];
  function visit(value: Values, prefix: string) {
    if ('n' in value && 'known_count' in value && 'missing_count' in value) {
      rows.push([prefix, value]);
    }
    for (const [key, child] of Object.entries(value)) {
      if (child && typeof child === 'object' && !Array.isArray(child))
        visit(object(child), prefix ? `${prefix} / ${key}` : key);
    }
  }
  visit(data, '');
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Measurement</th>
            <th>N</th>
            <th>Known</th>
            <th>Missing</th>
            <th>Rate / median</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, metric]) => (
            <tr key={name}>
              <td>{name || 'Selected sample'}</td>
              <td>{f.count(metric.n)}</td>
              <td>{f.count(metric.known_count)}</td>
              <td>{f.count(metric.missing_count)}</td>
              <td>{f.label(metric.value ?? metric.median)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ResearchPage({ mock = false }: { mock?: boolean }) {
  const [data, setData] = useState<Values | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (mock) return;
    let active = true;
    void request('/api/v1/behavior-research', parseResearch)
      .then((next) => {
        if (active) setData(next);
      })
      .catch(() => {
        if (active)
          setError(
            'Research unavailable. Start the offline research reader with a verified export.',
          );
      });
    return () => {
      active = false;
    };
  }, [mock]);
  const measurements = data ? object(object(data.fingerprint).measurements) : null;
  return (
    <>
      <Panel title="Research Lab" note="Offline deterministic statistics · read only">
        <ErrorNotice message={error} />
        {mock ? (
          <Empty>General dashboard mock is not a behavioral research run.</Empty>
        ) : !data ? (
          <Empty>No verified research run loaded.</Empty>
        ) : (
          <>
            <p className="notice" role="note">
              {data.dataset_type === 'SYNTHETIC_QUALIFICATION'
                ? 'SYNTHETIC QUALIFICATION — NO REAL BEHAVIOR CONCLUSION'
                : 'Descriptive associations only. No strategy classification or automatic qualification.'}
            </p>
            <Badge value={data.status} />
            <dl className="compact-details">
              {Object.entries({
                'Research run': data.run_id,
                'Dataset type': data.dataset_type,
                'EA candidate': (data.selected_candidates as string[]).join(', ') || 'Unknown',
                Sessions: (data.selected_session_ids as string[]).length,
                Episodes: object(measurements?.sample).n,
                'Feature set': data.feature_set_id,
                'Fingerprint version':
                  object(data.fingerprint).fingerprint_version ??
                  object(data.fingerprint).fingerprint_schema_version,
                'Data sufficiency': object(measurements?.sample).sufficiency,
              }).map(([key, value]) => (
                <div key={key} style={{ display: 'contents' }}>
                  <dt>{key}</dt>
                  <dd style={{ overflowWrap: 'anywhere' }}>
                    {typeof value === 'number' ? f.count(value) : f.label(value)}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="muted">
              N and missingness accompany every measurement. Associations do not establish hidden EA
              rules.
            </p>
          </>
        )}
      </Panel>
      {measurements &&
        Object.entries({
          Temporal: 'temporal',
          'SL/TP': 'stops',
          Volume: 'volume',
          'Entry spacing': 'spacing',
          'Market context': 'market_context',
        }).map(([title, key]) => (
          <Panel key={key} title={title} note="Observed sample only">
            <Metrics data={object(measurements[key])} />
          </Panel>
        ))}
    </>
  );
}
