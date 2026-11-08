import { useEffect, useState, type ReactNode } from 'react';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { ApplicationThemeContext } from './applicationThemeContext';

const THEME_KEY = 'maibo.application.theme';

function savedDarkTheme() {
  try { return localStorage.getItem(THEME_KEY) === 'dark'; } catch { return false; }
}

export function ApplicationTheme({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(savedDarkTheme);
  useEffect(() => {
    document.documentElement.dataset.mdmTheme = dark ? 'dark' : 'light';
    return () => { delete document.documentElement.dataset.mdmTheme; };
  }, [dark]);
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key === THEME_KEY || event.key === null) setDark(savedDarkTheme());
    };
    window.addEventListener('storage', changed);
    return () => window.removeEventListener('storage', changed);
  }, []);
  const toggleTheme = () => setDark((current) => {
    const next = !current;
    try { localStorage.setItem(THEME_KEY, next ? 'dark' : 'light'); } catch { /* Keep this page usable when browser storage is unavailable. */ }
    return next;
  });
  return <ApplicationThemeContext.Provider value={{ dark, toggleTheme }}>
    <ConfigProvider locale={zhCN} theme={{
      algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
      token: {
        colorPrimary: '#1F4E79',
        borderRadius: 4,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
      },
    }}>{children}</ConfigProvider>
  </ApplicationThemeContext.Provider>;
}

