import type { FormInstance } from 'antd';
import { message as antdMessage } from 'antd';
import type { AxiosError } from 'axios';
import type { ApiErrorInfo } from '@/api/types';

/**
 * 把后端 `meta.error.details[]` 映射到 Antd Form 字段级错误高亮（+ 字段下错误文字）。
 *
 * 后端约定（main.py request_validation_handler）：
 *   field 形如 "preferred_name" 或 "protein.extinction_coefficient"
 *
 * Antd Form name 既支持字符串 "preferred_name"，也支持数组 ["protein", "extinction_coefficient"]，
 * 这里统一拆成数组。CSS 在 index.css 给 .ant-form-item-has-error 加浅红背景。
 *
 * 用法：
 *   const createMutation = useMutation({
 *     mutationFn: api.create,
 *     onError: (err) => {
 *       if (applyFormErrors(form, err)) return;  // 已映射到字段
 *       antdMessage.error(err?.response?.data?.message ?? '保存失败');
 *     },
 *   });
 *
 * @returns true 表示有字段级错误被映射；caller 应跳过通用 toast
 */
export function applyFormErrors(form: FormInstance, error: unknown): boolean {
  const ax = error as AxiosError<{ meta?: { error?: ApiErrorInfo } }>;
  const details = ax?.response?.data?.meta?.error?.details;
  if (!details || details.length === 0) return false;

  const fieldErrors = details
    .filter((d) => d.field)
    .map((d) => ({
      name: parseFieldPath(d.field!),
      errors: [d.message],
    }));

  if (fieldErrors.length === 0) return false;

  form.setFields(fieldErrors);

  // 滚动到第一个错误字段，体验更顺
  const firstName = fieldErrors[0].name;
  try {
    form.scrollToField(firstName, { behavior: 'smooth', block: 'center' });
  } catch {
    /* form 未挂载时跳过 */
  }

  // 顶部 toast 给个全局提示（不重复列每个字段，因为字段已经红了）
  antdMessage.error(`有 ${fieldErrors.length} 项填写不符合要求，请检查标红字段`);
  return true;
}

/** 把 "protein.extinction_coefficient" 拆成 ["protein","extinction_coefficient"] */
function parseFieldPath(field: string): (string | number)[] {
  return field.split('.').map((seg) => {
    // 数组下标 "team[0].role" 形态：暂不出现；预留兼容
    const idx = parseInt(seg, 10);
    return Number.isNaN(idx) ? seg : idx;
  });
}
