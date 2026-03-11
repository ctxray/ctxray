"""Prompt recommendations based on history and effectiveness."""

from __future__ import annotations

from typing import Any

from reprompt.core.library import categorize_prompt
from reprompt.storage.db import PromptDB

# Templates for upgrading vague prompts to specific ones.
SPECIFICITY_UPGRADES: dict[str, str] = {
    "fix": (
        "Be specific: name the file, function, and error. "
        'e.g. "Fix the TypeError in auth/login.py:validate_token '
        "when token is expired\""
    ),
    "debug": (
        "Include the error message and where it occurs. "
        'e.g. "Debug the ConnectionRefusedError in db.py:get_connection '
        "— happens after 5 min idle\""
    ),
    "test": (
        "Specify what behavior to test and edge cases. "
        'e.g. "Add tests for UserService.create_user — cover duplicate email, '
        "missing fields, and valid creation\""
    ),
    "refactor": (
        "Name the target pattern and why. "
        'e.g. "Refactor PaymentService to use strategy pattern '
        "— currently has 6 if/elif branches for payment types\""
    ),
    "implement": (
        "Describe the interface, inputs, outputs, and constraints. "
        'e.g. "Add POST /api/users endpoint — accepts {name, email}, '
        "returns 201 with user object, 409 if email exists\""
    ),
}


def compute_recommendations(db: PromptDB) -> dict[str, Any]:
    """Analyze prompt history and generate actionable recommendations.

    Returns a dict with:
      - best_prompts: high-effectiveness prompts worth reusing
      - short_prompt_alerts: vague prompts correlated with low effectiveness
      - category_tips: advice based on category distribution
      - specificity_tips: upgrade suggestions for common vague patterns
      - overall_tips: general advice based on aggregate stats
    """
    conn = db._conn()
    try:
        # 1. Best prompts: unique prompts from high-effectiveness sessions
        best_rows = conn.execute(
            """SELECT p.text, p.char_count, s.effectiveness_score, s.project
               FROM prompts p
               JOIN session_meta s ON p.session_id = s.session_id
               WHERE p.duplicate_of IS NULL
                 AND s.effectiveness_score >= 0.6
               ORDER BY s.effectiveness_score DESC, p.char_count DESC
               LIMIT 10""",
        ).fetchall()
        best_prompts = [
            {
                "text": r["text"],
                "char_count": r["char_count"],
                "effectiveness": round(r["effectiveness_score"], 2),
                "project": r["project"],
            }
            for r in best_rows
        ]

        # 2. Short prompt alerts: short prompts in low-effectiveness sessions
        short_rows = conn.execute(
            """SELECT p.text, p.char_count, s.effectiveness_score, s.project
               FROM prompts p
               JOIN session_meta s ON p.session_id = s.session_id
               WHERE p.duplicate_of IS NULL
                 AND p.char_count < 40
                 AND s.effectiveness_score < 0.4
               ORDER BY s.effectiveness_score ASC
               LIMIT 5""",
        ).fetchall()
        short_prompt_alerts = [
            {
                "text": r["text"],
                "char_count": r["char_count"],
                "effectiveness": round(r["effectiveness_score"], 2),
                "category": categorize_prompt(r["text"]),
            }
            for r in short_rows
        ]

        # 3. Category distribution for tips
        cat_rows = conn.execute(
            """SELECT p.text
               FROM prompts p
               WHERE p.duplicate_of IS NULL"""
        ).fetchall()
        category_counts: dict[str, int] = {}
        for r in cat_rows:
            cat = categorize_prompt(r["text"])
            category_counts[cat] = category_counts.get(cat, 0) + 1
        total_prompts = sum(category_counts.values())

        # 4. Category-based tips
        category_tips: list[str] = []
        if total_prompts > 0:
            debug_pct = category_counts.get("debug", 0) / total_prompts
            test_pct = category_counts.get("test", 0) / total_prompts
            review_pct = category_counts.get("review", 0) / total_prompts

            if debug_pct > 0.3:
                category_tips.append(
                    f"Debug prompts are {debug_pct:.0%} of your total. "
                    "Consider writing more specific initial prompts to "
                    "reduce debugging cycles."
                )
            if test_pct < 0.05 and total_prompts > 20:
                category_tips.append(
                    "Very few test prompts detected. Adding test prompts "
                    "early in sessions can reduce later debugging."
                )
            if review_pct < 0.03 and total_prompts > 20:
                category_tips.append(
                    "Almost no review prompts. Asking for code review "
                    "before committing can catch issues earlier."
                )

        # 5. Specificity tips: find common short patterns
        specificity_tips: list[dict[str, str]] = []
        for alert in short_prompt_alerts:
            cat = alert["category"]
            if cat in SPECIFICITY_UPGRADES:
                specificity_tips.append(
                    {"original": alert["text"], "tip": SPECIFICITY_UPGRADES[cat]}
                )

        # 6. Avg effectiveness by category
        cat_eff_rows = conn.execute(
            """SELECT p.text, s.effectiveness_score
               FROM prompts p
               JOIN session_meta s ON p.session_id = s.session_id
               WHERE p.duplicate_of IS NULL
                 AND s.effectiveness_score IS NOT NULL"""
        ).fetchall()
        cat_eff: dict[str, list[float]] = {}
        for r in cat_eff_rows:
            cat = categorize_prompt(r["text"])
            cat_eff.setdefault(cat, []).append(r["effectiveness_score"])
        category_effectiveness = {
            cat: round(sum(scores) / len(scores), 2)
            for cat, scores in cat_eff.items()
            if scores
        }

        # 7. Overall tips
        overall_tips: list[str] = []
        eff_summary = db.get_effectiveness_summary()
        avg_score = eff_summary.get("avg_score") or 0

        if avg_score > 0 and avg_score < 0.35:
            overall_tips.append(
                "Your average session effectiveness is low. "
                "Try starting sessions with a clear goal and specific prompts."
            )

        # Check avg prompt length
        len_row = conn.execute(
            "SELECT AVG(char_count) FROM prompts WHERE duplicate_of IS NULL"
        ).fetchone()
        avg_len = len_row[0] if len_row and len_row[0] else 0
        if avg_len < 30:
            overall_tips.append(
                f"Your average prompt is only {avg_len:.0f} characters. "
                "Longer, more descriptive prompts tend to produce better results."
            )

    finally:
        conn.close()

    return {
        "best_prompts": best_prompts,
        "short_prompt_alerts": short_prompt_alerts,
        "category_tips": category_tips,
        "specificity_tips": specificity_tips,
        "category_effectiveness": category_effectiveness,
        "overall_tips": overall_tips,
        "total_prompts": total_prompts,
    }
