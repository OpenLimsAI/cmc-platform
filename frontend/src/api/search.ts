import { api, unwrap } from './client';
import type { GlobalSearchResponse } from './types';

export const searchApi = {
  // API-MDM-001 V1.1 §8.3：响应分组结构 {query, total, results: {substance, project, asset}}
  search: (q: string, types?: string, limit = 20) =>
    unwrap<GlobalSearchResponse>(
      api.get('/search', { params: { q, types, limit } })
    ),
};
