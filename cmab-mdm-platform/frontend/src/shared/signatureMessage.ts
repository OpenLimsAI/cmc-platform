/** Casdoor popup data is untrusted until source, origin and state all match. */
export function signatureMessage(
  event: { origin: string; source: unknown; data: unknown },
  expected: { origin: string; source: unknown; state: string; callbackOrigin?: string },
): { code: string; state: string } | null {
  if (!expected.source || event.source !== expected.source
      || (event.origin !== expected.origin && event.origin !== expected.callbackOrigin)) return null;
  const message = event.data as { type?: string; data?: { code?: unknown; state?: unknown } } | null;
  const data = message?.data;
  if (message?.type !== 'loginSuccess' || !data || data.state !== expected.state
      || typeof data.code !== 'string' || !data.code || data.code.length > 4096) return null;
  return {code: data.code, state: expected.state};
}
