import { useEffect } from 'react';
import { Alert } from 'antd';

/** Dedicated callback: no login bootstrap, tokens, cookie changes or form reload. */
export function SignatureCallbackPage() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    window.history.replaceState(null, '', window.location.pathname);
    if (window.parent !== window && code && code.length <= 4096 && state && state.length <= 128 && !params.has('error')) {
      window.parent.postMessage({type:'loginSuccess',data:{code,state}},window.location.origin);
    }
  }, []);
  return <Alert type="info" message="签名认证结果仅交回原 MDM 签名表单；此页不会建立登录会话。" />;
}
