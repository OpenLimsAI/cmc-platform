import type { Rule } from 'antd/es/form';

export const passwordRules: Rule[] = [
  { min: 8, message: '密码至少 8 位' },
  { pattern: /^(?=[\s\S]*[A-Z])(?=[\s\S]*[a-z])(?=[\s\S]*[0-9])(?=[\s\S]*[^\p{L}\p{N}\s])[\s\S]*$/u, message: '须包含大写、小写、数字和符号' },
  {
    validator: (_, value: string | undefined) =>
      value && new TextEncoder().encode(value).length > 72
        ? Promise.reject(new Error('密码过长，请缩短（中文等字符占多个字节）'))
        : Promise.resolve(),
  },
];
