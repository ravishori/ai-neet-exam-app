import { request } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const API = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const WEB = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3001";
const STATE = path.join(__dirname, ".auth", "student.json");

/**
 * Register once (with login fallback) and persist storage state for all projects.
 * Avoids /auth/register rate limit (5/min) across the viewport matrix.
 */
async function globalSetup() {
  fs.mkdirSync(path.dirname(STATE), { recursive: true });
  const email = process.env.PLAYWRIGHT_STUDENT_EMAIL ?? `pw-shared-${Date.now()}@example.com`;
  const password = process.env.PLAYWRIGHT_STUDENT_PASSWORD ?? "PracticeTest!234";

  // B6 hardening (2026-09-22): mobile/state_code/city were made required by
  // RegisterRequest well before this fixture was last touched — this
  // globalSetup was silently broken (422 on every fresh run) until now.
  const mobile = `9${Math.floor(100000000 + Math.random() * 900000000)}`;

  const api = await request.newContext({ baseURL: API });
  let reg = await api.post("/api/v1/auth/register", {
    data: {
      email,
      password,
      first_name: "Play",
      last_name: "Wright",
      mobile,
      state_code: "KARNATAKA",
      city: "Bangalore",
    },
  });

  if (!reg.ok()) {
    const body = await reg.text();
    if (body.includes("RATE_LIMITED") || reg.status() === 409 || body.includes("already")) {
      reg = await api.post("/api/v1/auth/login", { data: { email, password } });
    }
    if (!reg.ok()) {
      // Last resort: wait for rate window then register a unique email
      await new Promise((r) => setTimeout(r, 65_000));
      const retryEmail = `pw-shared-${Date.now()}@example.com`;
      reg = await api.post("/api/v1/auth/register", {
        data: {
          email: retryEmail,
          password,
          first_name: "Play",
          last_name: "Wright",
          mobile: `9${Math.floor(100000000 + Math.random() * 900000000)}`,
          state_code: "KARNATAKA",
          city: "Bangalore",
        },
      });
    }
  }

  if (!reg.ok()) {
    throw new Error(`globalSetup auth failed: ${reg.status()} ${await reg.text()}`);
  }

  const jar = await api.storageState();
  const cookies = [];
  for (const c of jar.cookies) {
    for (const url of [`${WEB}/`, `${API}/`]) {
      cookies.push({
        name: c.name,
        value: c.value,
        url,
        httpOnly: c.httpOnly,
        secure: false,
        sameSite: "Lax" as const,
      });
    }
  }

  fs.writeFileSync(
    STATE,
    JSON.stringify({ cookies, origins: [] }, null, 2),
  );
  await api.dispose();
}

export default globalSetup;
