/**
 * 「部署后旧标签页自动刷新」（2026-09-10，全公司前端统一做法；母本在 cmab-mdm-platform frontend/src/shared/appUpdate.tsx，这里是 LabOps 的一份）。
 *
 * 问题：部署新版后，用户早就开着的标签页还在跑旧代码；旧标签页还会被「多标签页同步登录」带着登进去，
 *       然后按旧逻辑跳页、调接口，被新后端拒绝。用户在别的标签页刷新也救不了这个旧标签页。
 * 做法：构建时注入 __APP_BUILD_ID__（vite.config.ts buildIdPlugin）并在 dist/ 写 version.json。
 *       本组件每 60 秒、切回本标签页、以及别的标签页登录/登出时，去拿 version.json 比对：
 *         - 登录页 / 未登录 / 别的标签页刚登录（页面状态本来就要重来）→ 立即刷新
 *         - 正在用的页面 → 右下角提示「系统已更新」并给按钮，且下一次切换页面时自动刷新（此时没有未提交的表单）
 * 依赖：nginx 对 version.json 走 no-cache（index.html 同一条规则），dev 由 vite 插件伺服。
 */
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { Button, notification } from "antd";

declare const __APP_BUILD_ID__: string;

const BUILD_ID: string = typeof __APP_BUILD_ID__ !== "undefined" ? __APP_BUILD_ID__ : "dev";
const BASE = import.meta.env.BASE_URL; // 以 / 结尾，如 "/mdm/"
const TOKEN_KEY = "cmab_access_token";
const POLL_MS = 60_000;
const NOTICE_KEY = "cmab-app-updated";

async function fetchServerBuildId(): Promise<string | null> {
  try {
    const r = await fetch(`${BASE}version.json?_=${Date.now()}`, { cache: "no-store", credentials: "same-origin" });
    if (!r.ok) return null;
    const j = (await r.json()) as { build_id?: unknown };
    return typeof j.build_id === "string" ? j.build_id : null;
  } catch {
    return null;
  }
}

export function AppUpdateWatcher() {
  const location = useLocation();
  const stale = useRef(false);
  const notified = useRef(false);
  const firstRender = useRef(true);

  useEffect(() => {
    let disposed = false;
    const reload = () => window.location.reload();

    const check = async (reason: "poll" | "visible" | "storage") => {
      if (disposed || stale.current) return;
      const server = await fetchServerBuildId();
      if (disposed || !server || server === BUILD_ID) return;
      stale.current = true;
      const onLoginPage = window.location.pathname.startsWith(`${BASE}login`);
      const hasToken = !!localStorage.getItem(TOKEN_KEY);
      if (reason === "storage" || onLoginPage || !hasToken) {
        reload();
        return;
      }
      if (!notified.current) {
        notified.current = true;
        notification.warning({
          key: NOTICE_KEY,
          message: "系统已更新",
          description: "当前页面还是旧版本。切换页面时会自动刷新；也可以现在点按钮刷新。",
          btn: (
            <Button type="primary" size="small" onClick={reload}>
              立即刷新
            </Button>
          ),
          duration: 0,
          placement: "bottomRight",
        });
      }
    };

    const timer = window.setInterval(() => void check("poll"), POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void check("visible");
    };
    const onStorage = (e: StorageEvent) => {
      // 别的标签页登录/登出 → 本页会被同步带着切换状态，若代码已过期就趁现在刷新
      if (e.key === TOKEN_KEY) void check("storage");
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    window.addEventListener("storage", onStorage);
    void check("poll");
    return () => {
      disposed = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  // 已知过期：下一次切换页面就刷新（换页的瞬间没有未提交的表单）
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    if (stale.current) window.location.reload();
  }, [location.pathname]);

  return null;
}
