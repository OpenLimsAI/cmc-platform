import { api, unwrap } from './client';
import type { GlobalSearchResponse, SearchEntityType } from './types';

export const searchApi = {
  // API-MDM-001 V1.1 §8.3：响应分组结构 {query, total, results: {substance, project, asset, material}}
  search: (
    q: string,
    types?: string | SearchEntityType[],
    limit = 20,
  ) =>
    unwrap<GlobalSearchResponse>(
      api.get('/search', {
        params: {
          q,
          types: Array.isArray(types) ? types.join(',') : types,
          limit,
        },
      })
    ),
};
