/**
 * 统一从 axios 错误中提取后端 detail 信息。
 * 此前各页面内联重复同一段类型断言(12+ 处),收拢到这里。
 */
export function getErrorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  // FastAPI 422 校验错误的 detail 是对象数组,直接丢给 message.error 渲染会崩页面
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean);
    if (msgs.length) return msgs.join("；");
  }
  return fallback;
}
