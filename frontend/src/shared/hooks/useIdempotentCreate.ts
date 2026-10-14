import { useRef } from 'react';

function submissionKey(): string {
  // 正式入口目前是内网 HTTP；getRandomValues 可用，randomUUID 未必可用。
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function stableBody(value: unknown): string {
  const normalize = (v: unknown): unknown => {
    if (Array.isArray(v)) return v.map(normalize);
    if (v && typeof v === 'object') return Object.fromEntries(
      Object.entries(v).sort(([a], [b]) => a.localeCompare(b)).map(([k, x]) => [k, normalize(x)]),
    );
    return v;
  };
  return JSON.stringify(normalize(JSON.parse(JSON.stringify(value))));
}

/** 网络结果不明时复用编号；确定失败后允许更正内容另行提交。 */
export function useIdempotentCreate<T, R>(create: (payload: T, key: string) => Promise<R>) {
  const pending = useRef<{ key: string; body: string }>();
  return async (payload: T): Promise<R> => {
    const body = stableBody(payload);
    if (pending.current && pending.current.body !== body) {
      throw new Error('上次提交结果尚未确认，请先用原内容重试');
    }
    const submission = pending.current ?? { key: submissionKey(), body };
    pending.current = submission;
    try {
      const result = await create(payload, submission.key);
      if (pending.current === submission) pending.current = undefined;
      return result;
    } catch (error) {
      const response = (error as { response?: { status: number; data?: { code?: number } } }).response;
      // 40905 可能代表同一提交仍在处理中；保留编号继续核对，不能另开一笔。
      if (response && response.status >= 400 && response.status < 500 && response.data?.code !== 40905) {
        if (pending.current === submission) pending.current = undefined;
      }
      throw error;
    }
  };
}
