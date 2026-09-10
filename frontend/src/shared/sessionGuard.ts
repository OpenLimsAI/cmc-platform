/**
 * 会话守卫（全公司统一，各子系统抄这一份）—— 空闲超时 + 主动续期 + 多标签页/多系统同步
 *
 * 规则（与 MDM 会话策略 /auth/session-policy 配合，2026-09-04）：
 *   1. 用户有动作（鼠标/键盘/触摸/滚动）→ 记到 localStorage['cmab_last_active']。
 *      所有子系统同源挂在门户之下，共用这个 key：在 MDM 里点鼠标，LabOps 也算活跃。
 *   2. 每 30 秒看一眼：
 *      - 距最后动作 > idle_timeout_minutes → 清令牌、回登录页（onLogout('idle')）。
 *        不发请求的纯展示页也会被踢。
 *      - 通行证快到期（剩余 < 提前量）且最近有动作 → 静默 refresh；失败 → onLogout('expired')。
 *      - 通行证已过期且最近有动作 → 同样试一次 refresh（比如电脑睡醒）。
 *   3. 监听 storage 事件：别的标签页/子系统清了令牌 → 本页同步退出；换了新令牌 → 本页同步用新的。
 *
 * 不依赖任何 UI 库；MDM 里由 useSessionGuard 挂到主布局。
 */
export const TOKEN_KEY = 'cmab_access_token';
export const LAST_ACTIVE_KEY = 'cmab_last_active';

const TICK_MS = 30_000;
const ACTIVITY_THROTTLE_MS = 10_000;
const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'wheel'] as const;

export type LogoutReason = 'idle' | 'expired' | 'other-tab';

/**
 * 拉不到会话策略时的保守兜底（与 MDM 默认值一致：通行证 15 分钟 / 空闲 30 分钟）。
 * 不写进 policy 变量，这样后续 tick 仍会继续尝试取真实策略。
 */
const FALLBACK_POLICY = { access_token_minutes: 15, idle_timeout_minutes: 30 };

export interface SessionGuardPolicy {
  access_token_minutes: number;
  idle_timeout_minutes: number;
}

export interface SessionGuardOptions {
  getToken: () => string | null;
  /** 拉当前用户生效的策略；失败会在下一 tick 重试 */
  loadPolicy: () => Promise<SessionGuardPolicy>;
  /** 静默续期：成功返回新 access token（调用方负责写回 store） */
  refresh: () => Promise<string>;
  /** 别的标签页换了新令牌时同步到本页 store */
  onTokenReplaced?: (token: string) => void;
  onLogout: (reason: LogoutReason) => void;
}

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

/** 记一次用户活动（登录成功后也要调一次，作为起点） */
export function touchActivity(): void {
  safeSet(LAST_ACTIVE_KEY, String(Date.now()));
}

export function readLastActive(): number {
  const v = Number(safeGet(LAST_ACTIVE_KEY));
  return Number.isFinite(v) && v > 0 ? v : 0;
}

/** 解 JWT 的 exp（毫秒）；解析失败返回 0（当作未知，交给 401 兜底） */
export function tokenExpMs(token: string | null): number {
  if (!token) return 0;
  try {
    const payload = token.split('.')[1];
    const json = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    return typeof json?.exp === 'number' ? json.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

/** 启动守卫；返回停止函数（组件卸载时调） */
export function startSessionGuard(opts: SessionGuardOptions): () => void {
  let policy: SessionGuardPolicy | null = null;
  let loadingPolicy = false;
  let refreshing = false;
  let stopped = false;
  let lastTouch = 0;

  const onActivity = () => {
    const now = Date.now();
    if (now - lastTouch < ACTIVITY_THROTTLE_MS) return;
    lastTouch = now;
    touchActivity();
  };

  const ensurePolicy = async () => {
    if (policy || loadingPolicy) return;
    loadingPolicy = true;
    try {
      policy = await opts.loadPolicy();
    } catch {
      /* 下一 tick 再试 */
    } finally {
      loadingPolicy = false;
    }
  };

  /** 续期一次；失败即按「会话已失效」登出 */
  const tryRefresh = async () => {
    if (refreshing || stopped) return;
    refreshing = true;
    try {
      await opts.refresh();
    } catch {
      if (!stopped) {
        stopped = true;
        opts.onLogout('expired');
      }
    } finally {
      refreshing = false;
    }
  };

  const tick = async () => {
    if (stopped) return;
    const token = opts.getToken();
    if (!token) return;
    const now = Date.now();
    const exp = tokenExpMs(token);

    // 通行证已经过期：此刻去拉会话策略必然 401，不能等拿到策略再决定。
    // 旧写法是「拉不到策略就 return」，于是令牌失效后守卫既不续期也不登出，
    // 页面就一直停在已登录的样子（2026-09-10 负责人反馈「打开门户直接就进来了」，已实测复现）。
    if (exp && exp <= now) {
      await tryRefresh();
      return;
    }

    await ensurePolicy();
    if (stopped) return;
    // 策略暂时拉不到（后端抖动等）就先用保守默认值，保证空闲登出照常生效
    const p = policy ?? FALLBACK_POLICY;

    const lastActive = readLastActive() || now; // 没记录（刚登录的旧数据）按现在算
    if (now - lastActive > p.idle_timeout_minutes * 60_000) {
      stopped = true;
      opts.onLogout('idle');
      return;
    }

    if (!exp) return;
    // 提前量：5 分钟与通行证时长 1/3 取小（通行证 15 分钟 → 提前 5 分钟）
    const aheadMs = Math.min(5 * 60_000, (p.access_token_minutes * 60_000) / 3);
    if (exp - now > aheadMs) return;
    await tryRefresh();
  };

  const onStorage = (e: StorageEvent) => {
    if (e.key !== TOKEN_KEY) return;
    if (!e.newValue) {
      if (!stopped) {
        stopped = true;
        opts.onLogout('other-tab');
      }
      return;
    }
    if (e.newValue !== opts.getToken()) opts.onTokenReplaced?.(e.newValue);
  };

  const onVisible = () => {
    if (document.visibilityState === 'visible') void tick();
  };

  // 起点：进页面算一次活动（否则刚登录就被旧的 last_active 判空闲）
  if (!readLastActive()) touchActivity();
  ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, onActivity, { passive: true }));
  window.addEventListener('storage', onStorage);
  document.addEventListener('visibilitychange', onVisible);
  const timer = window.setInterval(() => void tick(), TICK_MS);
  void tick();

  return () => {
    stopped = true;
    window.clearInterval(timer);
    ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity));
    window.removeEventListener('storage', onStorage);
    document.removeEventListener('visibilitychange', onVisible);
  };
}
