"""
ref schema Pydantic schemas

DM-MDM-001 V1.0：
  - §11.2 ref.project_substance
  - §11.3 ref.asset_substance
  - §11.4 ref.project_asset
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RelationType = Literal["primary", "secondary", "reference", "control", "derivative"]
ComponentRole = Literal[
    "main_component", "antibody", "linker", "payload", "excipient", "impurity"
]
# §11.4 文档没有限定枚举；前端按建议值展示，但后端不做 CHECK
ProjectAssetRelationType = Literal[
    "primary", "supporting", "derivative", "reference"
]


# ============== §11.2 ProjectSubstance ==============
class ProjectSubstanceLinkCreate(BaseModel):
    """POST /projects/{code}/substances 请求体"""

    substance_code: str = Field(..., max_length=32)
    relation_type: RelationType = "primary"
    is_primary: bool = False
    notes: str | None = None


class ProjectSubstanceLinkUnlink(BaseModel):
    """DELETE /projects/{code}/substances/{substance_code}/{relation_type} 请求体"""

    change_reason: str | None = Field(None, max_length=2000)


class ProjectSubstanceLinkItem(BaseModel):
    """双向列表项：同时携带 project 与 substance 的展示字段"""

    model_config = ConfigDict(from_attributes=True)

    relation_type: RelationType
    is_primary: bool
    notes: str | None = None
    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    project_code: str
    project_name: str
    project_status: str
    project_type: str

    substance_code: str
    substance_preferred_name: str
    substance_status: str
    substance_type: str


# ============== §11.3 AssetSubstance ==============
class AssetSubstanceLinkCreate(BaseModel):
    """POST /assets/{code}/substances"""

    substance_code: str = Field(..., max_length=32)
    component_role: ComponentRole = "main_component"
    is_active_ingredient: bool = True
    notes: str | None = None


class AssetSubstanceLinkUnlink(BaseModel):
    change_reason: str | None = Field(None, max_length=2000)


class AssetSubstanceLinkItem(BaseModel):
    """双向列表项：携带 asset + substance 投影"""

    model_config = ConfigDict(from_attributes=True)

    component_role: ComponentRole
    is_active_ingredient: bool
    notes: str | None = None
    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    asset_code: str
    asset_internal_name: str
    asset_type: str
    asset_status: str
    asset_phase: str

    substance_code: str
    substance_preferred_name: str
    substance_status: str
    substance_type: str


# ============== §11.4 ProjectAsset ==============
class ProjectAssetLinkCreate(BaseModel):
    """POST /projects/{code}/assets 或 POST /assets/{code}/projects"""

    # 至少其一会从 path 推断，schema 用 code 表达
    relation_type: ProjectAssetRelationType = "primary"
    notes: str | None = None


class ProjectAssetLinkByProject(ProjectAssetLinkCreate):
    """在 POST /projects/{code}/assets 时，请求体里给 asset_code"""

    asset_code: str = Field(..., max_length=32)


class ProjectAssetLinkByAsset(ProjectAssetLinkCreate):
    """在 POST /assets/{code}/projects 时，请求体里给 project_code"""

    project_code: str = Field(..., max_length=32)


class ProjectAssetLinkUnlink(BaseModel):
    change_reason: str | None = Field(None, max_length=2000)


class ProjectAssetLinkItem(BaseModel):
    """双向列表项：携带 project + asset 投影"""

    model_config = ConfigDict(from_attributes=True)

    relation_type: str
    notes: str | None = None
    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    project_code: str
    project_name: str
    project_status: str
    project_type: str

    asset_code: str
    asset_internal_name: str
    asset_type: str
    asset_status: str
    asset_phase: str
