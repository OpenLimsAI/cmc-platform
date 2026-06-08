/* ESLint 配置（ESLint 8 legacy 风格，配合 package.json "lint": eslint . --ext ts,tsx）
 * 基线策略：类型/未使用变量等已由 tsc(strict + noUnusedLocals) 兜底，
 * 这里只补 lint 层面 tsc 管不到的规则（React Hooks 依赖、HMR 边界）。
 * no-explicit-any 等暂关，避免对现有代码做大范围重构（后续可逐步收紧）。 */
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  plugins: ['@typescript-eslint', 'react-refresh'],
  ignorePatterns: ['dist', 'node_modules', 'vite.config.ts', '*.cjs', 'src/api/schema.d.ts'],
  rules: {
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    // tsc 已覆盖，关掉避免与 noUnusedLocals/noUnusedParameters 重复报
    '@typescript-eslint/no-unused-vars': 'off',
    // 现有代码大量使用 err: any / payload as any，过渡期暂关，避免大范围改写
    '@typescript-eslint/no-explicit-any': 'off',
    // antd 表单/事件回调常用空对象与非空断言，过渡期放宽
    '@typescript-eslint/no-non-null-assertion': 'off',
    '@typescript-eslint/ban-ts-comment': 'warn',
  },
};
