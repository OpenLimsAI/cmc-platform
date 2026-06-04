import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Typography, Table, Tag, Input, Select, Space, Button, Modal, Form,
  DatePicker, InputNumber, message, Switch, Radio, Alert, Descriptions, Spin,
} from "antd";
import { PlusOutlined, ExportOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import {
  listEquipment, createEquipment, updateEquipment, listEquipmentCategories,
  searchMdmEquipments, createEquipmentFromMdm,
  STATUS_LABEL, type Equipment, type EquipmentPayload, type MdmEquipmentBrief,
} from "../../../api/equipment";
import { useAuthStore } from "../../../stores/authStore";
import { mdmPortalUrl } from "../../../shared/mdmPortal";

const STATUS_OPTIONS = Object.entries(STATUS_LABEL).map(([value, v]) => ({
  value, label: v.text,
}));

function errDetail(err: unknown, fallback: string): string {
  return (
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
  );
}

export default function EquipmentListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasRole } = useAuthStore();
  const canEdit = hasRole("SYS_ADMIN") || hasRole("CMC_EQUIPMENT_ADMIN");

  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>();
  const [includeInactive, setIncludeInactive] = useState(false);
  const [editing, setEditing] = useState<Equipment | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  // 新建模式: 从 MDM 引用(推荐) / 本地新建(MDM 不可用时兜底)
  const [createMode, setCreateMode] = useState<"mdm" | "local">("mdm");
  const [mdmOptions, setMdmOptions] = useState<MdmEquipmentBrief[]>([]);
  const [mdmSelected, setMdmSelected] = useState<MdmEquipmentBrief | null>(null);
  const [mdmSearching, setMdmSearching] = useState(false);
  const [mdmLastSearch, setMdmLastSearch] = useState("");
  const mdmSearchSeq = useRef(0);
  const [form] = Form.useForm();

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["equipment", keyword, category, status, includeInactive],
    queryFn: () =>
      listEquipment({
        keyword: keyword || undefined,
        category,
        status,
        include_inactive: includeInactive || undefined,
      }).then((r) => r.data),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ["equipmentCategories"],
    queryFn: () => listEquipmentCategories().then((r) => r.data),
  });

  const closeModal = () => {
    setModalOpen(false);
    setEditing(null);
    setMdmSelected(null);
    setMdmOptions([]);
    form.resetFields();
  };

  const onSaved = (msg: string) => {
    message.success(msg);
    closeModal();
    queryClient.invalidateQueries({ queryKey: ["equipment"] });
    queryClient.invalidateQueries({ queryKey: ["equipmentCategories"] });
  };

  const saveMutation = useMutation({
    mutationFn: (data: EquipmentPayload) =>
      editing
        ? updateEquipment(editing.equipment_id, data)
        : createEquipment(data),
    onSuccess: () => onSaved(editing ? "设备已更新" : "设备已创建(本地,请尽快在 MDM 补登主数据)"),
    onError: (err: unknown) => message.error(errDetail(err, "保存失败")),
  });

  const fromMdmMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      createEquipmentFromMdm(mdmSelected!.equipment_code, data),
    onSuccess: () => onSaved(`已从 MDM 引用建档: ${mdmSelected?.equipment_code}`),
    onError: (err: unknown) => message.error(errDetail(err, "建档失败")),
  });

  const handleMdmSearch = async (q: string) => {
    setMdmLastSearch(q.trim());
    if (!q.trim()) {
      setMdmOptions([]);
      return;
    }
    const seq = ++mdmSearchSeq.current;
    setMdmSearching(true);
    try {
      const resp = await searchMdmEquipments(q.trim());
      if (seq === mdmSearchSeq.current) setMdmOptions(resp.data.data ?? []);
    } catch {
      if (seq === mdmSearchSeq.current) {
        setMdmOptions([]);
        message.warning("MDM 暂不可用,可切换为本地新建");
      }
    } finally {
      if (seq === mdmSearchSeq.current) setMdmSearching(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    setCreateMode("mdm");
    setMdmSelected(null);
    setMdmOptions([]);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (record: Equipment) => {
    setEditing(record);
    form.setFieldsValue({
      ...record,
      purchase_date: record.purchase_date ? dayjs(record.purchase_date) : null,
      commission_date: record.commission_date ? dayjs(record.commission_date) : null,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    if (!editing && createMode === "mdm") {
      if (!mdmSelected) {
        message.warning("请先搜索并选择 MDM 中的设备");
        return;
      }
      fromMdmMutation.mutate({
        location_room: values.location_room,
        location_detail: values.location_detail,
        responsible_person: values.responsible_person,
        commission_date: values.commission_date?.format("YYYY-MM-DD") ?? null,
        status: values.status ?? "in_use",
        remark: values.remark,
      });
      return;
    }
    const payload: EquipmentPayload = {
      ...values,
      purchase_date: values.purchase_date?.format("YYYY-MM-DD") ?? null,
      commission_date: values.commission_date?.format("YYYY-MM-DD") ?? null,
    };
    if (editing) delete payload.equipment_code; // 编号不可修改
    saveMutation.mutate(payload);
  };

  // 运营字段(两种新建模式共用 + 编辑)
  const operationalFields = (
    <>
      <Space.Compact block>
        <Form.Item name="location_room" label="所在房间" style={{ width: "50%", marginRight: 8 }}>
          <Input placeholder="如 2251" />
        </Form.Item>
        <Form.Item name="location_detail" label="安装位置" style={{ width: "50%" }}>
          <Input />
        </Form.Item>
      </Space.Compact>
      <Space.Compact block>
        <Form.Item name="responsible_person" label="负责人" style={{ width: "33%", marginRight: 8 }}>
          <Input />
        </Form.Item>
        <Form.Item name="commission_date" label="启用日期" style={{ width: "33%", marginRight: 8 }}>
          <DatePicker style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="status" label="状态" style={{ width: "34%" }} initialValue="in_use">
          <Select options={STATUS_OPTIONS} />
        </Form.Item>
      </Space.Compact>
      <Form.Item name="remark" label="备注">
        <Input.TextArea rows={2} />
      </Form.Item>
    </>
  );

  // 身份字段(仅本地新建/编辑可改;MDM 引用模式由 MDM 带入)
  const identityFields = (
    <>
      <Space.Compact block>
        <Form.Item
          name="equipment_code"
          label="设备编号(唯一,不可修改)"
          style={{ width: "50%", marginRight: 8 }}
          rules={[{ required: true, message: "请输入设备编号" }]}
        >
          <Input placeholder="如 EQP-0001" disabled={!!editing} />
        </Form.Item>
        <Form.Item
          name="name"
          label="设备名称"
          style={{ width: "50%" }}
          rules={[{ required: true, message: "请输入设备名称" }]}
        >
          <Input />
        </Form.Item>
      </Space.Compact>
      <Space.Compact block>
        <Form.Item
          name="category"
          label="设备分类"
          style={{ width: "50%", marginRight: 8 }}
          rules={[{ required: true, message: "请选择或输入分类" }]}
        >
          <Select
            showSearch
            allowClear
            placeholder="分析仪器 / 实验设备 / 辅助设备…"
            options={[...new Set([...categories, "分析仪器", "实验设备", "辅助设备"])].map(
              (c) => ({ value: c, label: c }),
            )}
          />
        </Form.Item>
        <Form.Item name="model" label="型号规格" style={{ width: "50%" }}>
          <Input />
        </Form.Item>
      </Space.Compact>
      <Space.Compact block>
        <Form.Item name="manufacturer" label="生产商" style={{ width: "33%", marginRight: 8 }}>
          <Input />
        </Form.Item>
        <Form.Item name="serial_no" label="序列号" style={{ width: "33%", marginRight: 8 }}>
          <Input />
        </Form.Item>
        <Form.Item name="asset_value" label="资产价值(元)" style={{ width: "34%" }}>
          <InputNumber min={0} style={{ width: "100%" }} />
        </Form.Item>
      </Space.Compact>
      <Form.Item name="purchase_date" label="购入日期">
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>
    </>
  );

  return (
    <>
      <Typography.Title level={4}>设备台账</Typography.Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder="搜索编号/名称/型号/序列号/负责人"
          style={{ width: 300 }}
          allowClear
          onSearch={setKeyword}
        />
        <Select
          placeholder="设备分类"
          style={{ width: 150 }}
          allowClear
          value={category}
          onChange={setCategory}
          options={categories.map((c) => ({ value: c, label: c }))}
        />
        <Select
          placeholder="状态"
          style={{ width: 130 }}
          allowClear
          value={status}
          onChange={setStatus}
          options={STATUS_OPTIONS}
        />
        <Space>
          <Switch size="small" checked={includeInactive} onChange={setIncludeInactive} />
          查看已报废
        </Space>
        {canEdit && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增设备
          </Button>
        )}
      </Space>

      <Table
        rowKey="equipment_id"
        size="small"
        loading={isLoading}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
        onRow={(record) => ({
          onClick: () => navigate(`/equipment/${record.equipment_id}`),
          style: { cursor: "pointer" },
        })}
        columns={[
          { title: "设备编号", dataIndex: "equipment_code", width: 140 },
          { title: "设备名称", dataIndex: "name", ellipsis: true },
          { title: "分类", dataIndex: "category", width: 100 },
          { title: "型号", dataIndex: "model", width: 140, ellipsis: true },
          { title: "房间", dataIndex: "location_room", width: 80 },
          { title: "负责人", dataIndex: "responsible_person", width: 90 },
          {
            title: "来源",
            dataIndex: "data_source",
            width: 80,
            render: (v: string) =>
              v === "mdm" ? <Tag color="geekblue">MDM</Tag> : <Tag>本地</Tag>,
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 90,
            render: (v: string) => {
              const t = STATUS_LABEL[v];
              return t ? <Tag color={t.color}>{t.text}</Tag> : v;
            },
          },
          ...(canEdit
            ? [{
                title: "操作",
                key: "actions",
                width: 80,
                render: (_: unknown, record: Equipment) => (
                  <Button
                    type="link"
                    size="small"
                    disabled={!record.is_active}
                    onClick={(e) => {
                      e.stopPropagation();
                      openEdit(record);
                    }}
                  >
                    编辑
                  </Button>
                ),
              }]
            : []),
        ]}
      />

      <Modal
        open={modalOpen}
        title={editing ? `编辑设备: ${editing.equipment_code}` : "新增设备"}
        onCancel={closeModal}
        onOk={handleSave}
        confirmLoading={saveMutation.isPending || fromMdmMutation.isPending}
        width={680}
        destroyOnClose
      >
        {!editing && (
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
        )}

        {!editing && createMode === "mdm" && (
          <>
            <Select
              showSearch
              placeholder="输入编码/名称/型号/序列号搜索 MDM 设备主数据"
              style={{ width: "100%", marginBottom: 12 }}
              filterOption={false}
              onSearch={handleMdmSearch}
              notFoundContent={mdmSearching ? <Spin size="small" /> : "无匹配(请先在 MDM Portal 登记)"}
              value={mdmSelected?.equipment_code}
              onChange={(code: string) => {
                setMdmSelected(mdmOptions.find((o) => o.equipment_code === code) ?? null);
              }}
              options={mdmOptions.map((o) => ({
                value: o.equipment_code,
                label: `${o.equipment_code} — ${o.equipment_name}${o.model ? ` (${o.model})` : ""}`,
              }))}
            />
            {mdmSelected ? (
              <Descriptions
                bordered
                size="small"
                column={2}
                style={{ marginBottom: 16 }}
              >
                <Descriptions.Item label="编码">{mdmSelected.equipment_code}</Descriptions.Item>
                <Descriptions.Item label="名称">{mdmSelected.equipment_name}</Descriptions.Item>
                <Descriptions.Item label="分类">{mdmSelected.category}</Descriptions.Item>
                <Descriptions.Item label="型号">{mdmSelected.model ?? "—"}</Descriptions.Item>
                <Descriptions.Item label="生产商">{mdmSelected.manufacturer ?? "—"}</Descriptions.Item>
                <Descriptions.Item label="序列号">{mdmSelected.serial_no ?? "—"}</Descriptions.Item>
              </Descriptions>
            ) : mdmLastSearch && !mdmSearching && mdmOptions.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
                message={`MDM 中没有匹配"${mdmLastSearch}"的设备`}
                description="新购设备需要先在 MDM 登记身份信息（名称/型号/厂家/序列号），登记完成后回到这里重新搜索即可。"
                action={
                  <Button
                    type="primary"
                    icon={<ExportOutlined />}
                    href={mdmPortalUrl("/equipments/new", { name: mdmLastSearch })}
                    target="_blank"
                  >
                    去 MDM 登记新设备
                  </Button>
                }
              />
            ) : (
              <Alert
                type="info"
                style={{ marginBottom: 16 }}
                message="主数据(名称/型号/生产商/购入信息)以 MDM 为权威源;此处仅补充本地运营信息"
              />
            )}
          </>
        )}

        <Form form={form} layout="vertical">
          {(editing || createMode === "local") && identityFields}
          {!editing && createMode === "local" && (
            <Alert
              type="warning"
              style={{ marginBottom: 16 }}
              message="本地新建仅作 MDM 不可用时的兜底;请事后在 MDM Portal 补登该设备主数据"
            />
          )}
          {operationalFields}
        </Form>
      </Modal>
    </>
  );
}
