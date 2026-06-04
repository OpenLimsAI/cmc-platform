import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Table, Input, Select, Button, Space, Tag, Modal, Form,
  message, Typography, Radio, Alert, Descriptions, Spin,
} from "antd";
import { PlusOutlined, SearchOutlined, ExportOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  listMaterials, createMaterial, createFromMdm, mdmSearch,
  listCategoryValues, listUnits,
  type Material, type MaterialCreate,
} from "../../../api/materials";
import { useAuthStore } from "../../../stores/authStore";
import { mdmPortalUrl } from "../../../shared/mdmPortal";

const MATERIAL_TYPE_MAP: Record<string, { label: string; color: string }> = {
  reagent: { label: "试剂", color: "blue" },
  consumable: { label: "耗材", color: "green" },
  standard: { label: "标准品", color: "gold" },
  column: { label: "色谱柱", color: "purple" },
};

// MDM 物料列表项(只取展示需要的字段)
interface MdmMaterialBrief {
  material_code: string;
  material_name: string;
  material_type: string;
  category: string | null;
  manufacturer: string | null;
  spec_model: string | null;
  unit: string | null;
}

export default function MaterialListPage() {
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState<string>();
  const [createOpen, setCreateOpen] = useState(false);
  // 新增模式: 从 MDM 引用(推荐) / 本地新建(MDM 不可用时兜底)
  const [createMode, setCreateMode] = useState<"mdm" | "local">("mdm");
  const [mdmOptions, setMdmOptions] = useState<MdmMaterialBrief[]>([]);
  const [mdmSelected, setMdmSelected] = useState<MdmMaterialBrief | null>(null);
  const [mdmSearching, setMdmSearching] = useState(false);
  const [mdmLastSearch, setMdmLastSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const mdmSearchSeq = useRef(0);
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

  const closeCreate = () => {
    setCreateOpen(false);
    setMdmSelected(null);
    setMdmOptions([]);
    setMdmLastSearch("");
    form.resetFields();
  };

  const handleMdmSearch = async (q: string) => {
    setMdmLastSearch(q.trim());
    if (!q.trim()) {
      setMdmOptions([]);
      return;
    }
    const seq = ++mdmSearchSeq.current;
    setMdmSearching(true);
    try {
      const resp = await mdmSearch(q.trim());
      if (seq === mdmSearchSeq.current) {
        setMdmOptions((resp.data as { data?: MdmMaterialBrief[] }).data ?? []);
      }
    } catch {
      if (seq === mdmSearchSeq.current) {
        setMdmOptions([]);
        message.warning("MDM 暂不可用,可切换为本地新建");
      }
    } finally {
      if (seq === mdmSearchSeq.current) setMdmSearching(false);
    }
  };

  const handleCreate = async () => {
    setCreating(true);
    try {
      if (createMode === "mdm") {
        if (!mdmSelected) {
          message.warning("请先搜索并选择 MDM 中的物料");
          return;
        }
        await createFromMdm(mdmSelected.material_code);
        message.success(`已从 MDM 引用建档: ${mdmSelected.material_code}`);
      } else {
        const values = await form.validateFields();
        await createMaterial(values as MaterialCreate);
        message.success("物料已创建(本地,请尽快在 MDM 补登主数据)");
      }
      closeCreate();
      refetch();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (detail) message.error(detail);
    } finally {
      setCreating(false);
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
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => { setCreateMode("mdm"); setCreateOpen(true); }}
          >
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
        onCancel={closeCreate}
        confirmLoading={creating}
        width={640}
        destroyOnClose
      >
        <Radio.Group
          value={createMode}
          onChange={(e) => {
            setCreateMode(e.target.value as "mdm" | "local");
            setMdmSelected(null);
            form.resetFields();
          }}
          style={{ marginBottom: 16 }}
        >
          <Radio.Button value="mdm">从 MDM 引用(推荐)</Radio.Button>
          <Radio.Button value="local">本地新建</Radio.Button>
        </Radio.Group>

        {createMode === "mdm" && (
          <>
            <Select
              showSearch
              placeholder="输入编码/名称/生产商/货号搜索 MDM 物料主数据"
              style={{ width: "100%", marginBottom: 12 }}
              filterOption={false}
              onSearch={handleMdmSearch}
              notFoundContent={mdmSearching ? <Spin size="small" /> : "无匹配(请先在 MDM Portal 登记)"}
              value={mdmSelected?.material_code}
              onChange={(code: string) => {
                setMdmSelected(mdmOptions.find((o) => o.material_code === code) ?? null);
              }}
              options={mdmOptions.map((o) => ({
                value: o.material_code,
                label: `${o.material_code} — ${o.material_name}${o.manufacturer ? ` (${o.manufacturer})` : ""}`,
              }))}
            />
            {mdmSelected ? (
              <Descriptions bordered size="small" column={2} style={{ marginBottom: 8 }}>
                <Descriptions.Item label="编码">{mdmSelected.material_code}</Descriptions.Item>
                <Descriptions.Item label="名称">{mdmSelected.material_name}</Descriptions.Item>
                <Descriptions.Item label="类型">
                  {MATERIAL_TYPE_MAP[mdmSelected.material_type]?.label ?? mdmSelected.material_type}
                </Descriptions.Item>
                <Descriptions.Item label="分类">{mdmSelected.category ?? "—"}</Descriptions.Item>
                <Descriptions.Item label="生产商">{mdmSelected.manufacturer ?? "—"}</Descriptions.Item>
                <Descriptions.Item label="单位">{mdmSelected.unit ?? "—"}</Descriptions.Item>
              </Descriptions>
            ) : mdmLastSearch && !mdmSearching && mdmOptions.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                style={{ marginBottom: 8 }}
                message={`MDM 中没有匹配"${mdmLastSearch}"的物料`}
                description="新物料需要先在 MDM 登记身份信息(编码/名称/厂家等),登记完成后回到这里重新搜索即可。"
                action={
                  <Button
                    type="primary"
                    icon={<ExportOutlined />}
                    href={mdmPortalUrl("/materials/new", { code: mdmLastSearch })}
                    target="_blank"
                  >
                    去 MDM 登记此物料
                  </Button>
                }
              />
            ) : (
              <Alert
                type="info"
                style={{ marginBottom: 8 }}
                message="物料身份信息(编码/名称/厂家/规格)以 MDM 为权威源,选中后自动抄入本系统"
              />
            )}
          </>
        )}

        {createMode === "local" && (
          <>
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message="本地新建仅作 MDM 不可用时的兜底;请事后在 MDM Portal 补登该物料主数据"
            />
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
          </>
        )}
      </Modal>
    </>
  );
}
