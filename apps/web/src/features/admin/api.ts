import { apiClient } from "@/lib/api-client";

export type DashboardOverview = {
  content_by_status: Record<string, number>;
  ingestion_by_status: Record<string, number>;
  pending_visual_assets: number;
  open_content_reports: number;
  total_users: number;
  ai_total_requests: number;
  ai_total_cost_usd: number;
};

export type AuditLogEntry = {
  id: string;
  actor_user_id: string | null;
  actor_email: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
};

export type AuditLogListParams = {
  actorUserId?: string;
  action?: string;
  entityType?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
};

export type AuditLogListResult = {
  data: AuditLogEntry[];
  meta: { total: number; limit: number; offset: number };
};

export const adminApi = {
  dashboard: () => apiClient.get<DashboardOverview>("/api/v1/admin/dashboard"),
  auditLogs: async (params: AuditLogListParams = {}): Promise<AuditLogListResult> => {
    const query = new URLSearchParams();
    if (params.actorUserId) query.set("actor_user_id", params.actorUserId);
    if (params.action) query.set("action", params.action);
    if (params.entityType) query.set("entity_type", params.entityType);
    if (params.since) query.set("since", params.since);
    if (params.until) query.set("until", params.until);
    query.set("limit", String(params.limit ?? 50));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<AuditLogEntry[]>(`/api/v1/admin/audit-logs?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as AuditLogListResult["meta"] };
  },
};
