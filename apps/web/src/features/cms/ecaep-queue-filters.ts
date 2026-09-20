/**
 * Admin ECAEP queue filter helpers (Phase 3.3-R1).
 * URL: ?subject_name=&status=&difficulty=&provenance=&readiness=&pilot=&batch_a=&page=
 */

export const ECAEP_WORKFLOW_STATUSES = [
  { value: "any", label: "All statuses" },
  { value: "DRAFT", label: "DRAFT" },
  { value: "IN_REVIEW", label: "IN_REVIEW" },
  { value: "APPROVED", label: "APPROVED" },
  { value: "CHANGES_REQUESTED", label: "CHANGES_REQUESTED" },
  { value: "PUBLISHED", label: "PUBLISHED" },
  { value: "ARCHIVED", label: "ARCHIVED" },
] as const;

/** Canonical status filter values (includes URL sentinel `any`). */
export type EcaepFilterStatus = (typeof ECAEP_WORKFLOW_STATUSES)[number]["value"];

/** Membership set typed as string keys so URL `string`s can be checked, then narrowed. */
const ALLOWED_STATUS: ReadonlySet<string> = new Set(
  ECAEP_WORKFLOW_STATUSES.map((s) => s.value),
);

function isEcaepFilterStatus(value: string): value is EcaepFilterStatus {
  return ALLOWED_STATUS.has(value);
}

export const BATCH_A_TAG = "acquisition-batch-A-diversify-p0";

export type EcaepQueueFilters = {
  subjectName: string;
  status: string;
  difficulty: string;
  provenance: string;
  readiness: string;
  pilotOnly: boolean;
  batchAOnly: boolean;
  page: number; // 0-based
};

export const DEFAULT_ECAEP_FILTERS: EcaepQueueFilters = {
  subjectName: "",
  status: "IN_REVIEW",
  difficulty: "",
  provenance: "",
  readiness: "",
  pilotOnly: false,
  batchAOnly: false,
  page: 0,
};

export function parseEcaepFilters(sp: URLSearchParams): EcaepQueueFilters {
  const rawStatus = sp.get("status");
  let status = DEFAULT_ECAEP_FILTERS.status;
  if (rawStatus === "") status = "any";
  else if (rawStatus != null && isEcaepFilterStatus(rawStatus)) status = rawStatus;

  const pageRaw = Number(sp.get("page") || "1");
  const page =
    Number.isFinite(pageRaw) && pageRaw >= 1 ? Math.floor(pageRaw) - 1 : 0;

  return {
    subjectName: sp.get("subject_name")?.trim() || "",
    status,
    difficulty: sp.get("difficulty") || "",
    provenance: sp.get("provenance") || "",
    readiness: sp.get("readiness") || "",
    pilotOnly: sp.get("pilot") === "1" || sp.get("pilot") === "true",
    batchAOnly: sp.get("batch_a") === "1" || sp.get("batch_a") === "true",
    page,
  };
}

export function ecaepFiltersToSearchParams(f: EcaepQueueFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.subjectName) p.set("subject_name", f.subjectName);
  if (f.status && f.status !== "any") p.set("status", f.status);
  else if (f.status === "any") p.set("status", "any");
  if (f.difficulty) p.set("difficulty", f.difficulty);
  if (f.provenance) p.set("provenance", f.provenance);
  if (f.readiness) p.set("readiness", f.readiness);
  if (f.pilotOnly) p.set("pilot", "1");
  if (f.batchAOnly) p.set("batch_a", "1");
  if (f.page > 0) p.set("page", String(f.page + 1));
  return p;
}

export function ecaepFiltersToApiParams(f: EcaepQueueFilters, pageSize: number) {
  return {
    status: f.status || "any",
    subject_name: f.subjectName || undefined,
    difficulty: f.difficulty || undefined,
    provenance: f.provenance || undefined,
    review_readiness: f.readiness || undefined,
    batch_tag: f.batchAOnly ? BATCH_A_TAG : undefined,
    pilot_only: f.pilotOnly || undefined,
    limit: pageSize,
    offset: f.page * pageSize,
  };
}

export function ecaepFilterSummary(f: EcaepQueueFilters): string {
  const subject = f.subjectName || "All subjects";
  const status =
    f.status === "any" || !f.status
      ? "All statuses"
      : f.status;
  return `${subject} · ${status}`;
}
