import type { Readiness } from './ReadinessPanel';
export type Artifact = { artifact_id: string; filename: string; sha256: string; size: number };
export type Binding = {
  broker_name: string;
  environment: 'DEMO';
  canonical_asset: string;
  broker_symbol: string;
  timeframe: string;
  symbol_confirmed: boolean;
};
export type Candidate = {
  product_name: string;
  version: string;
  vendor: string;
  source_reference: string;
  license_status: string;
  tester_access_status: string;
  known_magic_number: number | null;
  known_order_comments: string;
  notes: string;
  catalog_id: string | null;
  artifact_id: string | null;
  manual_id: string | null;
  candidate_id?: string;
  artifact_filename?: string;
  artifact_sha256?: string;
  artifact_size?: number;
  manual_filename?: string;
  manual_sha256?: string;
  manual_size?: number;
};
export type Project = {
  project_id: string;
  project_name: string;
  source_type: string;
  candidate_id: string;
  status: string;
  updated_at: string;
  broker_binding: Binding;
  product_name?: string;
};
export type Detail = Partial<Readiness> & {
  readiness_enabled?: boolean;
  research_environment?: {
    status: string;
    binding?: {
      terminal_executable: string;
      company: string;
      terminal_build: string;
      terminal_data_root: string;
    };
  };
  baseline_enabled?: boolean;
  project: Project;
  candidate: Candidate;
  verification: Record<string, string>;
  baseline_status: string;
  execution_available: false;
};
export type Catalog = {
  catalog_id: string;
  product_name: string;
  asset: string;
  research_class: string;
  source_reference: string;
};

export async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/workbench-api/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers:
      body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Workbench-Request': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok)
    throw new Error(
      response.status === 503
        ? 'Workbench storage is unavailable. Please try again.'
        : 'Could not save or load this item. Check the metadata and file, then retry.',
    );
  return response.json() as Promise<T>;
}

export async function upload(file: File, role: 'EA' | 'MANUAL'): Promise<Artifact> {
  if (!file.size || file.size > 16 * 1024 * 1024)
    throw new Error('Choose a non-empty file up to 16 MB.');
  if (!file.name.toLowerCase().endsWith(role === 'EA' ? '.ex5' : '.pdf'))
    throw new Error(role === 'EA' ? 'Choose an EX5 file.' : 'Choose a PDF manual.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  let encoded = '';
  for (let i = 0; i < bytes.length; i += 8192)
    encoded += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return request<Artifact>('artifacts', { filename: file.name, role, data_base64: btoa(encoded) });
}
