import { Button, Col, Form, Input, Row, Select, Space, Typography } from 'antd';
import { CloudDownloadOutlined } from '@ant-design/icons';

const { Text } = Typography;

// UniProt accession 官方正则（与后端 schemas.UNIPROT_ACCESSION_RE 一致）
export const UNIPROT_ACCESSION_RE = /^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$/i;

interface Props {
  /** 传入则显示「拉取」按钮：按 UniProt accession 自动预填（新建页用）*/
  onFetchUniprot?: (accession: string) => void;
  fetching?: boolean;
  /** 已从 UniProt 拉取成功：标准字段只读，手填字段收起 */
  fetched?: boolean;
  /** 编辑模式：accession 不可改（要换号请新建/重新拉取）*/
  lockAccession?: boolean;
}

/**
 * 靶点表单（新建 / 编辑共用）。
 * 0051 起：靶点字段对齐 UniProt 标准，全部由「拉取」自动带出；这里只有
 *   - UniProt accession（唯一需要人输入的）
 *   - 兜底字段（名称 / 基因 / 物种 / 别名 / 描述）—— 仅在没有 UniProt 号的特殊靶点时手填
 *   - 备注
 */
export function TargetFormFields({ onFetchUniprot, fetching, fetched, lockAccession }: Props) {
  const form = Form.useFormInstance();
  const doFetch = () => {
    const v = (form.getFieldValue('uniprot_id') as string | undefined)?.trim().toUpperCase();
    if (!v || !UNIPROT_ACCESSION_RE.test(v)) {
      form.setFields([{ name: 'uniprot_id', errors: ['请先填写合法的 UniProt accession（如 Q15116）'] }]);
      return;
    }
    onFetchUniprot?.(v);
  };
  return (
    <>
      <Row gutter={16}>
        <Col span={10}>
          <Form.Item
            label="UniProt accession"
            required={!lockAccession}
            extra={
              lockAccession
                ? '编码锚点不可改；UniProt 内容有更新请用详情页「从 UniProt 重新拉取」'
                : '填好后点「拉取」或回车，其余字段自动带出。已存在（含次级/旧号）会提示去建关联'
            }
          >
            <Space.Compact style={{ width: '100%' }}>
              <Form.Item
                name="uniprot_id"
                noStyle
                rules={[
                  {
                    validator: (_, v: string | undefined) =>
                      !v || UNIPROT_ACCESSION_RE.test(v.trim())
                        ? Promise.resolve()
                        : Promise.reject(new Error('不是合法的 UniProt accession（如 Q15116 / P04626）')),
                  },
                ]}
                normalize={(v?: string) => v?.trim().toUpperCase()}
              >
                <Input
                  placeholder="Q15116"
                  disabled={lockAccession}
                  onPressEnter={onFetchUniprot ? doFetch : undefined}
                  style={{ fontFamily: 'monospace' }}
                />
              </Form.Item>
              {onFetchUniprot && (
                <Button type="primary" icon={<CloudDownloadOutlined />} loading={fetching} onClick={doFetch}>
                  拉取
                </Button>
              )}
            </Space.Compact>
          </Form.Item>
        </Col>
      </Row>

      {/* 兜底字段：无 UniProt 号（非蛋白/未收录靶点）时才需要手填；拉取成功后收起（值仍在表单里） */}
      {!fetched && (
        <>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            没有 UniProt 号的特殊靶点，才需要在下面手填名称/基因/物种；有 UniProt 号请直接「拉取」。
          </Text>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="target_name" label="靶点名称" rules={[{ required: true, message: '请填写靶点名称或先拉取 UniProt' }, { max: 255 }]}>
                <Input placeholder="Programmed cell death protein 1" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="gene_symbol" label="基因符号" rules={[{ max: 64 }]}>
                <Input placeholder="PDCD1" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="organism" label="物种" rules={[{ max: 128 }]}>
                <Input placeholder="Homo sapiens" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="aliases" label="别名">
            <Select mode="tags" tokenSeparators={[',', ';']} placeholder="回车添加多个" open={false} />
          </Form.Item>
          <Form.Item name="description" label="功能描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </>
      )}

      <Form.Item name="notes" label="备注（人工）">
        <Input.TextArea rows={2} placeholder="内部约定叫法、项目备注等" />
      </Form.Item>
    </>
  );
}
