/**
 * Human-readable capability labels for RBAC permission codes, purely for
 * display in /admin/roles' Capability View. This is a presentation-only
 * lookup over the existing permission_codes RBAC already enforces
 * server-side (see require_permission() call sites in apps/backend) — it
 * grants nothing and changes no authorization behavior.
 *
 * `enforced: false` marks a permission that is seeded/assignable but has no
 * require_permission() call site yet in the backend, so the UI doesn't
 * imply an active gate that isn't there.
 */
export type CapabilityLabel = {
  feature: string;
  group: string;
  enforced: boolean;
};

export const PERMISSION_LABELS: Record<string, CapabilityLabel> = {
  "questions.read": { feature: "View questions", group: "Questions", enforced: true },
  "questions.create": { feature: "Create questions", group: "Questions", enforced: false },
  "questions.update": { feature: "Edit questions", group: "Questions", enforced: false },
  "questions.delete": { feature: "Delete questions", group: "Questions", enforced: false },

  "users.manage": { feature: "Manage user accounts and roles", group: "Platform", enforced: true },
  "reports.view": { feature: "View student/performance reports", group: "Platform", enforced: false },
  "analytics.view": { feature: "View analytics dashboards", group: "Platform", enforced: true },
  "audit.view": { feature: "View the platform audit log", group: "Platform", enforced: true },
  "search.admin": { feature: "Search console & reindexing", group: "Platform", enforced: true },

  "ai.use": { feature: "Use AI Tutor / Planner / Question Generator", group: "AI", enforced: true },

  "content.create": { feature: "Create content drafts (also gates PDF ingestion)", group: "Content", enforced: true },
  "content.edit_own_draft": { feature: "Edit your own draft content", group: "Content", enforced: true },
  "content.submit_for_review": { feature: "Submit a draft for review", group: "Content", enforced: true },
  "content.review": { feature: "Review submitted content", group: "Content", enforced: true },
  "content.approve": { feature: "Approve reviewed content", group: "Content", enforced: false },
  "content.publish": { feature: "Publish approved content", group: "Content", enforced: true },
  "content.archive": { feature: "Archive published content", group: "Content", enforced: true },
  "content.force_edit_published": {
    feature: "Hotfix published content (bypasses review)",
    group: "Content",
    enforced: false,
  },

  "knowledge.manage": { feature: "Manage Knowledge Units", group: "Content", enforced: true },
  "visual_assets.review": { feature: "Approve or reject visual assets", group: "Content", enforced: true },

  "content.factory.view": { feature: "View Content Factory batches/jobs", group: "Content Factory", enforced: true },
  "content.factory.create": {
    feature: "Create Content Factory batches/jobs",
    group: "Content Factory",
    enforced: true,
  },
  "content.factory.execute": {
    feature: "Run Content Factory generation",
    group: "Content Factory",
    enforced: true,
  },
  "content.factory.certify": { feature: "Certify factory batches", group: "Content Factory", enforced: false },
  "content.factory.trusted_submit": {
    feature: "Fast-track trusted drafts to review",
    group: "Content Factory",
    enforced: true,
  },
};

export const GROUP_ORDER = ["Platform", "Content", "Content Factory", "Questions", "AI"];

export function labelFor(code: string): CapabilityLabel {
  return PERMISSION_LABELS[code] ?? { feature: code, group: "Other", enforced: true };
}

export function groupPermissions(codes: string[]): { group: string; features: { code: string; label: CapabilityLabel }[] }[] {
  const byGroup = new Map<string, { code: string; label: CapabilityLabel }[]>();
  for (const code of codes) {
    const label = labelFor(code);
    const list = byGroup.get(label.group) ?? [];
    list.push({ code, label });
    byGroup.set(label.group, list);
  }
  const orderedGroups = [...GROUP_ORDER, ...[...byGroup.keys()].filter((g) => !GROUP_ORDER.includes(g))];
  return orderedGroups
    .filter((group) => byGroup.has(group))
    .map((group) => ({
      group,
      features: (byGroup.get(group) ?? []).sort((a, b) => a.label.feature.localeCompare(b.label.feature)),
    }));
}
