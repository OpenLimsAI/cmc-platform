import { useMemo, useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Space,
  Steps,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { substancesApi } from '@/api/substances';
import { applyFormErrors } from '@/shared/utils/formErrors';
import type {
  Confidentiality,
  ProteinExtensionInput,
  SubstanceCreatePayload,
  SubstanceType,
  SubstanceXrefInput,
} from '@/api/types';
import { SamenessCheckButton } from '../components/SamenessCheckButton';
import {
  EXPRESSION_SYSTEM_OPTIONS,
  ISOTYPE_OPTIONS,
  PROTEIN_TYPES,
  SUBSTANCE_TYPE_OPTIONS,
  XREF_TYPE_OPTIONS,
  cleanedSequenceLength,
} from '../constants';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface FormShape {
  // step 1
  substance_type: SubstanceType;
  internal_code?: string;
  preferred_name: string;
  preferred_name_en?: string;
  target?: string;
  target_type?: string;
  modality?: string;
  is_proprietary: boolean;
  confidentiality: Confidentiality;
  description?: string;
  notes?: string;
  // step 2
  protein?: ProteinExtensionInput;
  // step 3
  xrefs?: SubstanceXrefInput[];
}

export function SubstanceCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormShape>();
  const [currentStep, setCurrentStep] = useState(0);

  // 实时观察 substance_type，决定是否需要 Step 2（蛋白属性）
  const substanceType = Form.useWatch('substance_type', form);
  const internalCode = Form.useWatch('internal_code', form);
  const needsProteinStep = useMemo(
    () => PROTEIN_TYPES.includes(substanceType as SubstanceType),
    [substanceType]
  );

  // 序列长度实时展示
  const hcSeq = Form.useWatch(['protein', 'heavy_chain_sequence'], form);
  const lcSeq = Form.useWatch(['protein', 'light_chain_sequence'], form);

  const createMutation = useMutation({
    mutationFn: (payload: SubstanceCreatePayload) => substancesApi.create(payload),
    onSuccess: (data) => {
      message.success(`物质 ${data.substance_code} 创建成功`);
      navigate(`/substances/${data.substance_code}`);
    },
    onError: (err: any) => {
      if (applyFormErrors(form, err)) return;
      message.error(err?.response?.data?.message ?? '创建失败');
    },
  });

  // 步骤显式枚举：Steps UI 与表单逻辑用同一份
  const stepDefs = useMemo(() => {
    const items = [{ key: 'basic', title: '基本信息' }];
    if (needsProteinStep) items.push({ key: 'protein', title: '蛋白属性' });
    items.push({ key: 'xrefs', title: '标识符与确认' });
    return items;
  }, [needsProteinStep]);

  const currentStepKey = stepDefs[currentStep]?.key;

  // 当前步要校验的字段集合
  const fieldsForCurrentStep = (): (keyof FormShape | (string | number)[])[] => {
    if (currentStepKey === 'basic') {
      return [
        'substance_type',
        'preferred_name',
        'is_proprietary',
        'confidentiality',
      ];
    }
    return [];
  };

  const handleNext = async () => {
    try {
      await form.validateFields(fieldsForCurrentStep() as never);
      setCurrentStep((s) => s + 1);
    } catch {
      // antd 已在字段上展示错误
    }
  };

  const handlePrev = () => setCurrentStep((s) => Math.max(0, s - 1));

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: SubstanceCreatePayload = {
        substance_type: values.substance_type,
        internal_code: values.internal_code?.trim() || undefined,
        preferred_name: values.preferred_name.trim(),
        preferred_name_en: values.preferred_name_en?.trim() || undefined,
        target: values.target?.trim() || undefined,
        target_type: values.target_type?.trim() || undefined,
        modality: values.modality?.trim() || undefined,
        is_proprietary: values.is_proprietary,
        confidentiality: values.confidentiality,
        description: values.description?.trim() || undefined,
        notes: values.notes?.trim() || undefined,
      };

      if (needsProteinStep && values.protein) {
        const p = values.protein;
        const hcLen = cleanedSequenceLength(p.heavy_chain_sequence);
        const lcLen = cleanedSequenceLength(p.light_chain_sequence);
        const proteinPayload: ProteinExtensionInput = {
          isotype: p.isotype || undefined,
          architecture: p.architecture || undefined,
          expression_system: p.expression_system || undefined,
          cell_line: p.cell_line || undefined,
          expression_vector: p.expression_vector || undefined,
          molecular_weight_da: p.molecular_weight_da ?? undefined,
          pi_theoretical: p.pi_theoretical ?? undefined,
          extinction_coefficient: p.extinction_coefficient ?? undefined,
          heavy_chain_sequence: p.heavy_chain_sequence?.trim() || undefined,
          light_chain_sequence: p.light_chain_sequence?.trim() || undefined,
          sequence_length_hc: hcLen || undefined,
          sequence_length_lc: lcLen || undefined,
        };
        // 仅在至少有一个字段非空时才带 protein
        if (Object.values(proteinPayload).some((v) => v !== undefined && v !== '')) {
          payload.protein = proteinPayload;
        }
      }

      const xrefs = (values.xrefs ?? []).filter(
        (x) => x && x.xref_type && x.xref_value?.trim()
      );
      if (xrefs.length > 0) {
        payload.xrefs = xrefs.map((x) => ({
          xref_type: x.xref_type,
          xref_value: x.xref_value.trim(),
          xref_source: x.xref_source?.trim() || undefined,
          is_primary: x.is_primary ?? false,
        }));
      }

      createMutation.mutate(payload);
    } catch {
      message.error('表单校验未通过，请检查所有步骤的必填项');
    }
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/substances')}>物质</a> },
          { title: '新建' },
        ]}
      />

      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          新建物质
        </Title>
        <Text type="secondary">
          创建后状态为 <Tag>draft</Tag>，由 Substance Steward 审核后转为 active
        </Text>
      </Card>

      <Card>
        <Steps current={currentStep} items={stepDefs.map((s) => ({ title: s.title }))} style={{ marginBottom: 24 }} />

        <Form<FormShape>
          form={form}
          layout="vertical"
          initialValues={{
            substance_type: 'mab',
            is_proprietary: true,
            confidentiality: 'internal',
            xrefs: [],
          }}
          autoComplete="off"
        >
          {/* ============== Step 1: 基本信息 ============== */}
          <div style={{ display: currentStepKey === 'basic' ? 'block' : 'none' }}>
            <Form.Item
              name="substance_type"
              label="物质类型"
              rules={[{ required: true, message: '请选择物质类型' }]}
              tooltip="选择 mAb / 双抗 / 融合蛋白时，下一步会显示蛋白属性"
            >
              <Radio.Group optionType="button" buttonStyle="solid">
                {SUBSTANCE_TYPE_OPTIONS.map((opt) => (
                  <Radio.Button key={opt.value} value={opt.value}>
                    {opt.label}
                  </Radio.Button>
                ))}
              </Radio.Group>
            </Form.Item>

            <Form.Item
              name="internal_code"
              label="内部代号"
              tooltip="公司内部代号，如 CMAB-203。留空时系统不自动填，仅自动分配业务编码 SUB-XXXXXXX"
              rules={[{ max: 64 }]}
            >
              <Input placeholder="CMAB-XXX（可选）" />
            </Form.Item>

            <Form.Item
              name="preferred_name"
              label="首选名称（中文/通用）"
              rules={[
                { required: true, message: '请填写首选名称' },
                { max: 255 },
              ]}
            >
              <Input placeholder="如：Anti-HER2 mAb (biosimilar)" />
            </Form.Item>

            <Form.Item name="preferred_name_en" label="首选名称（英文）" rules={[{ max: 255 }]}>
              <Input placeholder="如：Anti-HER2 monoclonal antibody" />
            </Form.Item>

            <Space size="large" style={{ display: 'flex', width: '100%' }}>
              <Form.Item name="target" label="靶点" style={{ flex: 1 }} rules={[{ max: 128 }]}>
                <Input placeholder="如：HER2、PD-L1" />
              </Form.Item>
              <Form.Item name="target_type" label="靶点类型" style={{ flex: 1 }} rules={[{ max: 64 }]}>
                <Input placeholder="如：受体、抗原、酶" />
              </Form.Item>
              <Form.Item name="modality" label="模态描述" style={{ flex: 1 }} rules={[{ max: 64 }]}>
                <Input placeholder="如：humanized IgG1 mAb" />
              </Form.Item>
            </Space>

            <Space size="large">
              <Form.Item
                name="confidentiality"
                label="保密等级"
                rules={[{ required: true }]}
              >
                <Radio.Group>
                  <Radio value="public">公开</Radio>
                  <Radio value="internal">内部</Radio>
                  <Radio value="restricted">受限</Radio>
                </Radio.Group>
              </Form.Item>

              <Form.Item name="is_proprietary" label="是否专有" valuePropName="checked">
                <Switch checkedChildren="是" unCheckedChildren="否" />
              </Form.Item>
            </Space>

            <Form.Item name="description" label="描述">
              <TextArea rows={2} placeholder="物质用途、研发背景等" maxLength={2000} showCount />
            </Form.Item>

            <Form.Item name="notes" label="备注">
              <TextArea rows={2} placeholder="内部备注（不对外）" maxLength={2000} showCount />
            </Form.Item>
          </div>

          {/* ============== Step 2: 蛋白属性 ============== */}
          {needsProteinStep && (
            <div style={{ display: currentStepKey === 'protein' ? 'block' : 'none' }}>
              <Text type="secondary">本步骤仅对蛋白类（mAb / 双抗 / 融合蛋白）显示；所有字段均可留空，后续可补充。</Text>

              <Space size="large" style={{ display: 'flex', width: '100%', marginTop: 16 }}>
                <Form.Item name={['protein', 'isotype']} label="同型 (Isotype)" style={{ flex: 1 }}>
                  <Select allowClear placeholder="选择或输入" showSearch
                    options={ISOTYPE_OPTIONS.map((v) => ({ value: v, label: v }))} />
                </Form.Item>
                <Form.Item name={['protein', 'architecture']} label="架构" style={{ flex: 1 }}>
                  <Input placeholder="如：whole IgG / Fab / BiTE" />
                </Form.Item>
              </Space>

              <Space size="large" style={{ display: 'flex', width: '100%' }}>
                <Form.Item name={['protein', 'expression_system']} label="表达系统" style={{ flex: 1 }}>
                  <Select allowClear showSearch placeholder="选择或输入"
                    options={EXPRESSION_SYSTEM_OPTIONS.map((v) => ({ value: v, label: v }))} />
                </Form.Item>
                <Form.Item name={['protein', 'cell_line']} label="细胞株" style={{ flex: 1 }}>
                  <Input placeholder="如：CHO-K1-101" />
                </Form.Item>
                <Form.Item name={['protein', 'expression_vector']} label="表达载体" style={{ flex: 1 }}>
                  <Input placeholder="如：pCAG-Hyg-mAb" />
                </Form.Item>
              </Space>

              <Space size="large" style={{ display: 'flex', width: '100%' }}>
                <Form.Item name={['protein', 'molecular_weight_da']} label="分子量 (Da)" style={{ flex: 1 }}>
                  <InputNumber style={{ width: '100%' }} min={0} placeholder="如：148000.5" />
                </Form.Item>
                <Form.Item name={['protein', 'pi_theoretical']} label="理论 pI" style={{ flex: 1 }}>
                  <InputNumber style={{ width: '100%' }} min={0} max={14} step={0.01} placeholder="如：8.45" />
                </Form.Item>
                <Form.Item name={['protein', 'extinction_coefficient']} label="消光系数 (M⁻¹cm⁻¹)" style={{ flex: 1 }}>
                  <InputNumber style={{ width: '100%' }} min={0} step={0.1} placeholder="如：215000.5" />
                </Form.Item>
              </Space>

              <Form.Item
                name={['protein', 'heavy_chain_sequence']}
                label={
                  <span>
                    重链序列{' '}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      （氨基酸；当前 {cleanedSequenceLength(hcSeq)} aa）
                    </Text>
                  </span>
                }
              >
                <TextArea
                  rows={4}
                  placeholder="EVQLVESGGGLVQPGGSLRLSC..."
                  style={{ fontFamily: 'Consolas, monospace', fontSize: 13 }}
                />
              </Form.Item>

              <Form.Item
                name={['protein', 'light_chain_sequence']}
                label={
                  <span>
                    轻链序列{' '}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      （氨基酸；当前 {cleanedSequenceLength(lcSeq)} aa）
                    </Text>
                  </span>
                }
              >
                <TextArea
                  rows={4}
                  placeholder="DIQMTQSPSSLSASVGDRVTITC..."
                  style={{ fontFamily: 'Consolas, monospace', fontSize: 13 }}
                />
              </Form.Item>

              <div style={{ marginTop: 8, paddingTop: 12, borderTop: '1px dashed #d9d9d9' }}>
                <Text strong style={{ display: 'block', marginBottom: 8 }}>
                  提交前同一性判定
                </Text>
                <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>
                  基于已填的序列 / 内部代号，检查是否与现有 substance 重复，避免重复登记。
                </Text>
                <SamenessCheckButton
                  substanceType={substanceType as SubstanceType}
                  internalCode={internalCode}
                  heavyChainSequence={hcSeq}
                  lightChainSequence={lcSeq}
                />
              </div>
            </div>
          )}

          {/* ============== Step 3: 标识符 + 确认 ============== */}
          <div style={{ display: currentStepKey === 'xrefs' ? 'block' : 'none' }}>
            <Title level={5} style={{ marginTop: 0 }}>外部 / 内部标识符（可选）</Title>
            <Text type="secondary">如 INN / CAS / 项目代号，可后续在详情页继续添加。</Text>

            <Form.List name="xrefs">
              {(fields, { add, remove }) => (
                <div style={{ marginTop: 16 }}>
                  {fields.map(({ key, name, ...rest }) => (
                    <Space
                      key={key}
                      align="baseline"
                      style={{ display: 'flex', marginBottom: 8 }}
                    >
                      <Form.Item {...rest} name={[name, 'xref_type']} rules={[{ required: true, message: '选类型' }]} style={{ width: 160, marginBottom: 0 }}>
                        <Select placeholder="类型" options={XREF_TYPE_OPTIONS} />
                      </Form.Item>
                      <Form.Item {...rest} name={[name, 'xref_value']} rules={[{ required: true, message: '填值' }]} style={{ width: 260, marginBottom: 0 }}>
                        <Input placeholder="值" />
                      </Form.Item>
                      <Form.Item {...rest} name={[name, 'xref_source']} style={{ width: 160, marginBottom: 0 }}>
                        <Input placeholder="来源（可选）" />
                      </Form.Item>
                      <Form.Item {...rest} name={[name, 'is_primary']} valuePropName="checked" style={{ marginBottom: 0 }}>
                        <Switch checkedChildren="主" unCheckedChildren="次" />
                      </Form.Item>
                      <DeleteOutlined onClick={() => remove(name)} style={{ color: '#ff4d4f' }} />
                    </Space>
                  ))}
                  <Button type="dashed" onClick={() => add({ is_primary: false })} icon={<PlusOutlined />}>
                    添加标识符
                  </Button>
                </div>
              )}
            </Form.List>

            <Card type="inner" title="提交前确认" style={{ marginTop: 24 }}>
              <SummaryView form={form} needsProteinStep={needsProteinStep} />
            </Card>
          </div>

          {/* ============== 操作按钮 ============== */}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
            <Button onClick={() => navigate('/substances')}>取消</Button>
            <Space>
              {currentStep > 0 && <Button onClick={handlePrev}>上一步</Button>}
              {currentStep < stepDefs.length - 1 ? (
                <Button type="primary" onClick={handleNext}>
                  下一步
                </Button>
              ) : (
                <Button type="primary" loading={createMutation.isPending} onClick={handleSubmit}>
                  提交创建
                </Button>
              )}
            </Space>
          </div>
        </Form>
      </Card>
    </div>
  );
}

// ============== 提交前 review ==============
function SummaryView({
  form,
  needsProteinStep,
}: {
  form: ReturnType<typeof Form.useForm<FormShape>>[0];
  needsProteinStep: boolean;
}) {
  // 用 useWatch 监听整个表单，summary 会随用户回到前面修改而刷新
  const values = Form.useWatch([], form) as FormShape | undefined;
  if (!values) return null;

  const typeLabel = SUBSTANCE_TYPE_OPTIONS.find((o) => o.value === values.substance_type)?.label || values.substance_type;
  const xrefs = (values.xrefs ?? []).filter((x) => x?.xref_type && x?.xref_value?.trim());

  return (
    <Descriptions column={2} size="small" bordered labelStyle={{ width: 130 }}>
      <Descriptions.Item label="类型">{typeLabel}</Descriptions.Item>
      <Descriptions.Item label="内部代号">{values.internal_code || '—'}</Descriptions.Item>
      <Descriptions.Item label="首选名称">{values.preferred_name || '—'}</Descriptions.Item>
      <Descriptions.Item label="英文名">{values.preferred_name_en || '—'}</Descriptions.Item>
      <Descriptions.Item label="靶点">{values.target || '—'}</Descriptions.Item>
      <Descriptions.Item label="模态">{values.modality || '—'}</Descriptions.Item>
      <Descriptions.Item label="保密等级">{values.confidentiality}</Descriptions.Item>
      <Descriptions.Item label="是否专有">{values.is_proprietary ? '是' : '否'}</Descriptions.Item>

      {needsProteinStep && values.protein && (
        <>
          <Descriptions.Item label="同型">{values.protein.isotype || '—'}</Descriptions.Item>
          <Descriptions.Item label="表达系统">{values.protein.expression_system || '—'}</Descriptions.Item>
          <Descriptions.Item label="分子量 (Da)">
            {values.protein.molecular_weight_da?.toLocaleString() || '—'}
          </Descriptions.Item>
          <Descriptions.Item label="序列长度">
            HC {cleanedSequenceLength(values.protein.heavy_chain_sequence)} aa /
            LC {cleanedSequenceLength(values.protein.light_chain_sequence)} aa
          </Descriptions.Item>
        </>
      )}

      <Descriptions.Item label="标识符" span={2}>
        {xrefs.length === 0
          ? '—'
          : xrefs.map((x, i) => (
              <Tag key={i} color={x.is_primary ? 'blue' : 'default'}>
                {x.xref_type}: {x.xref_value}
                {x.is_primary ? ' ★' : ''}
              </Tag>
            ))}
      </Descriptions.Item>
    </Descriptions>
  );
}
