import client from "./client";

export interface AuditLogItem {
  id: number;
  user_id: number | null;
  username: string | null;
  full_name: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_json: unknown;
  after_json: unknown;
  source_ip: string | null;
  created_at: string;
}

export const listAuditLogs = (params?: {
  username?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  days?: number;
  limit?: number;
}) => client.get<AuditLogItem[]>("/api/audit/logs", { params });
