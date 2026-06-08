// 自定义图标统一管理。
// 设计系统约定（UI 信息架构 §图标）：主图标用 @ant-design/icons，
// 特殊图标用 Lucide React 补充，禁止混用其它图标库。
// 显微镜属 AntD 未收录的"特殊图标"，故取自 Lucide。
import Icon from '@ant-design/icons';
import type { GetProps } from 'antd';
import { Microscope } from 'lucide-react';

type CustomIconProps = Partial<GetProps<typeof Icon>>;

// size="1em" 让 svg 随父级 font-size 缩放；Lucide 默认 stroke="currentColor"，
// 由 AntD <Icon> 外层 .anticon 的 color 决定颜色 —— 与 AntD 自带图标行为一致。
const MicroscopeSvg = () => <Microscope size="1em" />;

/** 显微镜图标（设备域专用），用法与 AntD 图标一致 */
export function MicroscopeIcon(props: CustomIconProps) {
  return <Icon component={MicroscopeSvg} {...props} />;
}
