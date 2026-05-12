import { api, unwrap } from './client';
import type { SearchHit } from './types';

export const searchApi = {
  search: (q: string, types?: string, limit = 20) =>
    unwrap<SearchHit[]>(
      api.get('/search', { params: { q, types, limit } })
    ),
};
