"""
文件: backend/schemas.py
用途: Pydantic v2 数据传输对象(请求 / 响应模型)
说明:
    - 所有数量字段使用 Decimal,精确两位小数
    - Optional 字段统一以 None 兜底
    - response 模型使用 model_config = ConfigDict(from_attributes=True)
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


# 'TT内部物料' 作为保留 material_code 允许重复出现
TT_INTERNAL_CODE = "TT内部物料"

# 危化品分类允许的字面值
HAZARD_CLASS_VALUES = {"危化品", "易燃", "易制毒", "易制爆", "剧毒品"}

# MDM 对齐的 category 枚举值
CATEGORY_VALUES = {
    "一般耗材", "关键耗材", "关键试剂", "内包材", "外包材", "劳保",
    "原辅料", "参比品", "对照品", "工艺用水/气", "标准品",
    "细胞种子", "自制包材", "试剂", "运输包装材料",
}


# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------
class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Unit / Category / Location
# ---------------------------------------------------------------------------
class UnitOut(ORMBase):
    unit: str
    description: Optional[str] = None


class CategoryOut(ORMBase):
    category: str


class LocationBase(BaseModel):
    room_no: str = Field(..., min_length=1, max_length=20)
    cabinet_no: str = Field(..., min_length=1, max_length=20)
    layer_no: int = Field(..., ge=1)
    storage_condition: Optional[str] = None
    remark: Optional[str] = None


class LocationCreate(LocationBase):
    pass


class LocationOut(LocationBase, ORMBase):
    location_id: int
    name: str  # 由 DB 拼成 "{room}-{cabinet}-L{layer}"


# ---------------------------------------------------------------------------
# StorageNode (存放位置层级树) - v1.5
# ---------------------------------------------------------------------------
class StorageNodeOut(ORMBase):
    node_id: int
    parent_id: Optional[int] = None
    node_type: str
    code: str
    label: Optional[str] = None
    path: Optional[str] = None
    depth: int
    sort_order: int
    capacity_kind: Optional[str] = None
    location_id: Optional[int] = None
    temp_category: Optional[str] = None
    temp_text: Optional[str] = None
    equipment_no: Optional[str] = None       # 仅 FRIDGE: 绑定的 MDM 设备业务编号
    equipment_code: Optional[str] = None     # 仅 FRIDGE: MDM 内部码快照
    equipment_name: Optional[str] = None     # 仅 FRIDGE: 本地已同步设备表 join 出的设备名(显示用)
    is_active: bool
    remark: Optional[str] = None
    has_children: bool = False  # 由路由按需填充


class CabinetCreate(BaseModel):
    """试剂柜模板新增: 房间 + 柜号 + 板层数 → 生成 1 柜 + N 个 bulk 板层(各回链 location)。"""
    room_no: str = Field(..., min_length=1, max_length=20)
    cabinet_no: str = Field(..., min_length=1, max_length=20)
    layer_count: int = Field(..., ge=1, le=60)
    storage_condition: Optional[str] = None
    remark: Optional[str] = None


class FridgeCreate(BaseModel):
    """普通冰箱模板新增(2~8/-20): 房间 + MDM 设备编号 + 温区 + 隔板数 → FRIDGE + N 个 bulk 隔板。
    冰箱身份归 MDM,equipment_no 为业务编号(如 TT-SC-009),后端实时校验并绑定。"""
    room_no: str = Field(..., min_length=1, max_length=20)
    equipment_no: str = Field(..., min_length=1, max_length=64)
    temp_category: str = Field(..., pattern=r"^(normal|2-8|-20)$")
    shelf_count: int = Field(..., ge=1, le=60)
    storage_condition: Optional[str] = None
    remark: Optional[str] = None


class NodeUpdate(BaseModel):
    """节点改名 / 停用 / 备注。结构性字段(type/code/parent)不可改。"""
    label: Optional[str] = Field(None, max_length=80)
    remark: Optional[str] = None
    is_active: Optional[bool] = None


class AddChildrenRequest(BaseModel):
    """往已有节点追加下级(支持异构: 某架单独加层、某层加不同规格的盒等)。
    child_type 须与父节点类型匹配; 编号自动续接现有兄弟。"""
    child_type: str = Field(..., pattern=r"^(CABINET_LAYER|FRIDGE_SHELF|RACK|RACK_LAYER|BOX|CELL)$")
    count: int = Field(..., ge=1, le=1000)
    layers_per_rack: Optional[int] = Field(None, ge=1, le=20)   # 加 RACK 时
    boxes_per_layer: Optional[int] = Field(None, ge=1, le=26)   # 加 RACK / RACK_LAYER 时
    cells_per_box: Optional[int] = Field(None, ge=1, le=400)    # 加 RACK / RACK_LAYER / BOX 时
    storage_condition: Optional[str] = None                     # 加 CABINET_LAYER 时
    remark: Optional[str] = None


class FreezerCreate(BaseModel):
    """-80℃ 冰箱模板(期2): 房间 + 冰箱名 + 架/层/盒/孔参数 → 一次性展开整棵子树。
    架/盒用字母 A.. 编号(上限 26);层/孔用数字 1.. 编号。冰箱身份归 MDM,按业务编号绑定。"""
    room_no: str = Field(..., min_length=1, max_length=20)
    equipment_no: str = Field(..., min_length=1, max_length=64)
    rack_count: int = Field(..., ge=1, le=26)        # 架 A~(A+n)
    layers_per_rack: int = Field(..., ge=1, le=20)   # 每架层 1~N
    boxes_per_layer: int = Field(..., ge=1, le=26)   # 每层盒区 A~(A+n)
    cells_per_box: int = Field(..., ge=1, le=400)    # 每盒孔 1~M (81/100 常见)
    remark: Optional[str] = None


class CellOut(ORMBase):
    """孔位 + 占用状态(盒内热力图用)。"""
    cell_node_id: int
    code: str                         # 孔号 '23'
    occupied: bool
    occupancy_id: Optional[int] = None
    batch_id: Optional[int] = None
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    batch_no: Optional[str] = None
    sample_label: Optional[str] = None
    expiry_date: Optional[date] = None       # 占用孔的批次有效期(供热力图三色:绿/红)
    days_to_expiry: Optional[int] = None      # <0 已过期


class BatchCellOut(ORMBase):
    """某批次占用的单个孔(出库勾选 / 物料详情弹窗用)。"""
    cell_node_id: int
    code: str                         # 孔号
    box_node_id: Optional[int] = None  # 所在盒区节点(供出库盒可视化按盒分组)
    address: str                      # 完整地址,如 'TT1 B3:A,23'
    sample_label: Optional[str] = None
    expiry_date: Optional[date] = None
    days_to_expiry: Optional[int] = None


class ReleaseCellsRequest(BaseModel):
    """出库:批量释放(取走)若干孔。"""
    cell_node_ids: List[int] = Field(..., min_length=1)
    txn_date: Optional[date] = None
    purpose: Optional[str] = None
    remark: Optional[str] = None


class OccupyRequest(BaseModel):
    """-80℃ 孔位入库: 共性批次信息 + 选定的若干空孔 → 占用 + 一条 IN 流水。"""
    material_id: int
    batch_no: str = Field(..., min_length=1, max_length=100)
    expiry_date: Optional[date] = None
    received_date: date
    cell_node_ids: List[int] = Field(..., min_length=1)
    sample_labels: Optional[List[Optional[str]]] = None   # 与 cell_node_ids 等长, 选填
    intake_type: Optional[str] = None
    concentration: Optional[str] = None
    extinction_coefficient: Optional[Decimal] = None
    project_no: Optional[str] = None
    originator_batch_no: Optional[str] = None
    aliquot_date: Optional[date] = None
    aliquot_spec: Optional[str] = None
    remark: Optional[str] = None


class ReleaseRequest(BaseModel):
    cell_node_id: int
    remark: Optional[str] = None


class OccupyFromRequest(BaseModel):
    """-80℃ 起始连续填充:从起始孔起取连续 count 个孔(须全空),占用入库。"""
    material_id: int
    batch_no: str = Field(..., min_length=1, max_length=100)
    expiry_date: Optional[date] = None
    received_date: date
    start_cell_node_id: int
    count: int = Field(..., ge=1, le=5000)
    sample_labels: Optional[List[Optional[str]]] = None
    intake_type: Optional[str] = None
    concentration: Optional[str] = None
    extinction_coefficient: Optional[Decimal] = None
    project_no: Optional[str] = None
    originator_batch_no: Optional[str] = None
    aliquot_date: Optional[date] = None
    aliquot_spec: Optional[str] = None
    remark: Optional[str] = None


class OccupyResult(BaseModel):
    batch_id: int
    count: int
    addresses: List[str]      # 形如 ['TT3 B3:A,23', ...]


# ---------------------------------------------------------------------------
# 批量入库(期3, 散放层多行)
# ---------------------------------------------------------------------------
class BulkIntakeRow(BaseModel):
    material_id: int
    batch_no: str = Field(..., min_length=1, max_length=100)
    expiry_date: Optional[date] = None
    location_id: int          # 散放 bulk 叶子(级联解析得到)
    qty: Decimal = Field(..., gt=0)
    concentration: Optional[str] = None
    extinction_coefficient: Optional[Decimal] = None
    serial_no: Optional[str] = None
    asset_no: Optional[str] = None
    responsible_person: Optional[str] = None
    project_no: Optional[str] = None
    originator_batch_no: Optional[str] = None
    aliquot_date: Optional[date] = None
    aliquot_spec: Optional[str] = None
    remark: Optional[str] = None


class BulkIntakeRequest(BaseModel):
    received_date: date
    intake_type: Optional[str] = None      # 全表共用(reagent/consumable/standard/column)
    rows: List[BulkIntakeRow] = Field(..., min_length=1, max_length=1000)


class BulkRowResult(BaseModel):
    index: int
    status: str               # created / appended / error
    batch_id: Optional[int] = None
    message: Optional[str] = None


class BulkIntakeResult(BaseModel):
    ok: bool                  # True=全部成功并已提交; False=有校验失败, 未写入任何数据
    created: int
    appended: int
    failed: int
    results: List[BulkRowResult]


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------
def _validate_hazard_class(v: Optional[List[str]]) -> Optional[List[str]]:
    """限制危化品分类只能取预设的 5 个枚举值,去重保序。"""
    if v is None:
        return None
    cleaned: List[str] = []
    seen = set()
    for x in v:
        x = (x or "").strip()
        if not x:
            continue
        if x not in HAZARD_CLASS_VALUES:
            raise ValueError(
                f"危化品分类 '{x}' 不在允许集合 {sorted(HAZARD_CLASS_VALUES)} 中"
            )
        if x not in seen:
            seen.add(x)
            cleaned.append(x)
    return cleaned or None


class MaterialBase(BaseModel):
    category: Optional[str] = None
    material_type: Optional[str] = Field(
        None, pattern="^(reagent|consumable|standard|column)$"
    )
    name_cn: str
    name_en: Optional[str] = None
    grade: Optional[str] = None
    manufacturer: Optional[str] = None
    spec_model: Optional[str] = None
    catalog_no: Optional[str] = None
    unit: str
    package_spec: Optional[str] = None
    hazard_class: Optional[List[str]] = None
    remark: Optional[str] = None
    safety_stock: Decimal = Decimal("0")

    @field_validator("hazard_class", mode="before")
    @classmethod
    def _hc(cls, v):
        return _validate_hazard_class(v)

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        if v not in CATEGORY_VALUES:
            raise ValueError(
                f"分类 '{v}' 不在允许集合中，合法值: {sorted(CATEGORY_VALUES)}"
            )
        return v


class MaterialCreate(MaterialBase):
    material_code: str = Field(..., min_length=1, max_length=20)


class MaterialUpdate(BaseModel):
    category: Optional[str] = None
    material_type: Optional[str] = Field(
        None, pattern="^(reagent|consumable|standard|column)$"
    )
    name_cn: Optional[str] = None
    name_en: Optional[str] = None
    grade: Optional[str] = None
    manufacturer: Optional[str] = None
    spec_model: Optional[str] = None
    catalog_no: Optional[str] = None
    unit: Optional[str] = None
    package_spec: Optional[str] = None
    hazard_class: Optional[List[str]] = None
    remark: Optional[str] = None
    safety_stock: Optional[Decimal] = None

    @field_validator("hazard_class", mode="before")
    @classmethod
    def _hc(cls, v):
        return _validate_hazard_class(v)


class MaterialOut(MaterialBase, ORMBase):
    material_id: int
    material_code: str
    data_source: Optional[str] = "local"
    is_active: bool
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None
    deactivate_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DeactivateRequest(BaseModel):
    # operator 已由鉴权自动从登录用户取,不再手填
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------
class BatchBase(BaseModel):
    # 创建批次时:必须用 material_id(因为 material_code 在 TT 例外下不唯一)
    material_id: int
    batch_no: str
    expiry_date: Optional[date] = None
    location_id: int       # v1.2 必填:批次必须有物理位置
    received_date: date
    initial_qty: Decimal
    remark: Optional[str] = None
    # 入库时 tab 类型(reagent/consumable/standard/column), 由前端 tab 决定
    intake_type: Optional[str] = Field(
        None, pattern="^(reagent|consumable|standard|column)$"
    )
    # 类型特定字段(由前端入库表单按 tab 条件填):
    concentration: Optional[str] = None              # 标准物质 浓度(数值+单位文本)
    extinction_coefficient: Optional[Decimal] = None # 标准物质 消光系数(2 位小数)
    serial_no: Optional[str] = None                  # 色谱柱
    asset_no: Optional[str] = None                   # 色谱柱 编号
    responsible_person: Optional[str] = None         # 色谱柱
    project_no: Optional[str] = None                 # 标准品 项目编号
    originator_batch_no: Optional[str] = None        # 标准品 原研药批号
    aliquot_date: Optional[date] = None              # 标准品 分装日期
    aliquot_spec: Optional[str] = None         # 标准品 分装规格(数值+单位, 例 "100 uL/支")


class BatchCreate(BatchBase):
    # operator 由鉴权自动从登录用户取
    pass


class BatchOut(BatchBase, ORMBase):
    batch_id: int
    created_at: datetime
    # 实时计算 / 关联展示
    current_qty: Optional[Decimal] = None
    location_name: Optional[str] = None
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    unit: Optional[str] = None


# ---------------------------------------------------------------------------
# Inventory Transaction
# ---------------------------------------------------------------------------
class TxnInRequest(BaseModel):
    """对已有批次追加入库 — operator 由鉴权自动填"""
    batch_id: int
    qty: Decimal = Field(..., gt=0)
    txn_date: date
    remark: Optional[str] = None


class TxnOutRequest(BaseModel):
    """出库:从指定批次扣减 — operator 由鉴权自动填"""
    batch_id: int
    qty: Decimal = Field(..., gt=0)
    txn_date: date
    purpose: Optional[str] = None
    remark: Optional[str] = None


class TxnAdjustRequest(BaseModel):
    """盘点调整:正负皆可 — operator 由鉴权自动填"""
    batch_id: int
    qty: Decimal  # 不限制正负
    txn_date: date
    remark: Optional[str] = None


class TransferRequest(BaseModel):
    """移库:从源批次扣 qty,搬到目的位置(同物料同批号)
    - 目的位置若已有同批号 batch → 追加流水
    - 否则按源批次的 expiry/received_date 自动建一条新 batch 行
    - operator 由鉴权自动填,源/目的各落一条 inventory_txn(OUT + IN)
    """
    source_batch_id: int
    dest_location_id: int
    qty: Decimal = Field(..., gt=0)
    txn_date: date
    remark: Optional[str] = None


class TxnOut(ORMBase):
    txn_id: int
    batch_id: int
    txn_type: str
    qty: Decimal
    txn_date: date
    operator: str
    purpose: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    # 关联展示字段(从 batch / material / location join 上来)
    batch_no: Optional[str] = None
    material_id: Optional[int] = None
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    location_name: Optional[str] = None
    # 该批次入库时的 tab 类型
    intake_type: Optional[str] = None
    # batch 上的类型特定字段, 入库页"出入库条目"表按 tab 显示对应列
    concentration: Optional[str] = None
    extinction_coefficient: Optional[Decimal] = None
    serial_no: Optional[str] = None
    asset_no: Optional[str] = None
    responsible_person: Optional[str] = None
    project_no: Optional[str] = None
    originator_batch_no: Optional[str] = None
    aliquot_date: Optional[date] = None
    aliquot_spec: Optional[str] = None


# ---------------------------------------------------------------------------
# Stock 视图(实时聚合)
# ---------------------------------------------------------------------------
class StockByMaterial(BaseModel):
    material_id: int
    material_code: str
    name_cn: str
    category: Optional[str] = None
    material_type: Optional[str] = None  # reagent/consumable/standard/column
    manufacturer: Optional[str] = None
    spec_model: Optional[str] = None
    catalog_no: Optional[str] = None
    unit: str
    is_active: bool
    safety_stock: Decimal
    total_qty: Decimal
    low_stock: bool  # total_qty < safety_stock 且 safety_stock > 0


class BatchMetaUpdate(BaseModel):
    """批次元信息修改(双人复核电子签名)。
    仅可改元信息;批号/数量/位置/物料不在此改(数量走盘点、位置走移库)。
    只提交需要改动的字段;reviewer_* 为第二位库管员/管理员的当场复核签名凭据。"""
    expiry_date: Optional[date] = None
    received_date: Optional[date] = None
    remark: Optional[str] = None
    concentration: Optional[str] = None
    extinction_coefficient: Optional[Decimal] = None
    serial_no: Optional[str] = None
    asset_no: Optional[str] = None
    responsible_person: Optional[str] = None
    project_no: Optional[str] = None
    originator_batch_no: Optional[str] = None
    aliquot_date: Optional[date] = None
    aliquot_spec: Optional[str] = None
    # 复核签名:第二位库管员/管理员的账号密码(向 MDM 验证身份,证明本人)
    reviewer_username: str
    reviewer_password: str


class StockByBatch(BaseModel):
    batch_id: int
    material_id: int
    material_code: str
    name_cn: str
    category: Optional[str] = None
    material_type: Optional[str] = None
    intake_type: Optional[str] = None    # 本批次入库时所在 tab(可能与 material_type 不同)
    manufacturer: Optional[str] = None
    spec_model: Optional[str] = None
    catalog_no: Optional[str] = None
    unit: str
    batch_no: str
    originator_batch_no: Optional[str] = None    # 标准品 原研药批号
    intake_operator_name: Optional[str] = None   # 入库登记操作人姓名(快照)
    expiry_date: Optional[date] = None
    location_id: int
    location_name: str
    received_date: date
    current_qty: Decimal
    days_to_expiry: Optional[int] = None
    is_active: bool


class ExpiryAlert(BaseModel):
    batch_id: int
    material_id: int
    material_code: str
    name_cn: str
    unit: str
    batch_no: str
    expiry_date: date
    days_to_expiry: int
    current_qty: Decimal
    location_name: Optional[str] = None
    severity: str  # 'EXPIRED' | 'URGENT' | 'WARNING'


class LowStockAlert(BaseModel):
    material_id: int
    material_code: str
    name_cn: str
    unit: str
    safety_stock: Decimal
    total_qty: Decimal
    gap: Decimal  # safety_stock - total_qty


# ---------------------------------------------------------------------------
# 鉴权 / 审计（用户管理已移至 MDM Portal）
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class AuditLogOut(ORMBase):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    before_json: Optional[Any] = None
    after_json: Optional[Any] = None
    source_ip: Optional[str] = None
    created_at: datetime
