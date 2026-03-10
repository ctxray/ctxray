"""Pipeline orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reprompt.adapters.claude_code import ClaudeCodeAdapter
from reprompt.adapters.openclaw import OpenClawAdapter
from reprompt.config import Settings
from reprompt.core.analyzer import compute_tfidf_stats
from reprompt.core.dedup import DedupEngine
from reprompt.core.library import categorize_prompt, extract_patterns
from reprompt.core.models import Prompt
from reprompt.storage.db import PromptDB


@dataclass
class ScanResult:
    total_parsed: int = 0
    unique_after_dedup: int = 0
    duplicates: int = 0
    new_stored: int = 0
    sessions_scanned: int = 0
    sources: list[str] = field(default_factory=list)


def get_adapters() -> list:
    """Return all available adapters."""
    return [ClaudeCodeAdapter(), OpenClawAdapter()]


def run_scan(
    source: str | None = None,
    path: str | None = None,
    settings: Settings | None = None,
) -> ScanResult:
    """Full scan pipeline: discover -> parse -> dedup -> store."""
    if settings is None:
        settings = Settings()

    db = PromptDB(settings.db_path)
    result = ScanResult()

    # Get adapters
    adapters = get_adapters()
    if source:
        adapters = [a for a in adapters if a.name == source]

    all_prompts: list[Prompt] = []

    for adapter in adapters:
        # Determine scan root
        if path:
            scan_root = Path(path)
        else:
            scan_root = Path(adapter.default_session_path).expanduser()

        if not scan_root.exists():
            continue

        result.sources.append(adapter.name)

        # Find all .jsonl files
        for jsonl_file in sorted(scan_root.rglob("*.jsonl")):
            if db.is_session_processed(str(jsonl_file)):
                continue
            prompts = adapter.parse_session(jsonl_file)
            all_prompts.extend(prompts)
            result.sessions_scanned += 1
            db.mark_session_processed(str(jsonl_file), source=adapter.name)

    result.total_parsed = len(all_prompts)

    if not all_prompts:
        return result

    # Dedup
    engine = DedupEngine(backend=settings.embedding_backend, threshold=settings.dedup_threshold)
    unique, dupes = engine.deduplicate(all_prompts)
    result.unique_after_dedup = len(unique)
    result.duplicates = len(dupes)

    # Store
    for p in unique:
        if db.insert_prompt(
            p.text,
            source=p.source,
            project=p.project or "",
            session_id=p.session_id,
            timestamp=p.timestamp,
        ):
            result.new_stored += 1

    return result


def build_report_data(settings: Settings | None = None) -> dict:
    """Build report data from stored prompts."""
    if settings is None:
        settings = Settings()

    db = PromptDB(settings.db_path)
    stats = db.get_stats()
    all_prompts = db.get_all_prompts()

    texts = [p["text"] for p in all_prompts if p.get("duplicate_of") is None]

    # TF-IDF analysis
    top_terms = compute_tfidf_stats(texts, top_n=20) if texts else []

    # Store term stats
    for t in top_terms:
        db.upsert_term_stats(t["term"], t["count"], t["df"], t["tfidf_avg"])

    # Extract patterns
    patterns = extract_patterns(texts, min_frequency=settings.library_min_frequency)

    # Store patterns
    for p in patterns:
        db.insert_pattern(
            pattern_text=p["pattern_text"],
            frequency=p["frequency"],
            avg_length=p["avg_length"],
            projects=[],
            category=p["category"],
            first_seen="",
            last_seen="",
            examples=p.get("examples", []),
        )

    # Build project distribution
    projects: dict[str, int] = {}
    for p in all_prompts:
        proj = p.get("project", "unknown") or "unknown"
        projects[proj] = projects.get(proj, 0) + 1

    # Build category distribution
    categories: dict[str, int] = {}
    for t in texts:
        cat = categorize_prompt(t)
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "overview": {
            "total_prompts": stats.get("total_prompts", len(all_prompts)),
            "unique_prompts": len(texts),
            "sessions_scanned": stats.get("sessions_processed", 0),
            "sources": list({p.get("source", "") for p in all_prompts}),
            "date_range": (stats.get("earliest", ""), stats.get("latest", "")),
        },
        "top_patterns": [
            {
                "pattern_text": p["pattern_text"],
                "frequency": p["frequency"],
                "category": p["category"],
            }
            for p in patterns[:10]
        ],
        "projects": projects,
        "categories": categories,
        "top_terms": top_terms[:10],
    }
