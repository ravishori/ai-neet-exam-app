import { describe, expect, it } from "vitest";

import { groupPermissions, labelFor, PERMISSION_LABELS } from "./capability-labels";

describe("capability-labels", () => {
  it("labels every code covered by the seeded RBAC permission set", () => {
    const seededCodes = [
      "questions.read",
      "questions.create",
      "questions.update",
      "questions.delete",
      "users.manage",
      "reports.view",
      "analytics.view",
      "ai.use",
      "content.create",
      "content.edit_own_draft",
      "content.submit_for_review",
      "content.review",
      "content.approve",
      "content.publish",
      "content.archive",
      "content.force_edit_published",
      "knowledge.manage",
      "visual_assets.review",
      "search.admin",
      "audit.view",
      "content.factory.view",
      "content.factory.create",
      "content.factory.execute",
      "content.factory.certify",
      "content.factory.trusted_submit",
    ];
    for (const code of seededCodes) {
      expect(PERMISSION_LABELS[code], `missing label for ${code}`).toBeDefined();
    }
  });

  // The complete set of permission codes seeded in
  // apps/backend/app/modules/identity/seed.py that have NO
  // require_permission(...) call site anywhere under apps/backend/app/modules
  // (verified by grep against the backend at audit time). Any code not in
  // this list is expected to be actively enforced.
  const UNENFORCED_CODES = [
    "reports.view",
    "questions.create",
    "questions.update",
    "questions.delete",
    "content.approve",
    "content.force_edit_published",
    "content.factory.certify",
  ];

  it("marks the complete known set of seeded-but-unenforced permissions as not enforced", () => {
    for (const code of UNENFORCED_CODES) {
      expect(labelFor(code).enforced, `expected ${code} to be enforced:false`).toBe(false);
    }
  });

  it("marks every other seeded permission as actively enforced", () => {
    const allSeededCodes = Object.keys(PERMISSION_LABELS);
    for (const code of allSeededCodes) {
      if (UNENFORCED_CODES.includes(code)) continue;
      expect(labelFor(code).enforced, `expected ${code} to be enforced:true`).toBe(true);
    }
  });

  it("falls back to the raw code for an unknown permission", () => {
    const label = labelFor("some.unmapped.permission");
    expect(label.feature).toBe("some.unmapped.permission");
    expect(label.group).toBe("Other");
  });

  it("groups permissions and sorts features alphabetically within a group", () => {
    const groups = groupPermissions(["content.publish", "content.archive", "users.manage"]);
    const content = groups.find((g) => g.group === "Content");
    expect(content).toBeDefined();
    expect(content!.features.map((f) => f.code)).toEqual(["content.archive", "content.publish"]);

    const platform = groups.find((g) => g.group === "Platform");
    expect(platform!.features.map((f) => f.code)).toEqual(["users.manage"]);
  });

  it("returns an empty group list for no permissions", () => {
    expect(groupPermissions([])).toEqual([]);
  });
});
