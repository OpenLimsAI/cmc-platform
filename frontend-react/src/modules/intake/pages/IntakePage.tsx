import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Card, Tabs, Form, Input, InputNumber, DatePicker,
  Button, Descriptions, Tag, message, Space, Alert, Typography,
} from "antd";
import { SearchOutlined, ExportOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { createFromMdm, mdmLookup, type Material } from "../../../api/materials";
import { createBatch, type BatchCreate } from "../../../api/inventory";
import { listMaterials } from "../../../api/materials";
import { occupyCells, type OccupyRequest, type StorageNode } from "../../../api/storage";
import LocationPicker from "../components/LocationPicker";
import FreezerCellPicker from "../components/FreezerCellPicker";
import { mdmPortalUrl } from "../../../shared/mdmPortal";
import { getErrorDetail } from "../../../shared/errors";

type IntakeType = "reagent" | "consumable" | "standard" | "column";

const TAB_ITEMS = [
  { key: "reagent" as const, label: "试剂" },
  { key: "consumable" as const, label: "耗材" },
  { key: "standard" as const, label: "标准品" },
  { key: "column" as const, label: "色谱柱" },
];

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
  const [form] = Form.useForm();

  const resetAfterSuccess = () => {
    form.resetFields();
    setResolvedMaterial(null);
    setMaterialCode("");
    setFreezer(null);
    setCellIds([]);
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

  return (
    <>
      <Typography.Title level={4}>入库登记</Typography.Title>
      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as IntakeType)}
        items={TAB_ITEMS}
      />

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Input
            placeholder="输入物料编码"
            prefix={<SearchOutlined />}
            value={materialCode}
            onChange={(e) => setMaterialCode(e.target.value)}
            onPressEnter={handleLookup}
            style={{ width: 300 }}
          />
          <Button type="primary" loading={lookupLoading} onClick={handleLookup}>
            查询
          </Button>
        </Space>

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
          <Descriptions
            bordered
            size="small"
            column={3}
            style={{ marginTop: 16 }}
          >
            <Descriptions.Item label="物料编码">
              {resolvedMaterial.material_code}
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

            <Form.Item name="remark" label="备注">
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
