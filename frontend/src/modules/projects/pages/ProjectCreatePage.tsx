import {
  Button,
  Card,
  Form,
  Input,
  Select,
  Switch,
  DatePicker,
  Space,
  Typography,
  Breadcrumb,
  message,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import type { Dayjs } from 'dayjs';
import { projectsApi } from '@/api/projects';
import { assetsApi } from '@/api/assets';
import { applyFormErrors } from '@/shared/utils/formErrors';
import type { ProjectCategory, ProjectCreatePayload } from '@/api/types';
import {
  OWNING_FUNCTION_OPTIONS,
  PROJECT_CATEGORY_OPTIONS,
  PROJECT_NATURE_OPTIONS,
  PROJECT_PHASE_OPTIONS,
  PROJECT_TYPE_OPTIONS,
  REGULATORY_CHANGE_LEVEL_OPTIONS,
} from '../constants';

const { Title } = Typography;

interface FormValues {
  project_name: string;
  project_name_en?: string;
  project_type: ProjectCreatePayload['project_type'];
  project_phase?: ProjectCreatePayload['project_phase'];
  project_category: ProjectCategory;
  project_nature: ProjectCreatePayload['project_nature'];
  owning_function: ProjectCreatePayload['owning_function'];
  asset_id?: number;
  regulatory_change_level?: ProjectCreatePayload['regulatory_change_level'];
  pre_approval_required?: boolean;
  comparability_study_ref?: string;
  legacy_project_id?: string;
  program_name?: string;
  department?: string;
  objective?: string;
  planned_start_date?: Dayjs;
  planned_end_date?: Dayjs;
  description?: string;
  notes?: string;
}

const POST_APPROVAL_NATURES = ['cmc_change', 'lcm'];

export function ProjectCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const category = Form.useWatch('project_category', form);
  const nature = Form.useWatch('project_nature', form);
  const showRegulatory = POST_APPROVAL_NATURES.includes(nature ?? '');

  // 资产下拉：仅在 asset_related 时需要
  const { data: assetPage } = useQuery({
    queryKey: ['assets', 'for-project-link'],
    queryFn: () => assetsApi.list({ page_size: 100, sort: '-updated_at' }),
    enabled: category === 'asset_related',
  });
  const assetOptions = (assetPage?.items ?? []).map((a) => ({
    value: a.asset_id,
    label: `${a.asset_code} — ${a.internal_name}`,
  }));

  const createMutation = useMutation({
    mutationFn: (payload: ProjectCreatePayload) => projectsApi.create(payload),
    onSuccess: (detail) => {
      message.success(`项目已创建：${detail.project_code}`);
      navigate(`/projects/${encodeURIComponent(detail.project_code)}`);
    },
    onError: (err: any) => {
      if (applyFormErrors(form, err)) return;
      message.error(err?.response?.data?.message ?? '创建失败');
    },
  });

  const onFinish = (values: FormValues) => {
    const payload: ProjectCreatePayload = {
      project_name: values.project_name,
      project_name_en: values.project_name_en,
      project_type: values.project_type,
      project_phase: values.project_phase,
      project_category: values.project_category,
      project_nature: values.project_nature,
      owning_function: values.owning_function,
      asset_id: values.project_category === 'asset_related' ? values.asset_id : undefined,
      regulatory_change_level: showRegulatory ? values.regulatory_change_level : undefined,
      pre_approval_required: showRegulatory ? values.pre_approval_required : undefined,
      comparability_study_ref: showRegulatory ? values.comparability_study_ref : undefined,
      legacy_project_id: values.legacy_project_id,
      program_name: values.program_name,
      department: values.department,
      objective: values.objective,
      planned_start_date: values.planned_start_date?.format('YYYY-MM-DD'),
      planned_end_date: values.planned_end_date?.format('YYYY-MM-DD'),
      description: values.description,
      notes: values.notes,
    };
    createMutation.mutate(payload);
  };

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/projects')}>项目</a> },
          { title: '新建项目' },
        ]}
      />

      <Card>
        <Title level={3} style={{ marginTop: 0 }}>
          新建项目
        </Title>
        <p style={{ color: '#8c8c8c', marginTop: -8 }}>
          项目编码 <code>CMAB-PRJ-YYYY-NNNN</code> 由系统按年自动分配。初始状态为"已提议"，进入"已立项"需走审批流程（电子签名）。
        </p>

        <Form<FormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
          requiredMark
          initialValues={{
            project_type: 'cmc',
            project_category: 'non_asset',
            project_nature: 'discovery',
            owning_function: 'rd',
          }}
          style={{ maxWidth: 880 }}
        >
          <Form.Item
            label="项目名称"
            name="project_name"
            rules={[{ required: true, message: '请填写项目名称' }]}
          >
            <Input maxLength={255} placeholder="例：CMAB-001 PD-L1 单抗 CMC 开发" />
          </Form.Item>

          <Form.Item label="项目英文名" name="project_name_en">
            <Input maxLength={255} placeholder="可选" />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item
              label="项目类型"
              name="project_type"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Select options={PROJECT_TYPE_OPTIONS} />
            </Form.Item>
            <Form.Item label="阶段" name="project_phase" style={{ flex: 1 }}>
              <Select options={PROJECT_PHASE_OPTIONS} allowClear placeholder="可选" />
            </Form.Item>
          </Space>

          {/* SMP V2.1 §7.4 项目分类三维度 */}
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item
              label="是否关联资产"
              name="project_category"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Select options={PROJECT_CATEGORY_OPTIONS} />
            </Form.Item>
            <Form.Item
              label="项目性质"
              name="project_nature"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Select options={PROJECT_NATURE_OPTIONS} />
            </Form.Item>
            <Form.Item
              label="主责部门（受控）"
              name="owning_function"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Select options={OWNING_FUNCTION_OPTIONS} />
            </Form.Item>
          </Space>

          {category === 'asset_related' && (
            <Form.Item
              label="关联资产"
              name="asset_id"
              rules={[{ required: true, message: '资产相关项目必须绑定一个资产' }]}
              extra="SMP §7.5：资产相关项目须绑定唯一权威资产"
            >
              <Select
                options={assetOptions}
                showSearch
                optionFilterProp="label"
                placeholder="选择资产（按编码 / 名称搜索）"
              />
            </Form.Item>
          )}

          {/* SMP V2.1 §7A：仅 CMC 变更 / 生命周期管理项目需填 */}
          {showRegulatory && (
            <Space size="large" style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Form.Item
                label="变更级别"
                name="regulatory_change_level"
                rules={[{ required: true, message: 'CMC 变更 / LCM 项目须选变更级别' }]}
                style={{ flex: 1 }}
                extra="SMP §7A.4 / CDE 变更指导原则"
              >
                <Select options={REGULATORY_CHANGE_LEVEL_OPTIONS} />
              </Form.Item>
              <Form.Item
                label="需预先获批"
                name="pre_approval_required"
                valuePropName="checked"
                style={{ flex: 1 }}
                extra="major 级由系统强制为是"
              >
                <Switch />
              </Form.Item>
              <Form.Item label="可比性研究编号" name="comparability_study_ref" style={{ flex: 1 }}>
                <Input maxLength={50} placeholder="ICH Q5E Study ID（可选）" />
              </Form.Item>
            </Space>
          )}

          <Form.Item
            label="历史遗留编号"
            name="legacy_project_id"
            tooltip="SMP §11.8：迁移前的老项目编号，仅存档参考"
          >
            <Input maxLength={32} placeholder="可选，如 PRJ-2024-011" />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="所属 Program" name="program_name" style={{ flex: 1 }}>
              <Input maxLength={128} placeholder="可选，所属研发项目群" />
            </Form.Item>
            <Form.Item label="主责部门" name="department" style={{ flex: 1 }}>
              <Input maxLength={64} placeholder="例：CMC R&D / QA / Regulatory" />
            </Form.Item>
          </Space>

          <Form.Item label="项目目标 (objective)" name="objective">
            <Input.TextArea rows={2} placeholder="可选；将用于全局搜索命中" />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="计划开始" name="planned_start_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="计划结束" name="planned_end_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} placeholder="可选，项目背景 / 目标 / 范围" />
          </Form.Item>

          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} placeholder="可选" />
          </Form.Item>

          <Space>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              创建项目
            </Button>
            <Button onClick={() => navigate('/projects')}>取消</Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
