import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Table, Input, Select, Button, Space, Tag, Typography, Tooltip,
} from "antd";
import { SearchOutlined, ExportOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  listMaterials, listCategoryValues, type Material,
} from "../../../api/materials";
import { useAuthStore } from "../../../stores/authStore";
import { mdmPortalUrl } from "../../../shared/mdmPortal";

const MATERIAL_TYPE_MAP: Record<string, { label: string; color: string }> = {
  reagent: { label: "试剂", color: "blue" },
  consumable: { label: "耗材", color: "green" },
  standard: { label: "标准品", color: "gold" },
  column: { label: "色谱柱", color: "purple" },
};

/**
 * 物料查询(只读) — 展示本仓库使用过的物料。
 * 新增/编辑物料一律在 MDM Portal 操作(主数据权威源);
 * MDM 登记后,在入库页输入编码即自动引用建档,无需手工同步。
 */
export default function MaterialListPage() {
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState<string>();
  const canWrite = useAuthStore((s) => s.canWrite());

  const { data: materials = [], isLoading } = useQuery({
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

  const columns: ColumnsType<Material> = [
    {
      title: "物料ID",
      dataIndex: "material_id",
      width: 90,
      fixed: "left",
      render: (v: number) => <Typography.Text type="secondary" style={{ fontFamily: "monospace" }}>{v}</Typography.Text>,
    },
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
      <Typography.Title level={4}>物料查询</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        此处展示本仓库使用过的物料。新物料请在 MDM 登记,登记后在入库页输入编码即自动引用。
      </Typography.Paragraph>
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
          <Tooltip title="物料主数据统一在 MDM Portal 维护">
            <Button
              type="primary"
              icon={<ExportOutlined />}
              href={mdmPortalUrl("/materials/new")}
              target="_blank"
            >
              去 MDM 新增物料
            </Button>
          </Tooltip>
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
    </>
  );
}
