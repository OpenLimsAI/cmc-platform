"""
SRS Pydantic schemas
对齐 API-MDM-001 第 9 章
"""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.audit.schemas import SignatureBlock

SubstanceType = Literal[
    "mab", "bispecific", "adc", "fusion", "small_molecule", "oligonucleotide", "other"
]
SubstanceStatus = Literal[
    "draft", "registered", "active", "restricted", "deprecated", "obsoleted"
]
Confidentiality = Literal["public", "internal", "restricted"]


class SubstanceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    substance_type: SubstanceType
    internal_code: str | None = Field(None, max_length=64)
    preferred_name: str = Field(..., max_length=255)
    preferred_name_en: str | None = Field(None, max_length=255)
    target: str | None = Field(None, max_length=128)
    target_type: str | None = Field(None, max_length=64)
    modality: str | None = Field(None, max_length=64)
    is_proprietary: bool = True
    confidentiality: Confidentiality = "internal"
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class ProteinExtension(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    heavy_chain_sequence: str | None = None
    light_chain_sequence: str | None = None
    additional_chains: dict | None = None
    sequence_length_hc: int | None = None
    sequence_length_lc: int | None = None
    sequence_hash_hc: str | None = None
    sequence_hash_lc: str | None = None
    isotype: str | None = None
    architecture: str | None = None
    disulfide_bonds: dict | None = None
    glycosylation_sites: dict | None = None
    ptm_info: dict | None = None
    expression_system: str | None = None
    cell_line: str | None = None
    expression_vector: str | None = None
    molecular_weight_da: float | None = None
    pi_theoretical: float | None = None
    extinction_coefficient: int | None = None


# V1.2 评审 API13:A 决议 — PUT /substances/{code}/adc 独立写端点
class AdcExtension(BaseModel):
    """ADC 扩展（§7.4）

    父子 substance 用 substance_code 表达（前端友好），service 内查 ORM 转 ID。
    """

    model_config = ConfigDict(from_attributes=True)

    antibody_substance_code: str | None = None
    linker_substance_code: str | None = None
    payload_substance_code: str | None = None
    dar_average: float | None = Field(None, ge=0, le=30)
    dar_distribution: dict | None = None
    dar_method: str | None = Field(None, max_length=64)
    conjugation_chemistry: str | None = Field(None, max_length=64)
    conjugation_site: str | None = Field(None, max_length=128)


class SubstanceXrefBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    xref_type: Literal[
        "INN", "USAN", "CAS", "UNII", "GSRS_UUID", "ChEMBL", "DRUGBANK",
        "TRADE_NAME", "GENERIC_NAME", "HISTORICAL_CODE", "PROJECT_CODE", "OTHER"
    ]
    xref_value: str = Field(..., max_length=255)
    xref_source: str | None = Field(None, max_length=64)
    region: str | None = Field(None, max_length=16)
    is_primary: bool = False
    effective_date: date | None = None
    expiry_date: date | None = None
    notes: str | None = None


class SubstanceXref(SubstanceXrefBase):
    xref_id: int


class SubstanceCreate(SubstanceBase):
    """POST 请求体"""

    protein: ProteinExtension | None = None
    xrefs: list[SubstanceXrefBase] = Field(default_factory=list)


class SubstanceUpdate(BaseModel):
    """PUT 请求体（带乐观锁）

    status 字段不在此处修改，走 :approve / :restrict / :deprecate / :obsolete 等状态机端点
    """

    version: int = Field(..., description="乐观锁版本号")
    change_reason: str | None = None

    internal_code: str | None = None
    preferred_name: str | None = None
    preferred_name_en: str | None = None
    target: str | None = None
    target_type: str | None = None
    modality: str | None = None
    is_proprietary: bool | None = None
    confidentiality: Confidentiality | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None

    protein: ProteinExtension | None = None


class SubstanceStatusChange(BaseModel):
    """状态机端点请求体（API-MDM-001 V1.1 §6.5）

    GxP 关键动作（approve / activate / deprecate / obsolete）必传 signature 嵌套对象；
    :restrict 是可逆的临时风控，不要求 signature（service 层据此校验 SignatureRequiredError）。
    """

    comment: str = Field(..., min_length=5, max_length=2000, description="状态变更原因（写入审计 + status_history）")
    signature: SignatureBlock | None = None


class SubstanceDelete(BaseModel):
    """DELETE 端点请求体。21 CFR Part 11 要求软删除附 reason。"""

    change_reason: str = Field(..., min_length=5, max_length=2000)


class SubstanceXrefCreate(SubstanceXrefBase):
    pass


class SubstanceXrefUpdate(BaseModel):
    """xref PUT 请求体（所有字段可选，传什么改什么）"""

    xref_type: Literal[
        "INN", "USAN", "CAS", "UNII", "GSRS_UUID", "ChEMBL", "DRUGBANK",
        "TRADE_NAME", "GENERIC_NAME", "HISTORICAL_CODE", "PROJECT_CODE", "OTHER"
    ] | None = None
    xref_value: str | None = Field(None, max_length=255)
    xref_source: str | None = Field(None, max_length=64)
    region: str | None = Field(None, max_length=16)
    is_primary: bool | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    notes: str | None = None


# ============== 同一性判定 ==============
class CheckSamenessRequest(BaseModel):
    """同一性判定请求

    Phase 1 仅实现 exact 模式：序列 SHA-256 哈希 + internal_code 精确匹配。
    fuzzy（基于编辑距离/CDR 相似度）留 Phase 5。
    """

    substance_type: SubstanceType
    heavy_chain_sequence: str | None = None
    light_chain_sequence: str | None = None
    internal_code: str | None = None
    tolerance: Literal["exact"] = "exact"


class SamenessMatch(BaseModel):
    substance_code: str
    preferred_name: str
    status: SubstanceStatus
    substance_type: SubstanceType
    matched_fields: list[str]  # 命中了哪些字段
    confidence: float  # 0.0 - 1.0，启发式打分


class CheckSamenessResponse(BaseModel):
    matches: list[SamenessMatch]
    input_summary: dict


class SubstanceBrief(BaseModel):
    """列表项精简字段"""

    model_config = ConfigDict(from_attributes=True)

    substance_code: str
    substance_type: SubstanceType
    internal_code: str | None = None
    preferred_name: str
    preferred_name_en: str | None = None
    target: str | None = None
    status: SubstanceStatus
    confidentiality: Confidentiality
    inn: str | None = None
    cas_number: str | None = None
    project_count: int = 0
    asset_count: int = 0
    material_count: int = 0
    created_at: datetime
    updated_at: datetime


class SubstanceDetail(SubstanceBase):
    """详情响应"""

    substance_id: int
    substance_code: str
    status: SubstanceStatus
    external_uuid: UUID | None = None
    version: int

    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    registered_at: datetime | None = None
    registered_by: int | None = None

    protein: ProteinExtension | None = None
    xrefs: list[SubstanceXref] = Field(default_factory=list)


class SubstanceFilter(BaseModel):
    """列表查询过滤"""

    q: str | None = None
    substance_type: str | None = None
    status: str | None = None
    target: str | None = None
    confidentiality: str | None = None
