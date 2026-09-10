// 应用注册表（设计方案 §6）：图标墙由这张表渲染，加新系统 = 加一条，不改其他代码。
//
// requires 语义：
//   - 'authenticated'      只要登录就能看
//   - ['ROLE_A','ROLE_B']  拥有其中任一 MDM 角色码即可看；SYS_ADMIN 永远全可见
//   - { departmentPrefixes: ['TT','CMC'] }  MDM 里的部门（auth.user.department）以其中任一前缀开头即可看
//                          （不分大小写；SYS_ADMIN 永远全可见）。部门随登录用户信息和 access token 一起下发
// status：live 正常可点；planned 建设中（显示但标灰、不可点）；hidden 暂不展示
//
// ⚠️ 各系统的角色码请以 MDM 后台 /admin/roles 里实际配置为准，这里的默认值来自各子系统当前代码：
//   LabOps 只读对所有登录用户开放（写操作要 CMC_WAREHOUSE_ADMIN / CMC_EQUIPMENT_ADMIN，由 LabOps 后端自己管）
//   批号管理 认 CMC_USP_OPERATOR / CMC_USP_RESEARCHER / CMC_USP_MANAGER
//   上游工艺看板 认 CMC_USP_OPERATOR / CMC_USP_MANAGER / CMC_USP_RESEARCHER；LIMS 看板 认 CMC_LIMS_* 三角色 + CMC_RESEARCHER + QA_REVIEWER（2026-09-04）

export type AppRequirement = 'authenticated' | string[] | { departmentPrefixes: string[] }

export interface HubApp {
  id: string
  name: string
  description: string
  icon: string // 见 components/AppTile.tsx 里的图标表
  path: string // 门户下的子路径（nginx 反代到各子系统）
  requires: AppRequirement
  status: 'live' | 'planned' | 'hidden'
  color: string // 图标底色
  badge?: string // 可选：名字旁的醒目标签（如培训环境「练习专用」）
  tileTheme?: 'training' // 可选：整张卡片换配色（training = 黄底深字，图标小方块仍用 color）
}

export const HUB_APPS: HubApp[] = [
  {
    id: 'mdm',
    name: '主数据 MDM',
    description: '人员 / 角色 / 设备 / 物料 / 项目等主数据管理',
    icon: 'database',
    path: '/mdm/',
    requires: 'authenticated',
    status: 'live',
    color: '#1677ff',
  },
  {
    id: 'labops',
    name: '实验室运营 LabOps',
    description: '仓库库存、设备台账与日常运营',
    icon: 'experiment',
    path: '/labops/',
    requires: { departmentPrefixes: ['TT', 'CMC'] }, // 2026-09-10 负责人：实验室系统，TT*/CMC* 部门员工可见（LabOps 后端同口径拦截）
    status: 'live',
    color: '#13c2c2',
  },
  {
    id: 'batch',
    name: '批号管理',
    description: '研发批号登记、发放、谱系与取样计划',
    icon: 'barcode',
    path: '/batch/',
    requires: ['CMC_USP_OPERATOR', 'CMC_USP_RESEARCHER', 'CMC_USP_MANAGER'],
    status: 'live',
    color: '#722ed1',
  },
  {
    // 批号管理培训环境：同一套代码、独立练习库 cmc_analytics_training，随便点不影响正式数据（不自动清空）
    // 图标与正式完全相同（紫色条码），但整张卡片黄底 + 「练习专用」标签，一眼区分；培训环境页面本身也是浅黄底 + 顶部横幅
    id: 'batch-train',
    name: '批号管理【培训】',
    description: '练习专用：独立练习库，随便发放 / 修改 / 作废，不影响正式数据',
    icon: 'barcode',
    path: '/batch-train/',
    requires: ['CMC_USP_OPERATOR', 'CMC_USP_RESEARCHER', 'CMC_USP_MANAGER'],
    status: 'live',
    color: '#722ed1',
    badge: '练习专用',
    tileTheme: 'training',
  },
  {
    id: 'usp',
    name: '上游工艺看板',
    description: '上游发酵 / 细胞培养过程数据与批次趋势',
    icon: 'line-chart',
    path: '/usp/',
    requires: ['CMC_USP_OPERATOR', 'CMC_USP_MANAGER', 'CMC_USP_RESEARCHER'], // 2026-09-04 负责人：仅上游三角色（与 USP 后端 viewer 角色一致）
    status: 'live',
    color: '#52c41a',
  },
  {
    id: 'lims',
    name: 'LIMS 看板',
    description: '检验数据、周转与放行统计',
    icon: 'dashboard',
    path: '/lims/',
    requires: ['CMC_LIMS_ADMIN', 'CMC_LIMS_ANALYST', 'CMC_LIMS_CHEMIST', 'CMC_RESEARCHER', 'QA_REVIEWER'], // 2026-09-04 负责人：LIMS 三角色 + CMC 研究员 + QA 审核（与 LIMS 后端 VIEW_ROLES 一致）
    status: 'live',
    color: '#fa8c16',
  },
  {
    id: 'lcms',
    name: 'LC-MS/MS 定量看板',
    description: 'AB SCIEX 靶向定量数据解析与质控诊断',
    icon: 'dot-chart',
    path: '/lcms/',
    requires: ['CMC_LCMS_SCIEX_USER'],
    status: 'live',
    color: '#eb2f96',
  },
  {
    id: 'qv',
    name: '验证部平台',
    description: '温湿度分布验证工具箱；验证台账与设备验证档案陆续上线',
    icon: 'audit',
    path: '/qv/',
    requires: 'authenticated', // 2026-09-09 负责人：工具箱暂独立于 CMC 体系、自身无登录，门户上登录即可见
    status: 'live',
    color: '#2f54eb',
  },
  {
    id: 'cost',
    name: '成本模型',
    description: '工艺成本测算与情景比较',
    icon: 'calculator',
    path: '/cost/',
    requires: ['CMC_COST_USER'], // 2026-09-04 负责人：成本模型只给指定人（MDM 角色 CMC_COST_USER）+ SYS_ADMIN 看
    status: 'planned',
    color: '#eb2f96',
  },
]
