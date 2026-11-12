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
        colorPrimary: dark ? '#67baf4' : '#1e466b',
        colorInfo: dark ? '#67baf4' : '#1e466b',
        controlOutline: 'rgba(103, 186, 244, 0.22)',
        colorSuccess: dark ? '#83cba0' : '#2c7750',
        colorBgLayout: dark ? '#0d1722' : '#fafafa',
        colorBgContainer: dark ? '#142536' : '#ffffff',
        colorBgElevated: dark ? '#142536' : '#ffffff',
        colorFillAlter: dark ? '#203e57' : '#f6f8fb',
        colorBorder: dark ? '#30475c' : '#e0e6ed',
        colorBorderSecondary: dark ? '#30475c' : '#e0e6ed',
        colorText: dark ? '#f2f6fa' : '#0d0d0d',
        colorTextSecondary: dark ? '#b9cbdc' : '#607184',
        colorTextTertiary: dark ? '#9ab0c4' : '#65788a',
        borderRadius: 8,
        borderRadiusLG: 12,
        controlHeight: 36,
        boxShadow: '0 8px 28px rgba(30, 70, 107, 0.08)',
        boxShadowSecondary: '0 6px 24px rgba(30, 70, 107, 0.08)',
        fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
      },
      components: {
        Menu: {
          itemSelectedBg: dark ? '#203e57' : '#edf5fb',
          itemSelectedColor: dark ? '#67baf4' : '#1e466b',
          itemHoverBg: dark ? '#203e57' : '#edf5fb',
          itemBorderRadius: 8,
          itemHeight: 42,
        },
        Table: {
          headerBg: dark ? '#203e57' : '#f6f8fb',
          headerColor: dark ? '#b9cbdc' : '#607184',
          rowHoverBg: dark ? '#203e57' : '#f4f8fc',
          borderColor: dark ? '#30475c' : '#e0e6ed',
        },
        Card: { headerBg: 'transparent' },
        Progress: { defaultColor: '#67baf4' },
        Button: { primaryShadow: 'none', primaryColor: dark ? '#0d1722' : '#ffffff' },
        Tabs: { horizontalItemGutter: 24 },
      },
    }}>{children}</ConfigProvider>
  </ApplicationThemeContext.Provider>;
}

