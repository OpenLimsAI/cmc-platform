import type { ReactNode } from 'react';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';

export function ApplicationTheme({ children }: { children: ReactNode }) {
  return <ConfigProvider locale={zhCN} theme={{
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: '#1e466b',
      colorInfo: '#2563eb',
      controlOutline: 'rgba(37, 99, 235, 0.16)',
      colorSuccess: '#16a34a',
      colorWarning: '#d97706',
      colorError: '#dc2626',
      colorBgLayout: '#f6f8fa',
      colorBgContainer: '#ffffff',
      colorBgElevated: '#ffffff',
      colorFillAlter: '#f8fafc',
      colorBorder: '#d8e0e8',
      colorBorderSecondary: '#eef2f6',
      colorText: '#0f172a',
      colorTextSecondary: '#64748b',
      colorTextTertiary: '#94a3b8',
      borderRadius: 6,
      borderRadiusLG: 6,
      borderRadiusSM: 4,
      controlHeight: 34,
      boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
      boxShadowSecondary: '0 4px 12px rgba(15, 23, 42, 0.08)',
      fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    },
    components: {
      Menu: {
        itemSelectedBg: '#edf3f8',
        itemSelectedColor: '#1e466b',
        itemHoverBg: '#f1f5f9',
        itemBorderRadius: 4,
        itemHeight: 38,
      },
      Table: {
        headerBg: '#f8fafc',
        headerColor: '#475569',
        rowHoverBg: '#f8fafc',
        borderColor: '#eef2f6',
      },
      Card: { headerBg: 'transparent' },
      Progress: { defaultColor: '#2563eb' },
      Button: { primaryShadow: 'none', primaryColor: '#ffffff' },
      Tabs: { horizontalItemGutter: 24 },
    },
  }}>{children}</ConfigProvider>;
}

