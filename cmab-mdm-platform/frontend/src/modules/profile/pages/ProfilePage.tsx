import { useState } from 'react';
import {
  Breadcrumb,
  Button,
  Card,
  Descriptions,
  Empty,
  Result,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  EditOutlined,
  KeyOutlined,
  LoginOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/api/auth';
import { oidcApi } from '@/api/oidc';
import type { LoginHistoryItem, SignatureItem } from '@/api/types';
import { TimeDisplay } from '@/shared/components/TimeDisplay';

const { Title, Text } = Typography;

const MEANING_COLOR: Record<string, string> = {
  approve: 'gold',
  review: 'blue',
  release: 'green',
  witness: 'purple',
  reject: 'red',
};

const MEANING_LABEL: Record<string, string> = {
  approve: '审批',
  review: '复核',
  release: '放行',
  witness: '见证',
  reject: '驳回',
};

function BasicInfoTab() {
  const signingConfig = useQuery({queryKey:['oidc-signing-config'],queryFn:oidcApi.config});
  const navigate = useNavigate();
  const { data: me, isLoading, isError } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => authApi.me(),
  });

  if (isError)
    return <Result status="error" title="获取个人信息失败" />;

  return (
    <Card loading={isLoading}>
      {me && (
        <>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              marginBottom: 24,
            }}
          >
            <div>
              <Title level={3} style={{ marginBottom: 4 }}>
                {me.full_name}
                {me.full_name_en && (
                  <Text type="secondary" style={{ marginLeft: 12, fontSize: 16 }}>
                    {me.full_name_en}
                  </Text>
                )}
              </Title>
              <Space>
                <Text type="secondary">{me.username}</Text>
                <Text type="secondary">·</Text>
                <Text type="secondary">{me.email}</Text>
              </Space>
            </div>
            {signingConfig.data?.signature_mode === 'oidc_fresh' ? <Text type="secondary">密码与签名再次认证由 Casdoor 管理</Text> : <Button
              icon={<KeyOutlined />}
              onClick={() => navigate('/profile/password')}
            >
              修改密码
            </Button>}
          </div>

          <Descriptions
            column={2}
            bordered
            size="small"
            labelStyle={{ width: 120 }}
          >
            <Descriptions.Item label="部门">{me.department ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="职位">{me.title ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="电话">{me.phone ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="账户状态">
              <Tag color={me.status === 'active' ? 'green' : 'orange'}>{me.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="MFA">
              {me.mfa_enabled ? (
                <Tag color="green">已启用</Tag>
              ) : (
                <Tag color="default">未启用</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="最近登录">
              {me.last_login_at ? <TimeDisplay value={me.last_login_at} /> : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="角色" span={2}>
              <Space wrap>
                {me.roles.length === 0 && <Text type="secondary">未分配</Text>}
                {me.roles.map((r) => (
                  <Tag key={r.role_code} color="blue">
                    {r.role_name}
                  </Tag>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="权限" span={2}>
              <div style={{ maxHeight: 120, overflow: 'auto' }}>
                <Space wrap>
                  {me.permissions.length === 0 && <Text type="secondary">无</Text>}
                  {me.permissions.map((p) => (
                    <Tag key={p} style={{ fontSize: 11 }}>
                      {p}
                    </Tag>
                  ))}
                </Space>
              </div>
            </Descriptions.Item>
          </Descriptions>
        </>
      )}
    </Card>
  );
}

function LoginHistoryTab() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { data, isLoading } = useQuery({
    queryKey: ['my-login-history', page, pageSize],
    queryFn: () => authApi.myLoginHistory({ page, page_size: pageSize }),
  });

  const items: LoginHistoryItem[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '时间',
      dataIndex: 'login_at',
      key: 'login_at',
      width: 170,
      render: (v: string) => <TimeDisplay value={v} />,
    },
    {
      title: '结果',
      dataIndex: 'success',
      key: 'success',
      width: 90,
      render: (v: boolean, r: LoginHistoryItem) =>
        v ? (
          <Tag color="green">成功</Tag>
        ) : (
          <Tooltip title={r.failure_reason}>
            <Tag color="red">失败</Tag>
          </Tooltip>
        ),
    },
    {
      title: '失败原因',
      dataIndex: 'failure_reason',
      key: 'failure_reason',
      width: 160,
      render: (v: string | null) =>
        v ? <Text type="secondary">{v}</Text> : '—',
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 140,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: 'User Agent',
      dataIndex: 'user_agent',
      key: 'user_agent',
      ellipsis: true,
      render: (v: string | null) =>
        v ? (
          <Tooltip title={v}>
            <Text style={{ fontSize: 12 }}>{v}</Text>
          </Tooltip>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <Card>
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">
          共 {total} 条记录。如发现非本人 IP 的成功登录，请立即修改密码并联系管理员。
        </Text>
      </div>
      <Table<LoginHistoryItem>
        rowKey="login_id"
        columns={columns}
        dataSource={items}
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, size) => {
            setPage(p);
            setPageSize(size);
          },
        }}
        locale={{ emptyText: <Empty description="暂无登录记录" /> }}
      />
    </Card>
  );
}

function MySignaturesTab() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { data, isLoading } = useQuery({
    queryKey: ['my-signatures', page, pageSize],
    queryFn: () => authApi.mySignatures({ page, page_size: pageSize }),
  });

  const items: SignatureItem[] = data?.items ?? [];
  const total = data?.pagination.total ?? 0;

  const columns = [
    {
      title: '签名时间',
      dataIndex: 'signed_at',
      key: 'signed_at',
      width: 170,
      render: (v: string) => <TimeDisplay value={v} />,
    },
    {
      title: '含义',
      dataIndex: 'signature_meaning',
      key: 'signature_meaning',
      width: 110,
      render: (v: string) => (
        <Tag color={MEANING_COLOR[v] ?? 'default'}>{MEANING_LABEL[v] ?? v}</Tag>
      ),
    },
    {
      title: '对象',
      key: 'entity',
      width: 220,
      render: (_: unknown, r: SignatureItem) => (
        <span>
          <Tag>{r.entity_table}</Tag>
          {r.entity_code && <Text code>{r.entity_code}</Text>}
        </span>
      ),
    },
    {
      title: '理由',
      dataIndex: 'signature_reason',
      key: 'signature_reason',
      ellipsis: true,
    },
    {
      title: '签名哈希',
      dataIndex: 'signature_hash',
      key: 'signature_hash',
      width: 130,
      render: (v: string) => (
        <Tooltip title={v}>
          <Text code style={{ fontSize: 11 }}>
            {v.slice(0, 10)}…
          </Text>
        </Tooltip>
      ),
    },
  ];

  return (
    <Card>
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">
          您共执行过 {total} 次电子签名（21 CFR Part 11 §11.50）。签名哈希一经记录不可修改。
        </Text>
      </div>
      <Table<SignatureItem>
        rowKey="signature_id"
        columns={columns}
        dataSource={items}
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 次签名`,
          onChange: (p, size) => {
            setPage(p);
            setPageSize(size);
          },
        }}
        locale={{ emptyText: <Empty description="您尚未执行过电子签名" /> }}
      />
    </Card>
  );
}

export function ProfilePage() {
  return (
    <div>
      <Breadcrumb style={{ marginBottom: 12 }} items={[{ title: '个人中心' }]} />

      <Card style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          <UserOutlined style={{ marginRight: 8 }} />
          个人中心
        </Title>
        <Text type="secondary">
          查看个人信息 / 登录历史 / 我的电子签名记录；修改密码请用右上角按钮
        </Text>
      </Card>

      <Tabs
        defaultActiveKey="info"
        items={[
          {
            key: 'info',
            label: (
              <span>
                <EditOutlined /> 基本信息
              </span>
            ),
            children: <BasicInfoTab />,
          },
          {
            key: 'login-history',
            label: (
              <span>
                <LoginOutlined /> 登录历史
              </span>
            ),
            children: <LoginHistoryTab />,
          },
          {
            key: 'my-signatures',
            label: (
              <span>
                <SafetyCertificateOutlined /> 我的签名
              </span>
            ),
            children: <MySignaturesTab />,
          },
        ]}
      />
    </div>
  );
}
