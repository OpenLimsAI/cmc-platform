import { Link } from 'react-router-dom';

interface EntityCodeLinkProps {
  type: 'substance' | 'project' | 'asset' | 'material' | 'equipment' | 'target';
  code: string;
  name?: string | null;
  withName?: boolean;
}

const PATH_MAP = {
  substance: 'substances',
  project: 'projects',
  asset: 'assets',
  material: 'materials',
  equipment: 'equipments',
  target: 'targets',
};

export function EntityCodeLink({ type, code, name, withName }: EntityCodeLinkProps) {
  const href = `/${PATH_MAP[type]}/${encodeURIComponent(code)}`;
  return (
    <Link to={href} style={{ color: 'var(--mdm-accent)', fontWeight: 500 }}>
      {code}
      {withName && name ? <span style={{ marginLeft: 8, color: 'var(--mdm-ink)' }}>{name}</span> : null}
    </Link>
  );
}
