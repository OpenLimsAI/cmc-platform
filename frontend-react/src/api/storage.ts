import client from "./client";

// 存放位置层级树节点(v1.5)
// node_type: ROOM/CABINET/CABINET_LAYER/FRIDGE/FRIDGE_SHELF/RACK/RACK_LAYER/BOX/CELL
export interface StorageNode {
  node_id: number;
  parent_id: number | null;
  node_type: string;
  code: string;
  label: string | null;
  path: string | null;
  depth: number;
  sort_order: number;
  capacity_kind: "bulk" | "cell" | null;
  location_id: number | null;
  temp_category: string | null;
  temp_text: string | null;
  is_active: boolean;
  remark: string | null;
  has_children: boolean;
}

export interface CabinetCreate {
  room_no: string;
  cabinet_no: string;
  layer_count: number;
  storage_condition?: string | null;
  remark?: string | null;
}

export interface FridgeCreate {
  room_no: string;
  fridge_name: string;
  temp_category: "normal" | "2-8" | "-20";
  shelf_count: number;
  storage_condition?: string | null;
  remark?: string | null;
}

export interface NodeUpdate {
  label?: string | null;
  remark?: string | null;
  is_active?: boolean | null;
}

// -80℃ 冰箱模板(期2)
export interface FreezerCreate {
  room_no: string;
  fridge_name: string;
  rack_count: number;       // 架 A~(A+n), ≤26
  layers_per_rack: number;  // 每架层 1~N
  boxes_per_layer: number;  // 每层盒区 A~(A+n), ≤26
  cells_per_box: number;    // 每盒孔 1~M(常见 81/100)
  remark?: string | null;
}

// 孔位 + 占用状态(热力图)
export interface Cell {
  cell_node_id: number;
  code: string;
  occupied: boolean;
  occupancy_id: number | null;
  batch_id: number | null;
  material_code: string | null;
  material_name: string | null;
  batch_no: string | null;
  sample_label: string | null;
}

export interface OccupyRequest {
  material_id: number;
  batch_no: string;
  expiry_date?: string | null;
  received_date: string;
  cell_node_ids: number[];
  sample_labels?: (string | null)[] | null;
  intake_type?: string | null;
  concentration?: string | null;
  extinction_coefficient?: number | null;
  remark?: string | null;
}

// 取某节点的直接下级;parentId 省略 → 根节点(房间)
export const listNodes = (parentId?: number, nodeType?: string) =>
  client.get<StorageNode[]>("/api/storage/nodes", {
    params: { parent_id: parentId, node_type: nodeType },
  });

// 从根到该节点的祖先链(含自身)
export const listAncestors = (nodeId: number) =>
  client.get<StorageNode[]>(`/api/storage/nodes/${nodeId}/ancestors`);

export const createCabinet = (data: CabinetCreate) =>
  client.post<StorageNode>("/api/storage/cabinets", data);

export const createFridge = (data: FridgeCreate) =>
  client.post<StorageNode>("/api/storage/fridges", data);

export const updateNode = (nodeId: number, data: NodeUpdate) =>
  client.patch<StorageNode>(`/api/storage/nodes/${nodeId}`, data);

export const deleteNode = (nodeId: number) =>
  client.delete(`/api/storage/nodes/${nodeId}`);

// 往已有节点追加下级(结构性编辑;支持异构/分批)
export interface AddChildrenRequest {
  child_type: "CABINET_LAYER" | "FRIDGE_SHELF" | "RACK" | "RACK_LAYER" | "BOX" | "CELL";
  count: number;
  layers_per_rack?: number;
  boxes_per_layer?: number;
  cells_per_box?: number;
  storage_condition?: string | null;
  remark?: string | null;
}

export const addChildren = (parentId: number, data: AddChildrenRequest) =>
  client.post<{ created: number; child_type: string; codes: string[] }>(
    `/api/storage/nodes/${parentId}/children`, data,
  );

// -80℃ 期2
export const createFreezer = (data: FreezerCreate) =>
  client.post<StorageNode>("/api/storage/freezers", data);

export const listCells = (boxId: number) =>
  client.get<Cell[]>("/api/storage/cells", { params: { box_id: boxId } });

export const findFreeCells = (freezerId: number, count: number) =>
  client.get<{ count: number; cell_node_ids: number[]; addresses: string[] }>(
    "/api/storage/free-cells", { params: { freezer_id: freezerId, count } },
  );

export const occupyCells = (data: OccupyRequest) =>
  client.post<{ batch_id: number; count: number; addresses: string[] }>(
    "/api/storage/occupy", data,
  );

export const releaseCell = (cellNodeId: number, remark?: string) =>
  client.post("/api/storage/release", { cell_node_id: cellNodeId, remark });
