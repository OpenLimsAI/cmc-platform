import { Result } from 'antd';

interface PlaceholderProps {
  title?: string;
}

export function PlaceholderPage({ title = '功能开发中' }: PlaceholderProps) {
  return <Result icon={<div style={{ fontSize: 64 }}>🚧</div>} title={title} subTitle="该模块将在后续 Phase 上线" />;
}
