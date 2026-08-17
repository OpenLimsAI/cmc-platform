// 应用注册表（设计方案 §6）：图标墙由这张表渲染，加新系统 = 加一条，不改其他代码。
//
// requires 语义：
//   - 'authenticated'      只要登录就能看
//   - ['ROLE_A','ROLE_B']  拥有其中任一 MDM 角色码即可看；SYS_ADMIN 永远全可见
// status：live 正常可点；planned 建设中（显示但标灰、不可点）；hidden 暂不展示
//
// ⚠️ 各系统的角色码请以 MDM 后台 /admin/roles 里实际配置为准，这里的默认值来自各子系统当前代码：
//   LabOps 只读对所有登录用户开放（写操作要 CMC_WAREHOUSE_ADMIN / CMC_EQUIPMENT_ADMIN，由 LabOps 后端自己管）
//   批号管理 认 CMC_USP_OPERATOR / CMC_USP_RESEARCHER / CMC_USP_MANAGER
//   上游工艺看板 / LIMS 看板 目前无独立角色，登录即可看

export type AppRequirement = 'authenticated' | string[]

export interface HubApp {
  id: string
  name: string
  description: string
  icon: string // 见 components/AppTile.tsx 里的图标表
  path: string // 门户下的子路径（nginx 反代到各子系统）
  requires: AppRequirement
  status: 'live' | 'planned' | 'hidden'
  color: string // 图标底色
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
    requires: 'authenticated',
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
    status: 'planned',
    color: '#722ed1',
  },
  {
    id: 'usp',
    name: '上游工艺看板',
    description: '上游发酵 / 细胞培养过程数据与批次趋势',
    icon: 'line-chart',
    path: '/usp/',
    requires: 'authenticated',
    status: 'live',
    color: '#52c41a',
  },
  {
    id: 'lims',
    name: 'LIMS 看板',
    description: '检验数据、周转与放行统计',
    icon: 'dashboard',
    path: '/lims/',
    requires: 'authenticated',
    status: 'live',
    color: '#fa8c16',
  },
  {
    id: 'cost',
    name: '成本模型',
    description: '工艺成本测算与情景比较',
    icon: 'calculator',
    path: '/cost/',
    requires: 'authenticated',
    status: 'planned',
    color: '#eb2f96',
  },
]
