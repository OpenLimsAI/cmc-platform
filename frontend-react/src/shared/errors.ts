/**
 * 统一从 axios 错误中提取后端 detail 信息。
 * 此前各页面内联重复同一段类型断言(12+ 处),收拢到这里。
 */
export function getErrorDetail(err: unknown, fallback: string): string {
  return (
    (err as { response?: { data?: { detail?: string } } })?.response?.data
      ?.detail ?? fallback
  );
}
