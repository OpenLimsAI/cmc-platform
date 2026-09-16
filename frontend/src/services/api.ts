import axios from 'axios'
import type { DataSource, AttributeMeta, Coverage, ProjectMeta, ReleaseAttribute, ReleaseRequest, ReleaseOptions } from '@/types'
import type { AuthStatus, QapIdentity } from '@/types/auth'
import type { ImportCapabilities, PreviewResponse } from '@/types/imports'
import type { StabilityRequest, StabilityOptions, StabilityPanel } from '@/types/stability'
import { clearSession, getStoredToken, mdmRefresh } from '@/shared/cmabSession'
import { attachSessionInterceptors } from './sessionClient'

// 统一信封类型：后端所有响应为 { data, meta, errors }
export interface Envelope<T = unknown> {
  data: T
  meta: Record<string, unknown>
  errors: ErrorItem[]
}

export interface ErrorItem {
  code: string
  message: string
  detail?: unknown
}

const client = axios.create({ baseURL: '/api/v1', timeout: 120000 })
attachSessionInterceptors(client, { getToken: getStoredToken, refresh: mdmRefresh, clear: clearSession })

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message)
    this.name = 'ApiError'
  }
}

// 只呈现后端业务信息，不把 axios 配置中的令牌、连接地址等带到页面。
client.interceptors.response.use(undefined, async (error) => {
  if (error instanceof ApiError) throw error
  if (axios.isCancel(error)) throw error
  let body = error.response?.data
  if (body instanceof Blob) {
    try { body = JSON.parse(await body.text()) } catch { body = null }
  }
  const status = error.response?.status ?? 0
  const issue = body?.errors?.[0]
  const detail = typeof body?.detail === 'string' ? body.detail : null
  const fallback = status === 0 ? '无法连接服务，请检查连接后重试' : `请求未完成（${status}）`
  throw new ApiError(issue?.message || detail || fallback, status, issue?.code)
})

/** 解析信封：errors 非空则抛出第一个业务错误，否则返回 {data, meta}。 */
async function unwrap<T>(p: Promise<{ data: Envelope<T> }>): Promise<{ data: T; meta: Record<string, unknown> }> {
  const env = (await p).data
  if (env.errors && env.errors.length > 0) {
    const e = env.errors[0]
    throw new Error(`[${e.code}] ${e.message}`)
  }
  return { data: env.data, meta: env.meta }
}

export const api = {
  authStatus: () => unwrap<AuthStatus>(client.get('/auth/status')),
  me: () => unwrap<QapIdentity>(client.get('/auth/me')),
  importCapabilities: () => unwrap<ImportCapabilities>(client.get('/imports/capabilities')),
  downloadTemplate: (code: string) => client.get<Blob>(`/imports/templates/${encodeURIComponent(code)}.xlsx`, { responseType: 'blob' }),
  previewImport: (file: File, templateCode: string, signal?: AbortSignal) => {
    const form = new FormData()
    form.append('file', file)
    form.append('template_code', templateCode)
    return unwrap<PreviewResponse>(client.post('/imports/preview', form, { signal }))
  },
  projects: (signal?: AbortSignal, dataSource: DataSource = 'RD') => unwrap<ProjectMeta[]>(client.get('/meta/projects', { params: { data_source: dataSource }, signal })),
  releaseOptions: (projectId: string, signal?: AbortSignal, dataSource: DataSource = 'RD') => unwrap<ReleaseOptions>(client.get('/analysis/release/options', { params: { project_id: projectId, data_source: dataSource }, signal })),
  lines: (projectId: string, dataSource: DataSource = 'RD') => unwrap<string[]>(client.get('/meta/lines', { params: { project_id: projectId, data_source: dataSource } })),
  attributes: (projectId: string, dataType = 'Release', dataSource: DataSource = 'RD') =>
    unwrap<AttributeMeta[]>(client.get('/meta/attributes', { params: { project_id: projectId, data_type: dataType, data_source: dataSource } })),
  coverage: (projectId?: string, dataSource: DataSource = 'RD') =>
    unwrap<Coverage>(client.get('/meta/coverage', { params: { project_id: projectId, data_source: dataSource } })),
  analyzeRelease: (req: ReleaseRequest, signal?: AbortSignal) => unwrap<ReleaseAttribute[]>(client.post('/analysis/release', req, { signal })),
  stabilityOptions: (req: StabilityRequest, signal?: AbortSignal) => unwrap<StabilityOptions>(client.post('/analysis/stability/options', req, { signal })),
  analyzeStability: (req: StabilityRequest, signal?: AbortSignal) => unwrap<StabilityPanel[]>(client.post('/analysis/stability', req, { signal })),
}

export default client
