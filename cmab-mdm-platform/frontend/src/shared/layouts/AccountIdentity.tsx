import type { LoginResponseUser } from '@/api/types';
import { ROLE_LABELS } from '@/modules/admin/constants';

type AccountUser = Pick<LoginResponseUser, 'username' | 'roles' | 'displayName' | 'identityUsername'> & { full_name?: string };

/** Display business identity only; never infer privileges from an IdP role. */
export function AccountIdentity({ user }: { user: AccountUser | null }) {
  const unifiedUsername = user?.identityUsername?.trim();
  const name = (unifiedUsername ? user?.displayName?.trim() || unifiedUsername : user?.full_name?.trim()) || user?.username || '未登录';
  const identity = !unifiedUsername && user?.username && user.username !== name ? `${name} (${user.username})` : name;
  const roles = user?.roles.length ? [...new Set(user.roles)].map((role) => ROLE_LABELS[role] || role).join('、') : '未分配角色';
  return <span className="mdm-account-identity" title={unifiedUsername ? `统一身份账号：${unifiedUsername}` : undefined}>
    <span className="mdm-account-avatar" aria-hidden="true">{Array.from(name)[0]}</span>
    <span className="mdm-account-copy">
      <span className="mdm-account-name">{identity}</span>
      <span className="mdm-account-role">{roles}</span>
    </span>
  </span>;
}
