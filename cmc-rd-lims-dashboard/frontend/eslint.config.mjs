// ESLint 平面配置（Next.js 16 起 next lint 已移除，直接用 ESLint CLI）
// 接法照官方文档 node_modules/next/dist/docs/01-app/03-api-reference/05-config/03-eslint.md
import { defineConfig, globalIgnores } from "eslint/config"
import nextVitals from "eslint-config-next/core-web-vitals"
import nextTs from "eslint-config-next/typescript"

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
])

export default eslintConfig
