import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Table, Input, Select, Button, Space, Tag, Modal, Form,
  message, Typography,
} from "antd";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  listMaterials, createMaterial, listCategoryValues, listUnits,
  type Material, type MaterialCreate,
} from "../../../api/materials";
import { useAuthStore } from "../../../stores/authStore";

const MATERIAL_TYPE_MAP: Record<string, { label: string; color: string }> = {
  reagent: { label: "试剂", color: "blue" },
  consumable: { label: "耗材", color: "green" },
  standard: { label: "标准品", color: "gold" },
  column: { label: "色谱柱", color: "purple" },
};

export default function MaterialListPage() {
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState<string>();
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();
  const canWrite = useAuthStore((s) => s.canWrite());

  const { data: materials = [], isLoading, refetch } = useQuery({
    queryKey: ["materials", keyword, category],
    queryFn: () =>
      listMaterials({ keyword: keyword || undefined, category, include_inactive: true }).then(
        (r) => r.data,
      ),
  });

  const { data: categoryValues = [] } = useQuery({
    queryKey: ["categoryValues"],
    queryFn: () => listCategoryValues().then((r) => r.data),
  });

  const { data: units = [] } = useQuery({
    queryKey: ["units"],
    queryFn: () => listUnits().then((r) => r.data),
  });

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createMaterial(values as MaterialCreate);
      message.success("物料创建成功");
      setCreateOpen(false);
      form.resetFields();
      refetch();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (detail) message.error(detail);
    }
  };

  const columns: ColumnsType<Material> = [
    { title: "物料编码", dataIndex: "material_code", width: 120 },
    { title: "物料名称", dataIndex: "name_cn", ellipsis: true },
    {
      title: "类型",
      dataIndex: "material_type",
      width: 100,
      render: (v: string) => {
        const t = MATERIAL_TYPE_MAP[v];
        return t ? <Tag color={t.color}>{t.label}</Tag> : v;
      },
    },
    { title: "分类", dataIndex: "category", width: 120 },
    { title: "生产商", dataIndex: "manufacturer", width: 120, ellipsis: true },
    { title: "规格", dataIndex: "spec_model", width: 150, ellipsis: true },
    { title: "货号", dataIndex: "catalog_no", width: 120 },
    { title: "单位", dataIndex: "unit", width: 60 },
    {
      title: "来源",
      dataIndex: "data_source",
      width: 80,
      render: (v: string) =>
        v === "mdm" ? <Tag color="geekblue">MDM</Tag> : <Tag>本地</Tag>,
    },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 80,
      render: (v: boolean) =>
        v ? <Tag color="success">在用</Tag> : <Tag color="default">停用</Tag>,
    },
  ];

  return (
    <>
      <Typography.Title level={4}>物料管理</Typography.Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="编码/名称/生产商/规格/货号 (空格分隔多词, * 通配)"
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 360 }}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <Select
          placeholder="分类筛选"
          allowClear
          style={{ width: 160 }}
          value={category}
          onChange={setCategory}
          options={categoryValues.map((c: string) => ({ label: c, value: c }))}
        />
        {canWrite && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新增物料
          </Button>
        )}
      </Space>

      <Table
        rowKey="material_id"
        columns={columns}
        dataSource={materials}
        loading={isLoading}
        size="middle"
        pagination={{ pageSize: 50, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ x: 1200 }}
      />

      <Modal
        title="新增物料"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="material_code" label="物料编码" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name_cn" label="物料名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="unit" label="单位" rules={[{ required: true }]}>
            <Select
              showSearch
              options={units.map((u: { unit: string }) => ({ label: u.unit, value: u.unit }))}
            />
          </Form.Item>
          <Form.Item name="material_type" label="类型">
            <Select
              allowClear
              options={Object.entries(MATERIAL_TYPE_MAP).map(([k, v]) => ({
                label: v.label,
                value: k,
              }))}
            />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select
              allowClear
              showSearch
              options={categoryValues.map((c: string) => ({ label: c, value: c }))}
            />
          </Form.Item>
          <Form.Item name="manufacturer" label="生产商">
            <Input />
          </Form.Item>
          <Form.Item name="spec_model" label="规格/型号">
            <Input />
          </Form.Item>
          <Form.Item name="catalog_no" label="货号">
            <Input />
          </Form.Item>
          <Form.Item name="package_spec" label="包装规格">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
