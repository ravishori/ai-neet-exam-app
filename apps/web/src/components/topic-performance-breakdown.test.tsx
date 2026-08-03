import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TopicPerformanceBreakdown } from "@/components/topic-performance-breakdown";
import type { AttemptQuestion } from "@/features/assessment/api";

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

describe("TopicPerformanceBreakdown", () => {
  it("renders a row per topic with accuracy and time", () => {
    render(
      <TopicPerformanceBreakdown
        questions={[
          question({ topic: { id: "t1", name: "Mechanics" }, is_correct: true, time_spent_seconds: 20 }),
          question({ topic: { id: "t2", name: "Optics" }, is_correct: false, time_spent_seconds: 10 }),
        ]}
      />
    );

    expect(screen.getByText("Mechanics")).toBeInTheDocument();
    expect(screen.getByText("Optics")).toBeInTheDocument();
    expect(screen.getByText(/Avg time per question/)).toBeInTheDocument();
  });

  it("shows a fallback message when nothing has been graded", () => {
    render(<TopicPerformanceBreakdown questions={[]} />);

    expect(screen.getByText(/No graded questions/)).toBeInTheDocument();
  });
});
