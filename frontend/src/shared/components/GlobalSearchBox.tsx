import { useMemo, useState } from 'react';
import { AutoComplete, Input, Space, Tag, Typography, theme } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { searchApi } from '@/api/search';
import type { SearchHit } from '@/api/types';

const { Text } = Typography;

const ENTITY_LABEL: Record<string, string> = {
  substance: '物质',
  project: '项目',
  asset: '资产',
  material: '物料',
  equipment: '设备',
  target: '靶点',
};

const ENTITY_PATH: Record<string, string> = {
  substance: '/substances',
  project: '/projects',
  asset: '/assets',
  material: '/materials',
  equipment: '/equipments',
  target: '/targets',
};

const ENTITY_COLOR: Record<string, string> = {
  substance: 'geekblue',
  project: 'green',
  asset: 'gold',
  material: 'purple',
  equipment: 'cyan',
  target: 'blue',
};

const FIELD_LABEL: Record<string, string> = {
  code: '编码',
  name: '名称',
  name_en: '英文名',
  internal_code: '内部代号',
  indication: '适应症',
  trade_name: '商品名',
  inn_name: 'INN',
  objective: '目标',
  xref: '标识符',
  source_name: '来源',
  model: '型号',
  manufacturer: '厂商',
  serial_no: '序列号',
  equipment_no: '设备编号',
  fixed_asset_no: '固资编号',
  uniprot_id: 'UniProt',
  gene_symbol: '基因',
  cd_antigen: 'CD 号',
  alias: '别名',
};

/**
 * Header 全局搜索框。带防抖、分组下拉、点击跳详情。
 */
export function GlobalSearchBox() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState('');
  const [debounced, setDebounced] = useState('');
  const { token } = theme.useToken();

  // 简单 250ms 防抖
  const setQ = (v: string) => {
    setPending(v);
    if (window.__qts) window.clearTimeout(window.__qts);
    window.__qts = window.setTimeout(() => setDebounced(v.trim()), 250);
  };

  const { data, isFetching } = useQuery({
    queryKey: ['global-search', debounced],
    queryFn: () => searchApi.search(debounced, undefined, 20),
    enabled: debounced.length > 0,
    staleTime: 5_000,
  });

  const options = useMemo(() => {
    // G2-API6（V1.1 §8.3）+ M4.4：分组结构 {substance, project, asset, material} 各含 items
    if (!data) return [];
    const groups: Array<
      ['substance' | 'project' | 'asset' | 'material' | 'equipment' | 'target', SearchHit[]]
    > = [
      ['substance', data.results.substance.items],
      ['project', data.results.project.items],
      ['asset', data.results.asset.items],
      ['material', data.results.material.items],
      ['equipment', data.results.equipment.items],
      ['target', data.results.target?.items ?? []],
    ];
    return groups
      .filter(([, list]) => list.length > 0)
      .map(([type, list]) => ({
        label: (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {ENTITY_LABEL[type] ?? type}（{list.length}）
          </Text>
        ),
        options: list.map((h) => ({
          value: `${h.entity_type}:${h.code}`,
          hit: h,
          label: (
            <Space size="small" style={{ width: '100%' }}>
              <Tag color={ENTITY_COLOR[h.entity_type]} style={{ marginRight: 0 }}>
                {ENTITY_LABEL[h.entity_type] ?? h.entity_type}
              </Tag>
              <Text code style={{ fontSize: 12 }}>
                {h.code}
              </Text>
              <Text>{h.name}</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                · {FIELD_LABEL[h.matched_field] ?? h.matched_field}
                {h.snippet ? `: ${h.snippet}` : ''}
              </Text>
            </Space>
          ),
        })),
      }));
  }, [data]);

  const handleSelect = (_: unknown, option: any) => {
    const hit: SearchHit = option.hit;
    const base = ENTITY_PATH[hit.entity_type];
    if (!base) return;
    setOpen(false);
    setPending('');
    setDebounced('');
    navigate(`${base}/${encodeURIComponent(hit.code)}`);
  };

  return (
    <AutoComplete
      open={open && debounced.length > 0}
      onDropdownVisibleChange={setOpen}
      value={pending}
      onChange={setQ}
      onSelect={handleSelect}
      options={options as any}
      style={{ width: 380 }}
      popupMatchSelectWidth={520}
      notFoundContent={
        debounced.length === 0
          ? null
          : isFetching
          ? '搜索中…'
          : '无匹配结果'
      }
    >
      <Input
        size="middle"
        allowClear
        prefix={<SearchOutlined style={{ color: token.colorTextSecondary }} />}
        placeholder="搜索物质 / 项目 / 资产 / 物料 / 设备 / 靶点（编码、名称、INN、UniProt、CD 号）..."
        onFocus={() => setOpen(true)}
      />
    </AutoComplete>
  );
}

declare global {
  interface Window {
    __qts?: number;
  }
}
