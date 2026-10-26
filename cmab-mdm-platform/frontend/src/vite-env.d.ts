/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_VERSION?: string;
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** 构建标识，由 vite.config.ts buildIdPlugin 注入（见 src/shared/appUpdate.tsx） */
declare const __APP_BUILD_ID__: string;
