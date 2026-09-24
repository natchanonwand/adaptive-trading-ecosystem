import { useEffect, useState } from 'react';
import { object, request } from './api';
import { Badge, Empty, ErrorNotice, Panel } from './components';
import * as f from './format';
import type { Values } from './types';

export function parseFeatures(value: unknown): Values {
  const data = object(value);
  if (
    data.read_only !== true ||
    data.status !== 'VERIFIED_OFFLINE' ||
    !['SYNTHETIC_QUALIFICATION', 'REAL_DEMO_OBSERVATION'].includes(String(data.dataset_type))
  )
    throw new Error('Invalid feature dataset');
  object(data.datasets);
  object(data.missingness);
  object(object(data.source_confidence).counts);
  return data;
}

export function FeaturePage({ mock = false }: { mock?: boolean }) {
  const [data, setData] = useState<Values | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (mock) return;
    let active = true;
    void request('/api/v1/features', parseFeatures)
      .then((next) => {
        if (active) setData(next);
      })
      .catch(() => {
        if (active) setError('Feature dataset unavailable. Start the offline feature reader.');
      });
    return () => {
      active = false;
    };
  }, [mock]);
  return (
    <>
      <Panel title="Feature data quality" note="Offline measurements · read only">
        <p className="notice">
          Entry features and outcomes are separate. Synthetic qualification is not evidence of EA
          performance.
        </p>
        <ErrorNotice message={error} />
        {mock ? (
          <Empty>General dashboard mock does not represent a feature dataset.</Empty>
        ) : !data ? (
          <Empty>No verified feature dataset loaded.</Empty>
        ) : (
          <>
            <Badge value={data.status} />
            <dl className="compact-details">
              <dt>Dataset type</dt>
              <dd>{f.label(data.dataset_type)}</dd>
              <dt>Feature set</dt>
              <dd style={{ overflowWrap: 'anywhere' }}>{f.label(data.feature_set_id)}</dd>
              <dt>Sessions</dt>
              <dd>{f.count(data.sessions)}</dd>
              <dt>Causal feature count</dt>
              <dd>{f.count(data.causal_feature_count)}</dd>
              <dt>Outcome field count</dt>
              <dd>{f.count(data.outcome_field_count)}</dd>
              <dt>Real EA qualification</dt>
              <dd>{f.label(data.real_ea_qualification)}</dd>
            </dl>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th>Rows</th>
                    <th>Columns</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(object(data.datasets)).map(([name, value]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{f.count(object(value).rows)}</td>
                      <td>{f.count(object(value).columns)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
      {data && (
        <Panel title="Missingness and source quality" note="Unknown values remain null, never zero">
          <p>
            Source confidence:{' '}
            {Object.entries(object(object(data.source_confidence).counts))
              .map(([name, value]) => `${name}: ${String(value)}`)
              .join(', ') || '—'}
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Missing rows</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(object(data.missingness)).map(([name, count]) => (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{f.count(count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
}
