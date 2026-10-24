import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Typography, Table, Tag, Input, Select, Space, Button, Modal, Form,
  DatePicker, message, Switch, Alert, Descriptions, Spin, Popconfirm,
} from "antd";
import { PlusOutlined, ExportOutlined, CloudDownloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import {
  listEquipment, updateEquipment, listEquipmentCategories,
  searchMdmEquipments, createEquipmentFromMdm, batchCreateFromMdm,
  STATUS_LABEL, type Equipment, type EquipmentPayload, type MdmEquipmentBrief,
} from "../../../api/equipment";
import { useAuthStore } from "../../../stores/authStore";
import { mdmPortalUrl } from "../../../shared/mdmPortal";
import { getErrorDetail } from "../../../shared/errors";

const STATUS_OPTIONS = Object.entries(STATUS_LABEL).map(([value, v]) => ({
  value, label: v.text,
}));

/**
 * 设备台账 — 身份信息(名称/型号/厂家等)以 MDM 为权威源,只能从 MDM 引用建档;
 * LabOps 仅维护运营信息(状态/位置/负责人/启用日期)及校验/维护/维修记录。
 */
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
    setMdmLastSearch("");
    form.resetFields();
  };

  const onSaved = (msg: string) => {
    message.success(msg);
    closeModal();
    queryClient.invalidateQueries({ queryKey: ["equipment"] });
    queryClient.invalidateQueries({ queryKey: ["equipmentCategories"] });
  };

  // 编辑 = 仅运营字段(身份信息在 MDM 维护)
  const updateMutation = useMutation({
    mutationFn: (data: EquipmentPayload) => updateEquipment(editing!.equipment_id, data),
    onSuccess: () => onSaved("运营信息已更新"),
    onError: (err: unknown) => message.error(getErrorDetail(err, "保存失败")),
  });

  const fromMdmMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      createEquipmentFromMdm(mdmSelected!.equipment_code, data),
    onSuccess: () => onSaved(`已从 MDM 引用建档: ${mdmSelected?.equipment_code}`),
    onError: (err: unknown) => message.error(getErrorDetail(err, "建档失败")),
  });

  // 批量同步 = 台账初始化:MDM 全量设备一键建档,运营字段留空待补
  const batchMutation = useMutation({
    mutationFn: () => batchCreateFromMdm(),
    onSuccess: (resp) => {
      const r = resp.data;
      message.success(
        `批量同步完成: 新建 ${r.created} 台,已存在跳过 ${r.skipped_existing} 台` +
        (r.failed.length ? `,失败 ${r.failed.length} 台` : ""),
        6,
      );
      queryClient.invalidateQueries({ queryKey: ["equipment"] });
      queryClient.invalidateQueries({ queryKey: ["equipmentCategories"] });
    },
    onError: (err: unknown) => message.error(getErrorDetail(err, "批量同步失败")),
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
        message.warning("MDM 暂不可用,请稍后重试");
      }
    } finally {
      if (seq === mdmSearchSeq.current) setMdmSearching(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    setMdmSelected(null);
    setMdmOptions([]);
    setMdmLastSearch("");
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (record: Equipment) => {
    setEditing(record);
    form.setFieldsValue({
      location_room: record.location_room,
      location_detail: record.location_detail,
      responsible_person: record.responsible_person,
      status: record.status,
      remark: record.remark,
      commission_date: record.commission_date ? dayjs(record.commission_date) : null,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    const operational = {
      location_room: values.location_room,
      location_detail: values.location_detail,
      responsible_person: values.responsible_person,
      commission_date: values.commission_date?.format("YYYY-MM-DD") ?? null,
      status: values.status ?? "in_use",
      remark: values.remark,
    };
    if (editing) {
      updateMutation.mutate(operational as EquipmentPayload);
      return;
    }
    if (!mdmSelected) {
      message.warning("请先搜索并选择 MDM 中的设备");
      return;
    }
    fromMdmMutation.mutate(operational);
  };

  return (
    <>
      <Typography.Title level={4}>设备台账</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        设备身份信息(名称/型号/厂家)在 MDM 登记;此处从 MDM 引用建档并维护运营信息与校验/维护/维修记录。
      </Typography.Paragraph>
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
            新增设备(从 MDM 引用)
          </Button>
        )}
        {canEdit && (
          <Popconfirm
            title="从 MDM 批量同步设备"
            description="将 MDM 中所有在册设备一次性引用建档(已存在的跳过),运营信息(房间/负责人)之后再逐台补录。继续?"
            okText="开始同步"
            onConfirm={() => batchMutation.mutate()}
          >
            <Button icon={<CloudDownloadOutlined />} loading={batchMutation.isPending}>
              从 MDM 批量同步
            </Button>
          </Popconfirm>
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
          { title: "设备编码", dataIndex: "equipment_code", width: 140 },
          { title: "设备编号", dataIndex: "equipment_no", width: 100, render: (v: string | null) => v ?? "—" },
          { title: "设备名称", dataIndex: "name", ellipsis: true },
          { title: "分类", dataIndex: "category", width: 100 },
          { title: "型号", dataIndex: "model", width: 140, ellipsis: true },
          { title: "房间", dataIndex: "location_room", width: 80 },
          { title: "负责人", dataIndex: "responsible_person", width: 90 },
          {
            title: "来源",
            dataIndex: "data_source",
            width: 80,
            render: (v: string, record: Equipment) =>
              v === "mdm" ? (
                <Tag color={record.mdm_status === "retired" ? "orange" : "geekblue"}>
                  {record.mdm_status === "retired" ? "MDM·退役" : "MDM"}
                </Tag>
              ) : (
                <Tag>本地</Tag>
              ),
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
        title={editing ? `编辑运营信息: ${editing.equipment_code}` : "新增设备(从 MDM 引用)"}
        onCancel={closeModal}
        onOk={handleSave}
        confirmLoading={updateMutation.isPending || fromMdmMutation.isPending}
        width={680}
        destroyOnClose
      >
        {editing && (
          <Alert
            type="info"
            style={{ marginBottom: 16 }}
            message={`${editing.name}${editing.model ? ` / ${editing.model}` : ""} — 名称/型号/厂家等身份信息请在 MDM Portal 修改`}
            action={
              editing.data_source === "mdm" ? (
                <Button
                  size="small"
                  icon={<ExportOutlined />}
                  href={mdmPortalUrl(`/equipments/${encodeURIComponent(editing.equipment_code)}`)}
                  target="_blank"
                >
                  去 MDM 查看
                </Button>
              ) : undefined
            }
          />
        )}

        {!editing && (
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
                <Descriptions.Item label="设备编号">{mdmSelected.equipment_no ?? "—"}</Descriptions.Item>
                <Descriptions.Item label="固定资产号">{mdmSelected.fixed_asset_no ?? "—"}</Descriptions.Item>
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
                description="新购设备需要先在 MDM 登记身份信息(名称/型号/厂家/序列号),登记完成后回到这里重新搜索即可。"
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
        </Form>
      </Modal>
    </>
  );
}
