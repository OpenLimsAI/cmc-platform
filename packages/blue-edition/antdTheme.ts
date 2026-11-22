/**
 * MBERP Design System v2.0 — Swiss Clinical Precision Ant Design 5/6 Theme Preset
 *
 * Compatible with both Ant Design v5 (`^5.x`) and Ant Design v6 (`^6.x`) `<ConfigProvider theme={...}>`
 * without introducing a hard runtime import on `antd`, allowing lightweight consumption across
 * heterogeneous Vite / Next.js workspaces in `cmc-platform`.
 */

export const MAIBO_SWISS_TOKENS = {
  colorPrimary: '#1E466B',
  colorPrimaryHover: '#153552',
  colorInfo: '#2563EB',
  controlOutline: 'rgba(37, 99, 235, 0.16)',
  colorSuccess: '#16A34A',
  colorWarning: '#D97706',
  colorError: '#DC2626',
  colorBgLayout: '#F6F8FA',
  colorBgContainer: '#FFFFFF',
  colorBgElevated: '#FFFFFF',
  colorFillAlter: '#F8FAFC',
  colorBorder: '#D8E0E8',
  colorBorderSecondary: '#EEF2F6',
  colorText: '#0F172A',
  colorTextSecondary: '#64748B',
  colorTextTertiary: '#94A3B8',
  borderRadius: 6,
  borderRadiusLG: 6,
  borderRadiusSM: 4,
  lineWidth: 1,
  controlHeight: 34,
  fontSize: 13,
  headerHeight: 56,
  boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
  boxShadowSecondary: '0 4px 12px rgba(15, 23, 42, 0.08)',
  fontFamily:
    "Inter, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
  fontFamilyCode:
    "'JetBrains Mono', 'SF Mono', Menlo, Monaco, Consolas, monospace",
} as const;

export const MAIBO_CHART_PALETTE = [
  '#1E466B',
  '#2563EB',
  '#0D9488',
  '#475569',
  '#D97706',
  '#7C3AED',
  '#DC2626',
] as const;

export interface MaiboAntdThemePreset {
  cssVar?: boolean | { key?: string };
  hashed?: boolean;
  token: {
    colorPrimary: string;
    colorInfo: string;
    controlOutline: string;
    colorSuccess: string;
    colorWarning: string;
    colorError: string;
    colorBgLayout: string;
    colorBgContainer: string;
    colorBgElevated: string;
    colorFillAlter: string;
    colorBorder: string;
    colorBorderSecondary: string;
    colorText: string;
    colorTextSecondary: string;
    colorTextTertiary: string;
    borderRadius: number;
    borderRadiusLG: number;
    borderRadiusSM: number;
    lineWidth: number;
    controlHeight: number;
    fontSize: number;
    boxShadow: string;
    boxShadowSecondary: string;
    fontFamily: string;
    fontFamilyCode: string;
    [key: string]: string | number | boolean | undefined;
  };
  components: {
    Menu: {
      itemSelectedBg: string;
      itemSelectedColor: string;
      itemHoverBg: string;
      itemBorderRadius: number;
      itemHeight: number;
    };
    Table: {
      headerBg: string;
      headerColor: string;
      rowHoverBg: string;
      borderColor: string;
      cellPaddingBlock: number;
      cellPaddingInline: number;
    };
    Card: {
      headerBg: string;
      paddingLG: number;
    };
    Progress: {
      defaultColor: string;
    };
    Button: {
      primaryShadow: string;
      primaryColor: string;
      borderRadius: number;
    };
    Input: {
      borderRadius: number;
    };
    Select: {
      borderRadius: number;
    };
    Tag: {
      borderRadiusSM: number;
    };
    Tabs: {
      horizontalItemGutter: number;
    };
    [componentName: string]: Record<string, string | number | boolean | undefined>;
  };
}

export const maiboSwissAntdTheme: MaiboAntdThemePreset = {
  token: {
    colorPrimary: MAIBO_SWISS_TOKENS.colorPrimary,
    colorInfo: MAIBO_SWISS_TOKENS.colorInfo,
    controlOutline: MAIBO_SWISS_TOKENS.controlOutline,
    colorSuccess: MAIBO_SWISS_TOKENS.colorSuccess,
    colorWarning: MAIBO_SWISS_TOKENS.colorWarning,
    colorError: MAIBO_SWISS_TOKENS.colorError,
    colorBgLayout: MAIBO_SWISS_TOKENS.colorBgLayout,
    colorBgContainer: MAIBO_SWISS_TOKENS.colorBgContainer,
    colorBgElevated: MAIBO_SWISS_TOKENS.colorBgElevated,
    colorFillAlter: MAIBO_SWISS_TOKENS.colorFillAlter,
    colorBorder: MAIBO_SWISS_TOKENS.colorBorder,
    colorBorderSecondary: MAIBO_SWISS_TOKENS.colorBorderSecondary,
    colorText: MAIBO_SWISS_TOKENS.colorText,
    colorTextSecondary: MAIBO_SWISS_TOKENS.colorTextSecondary,
    colorTextTertiary: MAIBO_SWISS_TOKENS.colorTextTertiary,
    borderRadius: MAIBO_SWISS_TOKENS.borderRadius,
    borderRadiusLG: MAIBO_SWISS_TOKENS.borderRadiusLG,
    borderRadiusSM: MAIBO_SWISS_TOKENS.borderRadiusSM,
    lineWidth: MAIBO_SWISS_TOKENS.lineWidth,
    controlHeight: MAIBO_SWISS_TOKENS.controlHeight,
    fontSize: MAIBO_SWISS_TOKENS.fontSize,
    boxShadow: MAIBO_SWISS_TOKENS.boxShadow,
    boxShadowSecondary: MAIBO_SWISS_TOKENS.boxShadowSecondary,
    fontFamily: MAIBO_SWISS_TOKENS.fontFamily,
    fontFamilyCode: MAIBO_SWISS_TOKENS.fontFamilyCode,
  },
  components: {
    Menu: {
      itemSelectedBg: '#EDF3F8',
      itemSelectedColor: '#1E466B',
      itemHoverBg: '#F1F5F9',
      itemBorderRadius: 4,
      itemHeight: 38,
    },
    Table: {
      headerBg: '#F8FAFC',
      headerColor: '#475569',
      rowHoverBg: '#F8FAFC',
      borderColor: '#EEF2F6',
      cellPaddingBlock: 10,
      cellPaddingInline: 14,
    },
    Card: {
      headerBg: '#FFFFFF',
      paddingLG: 18,
    },
    Progress: {
      defaultColor: '#2563EB',
    },
    Button: {
      primaryShadow: 'none',
      primaryColor: '#FFFFFF',
      borderRadius: 4,
    },
    Input: {
      borderRadius: 4,
    },
    Select: {
      borderRadius: 4,
    },
    Tag: {
      borderRadiusSM: 4,
    },
    Tabs: {
      horizontalItemGutter: 24,
    },
  },
};

/** Alias retained for Wave 0/1 roadmap references. */
export const blueEditionAntdTheme = maiboSwissAntdTheme;

export function createMaiboAntdTheme(
  overrides?: {
    token?: Partial<MaiboAntdThemePreset['token']>;
    components?: Partial<MaiboAntdThemePreset['components']>;
  },
): MaiboAntdThemePreset {
  if (!overrides) {
    return maiboSwissAntdTheme;
  }
  const mergedComponents: MaiboAntdThemePreset['components'] = {
    ...maiboSwissAntdTheme.components,
  };
  if (overrides.components) {
    for (const [name, compTokens] of Object.entries(overrides.components)) {
      if (compTokens) {
        mergedComponents[name] = {
          ...(maiboSwissAntdTheme.components[name] ?? {}),
          ...compTokens,
        };
      }
    }
  }
  return {
    token: {
      ...maiboSwissAntdTheme.token,
      ...(overrides.token ?? {}),
    },
    components: mergedComponents,
  };
}
