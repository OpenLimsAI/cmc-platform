import { Button, Descriptions, Table, Tag, Typography, message } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import type { TargetUniprotFields, UniprotDomain, UniprotKeyword } from '@/api/targets';
import { KEYWORD_CATEGORY_LABELS, KEYWORD_CATEGORY_ORDER } from '../constants';

const { Text } = Typography;

const CATEGORY_COLOR: Record<string, string> = {
  'Molecular function': 'blue',
  'Cellular component': 'green',
  'Biological process': 'purple',
  Ligand: 'gold',
  Domain: 'cyan',
  PTM: 'magenta',
  Disease: 'red',
};

/** UniProt 风格：每行 60 个残基、每 10 个一组、行首位置号 */
function formatSequence(seq: string): string {
  const lines: string[] = [];
  const width = String(seq.length).length;
  for (let i = 0; i < seq.length; i += 60) {
    const chunk = seq.slice(i, i + 60);
    const groups = chunk.match(/.{1,10}/g) ?? [];
    lines.push(`${String(i + 1).padStart(width, ' ')}  ${groups.join(' ')}`);
  }
  return lines.join('\n');
}

function groupKeywords(keywords: UniprotKeyword[] | null | undefined) {
  const groups = new Map<string, UniprotKeyword[]>();
  for (const k of keywords ?? []) {
    const cat = k.category ?? '其他';
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat)!.push(k);
  }
  const ordered = [
    ...KEYWORD_CATEGORY_ORDER.filter((c) => groups.has(c)),
    ...[...groups.keys()].filter((c) => !KEYWORD_CATEGORY_ORDER.includes(c)),
  ];
  return ordered.map((cat) => ({ category: cat, items: groups.get(cat)! }));
}

interface Props {
  data: TargetUniprotFields & {
    uniprot_id?: string | null;
    gene_symbol?: string | null;
    organism?: string | null;
    aliases?: string[] | null;
    description?: string | null;
  };
  /** 紧凑模式：新建页拉取后预览用（不显示结构域表）*/
  compact?: boolean;
}

/**
 * UniProt 标准字段只读展示（新建页拉取预览 / 详情页共用）。
 * 字段全部来自 UniProt 受控词表（KW-xxxx 关键词 / SL-xxxx 亚细胞定位 / EC 号 / features），人不手填。
 */
export function UniprotInfoPanel({ data, compact }: Props) {
  const kwGroups = groupKeywords(data.keywords);
  const domainColumns = [
    { title: '类型', dataIndex: 'type', key: 'type', width: 140 },
    { title: '描述', dataIndex: 'description', key: 'description', render: (v: string | null) => v ?? '—' },
    { title: '起', dataIndex: 'start', key: 'start', width: 70 },
    { title: '止', dataIndex: 'end', key: 'end', width: 70 },
  ];
  return (
    <>
      <Descriptions bordered size="small" column={2}>
        <Descriptions.Item label="UniProt accession">
          {data.uniprot_id ? (
            <a href={`https://www.uniprot.org/uniprotkb/${data.uniprot_id}/entry`} target="_blank" rel="noreferrer">
              {data.uniprot_id}
            </a>
          ) : (
            '—'
          )}
        </Descriptions.Item>
        <Descriptions.Item label="条目类型 / 存在证据">
          {data.entry_type ?? '—'}
          {data.protein_existence ? <Text type="secondary">（{data.protein_existence}）</Text> : null}
        </Descriptions.Item>
        <Descriptions.Item label="基因符号">
          {data.gene_symbol ?? '—'}
          {data.gene_synonyms?.length ? (
            <Text type="secondary"> 别名：{data.gene_synonyms.join(', ')}</Text>
          ) : null}
        </Descriptions.Item>
        <Descriptions.Item label="CD 编号">
          {data.cd_antigen_names?.length ? data.cd_antigen_names.map((c) => <Tag key={c} color="geekblue">{c}</Tag>) : '—'}
        </Descriptions.Item>
        <Descriptions.Item label="物种">
          {data.organism ?? '—'}
          {data.tax_id ? <Text type="secondary">（taxId {data.tax_id}）</Text> : null}
        </Descriptions.Item>
        <Descriptions.Item label="EC 酶号">
          {data.ec_numbers?.length ? data.ec_numbers.map((e) => <Tag key={e}>{e}</Tag>) : '—'}
        </Descriptions.Item>
        <Descriptions.Item label="别名 / 次级 accession" span={2}>
          {data.aliases?.length ? data.aliases.map((a) => <Tag key={a}>{a}</Tag>) : '—'}
        </Descriptions.Item>
        <Descriptions.Item label="亚细胞定位（SL）" span={2}>
          {data.subcellular_locations?.length
            ? data.subcellular_locations.map((sl, i) => (
                <Tag key={`${sl.id}-${i}`} color="green" title={sl.id ?? undefined}>
                  {sl.location}
                  {sl.topology ? ` · ${sl.topology}` : ''}
                  {sl.molecule ? ` (${sl.molecule})` : ''}
                </Tag>
              ))
            : '—'}
        </Descriptions.Item>
        {kwGroups.map((g) => (
          <Descriptions.Item key={g.category} label={`关键词 · ${KEYWORD_CATEGORY_LABELS[g.category] ?? g.category}`} span={2}>
            {g.items.map((k) => (
              <Tag key={k.id ?? k.name} color={CATEGORY_COLOR[g.category] ?? 'default'} title={k.id ?? undefined}>
                {k.name}
              </Tag>
            ))}
          </Descriptions.Item>
        ))}
        {!kwGroups.length && (
          <Descriptions.Item label="关键词" span={2}>
            —
          </Descriptions.Item>
        )}
        <Descriptions.Item label="序列长度 / 分子量">
          {data.sequence_length ? `${data.sequence_length} aa` : '—'}
          {data.mol_weight != null ? ` · ${data.mol_weight.toLocaleString('en-US')} Da` : ''}
        </Descriptions.Item>
        <Descriptions.Item label="UniProt 版本 / 拉取时间">
          {data.uniprot_entry_version ? `v${data.uniprot_entry_version}` : '—'}
          {data.uniprot_fetched_at ? ` · ${new Date(data.uniprot_fetched_at).toLocaleString()}` : ''}
        </Descriptions.Item>
        <Descriptions.Item label="序列校验">
          <Text code copyable={data.sequence_md5 ? { text: data.sequence_md5 } : false}>
            MD5 {data.sequence_md5 ?? '—'}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="CRC64">
          <Text code copyable={data.sequence_crc64 ? { text: data.sequence_crc64 } : false}>
            {data.sequence_crc64 ?? '—'}
          </Text>
        </Descriptions.Item>
        {!compact && (
          <Descriptions.Item label={`完整序列（${data.sequence?.length ?? 0} aa）`} span={2}>
            {data.sequence ? (
              <div>
                <div style={{ marginBottom: 6 }}>
                  <Button
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={() => {
                      navigator.clipboard.writeText(data.sequence ?? '');
                      message.success('序列已复制');
                    }}
                  >
                    复制序列
                  </Button>{' '}
                  <Button
                    size="small"
                    onClick={() => {
                      const fasta = `>${data.uniprot_id ?? 'target'}${data.gene_symbol ? ` ${data.gene_symbol}` : ''}\n${data.sequence!.replace(/(.{60})/g, '$1\n')}`;
                      navigator.clipboard.writeText(fasta);
                      message.success('FASTA 已复制');
                    }}
                  >
                    复制 FASTA
                  </Button>
                </div>
                <pre
                  style={{
                    margin: 0,
                    padding: 8,
                    background: '#fafafa',
                    border: '1px solid #f0f0f0',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                    fontSize: 12,
                    lineHeight: '18px',
                    whiteSpace: 'pre',
                    overflowX: 'auto',
                    maxHeight: 320,
                  }}
                >
                  {formatSequence(data.sequence)}
                </pre>
              </div>
            ) : (
              '—'
            )}
          </Descriptions.Item>
        )}
        {!compact && (
          <Descriptions.Item label="功能描述（FUNCTION）" span={2}>
            {data.description ?? '—'}
          </Descriptions.Item>
        )}
      </Descriptions>
      {!compact && (data.domains?.length ?? 0) > 0 && (
        <Table<UniprotDomain>
          style={{ marginTop: 12 }}
          size="small"
          title={() => `结构域 / 区域（${data.domains!.length}，可用于关联表的"结合表位/结构域"）`}
          columns={domainColumns}
          dataSource={data.domains!}
          rowKey={(d, i) => `${d.type}-${d.start}-${d.end}-${i}`}
          pagination={data.domains!.length > 15 ? { pageSize: 15, size: 'small' } : false}
        />
      )}
    </>
  );
}
