import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Card, Tabs, Form, Input, InputNumber, DatePicker, Select, Divider,
  Button, Descriptions, Tag, message, Space, Alert, Typography, AutoComplete,
} from "antd";
import {
  SearchOutlined, ExportOutlined, ExperimentOutlined, InboxOutlined,
  MedicineBoxOutlined, FilterOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import {
  createFromMdm, mdmLookup, listMaterials, listUnits, createMaterial,
  TT_INTERNAL_CODE, type Material,
} from "../../../api/materials";
import { createBatch, type BatchCreate } from "../../../api/inventory";
import { occupyCells, type OccupyRequest, type StorageNode } from "../../../api/storage";
import LocationPicker from "../components/LocationPicker";
import FreezerCellPicker from "../components/FreezerCellPicker";
import { mdmPortalUrl } from "../../../shared/mdmPortal";
import { getErrorDetail } from "../../../shared/errors";

type IntakeType = "reagent" | "consumable" | "standard" | "column";

// 每种类型独立颜色/图标/说明 + 专属字段提示,让"当前在哪个标签"一眼可见
const TYPE_META: Record<IntakeType, {
  label: string; color: string; icon: React.ReactNode; hint: string; extra: string;
}> = {
  reagent:    { label: "试剂",   color: "#1677ff", icon: <ExperimentOutlined />,  hint: "常规试剂入库",            extra: "无额外专属字段" },
  consumable: { label: "耗材",   color: "#52c41a", icon: <InboxOutlined />,       hint: "耗材入库",                extra: "无额外专属字段" },
  standard:   { label: "标准品", color: "#722ed1", icon: <MedicineBoxOutlined />, hint: "标准品 / 对照品 / 参比品", extra: "浓度、消光系数" },
  column:     { label: "色谱柱", color: "#fa8c16", icon: <FilterOutlined />,      hint: "色谱柱入库",              extra: "序列号、资产编号、负责人" },
};

const TAB_ITEMS = (Object.keys(TYPE_META) as IntakeType[]).map((k) => ({
  key: k,
  label: <Space size={6}>{TYPE_META[k].icon}{TYPE_META[k].label}</Space>,
}));

export default function IntakePage() {
  const [activeTab, setActiveTab] = useState<IntakeType>("reagent");
  const [materialCode, setMaterialCode] = useState("");
  const [resolvedMaterial, setResolvedMaterial] = useState<Material | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  // 本地和 MDM 都没有的编码 → 提供"去 MDM 登记"跳转
  const [notFoundCode, setNotFoundCode] = useState<string | null>(null);
  // 选到 -80℃ 冰箱 → 切到冻存选孔模式
  const [freezer, setFreezer] = useState<StorageNode | null>(null);
  const [cellIds, setCellIds] = useState<number[]>([]);
  // 无编码物料就地登记
  const [noCodeOpen, setNoCodeOpen] = useState(false);
  const [nameQuery, setNameQuery] = useState("");
  const [form] = Form.useForm();
  const [noCodeForm] = Form.useForm();

  const { data: units = [] } = useQuery({
    queryKey: ["units"],
    queryFn: () => listUnits().then((r) => r.data),
  });
  // 无编码登记时按名称搜已有物料, 便于复用而非重复新建
  const { data: nameMatches = [] } = useQuery({
    queryKey: ["materials", "name", nameQuery],
    queryFn: () => listMaterials({ keyword: nameQuery.trim() }).then((r) => r.data),
    enabled: noCodeOpen && nameQuery.trim().length > 0,
  });

  const resetAfterSuccess = () => {
    form.resetFields();
    noCodeForm.resetFields();
    setResolvedMaterial(null);
    setMaterialCode("");
    setFreezer(null);
    setCellIds([]);
    setNoCodeOpen(false);
    setNameQuery("");
  };

  const createLocalMutation = useMutation({
    mutationFn: createMaterial,
    onSuccess: (res) => {
      setResolvedMaterial(res.data);
      setNoCodeOpen(false);
      message.success("已登记无编码物料,继续填写批次信息");
    },
    onError: (e) => message.error(getErrorDetail(e, "登记失败")),
  });

  const handleCreateLocal = async () => {
    const name = nameQuery.trim();
    if (!name) {
      message.warning("请填写物料名称");
      return;
    }
    const v = await noCodeForm.validateFields();
    createLocalMutation.mutate({
      material_code: TT_INTERNAL_CODE,
      name_cn: name,
      unit: v.unit,
      spec_model: v.spec_model,
      manufacturer: v.manufacturer,
      grade: v.grade,
    });
  };

  const batchMutation = useMutation({
    mutationFn: (data: BatchCreate) => createBatch(data),
    onSuccess: () => {
      message.success("入库成功");
      resetAfterSuccess();
    },
    onError: (err: unknown) => {
      message.error(getErrorDetail(err, "入库失败"));
    },
  });

  const occupyMutation = useMutation({
    mutationFn: (data: OccupyRequest) => occupyCells(data),
    onSuccess: (res) => {
      message.success(`已入库 ${res.data.count} 管到 -80℃ 冰箱`);
      resetAfterSuccess();
    },
    onError: (err: unknown) => {
      message.error(getErrorDetail(err, "冻存入库失败"));
    },
  });

  const handleLookup = async () => {
    const code = materialCode.trim();
    if (!code) return;

    setLookupLoading(true);
    setLookupError(null);
    setNotFoundCode(null);
    setResolvedMaterial(null);

    try {
      const localRes = await listMaterials({ keyword: code });
      const localMatch = localRes.data.find(
        (m: Material) => m.material_code === code,
      );

      if (localMatch) {
        setResolvedMaterial(localMatch);
        return;
      }

      try {
        await mdmLookup(code);
        const { data: created } = await createFromMdm(code);
        setResolvedMaterial(created);
        message.info("已从 MDM 获取物料信息");
      } catch {
        setNotFoundCode(code);
      }
    } catch {
      setLookupError("查询失败，请检查网络");
    } finally {
      setLookupLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!resolvedMaterial) {
      message.warning("请先查询物料");
      return;
    }
    try {
      const values = await form.validateFields();
      // -80℃ 冻存入库: 走孔位占用
      if (freezer) {
        if (cellIds.length === 0) {
          message.warning("请在 -80℃ 冰箱中选择孔位");
          return;
        }
        occupyMutation.mutate({
          material_id: resolvedMaterial.material_id,
          batch_no: values.batch_no,
          expiry_date: values.expiry_date?.format("YYYY-MM-DD") ?? null,
          received_date: values.received_date.format("YYYY-MM-DD"),
          cell_node_ids: cellIds,
          intake_type: activeTab,
          concentration: values.concentration,
          extinction_coefficient: values.extinction_coefficient,
          remark: values.remark,
        });
        return;
      }
      // 散放入库(柜 / 普通冰箱)
      const payload: BatchCreate = {
        material_id: resolvedMaterial.material_id,
        batch_no: values.batch_no,
        expiry_date: values.expiry_date?.format("YYYY-MM-DD") ?? null,
        location_id: values.location_id,
        received_date: values.received_date.format("YYYY-MM-DD"),
        initial_qty: values.initial_qty,
        remark: values.remark,
        intake_type: activeTab,
        concentration: values.concentration,
        extinction_coefficient: values.extinction_coefficient,
        serial_no: values.serial_no,
        asset_no: values.asset_no,
        responsible_person: values.responsible_person,
      };
      batchMutation.mutate(payload);
    } catch {
      // form validation error
    }
  };

  const meta = TYPE_META[activeTab];

  return (
    <>
      <Typography.Title level={4}>入库登记</Typography.Title>
      <Tabs
        type="card"
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as IntakeType)}
        items={TAB_ITEMS}
      />

      {/* 常驻横幅:不管下方有没有填,都能一眼看出当前登记类型 */}
      <div
        style={{
          borderLeft: `4px solid ${meta.color}`,
          background: `${meta.color}14`,
          padding: "10px 16px",
          borderRadius: 4,
          marginBottom: 16,
        }}
      >
        <Space>
          <span style={{ color: meta.color, fontSize: 18, lineHeight: 1 }}>{meta.icon}</span>
          <b style={{ color: meta.color }}>当前登记类型：{meta.label}</b>
          <Typography.Text type="secondary">
            {meta.hint} · 专属字段：{meta.extra}
          </Typography.Text>
        </Space>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Input
            placeholder="输入物料编码"
            prefix={<SearchOutlined />}
            value={materialCode}
            onChange={(e) => setMaterialCode(e.target.value)}
            onPressEnter={handleLookup}
            style={{ width: 300 }}
            disabled={noCodeOpen}
          />
          <Button type="primary" loading={lookupLoading} onClick={handleLookup} disabled={noCodeOpen}>
            查询
          </Button>
          {!resolvedMaterial && (
            <Button type="link" onClick={() => setNoCodeOpen((v) => !v)}>
              {noCodeOpen ? "返回按编码查询" : "没有物料编码?"}
            </Button>
          )}
        </Space>

        {noCodeOpen && !resolvedMaterial && (
          <Card size="small" style={{ marginTop: 12, background: "#fafafa" }} title="登记无编码物料(本地)">
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="适用于没有 MDM 编码的物料,如分装原研药作标准品。系统按本地物料记录(编码 TT内部物料),无需去 MDM 编码。"
            />
            <Form layout="vertical" form={noCodeForm} style={{ maxWidth: 560 }}>
              <Form.Item label="物料名称" required>
                <AutoComplete
                  value={nameQuery}
                  onChange={(v) => setNameQuery(v)}
                  placeholder="输入名称;若已登记过会在下方提示可直接选用"
                  options={nameMatches.map((m: Material) => ({
                    value: String(m.material_id),
                    label: `${m.name_cn}${m.material_code === TT_INTERNAL_CODE ? " · 无编码" : ` · ${m.material_code}`}`,
                    material: m,
                  }))}
                  onSelect={(_v, opt) => {
                    const m = (opt as { material: Material }).material;
                    setResolvedMaterial(m);
                    setNoCodeOpen(false);
                    message.success("已选用已有物料");
                  }}
                  filterOption={false}
                />
              </Form.Item>
              <Space wrap align="start">
                <Form.Item name="unit" label="单位" rules={[{ required: true, message: "选单位" }]}>
                  <Select
                    showSearch
                    style={{ width: 140 }}
                    placeholder="单位"
                    optionFilterProp="label"
                    options={units.map((u) => ({ label: u.unit, value: u.unit }))}
                  />
                </Form.Item>
                <Form.Item name="spec_model" label="规格">
                  <Input style={{ width: 160 }} placeholder="如 1 mg/支" />
                </Form.Item>
                <Form.Item name="manufacturer" label="生产商/来源">
                  <Input style={{ width: 160 }} />
                </Form.Item>
                <Form.Item name="grade" label="级别">
                  <Input style={{ width: 120 }} />
                </Form.Item>
              </Space>
              <Button
                type="primary"
                loading={createLocalMutation.isPending}
                onClick={handleCreateLocal}
              >
                登记并继续入库
              </Button>
            </Form>
          </Card>
        )}

        {lookupError && (
          <Alert type="warning" message={lookupError} style={{ marginTop: 12 }} showIcon />
        )}

        {notFoundCode && (
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 12 }}
            message={`本地和 MDM 都没有编码为 ${notFoundCode} 的物料`}
            description="新物料需要先在 MDM 登记身份信息（编码/名称/厂家等），登记完成后回到本页重新查询即可继续入库。"
            action={
              <Button
                type="primary"
                icon={<ExportOutlined />}
                href={mdmPortalUrl("/materials/new", { code: notFoundCode })}
                target="_blank"
              >
                去 MDM 登记此物料
              </Button>
            }
          />
        )}

        {resolvedMaterial && (
          <>
          <div style={{ marginTop: 16, marginBottom: 8, textAlign: "right" }}>
            <Button size="small" onClick={() => { setResolvedMaterial(null); setMaterialCode(""); setNameQuery(""); }}>
              重新选择物料
            </Button>
          </div>
          <Descriptions
            bordered
            size="small"
            column={3}
          >
            <Descriptions.Item label="物料ID">
              <Typography.Text type="secondary" style={{ fontFamily: "monospace" }}>
                {resolvedMaterial.material_id}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="物料编码">
              {resolvedMaterial.material_code === TT_INTERNAL_CODE ? (
                <Tag color="orange">无编码</Tag>
              ) : (
                resolvedMaterial.material_code
              )}
            </Descriptions.Item>
            <Descriptions.Item label="物料名称">
              {resolvedMaterial.name_cn}
            </Descriptions.Item>
            <Descriptions.Item label="来源">
              {resolvedMaterial.data_source === "mdm" ? (
                <Tag color="geekblue">MDM</Tag>
              ) : (
                <Tag>本地</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="生产商">
              {resolvedMaterial.manufacturer}
            </Descriptions.Item>
            <Descriptions.Item label="规格">
              {resolvedMaterial.spec_model}
            </Descriptions.Item>
            <Descriptions.Item label="货号">
              {resolvedMaterial.catalog_no}
            </Descriptions.Item>
            <Descriptions.Item label="单位">
              {resolvedMaterial.unit}
            </Descriptions.Item>
            <Descriptions.Item label="类型">
              {resolvedMaterial.material_type}
            </Descriptions.Item>
            <Descriptions.Item label="分类">
              {resolvedMaterial.category}
            </Descriptions.Item>
          </Descriptions>
          </>
        )}
      </Card>

      {resolvedMaterial && (
        <Card title="批次信息">
          <Form
            form={form}
            layout="vertical"
            initialValues={{ received_date: dayjs() }}
            style={{ maxWidth: 800 }}
          >
            <Form.Item name="batch_no" label="批号" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="expiry_date" label="有效期">
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item
              name="location_id"
              label="存放位置"
              rules={[{ required: !freezer, message: "请选择房间 / 柜或冰箱 / 板层" }]}
            >
              <LocationPicker onFreezerSelect={(f) => { setFreezer(f); setCellIds([]); }} />
            </Form.Item>

            {freezer && (
              <Form.Item label="冻存孔位">
                <FreezerCellPicker freezer={freezer} value={cellIds} onChange={setCellIds} />
              </Form.Item>
            )}

            <Form.Item name="received_date" label="入库日期" rules={[{ required: true }]}>
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
            {!freezer && (
              <Form.Item name="initial_qty" label="入库数量" rules={[{ required: true }]}>
                <InputNumber min={0.01} style={{ width: "100%" }} />
              </Form.Item>
            )}

            {/* 类型专属信息分区:常驻显示, 每种类型都有, 强化"当前标签"存在感 */}
            <Divider titlePlacement="left" style={{ borderColor: meta.color }}>
              <Space size={6}>
                <Tag color={meta.color}>{meta.label}</Tag>
                <span>类型专属信息</span>
              </Space>
            </Divider>

            {activeTab === "standard" && (
              <>
                <Form.Item name="concentration" label="浓度">
                  <Input placeholder="如 10 mg/mL" />
                </Form.Item>
                <Form.Item name="extinction_coefficient" label="消光系数">
                  <InputNumber style={{ width: "100%" }} />
                </Form.Item>
              </>
            )}

            {activeTab === "column" && (
              <>
                <Form.Item name="serial_no" label="序列号">
                  <Input />
                </Form.Item>
                <Form.Item name="asset_no" label="资产编号">
                  <Input />
                </Form.Item>
                <Form.Item name="responsible_person" label="负责人">
                  <Input />
                </Form.Item>
              </>
            )}

            {(activeTab === "reagent" || activeTab === "consumable") && (
              <Typography.Text type="secondary">
                {meta.label}无额外专属字段,按上方通用信息入库即可。
              </Typography.Text>
            )}

            <Form.Item name="remark" label="备注" style={{ marginTop: 16 }}>
              <Input.TextArea rows={2} />
            </Form.Item>

            <Button
              type="primary"
              size="large"
              loading={batchMutation.isPending || occupyMutation.isPending}
              onClick={handleSubmit}
            >
              {freezer ? `确认冻存入库${cellIds.length ? `(${cellIds.length} 管)` : ""}` : "确认入库"}
            </Button>
          </Form>
        </Card>
      )}
    </>
  );
}
