"""靶点域 Pydantic schemas — 对齐 0050_tgt_target migration。"""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# UniProt accession 官方正则（不含 isoform 后缀）：https://www.uniprot.org/help/accession_numbers
UNIPROT_ACCESSION_RE = re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$")


def _normalize_accession(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().upper()
    if not v:
        return None
    if not UNIPROT_ACCESSION_RE.match(v):
        raise ValueError(f"不是合法的 UniProt accession: {v}")
    return v


TargetStatus = Literal["draft", "published", "retired"]
MoleculeTargetRole = Literal["antibody_target", "payload_target", "other"]
SnapshotSource = Literal["uniprot", "chembl_target", "chembl_molecule", "chembl_mechanism", "other"]


# ============== UniProt 标准子结构 ==============
class UniprotKeyword(BaseModel):
    id: str | None = None          # KW-0675
    name: str                      # Receptor
    category: str | None = None    # Molecular function / Cellular component / Biological process / ...


class UniprotSubcellularLocation(BaseModel):
    id: str | None = None          # SL-0039
    location: str                  # Cell membrane
    topology: str | None = None    # Single-pass type I membrane protein
    topology_id: str | None = None # SL-9905
    orientation: str | None = None
    molecule: str | None = None    # 同种型/剪接体说明（若有）


class UniprotDomain(BaseModel):
    type: str                      # Domain / Region / Topological domain / Transmembrane / Signal / Chain
    description: str | None = None
    start: int | None = None
    end: int | None = None


# ============== tgt.target ==============
class TargetUniprotFields(BaseModel):
    """UniProt 标准字段（0051）：新建/更新时随预填一起提交；正常情况下由「拉取」自动带出，人不手填。"""

    model_config = ConfigDict(from_attributes=True)

    entry_type: str | None = Field(None, max_length=64)
    protein_existence: str | None = Field(None, max_length=64)
    cd_antigen_names: list[str] | None = None
    gene_synonyms: list[str] | None = None
    tax_id: int | None = None
    keywords: list[UniprotKeyword] | None = None
    subcellular_locations: list[UniprotSubcellularLocation] | None = None
    ec_numbers: list[str] | None = None
    domains: list[UniprotDomain] | None = None
    sequence_length: int | None = None
    mol_weight: int | None = None
    sequence_md5: str | None = Field(None, max_length=32)
    sequence_crc64: str | None = Field(None, max_length=16)
    sequence: str | None = Field(None, description="完整单字母氨基酸序列（UniProt canonical）")
    uniprot_entry_version: int | None = None
    uniprot_fetched_at: datetime | None = None


class TargetBase(TargetUniprotFields):
    target_name: str = Field(..., max_length=255, description="靶点名称（UniProt recommendedName；无 UniProt 号时人工填）")
    uniprot_id: str | None = Field(None, max_length=16, description="UniProt 主 accession（查重锚点）")
    gene_symbol: str | None = Field(None, max_length=64)
    organism: str | None = Field("Homo sapiens", max_length=128)
    aliases: list[str] | None = Field(None, description="短名/别名/次级 accession 列表（次级 accession 参与查重）")
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None

    @field_validator("uniprot_id")
    @classmethod
    def _v_uniprot(cls, v: str | None) -> str | None:
        return _normalize_accession(v)


class TargetCreate(TargetBase):
    """POST 请求体：target_code 由系统 TGT-NNNNNN 取号，status 默认 draft"""


class TargetUpdate(TargetUniprotFields):
    """PUT 请求体（target_code / status 不在此改；status 走 :publish / :retire）
    UniProt 字段一般由 :refresh-uniprot 整体刷新，PUT 主要改 notes / 兜底字段。"""

    change_reason: str | None = None

    target_name: str | None = Field(None, max_length=255)
    uniprot_id: str | None = Field(None, max_length=16)
    gene_symbol: str | None = Field(None, max_length=64)
    organism: str | None = Field(None, max_length=128)
    aliases: list[str] | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None

    @field_validator("uniprot_id")
    @classmethod
    def _v_uniprot(cls, v: str | None) -> str | None:
        return _normalize_accession(v)


class TargetDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class TargetStatusChange(BaseModel):
    """:publish / :retire 请求体（轻档：只要变更原因，无电签）"""

    change_reason: str = Field(..., min_length=5, max_length=2000)


class TargetRefreshUniprot(BaseModel):
    """:refresh-uniprot 请求体：按当前 uniprot_id 重新拉取并整体覆盖 UniProt 字段 + 存新快照"""

    change_reason: str = Field(..., min_length=5, max_length=2000)


class TargetBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_code: str
    target_name: str
    uniprot_id: str | None = None
    gene_symbol: str | None = None
    organism: str | None = None
    entry_type: str | None = None
    cd_antigen_names: list[str] | None = None
    keywords: list[UniprotKeyword] | None = None
    subcellular_locations: list[UniprotSubcellularLocation] | None = None
    status: TargetStatus
    created_at: datetime
    updated_at: datetime


class TargetDetail(TargetBase):
    target_id: int
    target_code: str
    status: TargetStatus
    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None


class TargetFilter(BaseModel):
    q: str | None = None
    keyword: str | None = None            # 关键词名精确（如 Receptor / Cytokine）
    keyword_category: str | None = None   # 配合 keyword 限定类别（如 Molecular function）
    location: str | None = None           # 亚细胞定位名（如 Cell membrane / Secreted），前缀匹配
    entry_type: str | None = None
    status: str | None = None
    uniprot_id: str | None = None


# ============== ref.molecule_target ==============
class MoleculeTargetLinkCreate(BaseModel):
    """POST /targets/{code}/molecules 请求体"""

    substance_code: str = Field(..., max_length=32, description="分子 = srs.substance.substance_code")
    relation_role: MoleculeTargetRole = "antibody_target"
    moa: str | None = None
    action_type: str | None = Field(None, max_length=64)
    binding_epitope_or_domain: str | None = None
    chembl_mechanism_id: int | None = None
    needs_confirm: bool = False
    notes: str | None = None


class MoleculeTargetLinkUpdate(BaseModel):
    """PUT /targets/{code}/molecules/{substance_code}/{relation_role}"""

    change_reason: str | None = None
    moa: str | None = None
    action_type: str | None = Field(None, max_length=64)
    binding_epitope_or_domain: str | None = None
    chembl_mechanism_id: int | None = None
    needs_confirm: bool | None = None
    notes: str | None = None


class MoleculeTargetLinkDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class MoleculeTargetLinkOut(BaseModel):
    """关联记录（带两端编码/名称快照，便于列表展示）"""

    model_config = ConfigDict(from_attributes=True)

    molecule_id: int
    substance_code: str
    substance_name: str | None = None
    target_id: int
    target_code: str
    target_name: str
    relation_role: MoleculeTargetRole
    moa: str | None = None
    action_type: str | None = None
    binding_epitope_or_domain: str | None = None
    chembl_mechanism_id: int | None = None
    needs_confirm: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# ============== tgt.target_source_snapshot ==============
class TargetSnapshotCreate(BaseModel):
    source: SnapshotSource
    source_id: str | None = Field(None, max_length=64)
    source_version: str | None = Field(None, max_length=64)
    source_url: str | None = None
    fetched_at: datetime
    payload: dict
    license: str | None = Field(None, max_length=64)


class TargetSnapshotBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    target_id: int
    source: SnapshotSource
    source_id: str | None = None
    source_version: str | None = None
    source_url: str | None = None
    fetched_at: datetime
    license: str | None = None
    created_at: datetime
    created_by: int


class TargetSnapshotDetail(TargetSnapshotBrief):
    payload: dict


# ============== UniProt 单条预填（GET /targets/prefill/uniprot）==============
class TargetPrefillForm(TargetUniprotFields):
    """与 TargetCreate 字段一致（不含 notes/extra），可直接回填表单 / 提交"""

    target_name: str | None = None
    uniprot_id: str | None = None
    gene_symbol: str | None = None
    organism: str | None = None
    aliases: list[str] | None = None
    description: str | None = None


class TargetPrefillHints(BaseModel):
    entry_type: str | None = None
    entry_version: int | None = None
    tax_id: int | None = None
    sequence_length: int | None = None
    is_human: bool | None = None
    is_reviewed: bool | None = None       # Swiss-Prot 人工审阅
    redirected_from: str | None = None    # 输入的是次级/旧号，UniProt 已重定向到主号


class TargetPrefillResponse(BaseModel):
    accession: str
    existing: TargetBrief | None = Field(None, description="库里已有同号靶点（含次级 accession）→ 应建关联而非新建")
    form: TargetPrefillForm
    hints: TargetPrefillHints
    snapshot: TargetSnapshotCreate = Field(..., description="保存靶点后可直接 POST 到 /targets/{code}/snapshots")


# ============== INN 全链路预填（POST /targets/prefill/inn）+ 应用（:apply）==============
class InnPrefillRequest(BaseModel):
    inn: str = Field(..., min_length=2, max_length=128, description="国际非专利名，如 guselkumab")


class InnPrefillCandidate(BaseModel):
    """一条候选关联（= mechanism × target_component 展开后的一行）"""

    uniprot_id: str | None = None
    target_name: str | None = None
    gene_symbol: str | None = None
    existing: TargetBrief | None = Field(None, description="库里已有 → 只建关联")
    new_target: TargetPrefillForm | None = Field(None, description="库里没有 → 可按此表单新建（UniProt 标准字段）")
    relation_role: MoleculeTargetRole = "antibody_target"
    moa: str | None = None
    action_type: str | None = None
    binding_epitope_or_domain: str | None = None
    chembl_mechanism_id: int | None = None
    chembl_target_id: str | None = None
    chembl_target_type: str | None = None
    binding_subunit_hint: str | None = None   # PROTEIN COMPLEX：LIKELY / UNLIKELY
    needs_confirm: bool = False
    confirm_reason: str | None = None
    suggested_selected: bool = True           # 前端默认勾选建议（UNLIKELY 亚基默认不勾）


class InnPrefillBiocomponent(BaseModel):
    component_id: int | None = None
    component_type: str | None = None   # Protein / None（二硫键、糖基化位点等结构注释）
    description: str | None = None      # Heavy chain / Light chain / Heavy chain: anti-FX ...
    organism: str | None = None
    sequence: str | None = None
    sequence_len: int = 0


class InnPrefillMolecule(BaseModel):
    chembl_id: str | None = None
    pref_name: str | None = None
    molecule_type: str | None = None
    max_phase: float | None = None
    first_approval: int | None = None
    research_codes: list[str] = []
    trade_names: list[str] = []
    usan_stem: str | None = None
    usan_stem_definition: str | None = None
    biotherapeutic_description: str | None = None   # 如 "Guselkumab (human mab)"
    biocomponents: list[InnPrefillBiocomponent] = []
    atc_classifications: list[str] = []
    synonyms: list[list[str | None]] = []            # [(name, syn_type)]
    cross_references: list[list[str | None]] = []    # [(src, id)]
    fetched_at: str | None = None
    # 单抗立项辅助：从组分推断
    heavy_chain_sequence: str | None = None
    light_chain_sequence: str | None = None
    is_simple_mab: bool | None = None                # Antibody 且恰好 1 条重链 + 1 条轻链


class InnPrefillResponse(BaseModel):
    inn: str
    outcome: str
    user_message: str | None = None
    molecule: InnPrefillMolecule | None = None
    warnings: list[str] = []
    candidates: list[InnPrefillCandidate] = []
    # 供 :apply 落快照：accession → 快照体（uniprot / chembl_target）
    snapshots: dict[str, list[TargetSnapshotCreate]] = {}
    chembl_candidates: list[dict] = Field(default_factory=list, description="NEEDS_MANUAL_PICK 时的模糊候选")


class InnApplyLink(BaseModel):
    uniprot_id: str
    relation_role: MoleculeTargetRole = "antibody_target"
    moa: str | None = None
    action_type: str | None = Field(None, max_length=64)
    binding_epitope_or_domain: str | None = None
    chembl_mechanism_id: int | None = None
    needs_confirm: bool = False
    notes: str | None = None
    new_target: TargetPrefillForm | None = Field(None, description="库里没有时按此新建（服务端会再查重一次）")


class InnApplyRequest(BaseModel):
    substance_code: str = Field(..., max_length=32)
    inn: str = Field(..., max_length=128)
    molecule: InnPrefillMolecule | None = None
    links: list[InnApplyLink] = Field(..., min_length=1)
    snapshots: dict[str, list[TargetSnapshotCreate]] = {}
    add_substance_xrefs: bool = Field(True, description="把 ChEMBL ID / INN / 商品名回填到物质标识符（已存在的跳过）")


class InnApplyResult(BaseModel):
    substance_code: str
    created_targets: list[TargetBrief] = []
    linked: list[MoleculeTargetLinkOut] = []
    skipped: list[str] = []
    xrefs_added: list[str] = []
