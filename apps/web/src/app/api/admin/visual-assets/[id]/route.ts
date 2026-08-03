import { NextRequest } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Same-origin proxy for the admin Visual Asset Review queue (PR 11) — same
// SameSite=Lax cookie problem and same fix as apps/web/src/app/api/visual-assets/[id]/route.ts
// (PR 7), just pointed at the review-only backend endpoint, which serves
// any review_status (not just VERIFIED) since a reviewer needs to see an
// asset's image before deciding to approve it.
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") ?? "";

  const backendResponse = await fetch(`${API_URL}/api/v1/ingestion/visual-assets/${id}/image`, {
    headers: { cookie },
    cache: "no-store",
  });

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "content-type": backendResponse.headers.get("content-type") ?? "application/octet-stream",
    },
  });
}
