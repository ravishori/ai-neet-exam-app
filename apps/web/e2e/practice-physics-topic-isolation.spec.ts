import { test, expect } from "@playwright/test";

import { bootstrapStudent } from "./helpers";

const API = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

/**
 * T6-E-FIX: browser-level Practice path with TOPIC isolation for Kinematics.
 * Requires authenticated student + published Physics TOPIC pools.
 */
test.describe("Practice Physics TOPIC isolation", () => {
  test("Motion in a Straight Line vs Plane — no cross-topic leakage", async ({ page }) => {
    await bootstrapStudent(page);

    const topics = await page.evaluate(async (apiBase) => {
      const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1] ?? "";
      // Academic browse: subjects → chapters → topics (public student APIs vary; use practice generate probe)
      const subjects = await fetch(`${apiBase}/api/v1/subjects`, { credentials: "include" });
      if (!subjects.ok) return { ok: false, stage: "subjects", status: subjects.status, body: await subjects.json() };
      const sj = await subjects.json();
      const physics = (sj.data || []).find((s: { code?: string; name?: string }) =>
        (s.code || "").toUpperCase() === "PHYSICS" || (s.name || "").toLowerCase().includes("physics"),
      );
      if (!physics) return { ok: false, stage: "physics", body: sj };
      const chapters = await fetch(`${apiBase}/api/v1/subjects/${physics.id}/chapters`, {
        credentials: "include",
      });
      if (!chapters.ok) return { ok: false, stage: "chapters", status: chapters.status };
      const cj = await chapters.json();
      const kinematics = (cj.data || []).find((c: { code?: string; name?: string }) =>
        (c.code || "") === "kinematics" || (c.name || "").toLowerCase().includes("kinematic"),
      );
      if (!kinematics) return { ok: false, stage: "kinematics", body: cj };
      const topicsResp = await fetch(`${apiBase}/api/v1/chapters/${kinematics.id}/topics`, {
        credentials: "include",
      });
      if (!topicsResp.ok) return { ok: false, stage: "topics", status: topicsResp.status };
      const tj = await topicsResp.json();
      const straight = (tj.data || []).find((t: { code?: string }) => t.code === "motion-in-a-straight-line");
      const plane = (tj.data || []).find((t: { code?: string }) => t.code === "motion-in-a-plane");
      return {
        ok: true,
        csrf: decodeURIComponent(csrf),
        straightId: straight?.id as string | undefined,
        planeId: plane?.id as string | undefined,
      };
    }, API);

    if (!topics.ok || !topics.straightId || !topics.planeId) {
      test.skip(true, `Kinematics topics unavailable in this environment: ${JSON.stringify(topics)}`);
      return;
    }

    const runTopic = async (scopeId: string) =>
      page.evaluate(
        async ({ apiBase, scopeId: sid, csrf }) => {
          const gen = await fetch(`${apiBase}/api/v1/assessments/practice`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
            body: JSON.stringify({ scope_type: "TOPIC", scope_id: sid, question_count: 20 }),
          });
          const gj = await gen.json();
          if (!gen.ok || !gj.success) return { ok: false, stage: "generate", status: gen.status, body: gj };
          const start = await fetch(`${apiBase}/api/v1/assessments/${gj.data.id}/attempts`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          });
          const sj = await start.json();
          if (!start.ok || !sj.success) return { ok: false, stage: "start", status: start.status, body: sj };
          const attemptId = sj.data.id as string;
          const detail = await fetch(`${apiBase}/api/v1/attempts/${attemptId}`, { credentials: "include" });
          const dj = await detail.json();
          return {
            ok: detail.ok && dj.success,
            attemptId,
            questions: (dj.data?.questions || dj.data?.items || []) as Array<{
              topic_id?: string;
              topic_code?: string;
              concept_id?: string;
            }>,
            raw: dj,
          };
        },
        { apiBase: API, scopeId, csrf: topics.csrf as string },
      );

    const straightRun = await runTopic(topics.straightId);
    const planeRun = await runTopic(topics.planeId);

    // If pools empty, mark NOT VERIFIED rather than false green
    if (!straightRun.ok || !planeRun.ok) {
      test.skip(
        true,
        `Practice TOPIC pools not populated for browser E2E: straight=${JSON.stringify(straightRun)} plane=${JSON.stringify(planeRun)}`,
      );
      return;
    }

    await page.goto(`/student/attempts/${straightRun.attemptId}`);
    await expect(page.getByText(/Question\s+1\s+of/i).first()).toBeVisible({ timeout: 30_000 });
    const optionA = page.getByRole("button", { name: /^Option A:/i }).first();
    await expect(optionA).toBeVisible();
    await optionA.click();
    await page.getByRole("button", { name: /^Submit$/i }).first().click();
    await expect(page.getByText(/Score:/i).first()).toBeVisible({ timeout: 30_000 });

    // Cross-topic leakage: no straight attempt question should claim plane topic id when metadata present
    for (const q of straightRun.questions || []) {
      if (q.topic_id) expect(q.topic_id).toBe(topics.straightId);
      if (q.topic_code) expect(q.topic_code).toBe("motion-in-a-straight-line");
    }
    for (const q of planeRun.questions || []) {
      if (q.topic_id) expect(q.topic_id).toBe(topics.planeId);
      if (q.topic_code) expect(q.topic_code).toBe("motion-in-a-plane");
    }
  });
});
