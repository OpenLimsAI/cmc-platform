import { useEffect } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Select,
  DatePicker,
  Space,
  Typography,
  Breadcrumb,
  Skeleton,
  Result,
  message,
} from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs, { Dayjs } from 'dayjs';
import { projectsApi } from '@/api/projects';
import { assetsApi } from '@/api/assets';
import { applyFormErrors } from '@/shared/utils/formErrors';
import type { ProjectCategory, ProjectUpdatePayload } from '@/api/types';
import {
  OWNING_FUNCTION_OPTIONS,
  PROJECT_CATEGORY_OPTIONS,
  PROJECT_NATURE_OPTIONS,
  PROJECT_PHASE_OPTIONS,
  PROJECT_TYPE_OPTIONS,
} from '../constants';

const { Title } = Typography;

interface FormValues {
  project_name?: string;
  project_name_en?: string;
  project_type?: ProjectUpdatePayload['project_type'];
  project_phase?: ProjectUpdatePayload['project_phase'];
  project_category?: ProjectCategory;
  project_nature?: ProjectUpdatePayload['project_nature'];
  owning_function?: ProjectUpdatePayload['owning_function'];
  asset_id?: number;
  program_name?: string;
  department?: string;
  objective?: string;
  planned_start_date?: Dayjs;
  planned_end_date?: Dayjs;
  actual_start_date?: Dayjs;
  actual_end_date?: Dayjs;
  description?: string;
  notes?: string;
  change_reason?: string;
}

export function ProjectEditPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const category = Form.useWatch('project_category', form);

  const {
    data: proj,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['project', code],
    queryFn: () => projectsApi.get(code!),
    enabled: !!code,
  });

  const { data: assetPage } = useQuery({
    queryKey: ['assets', 'for-project-link'],
    queryFn: () => assetsApi.list({ page_size: 100, sort: '-updated_at' }),
    enabled: category === 'asset_related',
  });
  const assetOptions = (assetPage?.items ?? []).map((a) => ({
    value: a.asset_id,
    label: `${a.asset_code} — ${a.internal_name}`,
  }));

  useEffect(() => {
    if (proj) {
      form.setFieldsValue({
        project_name: proj.project_name,
        project_name_en: proj.project_name_en ?? undefined,
        project_type: proj.project_type,
        project_phase: proj.project_phase ?? undefined,
        project_category: proj.project_category,
        project_nature: proj.project_nature,
        owning_function: proj.owning_function,
        asset_id: proj.asset_id ?? undefined,
        program_name: proj.program_name ?? undefined,
        department: proj.department ?? undefined,
        objective: proj.objective ?? undefined,
        planned_start_date: proj.planned_start_date ? dayjs(proj.planned_start_date) : undefined,
        planned_end_date: proj.planned_end_date ? dayjs(proj.planned_end_date) : undefined,
        actual_start_date: proj.actual_start_date ? dayjs(proj.actual_start_date) : undefined,
        actual_end_date: proj.actual_end_date ? dayjs(proj.actual_end_date) : undefined,
        description: proj.description ?? undefined,
        notes: proj.notes ?? undefined,
      });
    }
  }, [proj, form]);

  const updateMutation = useMutation({
    mutationFn: (payload: ProjectUpdatePayload) => projectsApi.update(code!, payload),
    onSuccess: (detail) => {
      message.success('更新成功');
      queryClient.invalidateQueries({ queryKey: ['project', code] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/projects/${encodeURIComponent(detail.project_code)}`);
    },
    onError: (err: any) => {
      if (applyFormErrors(form, err)) return;
      const status = err?.response?.status;
      if (status === 409) {
        message.error('数据已被他人修改，请刷新后重试');
      } else {
        message.error(err?.response?.data?.message ?? '更新失败');
      }
    },
  });

  const onFinish = (values: FormValues) => {
    if (!proj) return;
    const payload: ProjectUpdatePayload = {
      version: proj.version,
      change_reason: values.change_reason,
      project_name: values.project_name,
      project_name_en: values.project_name_en,
      project_type: values.project_type,
      project_phase: values.project_phase,
      project_category: values.project_category,
      project_nature: values.project_nature,
      owning_function: values.owning_function,
      asset_id: values.project_category === 'asset_related' ? values.asset_id : undefined,
      program_name: values.program_name,
      department: values.department,
      objective: values.objective,
      planned_start_date: values.planned_start_date?.format('YYYY-MM-DD'),
      planned_end_date: values.planned_end_date?.format('YYYY-MM-DD'),
      actual_start_date: values.actual_start_date?.format('YYYY-MM-DD'),
      actual_end_date: values.actual_end_date?.format('YYYY-MM-DD'),
      description: values.description,
      notes: values.notes,
    };
    updateMutation.mutate(payload);
  };

  if (isLoading) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 8 }} />
      </Card>
    );
  }
  if (isError || !proj) {
    return (
      <Result
        status="404"
        title="项目不存在"
        extra={
          <Button type="primary" onClick={() => navigate('/projects')}>
            返回列表
          </Button>
        }
      />
    );
  }

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/projects')}>项目</a> },
          {
            title: (
              <a onClick={() => navigate(`/projects/${encodeURIComponent(proj.project_code)}`)}>
                {proj.project_code}
              </a>
            ),
          },
          { title: '编辑' },
        ]}
      />

      <Card>
        <Title level={3} style={{ marginTop: 0 }}>
          编辑项目 <code>{proj.project_code}</code>{' '}
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            （当前版本 v{proj.version}）
          </Typography.Text>
        </Title>

        <Form<FormValues> form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 880 }}>
          <Form.Item
            label="项目名称"
            name="project_name"
            rules={[{ required: true, message: '请填写项目名称' }]}
          >
            <Input maxLength={255} />
          </Form.Item>

          <Form.Item label="项目英文名" name="project_name_en">
            <Input maxLength={255} />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="项目类型" name="project_type" style={{ flex: 1 }}>
              <Select options={PROJECT_TYPE_OPTIONS} />
            </Form.Item>
            <Form.Item label="阶段" name="project_phase" style={{ flex: 1 }}>
              <Select options={PROJECT_PHASE_OPTIONS} allowClear />
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

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="所属 Program" name="program_name" style={{ flex: 1 }}>
              <Input maxLength={128} />
            </Form.Item>
            <Form.Item label="主责部门" name="department" style={{ flex: 1 }}>
              <Input maxLength={64} />
            </Form.Item>
          </Space>

          <Form.Item label="项目目标" name="objective">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="计划开始" name="planned_start_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="计划结束" name="planned_end_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item label="实际开始" name="actual_start_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="实际结束" name="actual_end_date" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>

          <Form.Item label="备注" name="notes">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Form.Item
            label="变更原因"
            name="change_reason"
            tooltip="将写入审计日志（21 CFR Part 11）。建议填写。"
          >
            <Input.TextArea rows={2} placeholder="例：更新临床阶段为 phase_2，对齐 IND 批准" />
          </Form.Item>

          <Space>
            <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
              保存
            </Button>
            <Button
              onClick={() =>
                navigate(`/projects/${encodeURIComponent(proj.project_code)}`)
              }
            >
              取消
            </Button>
          </Space>
        </Form>
      </Card>
    </div>
  );
}
