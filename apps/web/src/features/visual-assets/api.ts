import { apiClient } from "@/lib/api-client";

export type ReviewStatus = "AUTO_DETECTED" | "VERIFIED" | "NEEDS_MANUAL_BBOX" | "REJECTED";

export type VisualAsset = {
  id: string;
  job_id: string;
  knowledge_unit_id: string | null;
  source_page: number;
  width_px: number | null;
  height_px: number | null;
  asset_type: string;
  detection_method: string;
  review_status: ReviewStatus;
  vision_description: string | null;
  approved_at: string | null;
  approved_by: string | null;
  rejection_reason: string | null;
  has_image: boolean;
};

export type VisualAssetListParams = {
  reviewStatus?: ReviewStatus;
  assetType?: string;
  limit?: number;
  offset?: number;
};

export type VisualAssetListResult = { data: VisualAsset[]; meta: { total: number; limit: number; offset: number } };

export const visualAssetsApi = {
  list: async (params: VisualAssetListParams = {}): Promise<VisualAssetListResult> => {
    const query = new URLSearchParams();
    if (params.reviewStatus) query.set("review_status", params.reviewStatus);
    if (params.assetType) query.set("asset_type", params.assetType);
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<VisualAsset[]>(`/api/v1/ingestion/visual-assets?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as VisualAssetListResult["meta"] };
  },
  approve: (id: string) => apiClient.post<VisualAsset>(`/api/v1/ingestion/visual-assets/${id}/approve`),
  reject: (id: string, reason: string) => apiClient.post<VisualAsset>(`/api/v1/ingestion/visual-assets/${id}/reject`, { reason }),
};
