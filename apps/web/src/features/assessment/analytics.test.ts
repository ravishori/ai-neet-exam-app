import { describe, expect, it } from "vitest";

import { computeScoreTrend, computeTimeStats, computeTopicBreakdown, formatDuration } from "@/features/assessment/analytics";
import type { AttemptQuestion } from "@/features/assessment/api";
import type { AttemptSummary } from "@/features/assessment/api";

function question(overrides: Partial<AttemptQuestion>): AttemptQuestion {
  return {
    question_type: "MCQ",
    concept: { id: "concept-1", name: "Concept" },
    topic: { id: "topic-1", name: "Mechanics" },
    chapter: { id: "chapter-1", name: "Chapter" },
    subject: { id: "subject-1", name: "Physics" },
    ncert_reference: null,
    images: [],
    bookmarked: false,
    content_item_id: "item-1",
    stem: "Stem",
    options: [],
    pyq_year: null,
    selected_option: "A",
    confidence: null,
    marked_for_review: false,
    is_correct: true,
    time_spent_seconds: 30,
    ...overrides,
  };
}

describe("computeTopicBreakdown", () => {
  it("groups by topic and computes accuracy over attempted questions only", () => {
    const questions = [
      question({ topic: { id: "t1", name: "Mechanics" }, is_correct: true, time_spent_seconds: 20 }),
      question({ topic: { id: "t1", name: "Mechanics" }, is_correct: false, time_spent_seconds: 40 }),
      question({ topic: { id: "t2", name: "Optics" }, is_correct: true, time_spent_seconds: 10 }),
    ];

    const result = computeTopicBreakdown(questions);

    expect(result).toHaveLength(2);
    const mechanics = result.find((t) => t.topicId === "t1")!;
    expect(mechanics).toMatchObject({ correct: 1, total: 2, accuracyPct: 50, avgTimeSeconds: 30 });
    const optics = result.find((t) => t.topicId === "t2")!;
    expect(optics).toMatchObject({ correct: 1, total: 1, accuracyPct: 100, avgTimeSeconds: 10 });
  });

  it("sorts weakest topic first", () => {
    const questions = [
      question({ topic: { id: "strong", name: "Strong" }, is_correct: true }),
      question({ topic: { id: "weak", name: "Weak" }, is_correct: false }),
    ];

    const result = computeTopicBreakdown(questions);

    expect(result.map((t) => t.topicId)).toEqual(["weak", "strong"]);
  });

  it("excludes skipped questions (is_correct null) from the denominator", () => {
    const questions = [
      question({ topic: { id: "t1", name: "Mechanics" }, is_correct: true }),
      question({ topic: { id: "t1", name: "Mechanics" }, is_correct: null, selected_option: null }),
    ];

    const result = computeTopicBreakdown(questions);

    expect(result).toEqual([expect.objectContaining({ topicId: "t1", correct: 1, total: 1, accuracyPct: 100 })]);
  });

  it("excludes questions with no linked topic", () => {
    const questions = [question({ topic: null })];

    expect(computeTopicBreakdown(questions)).toEqual([]);
  });

  it("returns an empty array when nothing was answered", () => {
    expect(computeTopicBreakdown([])).toEqual([]);
  });
});

describe("computeTimeStats", () => {
  it("averages only over questions with a positive time spent", () => {
    const questions = [
      question({ time_spent_seconds: 30 }),
      question({ time_spent_seconds: 10 }),
      question({ time_spent_seconds: null }),
      question({ time_spent_seconds: 0 }),
    ];

    expect(computeTimeStats(questions)).toEqual({ avgSeconds: 20, totalSeconds: 40, answeredCount: 2 });
  });

  it("returns a null average with no timed questions", () => {
    expect(computeTimeStats([question({ time_spent_seconds: null })])).toEqual({
      avgSeconds: null,
      totalSeconds: 0,
      answeredCount: 0,
    });
  });
});

describe("formatDuration", () => {
  it("formats sub-minute durations as seconds", () => {
    expect(formatDuration(45)).toBe("45s");
  });

  it("formats exact minutes without a seconds remainder", () => {
    expect(formatDuration(120)).toBe("2m");
  });

  it("formats minutes with a seconds remainder", () => {
    expect(formatDuration(150)).toBe("2m 30s");
  });
});

function attempt(overrides: Partial<AttemptSummary>): AttemptSummary {
  return {
    id: "attempt-1",
    assessment_id: "assessment-1",
    status: "SUBMITTED",
    started_at: "2026-01-01T00:00:00Z",
    submitted_at: "2026-01-01T00:10:00Z",
    score: 80,
    correct_count: 8,
    incorrect_count: 2,
    skipped_count: 0,
    ...overrides,
  };
}

describe("computeScoreTrend", () => {
  it("computes accuracy from correct/incorrect_count, not the raw score field", () => {
    // score is marks (varies by marks_per_question/negative marking across
    // assessments), not a 0-100 value — the trend must not plot it directly.
    const attempts = [
      attempt({ id: "a3", submitted_at: "2026-01-03T00:00:00Z", score: 999, correct_count: 7, incorrect_count: 3 }),
      attempt({ id: "a1", submitted_at: "2026-01-01T00:00:00Z", score: -5, correct_count: 5, incorrect_count: 5 }),
      attempt({ id: "a2", status: "IN_PROGRESS", submitted_at: null, correct_count: null, incorrect_count: null }),
    ];

    const result = computeScoreTrend(attempts);

    expect(result.map((p) => p.attemptId)).toEqual(["a1", "a3"]);
    expect(result.map((p) => p.score)).toEqual([50, 70]);
  });

  it("excludes an attempt where nothing was attempted (all skipped)", () => {
    const attempts = [attempt({ correct_count: 0, incorrect_count: 0, skipped_count: 10 })];

    expect(computeScoreTrend(attempts)).toEqual([]);
  });

  it("caps to the most recent `limit` attempts", () => {
    const attempts = Array.from({ length: 15 }, (_, i) =>
      attempt({ id: `a${i}`, submitted_at: `2026-01-${String(i + 1).padStart(2, "0")}T00:00:00Z`, correct_count: i, incorrect_count: 1 })
    );

    const result = computeScoreTrend(attempts, 5);

    expect(result).toHaveLength(5);
    expect(result.map((p) => p.attemptId)).toEqual(["a10", "a11", "a12", "a13", "a14"]);
  });
});
