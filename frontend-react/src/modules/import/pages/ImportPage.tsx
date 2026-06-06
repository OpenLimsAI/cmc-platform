import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Typography, Card, Upload, Button, message, Table, Tag, Alert,
  Checkbox, Space, Statistic, Row, Col,
} from "antd";
import { InboxOutlined } from "@ant-design/icons";
import {
  dryRunImport, commitImport, listImportLogs,
  type ImportPreviewResult, type ImportPreviewRow,
} from "../../../api/importApi";
import { getErrorDetail } from "../../../shared/errors";

const ACTION_TAG: Record<string, { color: string; text: string }> = {
  INSERT: { color: "green", text: "新增" },
  UPDATE: { color: "blue", text: "更新" },
  ERROR: { color: "red", text: "错误" },
};

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResult | null>(null);
  const [autoCreateUnits, setAutoCreateUnits] = useState(true);

  const { data: logs = [], refetch: refetchLogs } = useQuery({
    queryKey: ["importLogs"],
    queryFn: () => listImportLogs(20).then((r) => r.data),
  });

  const dryRunMutation = useMutation({
    mutationFn: (f: File) => dryRunImport(f),
    onSuccess: (resp) => setPreview(resp.data),
    onError: (err: unknown) => {
      const detail =
        getErrorDetail(err, "文件解析失败");
      message.error(detail);
    },
  });

  const commitMutation = useMutation({
    mutationFn: () =>
      commitImport({
        file_name: file?.name ?? "unknown.xlsx",
        auto_create_units: autoCreateUnits,
        rows: (preview?.rows ?? [])
          .filter((r) => r.action !== "ERROR")
          .map((r) => r.raw),
      }),
    onSuccess: (resp) => {
      const d = resp.data;
      message.success(
        `导入完成: 新增 ${d.inserted_rows} 条,更新 ${d.updated_rows} 条,失败 ${d.failed_rows} 条`,
      );
      setPreview(null);
      setFile(null);
      refetchLogs();
    },
    onError: (err: unknown) => {
      const detail =
        getErrorDetail(err, "导入失败");
      message.error(detail);
    },
  });

  return (
    <>
      <Typography.Title level={4}>物料导入</Typography.Title>

      <Card style={{ maxWidth: 720, marginBottom: 16 }}>
        <Upload.Dragger
          accept=".xlsx,.xls"
          maxCount={1}
          beforeUpload={(f) => {
            setFile(f);
            setPreview(null);
            dryRunMutation.mutate(f);
            return false; // 阻止默认上传,走干跑 API
          }}
          onRemove={() => {
            setFile(null);
            setPreview(null);
          }}
          fileList={file ? [{ uid: "-1", name: file.name }] : []}
        >
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽 Excel 文件到此处</p>
          <p className="ant-upload-hint">
            表头: 分类 / 代码 / 物料名称 / 级别 / 生产商 / 规格/型号 / 货号 / 单位 / 包装规格 / 备注。
            代码列前导 0 自动保留。
          </p>
        </Upload.Dragger>
        {dryRunMutation.isPending && (
          <Alert style={{ marginTop: 12 }} type="info" message="正在校验文件(干跑,不写库)…" />
        )}
      </Card>

      {preview && (
        <Card title="干跑预览" style={{ marginBottom: 16 }}>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col><Statistic title="总行数" value={preview.total_rows} /></Col>
            <Col><Statistic title="将新增" value={preview.insert_count} valueStyle={{ color: "#3f8600" }} /></Col>
            <Col><Statistic title="将更新" value={preview.update_count} valueStyle={{ color: "#1677ff" }} /></Col>
            <Col><Statistic title="错误行" value={preview.error_count} valueStyle={{ color: preview.error_count ? "#cf1322" : undefined }} /></Col>
          </Row>

          {preview.leading_zero_codes.length > 0 && (
            <Alert
              style={{ marginBottom: 8 }}
              type="warning"
              message={`含前导 0 的代码(请确认 Excel 未被去 0): ${preview.leading_zero_codes.join(", ")}`}
            />
          )}
          {preview.new_categories.length > 0 && (
            <Alert
              style={{ marginBottom: 8 }}
              type="info"
              message={`新分类将自动加入字典: ${preview.new_categories.join(", ")}`}
            />
          )}
          {preview.new_units.length > 0 && (
            <Alert
              style={{ marginBottom: 8 }}
              type="info"
              message={`新单位: ${preview.new_units.join(", ")}`}
            />
          )}

          <Table
            rowKey="row_index"
            size="small"
            dataSource={preview.rows}
            pagination={{ pageSize: 20 }}
            columns={[
              { title: "Excel 行", dataIndex: "row_index", width: 80 },
              { title: "代码", dataIndex: "material_code", width: 130 },
              { title: "物料名称", dataIndex: "name_cn", ellipsis: true },
              {
                title: "处理",
                dataIndex: "action",
                width: 80,
                render: (v: string) => {
                  const t = ACTION_TAG[v] ?? { color: "default", text: v };
                  return <Tag color={t.color}>{t.text}</Tag>;
                },
              },
              {
                title: "错误/警告",
                key: "msgs",
                render: (_: unknown, r: ImportPreviewRow) => (
                  <>
                    {r.errors.map((e, i) => (
                      <div key={`e${i}`} style={{ color: "#cf1322" }}>{e}</div>
                    ))}
                    {r.warnings.map((w, i) => (
                      <div key={`w${i}`} style={{ color: "#d48806" }}>{w}</div>
                    ))}
                  </>
                ),
              },
            ]}
          />

          <Space style={{ marginTop: 16 }}>
            <Checkbox
              checked={autoCreateUnits}
              onChange={(e) => setAutoCreateUnits(e.target.checked)}
            >
              新单位自动加入字典
            </Checkbox>
            <Button
              type="primary"
              disabled={preview.total_rows === preview.error_count}
              loading={commitMutation.isPending}
              onClick={() => commitMutation.mutate()}
            >
              确认导入 {preview.total_rows - preview.error_count} 行(错误行已排除)
            </Button>
          </Space>
        </Card>
      )}

      <Card title="导入历史(最近 20 次)">
        <Table
          rowKey="import_id"
          size="small"
          dataSource={logs}
          pagination={false}
          columns={[
            { title: "ID", dataIndex: "import_id", width: 60 },
            { title: "文件名", dataIndex: "file_name", ellipsis: true },
            { title: "时间", dataIndex: "imported_at", width: 170 },
            { title: "操作人", dataIndex: "operator", width: 100 },
            { title: "总行", dataIndex: "total_rows", width: 70 },
            { title: "新增", dataIndex: "inserted_rows", width: 70 },
            { title: "更新", dataIndex: "updated_rows", width: 70 },
            {
              title: "失败",
              dataIndex: "failed_rows",
              width: 70,
              render: (v: number) => (v ? <Tag color="red">{v}</Tag> : 0),
            },
          ]}
        />
      </Card>
    </>
  );
}
