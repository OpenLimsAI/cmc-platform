import { api, unwrap } from './client';

export interface PMCreateProject {
  code: string;
  name: string;
  product_type: string;
  current_stage: string;
  target_stage: string;
  owner_id: string;
  planned_start: string;
  planned_end: string;
  description?: string;
}
export interface PMCreateOperation {
  request_id: string;
  project_code: string;
  status: 'pending' | 'in_progress' | 'retryable_error' | 'remote_created' | 'linked' | 'reconciliation_required';
  attempts: number;
  created_at: string;
  updated_at: string;
  remote_project_id: string | null;
  last_error: string | null;
  can_retry: boolean;
  project: PMCreateProject;
  link: null | { link_id: number; pm_project_id: string };
  pm_url: string | null;
}
export interface PMCreateState { operation: PMCreateOperation | null }
export interface PMOwnerOptions {
  items: { id: string; display_name: string }[];
  current_user_id: string;
  options: { product_types: string[]; stages: string[] };
}
const path = (code: string) => `/projects/${encodeURIComponent(code)}/pm-create`;
export const pmCreateApi = {
  get: (code: string) => unwrap<PMCreateState>(api.get(path(code))),
  create: (code: string, payload: { client_request_id: string; change_reason: string; project: PMCreateProject }) => unwrap<PMCreateState>(api.post(path(code), payload)),
  retry: (code: string) => unwrap<PMCreateState>(api.post(`${path(code)}/retry`)),
  owners: () => unwrap<PMOwnerOptions>(api.get('/integration/pm/owners')),
};
