import { Alert, Button, Modal, Space, message } from 'antd';
import { withBase } from '@/shared/base';

export function EditConflictAlert({ recordPath, onReload }: {
  recordPath: string;
  onReload: () => Promise<void>;
}) {
  return (
    <Alert
      type="warning" showIcon style={{ marginBottom: 16 }}
      message="记录已被更新，您的填写内容已保留"
      description={
        <Space wrap>
          <a href={withBase(recordPath)} target="_blank" rel="noopener noreferrer">新开详情页查看最新记录</a>
          <Button onClick={() => Modal.confirm({
            title: '重新载入最新记录？',
            content: '当前未保存的填写内容将被丢弃，请先核对或保留需要的内容。',
            okText: '确认重新载入', cancelText: '继续保留填写内容',
            onOk: async () => {
              try { await onReload(); } catch { message.error('读取失败，填写内容仍保留'); throw new Error('reload_failed'); }
            },
          })}>重新载入最新记录</Button>
        </Space>
      }
    />
  );
}
