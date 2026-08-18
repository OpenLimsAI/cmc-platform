import { Button, Col, Form, Input, Row, Select, Space, Typography } from 'antd';
import { CloudDownloadOutlined } from '@ant-design/icons';
import type { TargetPrefillHints } from '@/api/targets';
import { TARGET_LOCATION_OPTIONS, TARGET_TYPE_OPTIONS } from '../constants';

const { Text } = Typography;

interface Props {
  /** 传入则显示「拉取」按钮：按 UniProt accession 自动预填（新建页用；编辑页不传）*/
  onFetchUniprot?: (accession: string) => void;
  fetching?: boolean;
  /** 上次拉取返回的依据（类型/定位为启发式建议）*/
  hints?: TargetPrefillHints | null;
}

// UniProt accession 官方正则（与后端 schemas.UNIPROT_ACCESSION_RE 一致）
export const UNIPROT_ACCESSION_RE = /^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$/i;

/**
 * 靶点表单字段（新建 / 编辑共用）。
 * 一期不做外部 API 预填向导：由 `app.scripts.prefill_targets` 离线产出预填 JSON，
 * 人工对照 summary.md 在此表单核对录入（决策 #7）。
 */
export function TargetFormFields({ onFetchUniprot, fetching, hints }: Props) {
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
        <Col span={12}>
          <Form.Item
            name="target_name"
            label="靶点名称"
            rules={[{ required: true, message: '请填写靶点名称' }, { max: 255 }]}
            extra="建议用 UniProt recommendedName，如 Programmed cell death protein 1"
          >
            <Input placeholder="Programmed cell death protein 1" />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item
            label="UniProt accession"
            extra={
              onFetchUniprot
                ? '填好后点「拉取」或回车：自动带出名称/基因/别名/建议类型定位；已存在（含次级号）会提示去建关联'
                : '查重锚点：已存在（含次级 accession）会被拒绝，请改为建立分子-靶点关联'
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
                <Input placeholder="Q15116" onPressEnter={onFetchUniprot ? doFetch : undefined} />
              </Form.Item>
              {onFetchUniprot && (
                <Button icon={<CloudDownloadOutlined />} loading={fetching} onClick={doFetch}>
                  拉取
                </Button>
              )}
            </Space.Compact>
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item name="gene_symbol" label="基因符号" rules={[{ max: 64 }]}>
            <Input placeholder="PDCD1" />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Form.Item
            name="target_type"
            label="靶点类型"
            rules={[{ required: true, message: '请选择靶点类型' }]}
            extra={
              hints?.target_type_reason ? (
                <Text type="warning">建议值依据：{hints.target_type_reason}（请人工确认）</Text>
              ) : (
                '拉取/预填给的是启发式建议值，请对照依据人工确认'
              )
            }
          >
            <Select
              placeholder="选择类型"
              options={TARGET_TYPE_OPTIONS}
              optionRender={(opt) => {
                const o = TARGET_TYPE_OPTIONS.find((x) => x.value === opt.value);
                return (
                  <div>
                    <div>{o?.label}</div>
                    <div style={{ fontSize: 12, color: '#999', whiteSpace: 'normal' }}>{o?.hint}</div>
                  </div>
                );
              }}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item
            name="target_location"
            label="靶点定位"
            rules={[{ required: true, message: '请选择靶点定位' }]}
            extra={
              hints?.target_location_reason ? (
                <Text type="warning">建议值依据：{hints.target_location_reason}（请人工确认）</Text>
              ) : undefined
            }
          >
            <Select
              placeholder="选择定位"
              options={TARGET_LOCATION_OPTIONS}
              optionRender={(opt) => {
                const o = TARGET_LOCATION_OPTIONS.find((x) => x.value === opt.value);
                return (
                  <div>
                    <div>{o?.label}</div>
                    <div style={{ fontSize: 12, color: '#999', whiteSpace: 'normal' }}>{o?.hint}</div>
                  </div>
                );
              }}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="organism" label="物种" rules={[{ max: 128 }]}>
            <Input placeholder="Homo sapiens" />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item
        name="aliases"
        label="别名 / 次级 accession"
        extra={
          <Text type="secondary">
            回车添加多个：短名、别名、CD 号、UniProt 次级 accession（次级 accession 参与查重）
          </Text>
        }
      >
        <Select mode="tags" tokenSeparators={[',', ';']} placeholder="PD-1, CD279, O00517 …" open={false} />
      </Form.Item>

      <Form.Item name="description" label="功能描述">
        <Input.TextArea rows={3} placeholder="UniProt FUNCTION 摘要或人工描述" />
      </Form.Item>
      <Form.Item name="notes" label="备注">
        <Input.TextArea rows={2} />
      </Form.Item>
    </>
  );
}
