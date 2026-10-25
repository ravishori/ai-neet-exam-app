"""Deterministic, rule-based study plan — the baseline StudyPlannerService
always computes first, regardless of AI provider availability. AI
personalization (when enabled, available, and within its spend cap) is an
optional improvement over this, never a replacement path that the feature
depends on to function at all.

No network calls, no randomness, no external state — same inputs always
produce the same plan, which is exactly what makes it safe to serve as a
graceful fallback (Steps elsewhere in this codebase use a similarly named
"deterministic-first" principle, e.g. the OTP/rate-limit work's own
layered-defense style)."""

from __future__ import annotations

_WEEKDAY_FOCUS_TEMPLATE = [
    "Weak-concept deep dive",
    "Practice set - weak concepts",
    "Weak-concept deep dive (second pass)",
    "Mixed practice set",
    "Full-length mock test",
    "Mock-test review + error log",
    "Revision of strong areas",
]


def build_deterministic_plan(
    *,
    target_score: int,
    current_score: int,
    days_remaining: int,
    hours_per_day: int,
    weak_concepts: list[str],
) -> dict:
    """Pure function — no I/O. Produces the same {summary, weekly_focus,
    daily_schedule} shape the AI prompt also targets (see
    app.modules.ai.prompts.study_planner.SYSTEM_PROMPT), so a caller never
    needs to branch on which source produced the plan.

    ``days_remaining`` already has its own >=1 floor applied by the
    caller (StudyPlannerService); this function treats it as informational
    (how urgent the gap is) rather than the length of daily_schedule, which
    is always a representative 7-day week template — the existing
    frontend/schema render "Day 1..N", not calendar dates, and a plan
    spanning the student's full remaining timeline would just repeat this
    same weekly template anyway.
    """
    gap = max(0, target_score - current_score)
    top_weak = weak_concepts[:3]

    if top_weak:
        weekly_focus = [
            *[f"Strengthen: {name}" for name in top_weak],
            "Full-length mock test",
            "Revision of strong areas",
        ]
        weak_summary = ", ".join(top_weak)
    else:
        weekly_focus = [
            "Broad concept review across all three subjects",
            "Full-length mock test",
            "Error-log review from the mock test",
        ]
        weak_summary = "no weak-concept signal yet — this will sharpen once you attempt more questions"

    summary = (
        f"Deterministic plan: closing a {gap}-point gap ({current_score} -> {target_score}/720) "
        f"over {days_remaining} day(s) at {hours_per_day}h/day. Weak concepts: {weak_summary}."
    )

    daily_schedule = []
    for day in range(1, 8):
        template_focus = _WEEKDAY_FOCUS_TEMPLATE[(day - 1) % len(_WEEKDAY_FOCUS_TEMPLATE)]
        if top_weak and day <= 2:
            focus = f"{template_focus}: {top_weak[(day - 1) % len(top_weak)]}"
        else:
            focus = template_focus
        daily_schedule.append(
            {
                "day": day,
                "focus": focus,
                "duration_minutes": hours_per_day * 60,
            }
        )

    return {"summary": summary, "weekly_focus": weekly_focus, "daily_schedule": daily_schedule}
