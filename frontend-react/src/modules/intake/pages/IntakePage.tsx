import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Card, Tabs, Form, Input, InputNumber, DatePicker, Select, Divider, Checkbox,
  Button, Tag, message, Space, Alert, Typography, AutoComplete, Segmented, Descriptions,
} from "antd";
import {
  SearchOutlined, ExportOutlined, PlusOutlined, DeleteOutlined,
  ExperimentOutlined, InboxOutlined, MedicineBoxOutlined, FilterOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import {
  createFromMdm, mdmLookup, listMaterials, listUnits, createMaterial,
  TT_INTERNAL_CODE, type Material,
} from "../../../api/materials";
import { bulkIntake, type BulkIntakeRow } from "../../../api/inventory";
import {
  occupyCells, occupyFrom, type StorageNode,
} from "../../../api/storage";
import LocationPicker from "../components/LocationPicker";
import FreezerCellPicker, { type FreezerSelection } from "../components/FreezerCellPicker";
import BulkIntakePage from "./BulkIntakePage";
import { mdmPortalUrl } from "../../../shared/mdmPortal";
import { getErrorDetail } from "../../../shared/errors";

type IntakeType = "reagent" | "consumable" | "standard" | "column";

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

interface BulkPos { key: number; locationId?: number; qty?: number }

function SingleIntake() {
  const [activeTab, setActiveTab] = useState<IntakeType>("reagent");
  const [noCode, setNoCode] = useState(false);
  const [materialCode, setMaterialCode] = useState("");
  const [resolved, setResolved] = useState<Material | null>(null);
  const [resolving, setResolving] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [notFoundCode, setNotFoundCode] = useState<string | null>(null);
  const [nameQuery, setNameQuery] = useState("");
  // 存放与分配
  const [primaryLoc, setPrimaryLoc] = useState<number>();
  const [primaryQty, setPrimaryQty] = useState<number>();
  const [extra, setExtra] = useState<BulkPos[]>([]);
  const [freezer, setFreezer] = useState<StorageNode | null>(null);
  const [freezerSel, setFreezerSel] = useState<FreezerSelection | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [form] = Form.useForm();
  const [noCodeForm] = Form.useForm();
  const meta = TYPE_META[activeTab];

  const { data: units = [] } = useQuery({
    queryKey: ["units"], queryFn: () => listUnits().then((r) => r.data),
  });
  const { data: nameMatches = [] } = useQuery({
    queryKey: ["materials", "name", nameQuery],
    queryFn: () => listMaterials({ keyword: nameQuery.trim() }).then((r) => r.data),
    enabled: noCode && nameQuery.trim().length > 0,
  });

  const reset = () => {
    form.resetFields(); noCodeForm.resetFields();
    setResolved(null); setMaterialCode(""); setNameQuery("");
    setPrimaryLoc(undefined); setPrimaryQty(undefined); setExtra([]);
    setFreezer(null); setFreezerSel(null); setResetKey((k) => k + 1);
    setLookupError(null); setNotFoundCode(null);
  };

  const onDone = (msg: string) => { message.success(msg); reset(); };
  const bulkMut = useMutation({
    mutationFn: bulkIntake,
    onSuccess: (res) => res.data.ok
      ? onDone(`入库成功:新建 ${res.data.created} 条、追加 ${res.data.appended} 条`)
      : message.error(res.data.results.find((r) => r.status === "error")?.message ?? "入库失败"),
    onError: (e) => message.error(getErrorDetail(e, "入库失败")),
  });
  const occMut = useMutation({
    mutationFn: occupyCells,
    onSuccess: (res) => onDone(`已入库 ${res.data.count} 管到 -80℃ 冰箱`),
    onError: (e) => message.error(getErrorDetail(e, "冻存入库失败")),
  });
  const occFromMut = useMutation({
    mutationFn: occupyFrom,
    onSuccess: (res) => onDone(`已从起始位置连续填充 ${res.data.count} 管`),
    onError: (e) => message.error(getErrorDetail(e, "连续填充失败")),
  });

  const resolveCode = async () => {
    const code = materialCode.trim();
    if (!code) return;
    setResolving(true); setLookupError(null); setNotFoundCode(null); setResolved(null);
    try {
      const local = await listMaterials({ keyword: code });
      const m = local.data.find((x: Material) => x.material_code === code);
      if (m) { setResolved(m); return; }
      try {
        await mdmLookup(code);
        const { data: created } = await createFromMdm(code);
        setResolved(created); message.info("已从 MDM 获取物料信息");
      } catch { setNotFoundCode(code); }
    } catch { setLookupError("查询失败,请检查网络"); }
    finally { setResolving(false); }
  };

  // 解析/取得 material_id;无编码时按需新建本地物料
  const ensureMaterialId = async (): Promise<number | null> => {
    if (!noCode) {
      if (!resolved) { message.warning("请输入物料编码并解析"); return null; }
      return resolved.material_id;
    }
    if (resolved) return resolved.material_id;        // 自动补全选了已有
    const name = nameQuery.trim();
    if (!name) { message.warning("请填写物料名称"); return null; }
    const v = await noCodeForm.validateFields();
    const { data } = await createMaterial({
      material_code: TT_INTERNAL_CODE, name_cn: name, unit: v.unit,
      spec_model: v.spec_model, manufacturer: v.manufacturer, grade: v.grade,
    });
    return data.material_id;
  };

  const submit = async () => {
    let v;
    try { v = await form.validateFields(); } catch { return; }
    const materialId = await ensureMaterialId();
    if (materialId == null) return;
    const received = v.received_date.format("YYYY-MM-DD");
    const expiry = v.expiry_date?.format("YYYY-MM-DD") ?? null;
    const typeFields = {
      concentration: v.concentration, extinction_coefficient: v.extinction_coefficient,
      serial_no: v.serial_no, asset_no: v.asset_no, responsible_person: v.responsible_person,
    };

    if (freezer) {
      if (!freezerSel) { message.warning("请在 -80℃ 冰箱中选孔"); return; }
      if (freezerSel.mode === "from") {
        if (!freezerSel.startCellId) { message.warning("请点选起始孔"); return; }
        occFromMut.mutate({
          material_id: materialId, batch_no: v.batch_no, expiry_date: expiry, received_date: received,
          start_cell_node_id: freezerSel.startCellId, count: freezerSel.count,
          intake_type: activeTab, concentration: v.concentration, extinction_coefficient: v.extinction_coefficient, remark: v.remark,
        });
      } else {
        if (!freezerSel.cellIds.length) { message.warning("请选择孔位"); return; }
        occMut.mutate({
          material_id: materialId, batch_no: v.batch_no, expiry_date: expiry, received_date: received,
          cell_node_ids: freezerSel.cellIds,
          intake_type: activeTab, concentration: v.concentration, extinction_coefficient: v.extinction_coefficient, remark: v.remark,
        });
      }
      return;
    }

    // 散放:主位置 + 额外位置
    const all: BulkPos[] = [{ key: -1, locationId: primaryLoc, qty: primaryQty }, ...extra];
    const rows: BulkIntakeRow[] = all
      .filter((p) => p.locationId && (p.qty ?? 0) > 0)
      .map((p) => ({
        material_id: materialId, batch_no: v.batch_no, expiry_date: expiry,
        location_id: p.locationId!, qty: p.qty!, remark: v.remark, ...typeFields,
      }));
    if (!rows.length) { message.warning("请选择存放位置并填写数量"); return; }
    bulkMut.mutate({ received_date: received, intake_type: activeTab, rows });
  };

  const pending = bulkMut.isPending || occMut.isPending || occFromMut.isPending;

  return (
    <>
      <Tabs type="card" activeKey={activeTab} onChange={(k) => setActiveTab(k as IntakeType)} items={TAB_ITEMS} />
      <div style={{ borderLeft: `4px solid ${meta.color}`, background: `${meta.color}14`, padding: "10px 16px", borderRadius: 4, marginBottom: 16 }}>
        <Space>
          <span style={{ color: meta.color, fontSize: 18, lineHeight: 1 }}>{meta.icon}</span>
          <b style={{ color: meta.color }}>当前登记类型：{meta.label}</b>
          <Typography.Text type="secondary">{meta.hint} · 专属字段：{meta.extra}</Typography.Text>
        </Space>
      </div>

      <Card>
        <Form form={form} layout="vertical" initialValues={{ received_date: dayjs() }} style={{ maxWidth: 860 }}>
          {/* 物料识别 */}
          <Form.Item label="物料">
            <Space align="start" wrap>
              {!noCode ? (
                <>
                  <Input
                    placeholder="输入物料编码后回车/失焦解析"
                    prefix={<SearchOutlined />}
                    value={materialCode}
                    onChange={(e) => setMaterialCode(e.target.value)}
                    onPressEnter={resolveCode}
                    onBlur={resolveCode}
                    style={{ width: 280 }}
                  />
                  {resolving && <Tag>解析中…</Tag>}
                  {resolved && <Tag color="green">{resolved.name_cn}</Tag>}
                </>
              ) : (
                <AutoComplete
                  style={{ width: 280 }}
                  value={nameQuery}
                  onChange={(v) => { setNameQuery(v); setResolved(null); }}
                  placeholder="物料名称(已建过会提示可选用)"
                  options={nameMatches.map((m: Material) => ({
                    value: String(m.material_id),
                    label: `${m.name_cn}${m.material_code === TT_INTERNAL_CODE ? " · 无编码" : ` · ${m.material_code}`}`,
                    material: m,
                  }))}
                  onSelect={(_v, opt) => {
                    const m = (opt as { material: Material }).material;
                    setResolved(m); setNameQuery(m.name_cn); message.success("已选用已有物料");
                  }}
                  filterOption={false}
                />
              )}
              <Checkbox
                checked={noCode}
                onChange={(e) => { setNoCode(e.target.checked); setResolved(null); setMaterialCode(""); setNameQuery(""); setNotFoundCode(null); }}
              >
                无编码
              </Checkbox>
            </Space>
          </Form.Item>

          {notFoundCode && (
            <Alert
              type="warning" showIcon style={{ marginBottom: 16 }}
              message={`本地和 MDM 都没有编码 ${notFoundCode} 的物料`}
              description="可去 MDM 登记后回来重查;或勾选「无编码」直接登记本地物料。"
              action={<Button type="primary" icon={<ExportOutlined />} href={mdmPortalUrl("/materials/new", { code: notFoundCode })} target="_blank">去 MDM 登记</Button>}
            />
          )}
          {lookupError && <Alert type="warning" showIcon message={lookupError} style={{ marginBottom: 16 }} />}

          {noCode && !resolved && (
            <div style={{ marginBottom: 16 }}>
              <Form form={noCodeForm} layout="inline" component={false}>
                <Space wrap>
                  <Form.Item name="unit" label="单位" rules={[{ required: true, message: "选单位" }]}>
                    <Select showSearch style={{ width: 120 }} placeholder="单位" optionFilterProp="label"
                      options={units.map((u) => ({ label: u.unit, value: u.unit }))} />
                  </Form.Item>
                  <Form.Item name="spec_model" label="规格"><Input style={{ width: 140 }} placeholder="如 1 mg/支" /></Form.Item>
                  <Form.Item name="manufacturer" label="来源/厂家"><Input style={{ width: 140 }} /></Form.Item>
                  <Form.Item name="grade" label="级别"><Input style={{ width: 100 }} /></Form.Item>
                </Space>
              </Form>
            </div>
          )}

          {/* 物料基本信息(只读;常驻显示,解析后填充) */}
          <Descriptions bordered size="small" column={3} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="物料ID">
              {resolved ? <Typography.Text type="secondary">{resolved.material_id}</Typography.Text> : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="物料编码">
              {resolved
                ? (resolved.material_code === TT_INTERNAL_CODE ? <Tag color="orange">无编码</Tag> : resolved.material_code)
                : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="物料名称">{resolved?.name_cn ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="来源">
              {resolved ? (resolved.data_source === "mdm" ? <Tag color="geekblue">MDM</Tag> : <Tag>本地</Tag>) : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="生产商">{resolved?.manufacturer ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="规格">{resolved?.spec_model ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="货号">{resolved?.catalog_no ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="单位">{resolved?.unit ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="分类">{resolved?.category ?? "—"}</Descriptions.Item>
          </Descriptions>

          {/* 通用批次字段 */}
          <Space wrap size="large" align="start">
            <Form.Item name="batch_no" label="批号" rules={[{ required: true }]}><Input style={{ width: 200 }} /></Form.Item>
            <Form.Item name="expiry_date" label="有效期"><DatePicker style={{ width: 160 }} /></Form.Item>
            <Form.Item name="received_date" label="入库日期" rules={[{ required: true }]}><DatePicker style={{ width: 160 }} /></Form.Item>
          </Space>

          {/* 类型专属字段(常驻) */}
          <Divider titlePlacement="left" style={{ borderColor: meta.color }}>
            <Space size={6}><Tag color={meta.color}>{meta.label}</Tag><span>类型专属信息</span></Space>
          </Divider>
          {activeTab === "standard" && (
            <Space wrap size="large">
              <Form.Item name="concentration" label="浓度"><Input placeholder="如 10 mg/mL" style={{ width: 200 }} /></Form.Item>
              <Form.Item name="extinction_coefficient" label="消光系数"><InputNumber style={{ width: 200 }} /></Form.Item>
            </Space>
          )}
          {activeTab === "column" && (
            <Space wrap size="large">
              <Form.Item name="serial_no" label="序列号"><Input style={{ width: 160 }} /></Form.Item>
              <Form.Item name="asset_no" label="资产编号"><Input style={{ width: 160 }} /></Form.Item>
              <Form.Item name="responsible_person" label="负责人"><Input style={{ width: 120 }} /></Form.Item>
            </Space>
          )}
          {(activeTab === "reagent" || activeTab === "consumable") && (
            <Typography.Text type="secondary">{meta.label}无额外专属字段。</Typography.Text>
          )}

          {/* 存放与数量分配 */}
          <Divider titlePlacement="left">存放位置与数量</Divider>
          <Space align="start" wrap>
            <LocationPicker
              value={primaryLoc}
              onChange={setPrimaryLoc}
              onFreezerSelect={(f) => { setFreezer(f); if (f) setFreezerSel(null); }}
            />
            {!freezer && (
              <InputNumber placeholder="数量" min={0.01} value={primaryQty} onChange={(q) => setPrimaryQty(q ?? undefined)} style={{ width: 120 }} />
            )}
          </Space>

          {freezer && (
            <div style={{ marginTop: 12 }}>
              <FreezerCellPicker freezer={freezer} resetKey={resetKey} onChange={setFreezerSel} />
            </div>
          )}

          {!freezer && (
            <div style={{ marginTop: 8 }}>
              {extra.map((p) => (
                <Space key={p.key} align="start" wrap style={{ display: "flex", marginBottom: 8 }}>
                  <LocationPicker value={p.locationId} onChange={(loc) => setExtra((xs) => xs.map((x) => x.key === p.key ? { ...x, locationId: loc } : x))} />
                  <InputNumber placeholder="数量" min={0.01} value={p.qty} onChange={(q) => setExtra((xs) => xs.map((x) => x.key === p.key ? { ...x, qty: q ?? undefined } : x))} style={{ width: 120 }} />
                  <Button danger icon={<DeleteOutlined />} onClick={() => setExtra((xs) => xs.filter((x) => x.key !== p.key))} />
                </Space>
              ))}
              <Button type="dashed" icon={<PlusOutlined />} onClick={() => setExtra((xs) => [...xs, { key: Date.now() }])}>
                加位置(同一批放不下时分散到其他柜/板层)
              </Button>
            </div>
          )}

          <div style={{ marginTop: 20 }}>
            <Form.Item name="remark" label="备注" style={{ maxWidth: 600 }}><Input.TextArea rows={2} /></Form.Item>
            <Button type="primary" size="large" loading={pending} onClick={submit}>确认入库</Button>
          </div>
        </Form>
      </Card>
    </>
  );
}

export default function IntakePage() {
  const [mode, setMode] = useState<"single" | "multi">("single");
  return (
    <>
      <Typography.Title level={4}>入库登记</Typography.Title>
      <Segmented
        value={mode}
        onChange={(v) => setMode(v as "single" | "multi")}
        options={[
          { label: "单物料登记", value: "single" },
          { label: "多物料批量", value: "multi" },
        ]}
        style={{ marginBottom: 16 }}
      />
      {mode === "single" ? <SingleIntake /> : <BulkIntakePage embedded />}
    </>
  );
}
