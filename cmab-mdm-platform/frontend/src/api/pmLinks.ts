import { api, unwrap } from './client';

export interface PMProjectLink {
  link: null | {
    link_id: number;
    project_id: number;
    pm_project_id: string;
    pm_project_code: string;
    pm_project_name: string;
    verified_at: string;
    created_at: string;
    created_by: number;
  };
  remote_status: 'unlinked' | 'verified' | 'inactive' | 'missing' | 'not_configured' | 'unavailable';
  reference: null | { id: string; code: string; name: string; status: string; bindable: boolean };
  pm_url: string | null;
}

export const pmLinksApi = {
  get: (code: string) => unwrap<PMProjectLink>(api.get(`/projects/${encodeURIComponent(code)}/pm-link`)),
  bind: (code: string, payload: { pm_project_id: string; change_reason: string }) =>
    unwrap<PMProjectLink>(api.post(`/projects/${encodeURIComponent(code)}/pm-link`, payload)),
  resolve: (pmId: string) => unwrap<{ project_code: string }>(api.get(`/integration/pm-projects/${encodeURIComponent(pmId)}`)),
};
