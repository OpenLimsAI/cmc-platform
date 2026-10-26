import { Card, Col, DatePicker, Form, Input, Row, Select } from 'antd';
import { criticalityOptions, ANALYTICAL_CATEGORY } from '../constants';

/**
 * 公司级设备清单治理字段区块（Create / Edit 共用，0056）。
 *
 * 使用部门 / 厂区 / 房间 / 分级 / 分级依据 / 首次启用日期。
 * 分级字典跟着设备分类走：分析仪器（检验设备）= A/B/C（USP 口径），
 * 其他分类（工艺制备=生产设备、公用工程、通用实验室、IT）= 关键/一般。
 * 改分类后原分级若不在新字典里，自动清空，避免提交被后端/DB 打回。
 */
export function GovernanceFields() {
  return (
    <Card size="small" title="使用与分级（设备部维护）" style={{ marginBottom: 16 }}>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="department" label="使用部门" rules={[{ max: 64 }]}>
            <Input placeholder="如 生产一部、质量控制部、研发部" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="site" label="厂区" rules={[{ max: 64 }]}>
            <Input placeholder="如 南楼、北楼、祥泰路" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="room" label="存放位置" rules={[{ max: 100 }]}>
            <Input placeholder="如 3129培养间" />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item
            noStyle
            shouldUpdate={(p, c) => p.category !== c.category}
          >
            {(form) => {
              const category = form.getFieldValue('category');
              const options = criticalityOptions(category);
              const current = form.getFieldValue('criticality');
              // 分类换了、原分级不在新字典里 → 清空（渲染期不能直接 setFields，放微任务）
              if (current && !options.some((o) => o.value === current)) {
                queueMicrotask(() =>
                  form.setFieldValue('criticality', undefined),
                );
              }
              return (
                <Form.Item
                  name="criticality"
                  label="设备分级"
                  extra={
                    category === ANALYTICAL_CATEGORY
                      ? '分析仪器按 USP 口径分 A / B / C'
                      : '生产及其他设备分 关键 / 一般'
                  }
                >
                  <Select
                    allowClear
                    placeholder="选择分级"
                    options={options}
                    optionRender={(opt) => {
                      const o = options.find((x) => x.value === opt.value);
                      return (
                        <div>
                          <div>{o?.label}</div>
                          <div
                            style={{
                              fontSize: 12,
                              color: '#999',
                              whiteSpace: 'normal',
                            }}
                          >
                            {o?.hint}
                          </div>
                        </div>
                      );
                    }}
                  />
                </Form.Item>
              );
            }}
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="commission_date" label="首次启用日期">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="criticality_basis" label="分级依据" rules={[{ max: 2000 }]}>
            <Input placeholder="如 直接接触产品 / 仅辅助测量" />
          </Form.Item>
        </Col>
      </Row>
    </Card>
  );
}
