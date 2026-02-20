"""Service for exercise-history guidance summaries."""

from typing import List


class HistoryGuidanceService:
    """Fetch logging context and summarize it in concise user-facing lines."""

    def __init__(self, agent):
        self.agent = agent

    def get_logging_context(self, exercise_name: str):
        return self.agent.prepare_exercise_logging(exercise_name)

    @staticmethod
    def to_concise_lines(context) -> List[str]:
        lines: List[str] = [f"Logging: {context.exercise_name}"]

        if context.is_new_exercise:
            lines.append("No history yet for this exercise.")
            return lines

        if context.last_weight is not None:
            days = (
                f"{context.days_since_last} days ago"
                if context.days_since_last is not None
                else "recently"
            )
            lines.append(f"Last logged top set: {context.last_weight}kg ({days}).")

        if context.max_weight is not None:
            lines.append(f"Max recorded weight: {context.max_weight}kg.")

        if context.suggested_weight is not None:
            lines.append(f"Suggested working weight today: {context.suggested_weight}kg.")

        if context.suggested_reps_range:
            lo, hi = context.suggested_reps_range
            lines.append(f"Typical rep range: {lo}-{hi} reps.")

        return lines

