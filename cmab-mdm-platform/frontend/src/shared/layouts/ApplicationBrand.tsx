import { withBase } from '@/shared/base';

/** Shared company identity; application-specific copy mirrors the PM workbench. */
export function ApplicationBrand() {
  return <div className="mdm-app-brand">
    <img src={withBase('/brand/maibo-pharma-logo.png')} alt="迈博药业" width={34} height={34} />
    <div className="mdm-app-brand-copy">
      <div className="mdm-app-brand-title">MBERP</div>
      <div className="mdm-app-brand-subtitle">迈博药业 · 主数据</div>
    </div>
  </div>;
}
