import { useEffect, useRef, useState } from 'react';
import { Alert, Spin } from 'antd';
import { oidcApi, type SignatureChallenge } from '@/api/oidc';
import { signatureMessage } from '@/shared/signatureMessage';
import { authCopy } from '@/shared/authCopy';

/** A dedicated signing surface. Never stores tokens, reloads, or changes authStore. */
export function OidcSignatureFrame({challenge, onVerified, onFailure}: {
  challenge: SignatureChallenge; onVerified: () => void; onFailure: (message: string) => void;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const claimed = useRef(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const listener = (event: MessageEvent) => {
      const result = signatureMessage(event, {origin:challenge.issuer_origin,
        callbackOrigin:window.location.origin, source:frame.current?.contentWindow, state:challenge.state});
      if (!result || claimed.current) return;
      claimed.current = true;
      setBusy(true);
      oidcApi.completeSignature(challenge.challenge_id, result).then(() => {
        if (active) onVerified();
      }).catch(() => {
        if (active) onFailure('再次认证未通过：请使用当前用户重新验证；原登录会话和表单已保留。');
      });
    };
    window.addEventListener('message', listener);
    const timer = window.setTimeout(() => {
      if (active) onFailure('签名挑战已过期，请重新发起认证。');
    }, Math.max(0, Date.parse(challenge.expires_at) - Date.now()));
    return () => { active = false; window.clearTimeout(timer); window.removeEventListener('message', listener); };
  }, [challenge, onVerified, onFailure]);
  return <div>
    <Alert type="info" showIcon message={authCopy.signatureNotice} />
    {busy && <Spin tip="正在核验签名身份" />}
    <iframe ref={frame} title={authCopy.signatureFrameTitle} src={challenge.authorization_url}
      referrerPolicy="no-referrer" style={{width:'100%',height:500,border:0}} />
  </div>;
}
