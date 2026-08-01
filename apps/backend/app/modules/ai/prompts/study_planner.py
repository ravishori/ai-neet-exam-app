SYSTEM_PROMPT = """You are a NEET study planner. Given a student's target score, current \
score, days remaining, daily study hours, and weak concepts, produce a study plan as \
strict JSON, nothing else — no markdown fences, no commentary:
{"summary": str, "weekly_focus": [str, ...], "daily_schedule": [{"day": int, "focus": str, \
"duration_minutes": int}, ...]}
Prioritize weak concepts early, but include revision of strong areas too. Keep the plan \
realistic for the stated daily hours."""


def build_prompt(
    *,
    target_score: int,
    current_score: int,
    days_remaining: int,
    hours_per_day: int,
    weak_concepts: list[str],
) -> str:
    lines = [
        f"Target score: {target_score}/720",
        f"Current score: {current_score}/720",
        f"Days remaining until exam: {days_remaining}",
        f"Hours available per day: {hours_per_day}",
    ]
    if weak_concepts:
        lines.append("Weak concepts (from recent incorrect answers): " + ", ".join(weak_concepts))
    else:
        lines.append("No weak-concept signal yet — student hasn't attempted enough questions.")
    return "\n".join(lines)
