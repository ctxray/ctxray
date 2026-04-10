"""Aggregate E9 specificity-gradient results across baseline + contributed runs.

Reads:
  - .output/experiments/e9_specificity_*.json    baseline multi-model runs
  - experiments/contributed/*.json               contributed single-model runs

Emits a markdown cross-model comparison table to stdout (optionally clipboard).

Usage:
    uv run python experiments/aggregate.py
    uv run python experiments/aggregate.py --copy      # also copy to clipboard
    uv run python experiments/aggregate.py --json      # emit JSON instead
    uv run python experiments/aggregate.py --contributed-only  # skip baseline
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = ROOT / ".output" / "experiments"
CONTRIBUTED_DIR = ROOT / "experiments" / "contributed"

LEVELS = ["vague", "task_only", "task_io", "full_spec"]


def _load_e9_files(include_baseline: bool) -> list[tuple[str, Path]]:
    """Return [(source_label, path), ...] for all E9 specificity files found."""
    files: list[tuple[str, Path]] = []
    if include_baseline and BASELINE_DIR.exists():
        # Match both e9_specificity.json (original small-set) and
        # e9_specificity_<suffix>.json (midrange/frontier/etc.).
        for p in sorted(BASELINE_DIR.glob("e9_specificity*.json")):
            # _custom_ files are contributor runs written by the maintainer's
            # own machine — they belong to the contributed set, not baseline.
            if "_custom_" in p.name:
                continue
            files.append(("baseline", p))
    if CONTRIBUTED_DIR.exists():
        for p in sorted(CONTRIBUTED_DIR.glob("*.json")):
            files.append(("contributed", p))
    return files


def _extract_rows(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        print(f"  WARN: failed to load {path.name}: {e}", file=sys.stderr)
        return []
    if data.get("experiment") != "e9_specificity":
        return []
    return data.get("results", [])


def aggregate(include_baseline: bool = True) -> dict[str, dict]:
    """Build {model_name: {levels, source, total_calls}}.

    Multiple measurements for the same (model, level) are averaged. Source is
    'contributed' if the model appears in any contributed file, else 'baseline'.
    """
    per_model: dict[str, dict] = defaultdict(
        lambda: {
            "rates_by_level": defaultdict(list),
            "sources": set(),
            "calls": 0,
        }
    )

    for source, path in _load_e9_files(include_baseline):
        rows = _extract_rows(path)
        for row in rows:
            name = row.get("model_name")
            # Fall back to internal key only if model_name is missing and the
            # key is clearly not a placeholder.
            if not name:
                key = row.get("model")
                if not key or key == "custom":
                    continue
                name = key

            level = row.get("level")
            rate = row.get("avg_pass_rate")
            if level not in LEVELS or rate is None:
                continue

            per_model[name]["rates_by_level"][level].append(float(rate))
            per_model[name]["sources"].add(source)
            per_model[name]["calls"] += len(row.get("pass_rates") or [])

    flat: dict[str, dict] = {}
    for name, entry in per_model.items():
        level_means = {
            level: mean(entry["rates_by_level"][level])
            for level in LEVELS
            if entry["rates_by_level"][level]
        }
        sources = entry["sources"]
        if sources == {"baseline"}:
            source_label = "baseline"
        elif sources == {"contributed"}:
            source_label = "contributed"
        else:
            source_label = "merged"
        flat[name] = {
            "levels": level_means,
            "source": source_label,
            "total_calls": entry["calls"],
        }
    return flat


def to_markdown(agg: dict[str, dict]) -> str:
    if not agg:
        return "(no E9 data found — run experiments/validate.py e9 first)"

    def sort_key(item: tuple[str, dict]) -> tuple[int, str]:
        name, data = item
        source_rank = {"baseline": 0, "merged": 1, "contributed": 2}[data["source"]]
        return (source_rank, name.lower())

    lines: list[str] = []
    lines.append("## E9 Specificity Gradient — Cross-Model Results")
    lines.append("")
    lines.append(
        "| Model | vague | task_only | task_io | full_spec | Δ (vague→full) | Source |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---|")

    total_calls = 0
    for name, data in sorted(agg.items(), key=sort_key):
        levels = data["levels"]
        cells: list[str] = [f"`{name}`"]
        for level in LEVELS:
            val = levels.get(level)
            cells.append(f"{val:.2f}" if val is not None else "—")
        vague = levels.get("vague")
        full = levels.get("full_spec")
        if vague is not None and full is not None:
            cells.append(f"{full - vague:+.2f}")
        else:
            cells.append("—")
        cells.append(data["source"])
        lines.append("| " + " | ".join(cells) + " |")
        total_calls += data["total_calls"]

    baseline_n = sum(1 for d in agg.values() if d["source"] == "baseline")
    contributed_n = sum(1 for d in agg.values() if d["source"] == "contributed")
    merged_n = sum(1 for d in agg.values() if d["source"] == "merged")

    count_parts = [f"{baseline_n} baseline"]
    if merged_n:
        count_parts.append(f"{merged_n} merged")
    count_parts.append(f"{contributed_n} contributed")

    noun = "model" if len(agg) == 1 else "models"
    lines.append("")
    lines.append(
        f"**{len(agg)} {noun}** ({', '.join(count_parts)}), "
        f"**~{total_calls} Ollama calls total**."
    )

    # Headline findings
    highlights = _find_highlights(agg)
    if highlights:
        lines.append("")
        lines.append("**Highlights:**")
        for h in highlights:
            lines.append(f"- {h}")

    return "\n".join(lines)


def _find_highlights(agg: dict[str, dict]) -> list[str]:
    """Surface the most interesting findings across the aggregated data."""
    highlights: list[str] = []

    # Biggest specificity gain
    gains: list[tuple[str, float]] = []
    for name, data in agg.items():
        levels = data["levels"]
        vague = levels.get("vague")
        full = levels.get("full_spec")
        if vague is not None and full is not None:
            gains.append((name, full - vague))
    if gains:
        best = max(gains, key=lambda t: t[1])
        highlights.append(
            f"Biggest specificity gain: `{best[0]}` ({best[1]:+.2f} vague→full_spec)"
        )

    # U-curves: full_spec below task_io
    u_curves: list[tuple[str, float]] = []
    for name, data in agg.items():
        levels = data["levels"]
        task_io = levels.get("task_io")
        full = levels.get("full_spec")
        if task_io is not None and full is not None and full < task_io - 0.05:
            u_curves.append((name, task_io - full))
    if u_curves:
        u_curves.sort(key=lambda t: -t[1])
        names = ", ".join(f"`{n}` (-{d:.2f})" for n, d in u_curves[:3])
        highlights.append(
            f"Specificity **hurts** these models at full_spec (U-curve): {names}"
        )

    # Best raw pass rate at full_spec
    full_rates: list[tuple[str, float]] = [
        (name, data["levels"]["full_spec"])
        for name, data in agg.items()
        if "full_spec" in data["levels"]
    ]
    if full_rates:
        best = max(full_rates, key=lambda t: t[1])
        highlights.append(
            f"Highest full_spec pass rate: `{best[0]}` ({best[1]:.2f})"
        )

    return highlights


def main() -> None:
    args = sys.argv[1:]
    emit_json = "--json" in args
    copy_clip = "--copy" in args
    contributed_only = "--contributed-only" in args

    agg = aggregate(include_baseline=not contributed_only)

    if emit_json:
        output = json.dumps(agg, indent=2, ensure_ascii=False)
    else:
        output = to_markdown(agg)

    print(output)

    if copy_clip:
        try:
            subprocess.run(["pbcopy"], input=output.encode(), check=True)
            print("\n(copied to clipboard)", file=sys.stderr)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("\n(pbcopy unavailable — clipboard skipped)", file=sys.stderr)


if __name__ == "__main__":
    main()
