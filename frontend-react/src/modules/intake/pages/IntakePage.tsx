import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card, Form, Input, InputNumber, DatePicker, Select, Divider, Checkbox,
  Button, Tag, message, Space, Alert, Typography, AutoComplete, Descriptions, Tooltip,
} from "antd";
import Icon, {
  SearchOutlined, ExportOutlined, PlusOutlined, DeleteOutlined,
  ExperimentOutlined, InboxOutlined,
} from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
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
import { mdmPortalUrl } from "../../../shared/mdmPortal";
import { getErrorDetail } from "../../../shared/errors";

// 天平(标准品)与色谱柱在 antd 图标库无对应,用自定义线性 SVG,随字号(1em)与主题色(currentColor)
const BalanceSvg = () => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor"
    strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 4v16" />
    <path d="M8 21h8" />
    <path d="M4.5 6.5h15" />
    <circle cx="12" cy="4" r="1.2" />
    <path d="M4.5 6.5 2 12M4.5 6.5 7 12" />
    <path d="M2 12a2.5 2.5 0 0 0 5 0" />
    <path d="M19.5 6.5 17 12M19.5 6.5 22 12" />
    <path d="M17 12a2.5 2.5 0 0 0 5 0" />
  </svg>
);
const ColumnSvg = () => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor"
    strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2v2" />
    <rect x="8" y="4" width="8" height="15" rx="2.5" />
    <path d="M8 8.5h8" />
    <path d="M8 14.5h8" />
    <path d="M12 19v3" />
  </svg>
);

type IntakeType = "reagent" | "consumable" | "standard" | "column";

const TYPE_META: Record<IntakeType, {
  label: string; color: string; icon: React.ReactNode; hint: string; extra: string;
}> = {
  reagent:    { label: "试剂",   color: "#1677ff", icon: <ExperimentOutlined />,  hint: "常规试剂入库",            extra: "无额外专属字段" },
  consumable: { label: "耗材",   color: "#52c41a", icon: <InboxOutlined />,       hint: "耗材入库",                extra: "无额外专属字段" },
  standard:   { label: "标准品", color: "#722ed1", icon: <Icon component={BalanceSvg} />, hint: "标准品 / 对照品 / 参比品", extra: "浓度、消光系数" },
  column:     { label: "色谱柱", color: "#fa8c16", icon: <Icon component={ColumnSvg} />,  hint: "色谱柱入库",              extra: "序列号、资产编号、负责人" },
};

const TYPES = Object.keys(TYPE_META) as IntakeType[];

// 标准品浓度/活性单位:常见预设(可自行输入其他),与包装/数量单位表(listUnits)是两回事
const CONC_UNITS = [
  "mg/mL", "µg/mL", "ng/mL", "g/L", "mg/L", "µg/L",
  "mol/L", "mmol/L", "µmol/L", "U/mL", "IU/mL", "U/mg", "%",
];

// 批次组 / 位置行的唯一 key 计数器(仅用于 React key,跨挂载递增无妨)
let idCounter = 1;
const nextId = () => idCounter++;

// 字段名在输入框上方
const Labeled = ({ label, children }: { label: React.ReactNode; children: React.ReactNode }) => (
  <div>
    <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>{label}</div>
    {children}
  </div>
);

// 一个存放位置 + 数量(散放),或一个 -80℃ 冰箱孔位选择
interface Pos {
  key: number;
  locationId?: number;
  qty?: number;
  freezer: StorageNode | null;
  freezerSel: FreezerSelection | null;
}
// 一组批次信息:批号/有效期/入库日期 + 类型专属字段 + 1..N 个存放位置
interface BatchGroup {
  key: number;
  batchNo: string;
  expiry: Dayjs | null;
  received: Dayjs;
  positions: Pos[];
  // 色谱柱专属(每根色谱柱一组)
  serialNo?: string;
  assetNo?: string;
  responsiblePerson?: string;
  // 标准品专属:浓度/活性(数值) + 单位 + 原研药批号 + 分装日期
  concValue?: number;
  concUnit?: string;
  originatorBatchNo?: string;
  aliquotDate?: Dayjs | null;
}

function IntakeForm() {
  const newPos = (): Pos => ({ key: nextId(), freezer: null, freezerSel: null });
  const newGroup = (): BatchGroup => ({
    key: nextId(), batchNo: "", expiry: null, received: dayjs(), positions: [newPos()],
  });

  const [activeTab, setActiveTab] = useState<IntakeType>("reagent");
  const [noCode, setNoCode] = useState(false);
  const [materialCode, setMaterialCode] = useState("");
  const [resolved, setResolved] = useState<Material | null>(null);
  const [resolving, setResolving] = useState(false);
  const [notFoundCode, setNotFoundCode] = useState<string | null>(null);
  const [nameQuery, setNameQuery] = useState("");
  // 物料级:单位 / 规格 —— 主数据有则只读取自 resolved;无编码新建时用下面两个本地态
  const [unitVal, setUnitVal] = useState("");
  const [specVal, setSpecVal] = useState("");
  // 标准品:项目编号(表单级,所有批次共用)
  const [projectNo, setProjectNo] = useState("");
  // 实际展示/提交的单位、规格:已解析物料用主数据,否则用用户输入
  const unitShown = resolved ? (resolved.unit ?? "") : unitVal;
  const specShown = resolved ? (resolved.spec_model ?? "") : specVal;
  // 批次组(可多组,每组可多位置)
  const [groups, setGroups] = useState<BatchGroup[]>(() => [newGroup()]);
  const [resetKey, setResetKey] = useState(0);
  const [submitting, setSubmitting] = useState(false);
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
  // 编码模式:多字段(编码/名称/厂家/规格/货号)、多词、忽略大小写的实时搜索
  const { data: codeMatches = [], isFetching: codeSearching } = useQuery({
    queryKey: ["materials", "search", materialCode],
    queryFn: () => listMaterials({ keyword: materialCode.trim() }).then((r) => r.data),
    enabled: !noCode && materialCode.trim().length > 0 && !resolved,
  });
  const codeOptions = (() => {
    const opts: { value: string; label: React.ReactNode; material?: Material }[] = codeMatches
      .slice(0, 20)
      .map((m: Material) => ({
        value: `id:${m.material_id}`,
        label: (
          <Space size={6} wrap>
            <span>{m.material_code === TT_INTERNAL_CODE ? "无编码" : m.material_code}</span>
            <b>{m.name_cn}</b>
            {m.manufacturer && <Typography.Text type="secondary">{m.manufacturer}</Typography.Text>}
            {m.catalog_no && <Typography.Text type="secondary">货号 {m.catalog_no}</Typography.Text>}
          </Space>
        ),
        material: m,
      }));
    const q = materialCode.trim();
    const exact = codeMatches.some((m: Material) => m.material_code === q);
    if (q && !exact) opts.push({ value: "__mdm__", label: `🔍 本地无匹配 → 从 MDM 按编码获取「${q}」` });
    return opts;
  })();

  const onCodePick = async (value: string, opt: { material?: Material }) => {
    if (value === "__mdm__") {
      const code = materialCode.trim();
      setResolving(true); setNotFoundCode(null);
      try {
        await mdmLookup(code);
        const { data } = await createFromMdm(code);
        setResolved(data); setMaterialCode(`${data.material_code} ${data.name_cn}`);
        message.info("已从 MDM 获取物料信息");
      } catch { setNotFoundCode(code); }
      finally { setResolving(false); }
      return;
    }
    const m = opt.material;
    if (m) {
      setResolved(m);
      setMaterialCode(`${m.material_code === TT_INTERNAL_CODE ? "无编码" : m.material_code} ${m.name_cn}`);
      if (m.material_code !== TT_INTERNAL_CODE) {
        setResolving(true);
        try {
          const { data } = await createFromMdm(m.material_code);
          setResolved(data);
          setMaterialCode(`${data.material_code} ${data.name_cn}`);
        } catch {
          message.warning("MDM 暂不可用,已使用本地物料快照");
        } finally {
          setResolving(false);
        }
      }
    }
  };

  // ---- 批次组 / 位置 的不可变更新 ----
  const patchGroup = (gk: number, patch: Partial<BatchGroup>) =>
    setGroups((gs) => gs.map((g) => (g.key === gk ? { ...g, ...patch } : g)));
  const patchPos = (gk: number, pk: number, patch: Partial<Pos>) =>
    setGroups((gs) => gs.map((g) =>
      g.key === gk ? { ...g, positions: g.positions.map((p) => (p.key === pk ? { ...p, ...patch } : p)) } : g));
  const addPos = (gk: number) =>
    setGroups((gs) => gs.map((g) => (g.key === gk ? { ...g, positions: [...g.positions, newPos()] } : g)));
  const removePos = (gk: number, pk: number) =>
    setGroups((gs) => gs.map((g) =>
      g.key === gk ? { ...g, positions: g.positions.filter((p) => p.key !== pk) } : g));
  const addGroup = () => setGroups((gs) => [...gs, newGroup()]);
  const removeGroup = (gk: number) => setGroups((gs) => gs.filter((g) => g.key !== gk));

  const reset = () => {
    form.resetFields(); noCodeForm.resetFields();
    setResolved(null); setMaterialCode(""); setNameQuery("");
    setUnitVal(""); setSpecVal(""); setNotFoundCode(null);
    setProjectNo("");
    setGroups([newGroup()]);
    setResetKey((k) => k + 1);
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
    if (!unitVal.trim()) { message.warning("请填写物料单位(顶部「无编码物料」区的「单位」)"); return null; }
    const v = await noCodeForm.validateFields();
    const { data } = await createMaterial({
      material_code: TT_INTERNAL_CODE, name_cn: name, unit: unitVal.trim(),
      spec_model: specVal.trim() || undefined, manufacturer: v.manufacturer, grade: v.grade,
    });
    return data.material_id;
  };

  type TaskResult =
    | { kind: "bulk"; ok: boolean; created: number; appended: number; error?: string }
    | { kind: "cells"; count: number };

  const submit = async () => {
    let v;
    try { v = await form.validateFields(); } catch { return; }
    const materialId = await ensureMaterialId();
    if (materialId == null) return;

    const remark = v.remark;

    const tasks: Promise<TaskResult>[] = [];
    let anyPos = false;

    for (const g of groups) {
      if (!g.batchNo.trim()) { message.warning("请填写批号"); return; }
      if (!g.received) { message.warning("请填写入库日期"); return; }
      const received = g.received.format("YYYY-MM-DD");
      const expiry = g.expiry?.format("YYYY-MM-DD") ?? null;

      // 类型专属字段(每组各自):标准品=浓度/活性(数值+单位合成字符串);色谱柱=序列号/编号/负责人
      const conc = activeTab === "standard" && g.concValue != null
        ? `${g.concValue}${g.concUnit ? ` ${g.concUnit}` : ""}` : undefined;
      // 标准品专属(项目编号为表单级,所有批次共用;原研药批号/分装日期为每批次)
      const std = activeTab === "standard"
        ? {
            project_no: projectNo.trim() || undefined,
            originator_batch_no: g.originatorBatchNo?.trim() || undefined,
            aliquot_date: g.aliquotDate?.format("YYYY-MM-DD") ?? undefined,
          }
        : {};
      const tf = activeTab === "column"
        ? { serial_no: g.serialNo || undefined, asset_no: g.assetNo || undefined, responsible_person: g.responsiblePerson || undefined }
        : activeTab === "standard"
          ? { concentration: conc, ...std }
          : {};

      const bulkRows: BulkIntakeRow[] = [];
      for (const p of g.positions) {
        if (p.freezer) {
          if (!p.freezerSel) { message.warning(`批次「${g.batchNo}」的 -80℃ 冰箱尚未选孔`); return; }
          anyPos = true;
          const base = {
            material_id: materialId, batch_no: g.batchNo, expiry_date: expiry, received_date: received,
            intake_type: activeTab, concentration: conc, ...std, remark,
          };
          if (p.freezerSel.mode === "from") {
            if (!p.freezerSel.startCellId) { message.warning("请点选起始孔"); return; }
            tasks.push(occupyFrom({
              ...base, start_cell_node_id: p.freezerSel.startCellId, count: p.freezerSel.count,
            }).then((r) => ({ kind: "cells", count: r.data.count })));
          } else {
            if (!p.freezerSel.cellIds.length) { message.warning("请选择孔位"); return; }
            tasks.push(occupyCells({
              ...base, cell_node_ids: p.freezerSel.cellIds,
            }).then((r) => ({ kind: "cells", count: r.data.count })));
          }
        } else if (p.locationId && (p.qty ?? 0) > 0) {
          anyPos = true;
          bulkRows.push({
            material_id: materialId, batch_no: g.batchNo, expiry_date: expiry,
            location_id: p.locationId, qty: p.qty!, remark, ...tf,
          });
        }
      }
      if (bulkRows.length) {
        tasks.push(bulkIntake({ received_date: received, intake_type: activeTab, rows: bulkRows })
          .then((r) => ({
            kind: "bulk", ok: r.data.ok, created: r.data.created, appended: r.data.appended,
            error: r.data.ok ? undefined : (r.data.results.find((x) => x.status === "error")?.message ?? "入库失败"),
          })));
      }
    }

    if (!anyPos) { message.warning("请至少填写一个存放位置与数量(或 -80℃ 孔位)"); return; }

    setSubmitting(true);
    const settled = await Promise.allSettled(tasks);
    setSubmitting(false);

    let created = 0, appended = 0, cells = 0;
    const errors: string[] = [];
    for (const s of settled) {
      if (s.status === "rejected") { errors.push(getErrorDetail(s.reason, "入库失败")); continue; }
      const d = s.value;
      if (d.kind === "bulk") {
        if (!d.ok) errors.push(d.error ?? "入库失败");
        created += d.created; appended += d.appended;
      } else {
        cells += d.count;
      }
    }

    if (errors.length) {
      message.error(errors.join("；"));
      return;
    }
    const parts = [`新建 ${created} 条`, `追加 ${appended} 条`];
    if (cells) parts.push(`冻存 ${cells} 管`);
    message.success(`入库成功:${parts.join("、")}`);
    reset();
  };

  return (
    <div style={{ maxWidth: 1600, margin: "0 auto" }}>
      {/* 四个彩色标签(与下方表格等宽) */}
      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        {TYPES.map((k) => {
          const m = TYPE_META[k];
          const active = k === activeTab;
          return (
            <button
              key={k}
              type="button"
              onClick={() => setActiveTab(k)}
              style={{
                flex: 1, cursor: "pointer", border: `2px solid ${m.color}`, borderRadius: 8,
                padding: "12px 16px", fontSize: 16, fontWeight: 600,
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                background: active ? m.color : `${m.color}12`,
                color: active ? "#fff" : m.color,
                boxShadow: active ? `0 2px 10px ${m.color}59` : "none",
                transition: "all .15s",
              }}
            >
              <span style={{ fontSize: 18, lineHeight: 1 }}>{m.icon}</span>
              {m.label}
            </button>
          );
        })}
      </div>
      <div style={{ marginBottom: 16, color: "#888", fontSize: 13 }}>
        当前登记类型：<b style={{ color: meta.color }}>{meta.label}</b> · {meta.hint} · 专属字段：{meta.extra}
      </div>

      <Card>
        <Form form={form} layout="vertical">
          {/* 物料识别 */}
          <Form.Item label="物料">
            <div style={{ display: "flex", alignItems: "flex-end", flexWrap: "wrap", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
                {!noCode ? (
                  <>
                    <AutoComplete
                      style={{ width: 460 }}
                      value={materialCode}
                      onChange={(val) => { setMaterialCode(val); setResolved(null); setNotFoundCode(null); }}
                      options={codeOptions}
                      onSelect={onCodePick}
                      filterOption={false}
                      notFoundContent={codeSearching ? "搜索中…" : (materialCode.trim() ? "无匹配" : null)}
                    >
                      <Input placeholder="编码/名称/厂家/货号 模糊搜索(空格分隔多词)" prefix={<SearchOutlined />} />
                    </AutoComplete>
                    {resolving && <Tag>解析中…</Tag>}
                    {resolved && <Tag color="green">已选</Tag>}
                  </>
                ) : (
                  <AutoComplete
                    style={{ width: 460 }}
                    value={nameQuery}
                    onChange={(val) => { setNameQuery(val); setResolved(null); }}
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
              </div>
              {activeTab === "standard" && (
                <Labeled label="项目编号">
                  <Input
                    style={{ width: 220 }} placeholder="项目编号" value={projectNo}
                    onChange={(e) => setProjectNo(e.target.value)}
                  />
                </Labeled>
              )}
              <Checkbox
                style={{ paddingBottom: 6, fontSize: 16, fontWeight: 600 }}
                checked={noCode}
                onChange={(e) => { setNoCode(e.target.checked); setResolved(null); setMaterialCode(""); setNameQuery(""); setNotFoundCode(null); }}
              >
                无编码
              </Checkbox>
            </div>
          </Form.Item>

          {notFoundCode && (
            <Alert
              type="warning" showIcon style={{ marginBottom: 16 }}
              message={`本地和 MDM 都没有编码 ${notFoundCode} 的物料`}
              description="可去 MDM 登记后回来重查;或勾选「无编码」直接登记本地物料。"
              action={<Button type="primary" icon={<ExportOutlined />} href={mdmPortalUrl("/materials/new", { code: notFoundCode })} target="_blank">去 MDM 登记</Button>}
            />
          )}

          {noCode && !resolved && (
            <Form form={noCodeForm} layout="vertical" component={false}>
              <Space wrap align="end" size="middle" style={{ marginBottom: 16 }}>
                <Form.Item name="manufacturer" label="来源/厂家" style={{ marginBottom: 0 }}><Input style={{ width: 160 }} /></Form.Item>
                <Form.Item name="grade" label="级别" style={{ marginBottom: 0 }}><Input style={{ width: 120 }} /></Form.Item>
                {/* 单位/规格是物料级属性,无编码新建在此填(不受散放/冻存影响),位置行里只读回显 */}
                <Labeled label={<span>单位 <span style={{ color: "#ff4d4f" }}>*</span></span>}>
                  <Select
                    showSearch placeholder="单位" optionFilterProp="label" style={{ width: 120 }}
                    value={unitVal || undefined} onChange={(val) => setUnitVal(val)}
                    options={units.map((u) => ({ label: u.unit, value: u.unit }))}
                  />
                </Labeled>
                <Labeled label="规格">
                  <Input placeholder="规格" style={{ width: 150 }}
                    value={specVal} onChange={(e) => setSpecVal(e.target.value)} />
                </Labeled>
              </Space>
            </Form>
          )}

          {/* 物料基本信息(只读;常驻显示,解析后填充) */}
          <Descriptions bordered size="small" column={{ xs: 1, sm: 2, lg: 3, xxl: 4 }} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="物料ID">
              {resolved ? <span style={{ color: "#8c8c8c" }}>{resolved.material_id}</span> : "—"}
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

          <Divider titlePlacement="left">批次信息</Divider>

          {groups.map((g, gi) => (
            <Card
              key={g.key}
              size="small"
              style={{ marginBottom: 12, borderLeft: `3px solid ${meta.color}` }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <Tag color={meta.color}>批次 {gi + 1}</Tag>
                {groups.length > 1 && (
                  <Tooltip title="删除此批次">
                    <Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeGroup(g.key)} />
                  </Tooltip>
                )}
              </div>

              {/* 第一行:[标准品 原研药批号/分装日期] 批号 / 有效期 / 入库日期 + 类型专属字段 + 加批次 */}
              <Space align="end" wrap size="middle" style={{ marginBottom: 4 }}>
                {/* 标准品:原研药批号 + 分装日期 排在批号之前 */}
                {activeTab === "standard" && (
                  <>
                    <Labeled label="原研药批号">
                      <Input style={{ width: 180 }} value={g.originatorBatchNo}
                        onChange={(e) => patchGroup(g.key, { originatorBatchNo: e.target.value })} />
                    </Labeled>
                    <Labeled label="分装日期">
                      <DatePicker style={{ width: 150 }} value={g.aliquotDate ?? null}
                        onChange={(d) => patchGroup(g.key, { aliquotDate: d })} />
                    </Labeled>
                  </>
                )}
                <Labeled label={<span>{activeTab === "column" ? "色谱柱批号" : "批号"} <span style={{ color: "#ff4d4f" }}>*</span></span>}>
                  <Input
                    style={{ width: 180 }} value={g.batchNo}
                    onChange={(e) => patchGroup(g.key, { batchNo: e.target.value })}
                  />
                </Labeled>
                <Labeled label="有效期">
                  <DatePicker style={{ width: 150 }} value={g.expiry}
                    onChange={(d) => patchGroup(g.key, { expiry: d })} />
                </Labeled>
                <Labeled label={<span>入库日期 <span style={{ color: "#ff4d4f" }}>*</span></span>}>
                  <DatePicker style={{ width: 150 }} value={g.received}
                    onChange={(d) => patchGroup(g.key, { received: d ?? dayjs() })} />
                </Labeled>

                {/* 色谱柱专属:序列号 / 编号 / 负责人 */}
                {activeTab === "column" && (
                  <>
                    <Labeled label="色谱柱序列号">
                      <Input style={{ width: 160 }} value={g.serialNo}
                        onChange={(e) => patchGroup(g.key, { serialNo: e.target.value })} />
                    </Labeled>
                    <Labeled label="色谱柱编号">
                      <Input style={{ width: 160 }} value={g.assetNo}
                        onChange={(e) => patchGroup(g.key, { assetNo: e.target.value })} />
                    </Labeled>
                    <Labeled label="负责人">
                      <Input style={{ width: 120 }} value={g.responsiblePerson}
                        onChange={(e) => patchGroup(g.key, { responsiblePerson: e.target.value })} />
                    </Labeled>
                  </>
                )}

                {/* 标准品专属:浓度/活性(数值) + 单位 */}
                {activeTab === "standard" && (
                  <>
                    <Labeled label="浓度/活性">
                      <InputNumber style={{ width: 140 }} placeholder="数值" value={g.concValue}
                        onChange={(val) => patchGroup(g.key, { concValue: val ?? undefined })} />
                    </Labeled>
                    <Labeled label="单位">
                      <AutoComplete
                        style={{ width: 130 }} placeholder="如 mg/mL" allowClear
                        value={g.concUnit}
                        onChange={(val) => patchGroup(g.key, { concUnit: val || undefined })}
                        options={CONC_UNITS.map((u) => ({ value: u }))}
                        filterOption={(input, opt) => (opt?.value ?? "").toLowerCase().includes(input.toLowerCase())}
                      />
                    </Labeled>
                  </>
                )}

                <Tooltip title="再加一组批次(同一物料的不同批号)">
                  <Button type="primary" icon={<PlusOutlined />} onClick={addGroup}>加批次</Button>
                </Tooltip>
              </Space>

              {/* 存放位置与数量(可多行) */}
              {g.positions.map((p, pi) => (
                <div key={p.key} style={{ marginTop: 8 }}>
                  <Space align="end" wrap size="middle">
                    <LocationPicker
                      labeled
                      value={p.locationId}
                      onChange={(loc) => patchPos(g.key, p.key, { locationId: loc })}
                      onFreezerSelect={(f) => patchPos(g.key, p.key, { freezer: f, freezerSel: null, locationId: undefined })}
                    />
                    {!p.freezer && (
                      <>
                        <Labeled label="数量">
                          <InputNumber placeholder="数量" min={0.01} value={p.qty} style={{ width: 110 }}
                            onChange={(q) => patchPos(g.key, p.key, { qty: q ?? undefined })} />
                        </Labeled>
                        {/* 单位/规格为物料级,此处只读回显;编辑入口:有编码看物料信息表,无编码在顶部"无编码物料"区 */}
                        <Labeled label="单位">
                          <Input disabled placeholder="单位" style={{ width: 100 }} value={unitShown} />
                        </Labeled>
                        <Labeled label="规格">
                          <Input disabled placeholder="规格" style={{ width: 150 }} value={specShown} />
                        </Labeled>
                      </>
                    )}
                    {pi === 0 ? (
                      <Tooltip title="再加一个存放位置(同一批号分散存放)">
                        <Button type="primary" icon={<PlusOutlined />} onClick={() => addPos(g.key)}>加位置</Button>
                      </Tooltip>
                    ) : (
                      <Tooltip title="删除此存放位置">
                        <Button danger icon={<DeleteOutlined />} onClick={() => removePos(g.key, p.key)} />
                      </Tooltip>
                    )}
                  </Space>
                  {p.freezer && (
                    <div style={{ marginTop: 12 }}>
                      <FreezerCellPicker
                        freezer={p.freezer} resetKey={resetKey}
                        onChange={(sel) => patchPos(g.key, p.key, { freezerSel: sel })}
                      />
                    </div>
                  )}
                </div>
              ))}
            </Card>
          ))}

          {/* 备注 */}
          <Form.Item name="remark" label="备注" style={{ marginTop: 8 }}>
            <Input.TextArea rows={2} />
          </Form.Item>

          <Button type="primary" size="large" loading={submitting} onClick={submit}>确认入库</Button>
        </Form>
      </Card>
    </div>
  );
}

export default function IntakePage() {
  return (
    <>
      <Typography.Title level={4}>入库登记</Typography.Title>
      <IntakeForm />
    </>
  );
}
