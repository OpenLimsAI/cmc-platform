import { Card, Checkbox, Col, Form, Input, Row } from 'antd';
import { IT_CATEGORY, WORKSTATION_FIELDS } from '../constants';

/**
 * 工作站 / 本机硬件配置区块（Create / Edit 共用）。
 * - 普通设备：显示「附带专用工作站」勾选框，勾上才展开全部字段（含电脑品牌/型号/序列号）。
 * - IT/自动化与数据系统：设备本身即电脑，自动展开「本机硬件/系统配置」，只渲染 spec 子集
 *   （品牌/型号/序列号复用设备主字段，不重复填）。
 */
export function WorkstationFields() {
  return (
    <Form.Item
      noStyle
      shouldUpdate={(p, c) =>
        p.category !== c.category || p.has_workstation !== c.has_workstation
      }
    >
      {(form) => {
        const isIT = form.getFieldValue('category') === IT_CATEGORY;
        const checked = !!form.getFieldValue('has_workstation');
        const show = isIT || checked;
        const fields = WORKSTATION_FIELDS.filter((f) =>
          isIT ? f.group === 'spec' : true,
        );
        return (
          <>
            {!isIT && (
              <Form.Item name="has_workstation" valuePropName="checked">
                <Checkbox>附带专用工作站（勾选后填写工作站电脑配置）</Checkbox>
              </Form.Item>
            )}
            {show && (
              <Card
                size="small"
                title={isIT ? '本机硬件 / 系统配置' : '专用工作站配置'}
                style={{ marginBottom: 16 }}
              >
                <Row gutter={16}>
                  {fields.map((f) => (
                    <Col span={8} key={f.key}>
                      <Form.Item name={['workstation_info', f.key]} label={f.label}>
                        <Input maxLength={120} />
                      </Form.Item>
                    </Col>
                  ))}
                </Row>
              </Card>
            )}
          </>
        );
      }}
    </Form.Item>
  );
}
