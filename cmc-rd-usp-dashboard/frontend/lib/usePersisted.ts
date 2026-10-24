"use client";

// 把一份 React 状态同步存到浏览器本地（localStorage），刷新页面后原样恢复。
// 用法同 useState：const [v, setV] = usePersisted("key", 默认值)。
// - 首次渲染先用默认值（和服务端渲染保持一致，避免闪烁/不匹配），挂载后再从本地读回；
// - 读回之前不往本地写，免得把默认值覆盖掉已存的；
// - 本地存储不可用（隐私模式等）时静默退化为普通 useState。
import { useEffect, useState } from "react";

const PREFIX = "usp_dashboard:";

export function usePersisted<T>(key: string, initial: T): [T, React.Dispatch<React.SetStateAction<T>>, boolean] {
  const [value, setValue] = useState<T>(initial);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      if (raw != null) setValue(JSON.parse(raw) as T);
    } catch {
      /* 存的东西坏了或不可用：用默认值 */
    }
    setReady(true);
  }, [key]);

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  }, [key, value, ready]);

  return [value, setValue, ready];
}
