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
  message,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import type { Dayjs } from 'dayjs';
import { projectsApi } from '@/api/projects';
import { applyFormErrors } from '@/shared/utils/formErrors';
import type { ProjectCreatePayload } from '@/api/types';
import {
  PROJECT_PHASE_OPTIONS,
  PROJECT_TYPE_OPTIONS,
} from '../constants';

const { Title } = Typography;

interface FormValues {
  project_name: string;
  project_name_en?: string;
  project_type: ProjectCreatePayload['project_type'];
  project_phase?: string;
  program_name?: string;
  department?: string;
  objective?: string;
  planned_start_date?: Dayjs;
  planned_end_date?: Dayjs;
  description?: string;
  notes?: string;
}

export function ProjectCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();

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
          项目编码 <code>PRJ-YYYY-XXXX</code> 由系统按年自动分配。初始状态为"已提议"，进入"已立项"需走审批流程（电子签名）。
        </p>

        <Form<FormValues>
          form={form}
          layout="vertical"
          onFinish={onFinish}
          requiredMark
          initialValues={{ project_type: 'cmc' }}
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
