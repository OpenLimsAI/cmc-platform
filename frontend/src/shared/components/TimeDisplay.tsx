import { Tooltip } from 'antd';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

interface TimeDisplayProps {
  value?: string | null;
  /** 默认 'relative'：显示相对时间并 hover 显示绝对时间 */
  format?: 'relative' | 'datetime' | 'date';
}

export function TimeDisplay({ value, format = 'relative' }: TimeDisplayProps) {
  if (!value) return <span className="text-disabled">—</span>;
  const m = dayjs(value);
  const abs = m.format('YYYY-MM-DD HH:mm:ss');

  if (format === 'datetime') return <span>{m.format('YYYY-MM-DD HH:mm')}</span>;
  if (format === 'date') return <span>{m.format('YYYY-MM-DD')}</span>;

  return (
    <Tooltip title={abs}>
      <span>{m.fromNow()}</span>
    </Tooltip>
  );
}
