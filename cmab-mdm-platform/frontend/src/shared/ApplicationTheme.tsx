import type { ReactNode } from 'react';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';

export function ApplicationTheme({ children }: { children: ReactNode }) {
  return <ConfigProvider locale={zhCN} theme={{
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: '#1e466b',
      colorInfo: '#1e466b',
      controlOutline: 'rgba(103, 186, 244, 0.22)',
      colorSuccess: '#2c7750',
      colorBgLayout: '#fafafa',
      colorBgContainer: '#ffffff',
      colorBgElevated: '#ffffff',
      colorFillAlter: '#f6f8fb',
      colorBorder: '#e0e6ed',
      colorBorderSecondary: '#e0e6ed',
      colorText: '#0d0d0d',
      colorTextSecondary: '#607184',
      colorTextTertiary: '#65788a',
      borderRadius: 8,
      borderRadiusLG: 12,
      controlHeight: 36,
      boxShadow: '0 8px 28px rgba(30, 70, 107, 0.08)',
      boxShadowSecondary: '0 6px 24px rgba(30, 70, 107, 0.08)',
      fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    },
    components: {
      Menu: {
        itemSelectedBg: '#edf5fb',
        itemSelectedColor: '#1e466b',
        itemHoverBg: '#edf5fb',
        itemBorderRadius: 8,
        itemHeight: 42,
      },
      Table: {
        headerBg: '#f6f8fb',
        headerColor: '#607184',
        rowHoverBg: '#f4f8fc',
        borderColor: '#e0e6ed',
      },
      Card: { headerBg: 'transparent' },
      Progress: { defaultColor: '#67baf4' },
      Button: { primaryShadow: 'none', primaryColor: '#ffffff' },
      Tabs: { horizontalItemGutter: 24 },
    },
  }}>{children}</ConfigProvider>;
}

