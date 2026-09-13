import { describe, expect, it } from "vitest";

import {
  BATCH_A_TAG,
  DEFAULT_ECAEP_FILTERS,
  ecaepFilterSummary,
  ecaepFiltersToApiParams,
  ecaepFiltersToSearchParams,
  parseEcaepFilters,
} from "@/features/cms/ecaep-queue-filters";

describe("ecaep-queue-filters", () => {
  it("defaults to IN_REVIEW without Batch A / pilot gates", () => {
    expect(DEFAULT_ECAEP_FILTERS.status).toBe("IN_REVIEW");
    expect(DEFAULT_ECAEP_FILTERS.subjectName).toBe("");
    expect(DEFAULT_ECAEP_FILTERS.pilotOnly).toBe(false);
    expect(DEFAULT_ECAEP_FILTERS.batchAOnly).toBe(false);
  });

  it("parses Zoology + IN_REVIEW from URL", () => {
    const f = parseEcaepFilters(
      new URLSearchParams("subject_name=Zoology&status=IN_REVIEW"),
    );
    expect(f.subjectName).toBe("Zoology");
    expect(f.status).toBe("IN_REVIEW");
    expect(ecaepFilterSummary(f)).toBe("Zoology · IN_REVIEW");
  });

  it("maps filters to API params including subject_name", () => {
    const api = ecaepFiltersToApiParams(
      {
        ...DEFAULT_ECAEP_FILTERS,
        subjectName: "Zoology",
        status: "IN_REVIEW",
        page: 1,
      },
      20,
    );
    expect(api).toMatchObject({
      status: "IN_REVIEW",
      subject_name: "Zoology",
      limit: 20,
      offset: 20,
    });
    expect(api.batch_tag).toBeUndefined();
    expect(api.pilot_only).toBeUndefined();
  });

  it("sets batch_tag when Batch A only is enabled", () => {
    const api = ecaepFiltersToApiParams(
      { ...DEFAULT_ECAEP_FILTERS, batchAOnly: true },
      20,
    );
    expect(api.batch_tag).toBe(BATCH_A_TAG);
  });

  it("serializes URL state and round-trips", () => {
    const original = {
      ...DEFAULT_ECAEP_FILTERS,
      subjectName: "Chemistry",
      status: "DRAFT",
      page: 2,
      pilotOnly: true,
    };
    const qs = ecaepFiltersToSearchParams(original);
    expect(qs.get("subject_name")).toBe("Chemistry");
    expect(qs.get("status")).toBe("DRAFT");
    expect(qs.get("page")).toBe("3");
    expect(qs.get("pilot")).toBe("1");
    expect(parseEcaepFilters(qs)).toEqual(original);
  });

  it("falls back safely on invalid status", () => {
    const f = parseEcaepFilters(new URLSearchParams("status=NOT_A_STATE"));
    expect(f.status).toBe("IN_REVIEW");
  });

  it("reset target equals defaults", () => {
    expect(ecaepFilterSummary(DEFAULT_ECAEP_FILTERS)).toBe("All subjects · IN_REVIEW");
  });
});
