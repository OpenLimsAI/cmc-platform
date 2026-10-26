import { api, unwrap, unwrapList } from './client';
import type {
  AuditLogItem,
  MaterialBatch,
  MaterialBatchCreatePayload,
  MaterialBatchUpdatePayload,
  MaterialBrief,
  MaterialCreatePayload,
  MaterialDetail,
  MaterialListQuery,
  MaterialUpdatePayload,
} from './types';

export const materialsApi = {
  list: (query: MaterialListQuery = {}) =>
    unwrapList<MaterialBrief>(api.get('/materials', { params: query })),

  get: (code: string) =>
    unwrap<MaterialDetail>(api.get(`/materials/${encodeURIComponent(code)}`)),

  create: (payload: MaterialCreatePayload, submissionKey?: string) =>
    unwrap<MaterialDetail>(api.post('/materials', payload, submissionKey ? { headers: { 'Idempotency-Key': submissionKey } } : undefined)),

  update: (code: string, payload: MaterialUpdatePayload) =>
    unwrap<MaterialDetail>(api.put(`/materials/${encodeURIComponent(code)}`, payload)),

  delete: (code: string, change_reason: string) =>
    api.delete(`/materials/${encodeURIComponent(code)}`, {
      data: { change_reason },
    }),

  auditLogs: (
    code: string,
    query: { page?: number; page_size?: number; include_children?: boolean } = {},
  ) =>
    unwrapList<AuditLogItem>(
      api.get(`/materials/${encodeURIComponent(code)}/audit-logs`, { params: query }),
    ),

  // material_batch (§10.2)
  listBatches: (code: string) =>
    unwrap<MaterialBatch[]>(
      api.get(`/materials/${encodeURIComponent(code)}/batches`),
    ),

  addBatch: (code: string, payload: MaterialBatchCreatePayload) =>
    unwrap<MaterialBatch>(
      api.post(`/materials/${encodeURIComponent(code)}/batches`, payload),
    ),

  updateBatch: (
    code: string,
    batch_id: number,
    payload: MaterialBatchUpdatePayload,
  ) =>
    unwrap<MaterialBatch>(
      api.put(
        `/materials/${encodeURIComponent(code)}/batches/${batch_id}`,
        payload,
      ),
    ),

  deleteBatch: (code: string, batch_id: number, change_reason: string) =>
    api.delete(
      `/materials/${encodeURIComponent(code)}/batches/${batch_id}`,
      { data: { change_reason } },
    ),
};
