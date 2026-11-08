import type { ReactNode } from 'react';
import { Contrast, Grid2X2, MessageSquareText } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { withBase } from '@/shared/base';
import { useApplicationTheme } from '@/shared/applicationThemeContext';
import './applicationActions.css';

export function ApplicationActions({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { dark, toggleTheme } = useApplicationTheme();
  const feedbackQuery = new URLSearchParams({ compose: '1', application: 'mdm', source_path: withBase(pathname) });
  return <div className="mdm-application-actions">
    <a className="mdm-header-link mdm-feedback-link" href={`/feedback?${feedbackQuery}`} target="_blank" rel="noopener noreferrer"
      aria-label="回音壁（新标签页打开）" title="在新标签页打开回音壁，原页面保留">
      <MessageSquareText size={17} aria-hidden="true" /><span>回音壁</span>
    </a>
    <a className="mdm-header-link mdm-workbench-link" href="/" aria-label="应用工作台" title="应用工作台">
      <Grid2X2 size={17} aria-hidden="true" /><span>工作台</span>
    </a>
    <span className="mdm-header-divider" aria-hidden="true" />
    {children}
    <button type="button" className="mdm-theme-toggle" aria-label="切换主题" aria-pressed={dark}
      title={dark ? '切换浅色主题' : '切换深色主题'} onClick={toggleTheme}>
      <Contrast size={20} aria-hidden="true" />
    </button>
  </div>;
}
