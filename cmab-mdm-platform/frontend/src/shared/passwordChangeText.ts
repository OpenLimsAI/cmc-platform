/** The same MDM password has a signing-only purpose when native auth is disabled. */
export function passwordChangeText(mode: 'native' | 'oidc' | null, nativeAllowed: boolean) {
  const oidc = mode === 'oidc';
  const signingOnly = oidc && !nativeAllowed;
  return {
    heading: signingOnly ? '修改审批签名密码' : '修改密码',
    description: signingOnly
      ? '这是 MDM 审批签名密码，不能用于登录，也不是 Casdoor 密码。'
      : oidc ? '这里修改 MDM 本地密码，Casdoor 密码不受影响。' : '修改 MDM 账号密码后需要重新登录。',
    currentLabel: signingOnly ? '当前签名密码' : '当前密码',
    newLabel: signingOnly ? '新签名密码' : '新密码',
    confirmLabel: signingOnly ? '确认新签名密码' : '确认新密码',
    success: oidc
      ? 'MDM 密码已更新，即将退出本应用。请通过 Casdoor 重新进入。'
      : '密码已修改，3 秒后将自动退出登录。请用新密码重新登录。',
    loginNotice: !nativeAllowed
      ? '审批签名密码已更新，请通过统一身份登录重新进入；该密码不能用于登录。'
      : '密码已修改成功，请用新密码登录',
  };
}
