import { Database } from 'lucide-react';

/** Application identity uses the shared Maibo workspace visual language. */
export function ApplicationBrand() {
  return <div className="mdm-app-brand" aria-label="迈博主数据管理">
    <span className="mdm-app-mark"><Database size={22} strokeWidth={1.7} aria-hidden="true" /></span>
    <div className="mdm-app-brand-copy">
      <div className="mdm-app-brand-title">主数据管理</div>
      <div className="mdm-app-brand-subtitle">MASTER DATA STUDIO</div>
    </div>
  </div>;
}
