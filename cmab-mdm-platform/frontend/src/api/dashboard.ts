import { api, unwrap } from './client';
import type { DashboardSummary, GanttProject } from './types';

export const dashboardApi = {
  summary: () => unwrap<DashboardSummary>(api.get('/dashboard/summary')),

  gantt: (project_status?: string) =>
    unwrap<GanttProject[]>(
      api.get('/dashboard/gantt', {
        params: project_status ? { project_status } : undefined,
      }),
    ),
};
