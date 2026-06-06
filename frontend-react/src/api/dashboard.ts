import client from "./client";

export interface DashboardStats {
  material_count: number;
  equipment_count: number;
  active_batch_count: number;
}

export const getDashboardStats = () =>
  client.get<DashboardStats>("/api/dashboard/stats");
