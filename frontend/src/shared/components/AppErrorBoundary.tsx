/**
 * 全局错误兜底（2026-09-10）：页面组件渲染/懒加载抛错时不再整页空白。
 *
 * 场景 1：部署后浏览器还拿着旧版 index.html，懒加载的页面脚本已改名 →
 *   "Failed to fetch dynamically imported module" / "Importing a module script failed"。
 *   处理：自动整页刷新一次拿新版（sessionStorage 记一次，60 秒内不重复刷，防止死循环）。
 * 场景 2：其他运行时错误 → 显示错误卡片 + 「重新加载」按钮，而不是白页。
 *
 * 配合 nginx（deploy/nginx/linux-host/cmab-mdm.conf）：index.html no-cache、assets/ 长缓存。
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button, Result } from 'antd';

const CHUNK_ERROR_RE =
  /Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk [\w-]+ failed|Loading CSS chunk/i;
const RELOAD_KEY = 'cmab_mdm_chunk_reload_at';
const RELOAD_WINDOW_MS = 60_000;

export function isChunkLoadError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err ?? '');
  return CHUNK_ERROR_RE.test(msg);
}

/** 60 秒内只自动刷新一次；返回是否已触发刷新 */
function reloadOnceForChunkError(): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? '0');
    if (Date.now() - last < RELOAD_WINDOW_MS) return false;
    sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
  } catch {
    /* sessionStorage 不可用也照样刷新一次 */
  }
  window.location.reload();
  return true;
}

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  reloading: boolean;
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null, reloading: false };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (isChunkLoadError(error)) {
      const reloading = reloadOnceForChunkError();
      this.setState({ reloading });
      return;
    }
    console.error('[AppErrorBoundary]', error, info.componentStack);
  }

  render() {
    const { error, reloading } = this.state;
    if (!error) return this.props.children;
    if (reloading) return null; // 正在整页刷新，什么都不画

    const chunk = isChunkLoadError(error);
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px 16px' }}>
        <Result
          status={chunk ? 'warning' : 'error'}
          title={chunk ? '系统刚更新了版本，需要重新加载' : '页面出错了'}
          subTitle={
            chunk
              ? '浏览器里还是旧版本的页面文件，点下面按钮重新加载即可（不会丢失登录状态）。'
              : error.message
          }
          extra={
            <Button type="primary" onClick={() => window.location.reload()}>
              重新加载
            </Button>
          }
        />
      </div>
    );
  }
}
