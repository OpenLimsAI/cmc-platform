"""Structural types for local synthetic/demo fixture definitions; no data or side effects."""
from typing import Required, TypedDict


class UserSeed(TypedDict, total=False):
    department: Required[str]
    email: Required[str]
    full_name: Required[str]
    full_name_en: str
    password: Required[str]
    roles: Required[list[str]]
    title: Required[str]
    username: Required[str]


class SubstanceSeedProtein(TypedDict, total=False):
    cell_line: str
    expression_system: Required[str]
    heavy_chain_sequence: str
    isotype: Required[str]
    light_chain_sequence: str
    molecular_weight_da: Required[float]


class SubstanceSeedXrefsItem(TypedDict, total=False):
    is_primary: bool
    xref_source: Required[str]
    xref_type: Required[str]
    xref_value: Required[str]


class SubstanceSeed(TypedDict, total=False):
    confidentiality: Required[str]
    description: Required[str]
    internal_code: Required[str]
    modality: Required[str]
    preferred_name: Required[str]
    preferred_name_en: str
    protein: SubstanceSeedProtein
    status: Required[str]
    substance_type: Required[str]
    target: Required[str]
    target_type: str
    xrefs: list[SubstanceSeedXrefsItem]


class ProjectSeedMilestonesItem(TypedDict, total=False):
    actual_date: str
    name: Required[str]
    planned_date: Required[str]
    status: Required[str]
    type: Required[str]


class ProjectSeed(TypedDict, total=False):
    actual_end_date: str
    actual_start_date: str
    department: str
    description: Required[str]
    indication: Required[str]
    link_relation: Required[str]
    link_substance: Required[str]
    milestones: Required[list[ProjectSeedMilestonesItem]]
    name: Required[str]
    name_en: Required[str]
    owner_username: Required[str]
    phase: Required[str]
    planned_end_date: Required[str]
    planned_start_date: Required[str]
    project_type: Required[str]
    status: Required[str]
    team: Required[list[tuple[str, str]]]
    therapeutic_area: Required[str]


class AssetSeedComponentsItem(TypedDict, total=False):
    component_role: Required[str]
    substance_internal_code: Required[str]


class AssetSeedMarketIdsItem(TypedDict, total=False):
    expiry_date: str | None
    application_date: Required[str]
    approval_date: Required[str]
    id_type: Required[str]
    id_value: Required[str]
    issuing_authority: Required[str]
    market_code: Required[str]
    status: Required[str]


class AssetSeedProjectsItem(TypedDict, total=False):
    project_name: Required[str]
    relation_type: Required[str]


class AssetSeed(TypedDict, total=False):
    asset_type: Required[str]
    components: Required[list[AssetSeedComponentsItem]]
    current_phase: Required[str]
    description: Required[str]
    dosage_form: str
    first_approval_date: str
    first_launch_date: str
    indication: Required[str]
    inn_name: str | None
    internal_name: Required[str]
    is_commercial: Required[bool]
    market_ids: list[AssetSeedMarketIdsItem]
    projects: list[AssetSeedProjectsItem]
    route_of_administration: str
    status: Required[str]
    strength: str
    therapeutic_area: Required[str]
    trade_name: str | None


class MaterialSeedBatchesItem(TypedDict, total=False):
    batch_number: Required[str]
    expiry_date: str
    manufacture_date: str
    quantity_unit: Required[str]
    quantity_value: Required[str]
    receive_date: Required[str]
    source_batch_ref: str
    status: Required[str]
    storage_location: Required[str]


class MaterialSeed(TypedDict, total=False):
    batches: Required[list[MaterialSeedBatchesItem]]
    catalog_no: Required[str]
    category: Required[str]
    description: Required[str]
    grade: str
    manufacturer: Required[str]
    material_code: Required[str]
    material_name: Required[str]
    material_name_en: Required[str]
    material_type: Required[str]
    package_spec: Required[str]
    physical_form: str
    source_name: Required[str]
    source_type: Required[str]
    spec_model: str
    storage_condition: Required[str]
    substance_internal_code: str
    unit: Required[str]
