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


TargetType = Literal["受体", "配体·细胞因子", "表面抗原", "酶", "其他"]
TargetLocation = Literal["膜型", "可溶型", "两者都有", "胞内"]
TargetStatus = Literal["draft", "published", "retired"]
MoleculeTargetRole = Literal["antibody_target", "payload_target", "other"]
SnapshotSource = Literal["uniprot", "chembl_target", "chembl_molecule", "chembl_mechanism", "other"]


# ============== tgt.target ==============
class TargetBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_name: str = Field(..., max_length=255, description="靶点名称（UniProt recommendedName 或人工）")
    uniprot_id: str | None = Field(None, max_length=16, description="UniProt 主 accession（查重锚点）")
    gene_symbol: str | None = Field(None, max_length=64)
    organism: str | None = Field("Homo sapiens", max_length=128)
    aliases: list[str] | None = Field(None, description="别名/短名/次级 accession 列表")
    target_type: TargetType
    target_location: TargetLocation
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None

    @field_validator("uniprot_id")
    @classmethod
    def _v_uniprot(cls, v: str | None) -> str | None:
        return _normalize_accession(v)


class TargetCreate(TargetBase):
    """POST 请求体：target_code 由系统 TGT-NNNNNN 取号，status 默认 draft"""


class TargetUpdate(BaseModel):
    """PUT 请求体（target_code / status 不在此改；status 走 :publish / :retire）"""

    change_reason: str | None = None

    target_name: str | None = Field(None, max_length=255)
    uniprot_id: str | None = Field(None, max_length=16)
    gene_symbol: str | None = Field(None, max_length=64)
    organism: str | None = Field(None, max_length=128)
    aliases: list[str] | None = None
    target_type: TargetType | None = None
    target_location: TargetLocation | None = None
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


class TargetBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_code: str
    target_name: str
    uniprot_id: str | None = None
    gene_symbol: str | None = None
    organism: str | None = None
    target_type: TargetType
    target_location: TargetLocation
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
    target_type: str | None = None
    target_location: str | None = None
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
