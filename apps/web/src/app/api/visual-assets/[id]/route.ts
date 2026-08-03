import { NextRequest } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Same-origin proxy for question images (PR 7). The backend's access-token
// cookie is SameSite=Lax, so a browser <img src> pointed directly at the
// backend's different-origin dev port never carries it — SameSite=Lax
// excludes cross-site subresource requests, only allowing top-level
// navigations. Rather than loosening that cookie's SameSite policy (a
// broad, unrelated security change), this route runs server-side: it reads
// the incoming request's Cookie header itself (a same-origin browser
// request always includes it) and forwards it in its own server-to-server
// fetch to the backend, which isn't subject to browser SameSite rules at
// all.
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") ?? "";

  const backendResponse = await fetch(`${API_URL}/api/v1/knowledge/visual-assets/${id}/image`, {
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
