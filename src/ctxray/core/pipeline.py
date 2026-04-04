"""Pipeline orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ctxray.adapters.aider import AiderAdapter
from ctxray.adapters.chatgpt import ChatGPTAdapter
from ctxray.adapters.claude_chat import ClaudeChatAdapter
from ctxray.adapters.claude_code import ClaudeCodeAdapter
from ctxray.adapters.cline import ClineAdapter
from ctxray.adapters.codex import CodexAdapter
from ctxray.adapters.cursor import CursorAdapter
from ctxray.adapters.gemini import GeminiAdapter
from ctxray.adapters.openclaw import OpenClawAdapter
from ctxray.config import Settings
from ctxray.core.analyzer import cluster_prompts, compute_tfidf_stats
from ctxray.core.dedup import DedupEngine
from ctxray.core.library import categorize_prompt, extract_patterns
from ctxray.core.models import Prompt
from ctxray.core.privacy import compute_privacy_summary
from ctxray.storage.db import PromptDB

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    total_parsed: int = 0
    unique_after_dedup: int = 0
    duplicates: int = 0
    new_stored: int = 0
    sessions_scanned: int = 0
    sources: list[str] = field(default_factory=list)


def get_adapters() -> list[
    ClaudeCodeAdapter
    | OpenClawAdapter
    | CursorAdapter
    | AiderAdapter
    | GeminiAdapter
    | ClineAdapter
    | CodexAdapter
    | ChatGPTAdapter
    | ClaudeChatAdapter
]:
    """Return all available adapters."""
    return [
        ClaudeCodeAdapter(),
        OpenClawAdapter(),
        CursorAdapter(),
        AiderAdapter(),
        GeminiAdapter(),
        ClineAdapter(),
        CodexAdapter(),
        ChatGPTAdapter(),
        ClaudeChatAdapter(),
    ]


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
    scanned_files: list[tuple[str, str]] = []  # (file_path, adapter_name)

    for adapter in adapters:
        # Determine scan root
        if path:
            scan_root = Path(path)
        else:
            scan_root = Path(adapter.default_session_path).expanduser()

        if not scan_root.exists():
            continue

        result.sources.append(adapter.name)

        # Find session files — use adapter's discover method if available,
        # otherwise fall back to extension-based glob.
        if hasattr(adapter, "discover_sessions"):
            session_files = adapter.discover_sessions()
        else:
            ext = "*.vscdb" if adapter.name == "cursor" else "*.jsonl"
            session_files = sorted(scan_root.rglob(ext))
        for session_file in session_files:
            if db.is_session_processed(str(session_file)):
                continue
            prompts = adapter.parse_session(session_file)
            all_prompts.extend(prompts)
            result.sessions_scanned += 1
            scanned_files.append((str(session_file), adapter.name))

    result.total_parsed = len(all_prompts)

    if not all_prompts:
        return result

    # Dedup
    engine = DedupEngine(
        backend=settings.embedding_backend,
        threshold=settings.dedup_threshold,
        ollama_url=settings.ollama_url,
    )
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

    # Compute PromptDNA features for new prompts
    from ctxray.core.extractors import extract_features
    from ctxray.core.scorer import score_prompt

    for p in unique:
        try:
            dna = extract_features(
                p.text,
                source=p.source,
                session_id=p.session_id,
                project=p.project,
            )
            breakdown = score_prompt(dna)
            dna.overall_score = breakdown.total
            db.store_features(dna.prompt_hash, dna.to_dict())
        except Exception:
            logger.debug(
                "PromptDNA extraction failed for prompt %s: %s", p.text[:40], exc_info=True
            )

    # Extract session metadata and compute effectiveness scores
    for file_path, adapter_name in scanned_files:
        matched = next((a for a in adapters if a.name == adapter_name), None)
        if matched and hasattr(matched, "parse_session_meta"):
            try:
                meta = matched.parse_session_meta(Path(file_path))
                if meta:
                    from ctxray.core.effectiveness import compute_effectiveness
                    from ctxray.core.trends import _norm

                    specificity = _norm(meta.avg_prompt_length, 50, 500)
                    score = compute_effectiveness(meta, prompt_specificity=specificity)
                    db.upsert_session_meta(
                        session_id=meta.session_id,
                        source=meta.source,
                        project=meta.project,
                        start_time=meta.start_time,
                        end_time=meta.end_time,
                        duration_seconds=meta.duration_seconds,
                        prompt_count=meta.prompt_count,
                        tool_call_count=meta.tool_call_count,
                        error_count=meta.error_count,
                        final_status=meta.final_status,
                        avg_prompt_length=meta.avg_prompt_length,
                        effectiveness_score=score,
                    )
                    db.update_prompt_effectiveness(meta.session_id, score)
            except Exception:
                logger.debug("Session metadata extraction failed for %s", file_path, exc_info=True)

    # Compute session quality scores
    from datetime import datetime

    from ctxray.core.agent import analyze_session
    from ctxray.core.conversation import Conversation
    from ctxray.core.distill import distill_conversation
    from ctxray.core.session_quality import score_session

    quality_failures = 0
    for file_path, adapter_name in scanned_files:
        try:
            matched = next((a for a in adapters if a.name == adapter_name), None)
            if not matched:
                continue

            # parse_conversation returns list[ConversationTurn], wrap into Conversation
            turns = matched.parse_conversation(Path(file_path))
            if not turns:
                continue

            session_id = Path(file_path).stem
            start_time = None
            end_time = None
            duration = None
            timestamps = [t.timestamp for t in turns if t.timestamp]
            if len(timestamps) >= 2:
                start_time = timestamps[0]
                end_time = timestamps[-1]
                try:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    duration = int((end_dt - start_dt).total_seconds())
                except (ValueError, TypeError):
                    pass

            project = None
            if hasattr(matched, "_project_from_path"):
                project = matched._project_from_path(file_path)

            conversation = Conversation(
                session_id=session_id,
                source=adapter_name,
                project=project,
                turns=turns,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
            )

            # Agent analysis (efficiency, error loops)
            agent_report = None
            try:
                agent_report = analyze_session(conversation)
            except Exception:
                logger.warning("Agent analysis failed for %s", file_path, exc_info=True)

            # Distill analysis (focus/retention)
            distill_result = None
            try:
                distill_result = distill_conversation(conversation)
            except Exception:
                logger.warning("Distill analysis failed for %s", file_path, exc_info=True)

            # Avg prompt score from stored features
            avg_prompt_score = None
            scores = db.get_prompt_scores_for_session(session_id)
            if scores:
                avg_prompt_score = sum(scores) / len(scores)

            # Effectiveness score from session_meta
            effectiveness = db.get_effectiveness_for_session(session_id)

            quality = score_session(
                conversation,
                agent_report=agent_report,
                distill_result=distill_result,
                effectiveness_score=effectiveness,
                avg_prompt_score=avg_prompt_score,
            )
            db.upsert_session_quality(
                session_id=quality.session_id,
                quality_score=quality.quality_score,
                prompt_quality_score=quality.prompt_quality,
                efficiency_score=quality.efficiency,
                focus_score=quality.focus,
                outcome_score=quality.outcome,
                has_abandonment=quality.frustration.abandonment,
                has_escalation=quality.frustration.escalation,
                stall_turns=quality.frustration.stall_turns,
                session_type=quality.session_type,
                quality_insight=quality.insight,
            )
        except Exception:
            quality_failures += 1
            logger.warning("Session quality scoring failed for %s", file_path, exc_info=True)

    if quality_failures:
        logger.warning("Quality scoring failed for %d session(s)", quality_failures)

    # Mark sessions processed only after successful dedup+store
    for file_path, adapter_name in scanned_files:
        db.mark_session_processed(file_path, source=adapter_name)

    return result


def build_report_data(
    settings: Settings | None = None,
    n_clusters: int | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Build report data from stored prompts, optionally filtered by source."""
    if settings is None:
        settings = Settings()

    db = PromptDB(settings.db_path)
    stats = db.get_stats()
    all_prompts = db.get_all_prompts(source=source)

    texts = [p["text"] for p in all_prompts if p.get("duplicate_of") is None]

    # TF-IDF analysis
    top_terms = compute_tfidf_stats(texts, top_n=20) if texts else []

    # Store term stats
    for t in top_terms:
        db.upsert_term_stats(t["term"], t["count"], t["df"], t["tfidf_avg"])

    # Extract patterns
    patterns = extract_patterns(texts, min_frequency=settings.library_min_frequency)

    # Upsert patterns — keeps IDs stable across repeated report runs
    for p in patterns:
        db.upsert_pattern(
            pattern_text=p["pattern_text"],
            frequency=p["frequency"],
            avg_length=p["avg_length"],
            projects=[],
            category=p["category"],
            first_seen="",
            last_seen="",
            examples=p.get("examples", []),
        )
    db.compute_pattern_effectiveness()

    # K-means clustering (only if enough texts)
    clusters_summary: list[dict[str, Any]] = []
    if len(texts) >= 5:
        raw_clusters = cluster_prompts(texts, n_clusters=n_clusters)
        for cid, members in sorted(raw_clusters.items()):
            clusters_summary.append(
                {
                    "cluster_id": cid,
                    "size": len(members),
                    "sample": members[0][:80] if members else "",
                }
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

    # Privacy exposure breakdown
    source_counts: dict[str, int] = {}
    for p in all_prompts:
        src = p.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    privacy = compute_privacy_summary(source_counts)

    # Compute avg compressibility from stored features
    all_features = db.get_all_features()
    avg_compressibility = 0.0
    if all_features:
        compress_vals = [f.get("compressibility", 0.0) for f in all_features]
        avg_compressibility = sum(compress_vals) / len(compress_vals) if compress_vals else 0.0

    # Compute total token cost
    from collections import defaultdict

    from ctxray.core.cost import estimate_cost, format_cost

    by_source_tokens: dict[str, int] = defaultdict(int)
    for f in all_features:
        src = f.get("source", "manual")
        by_source_tokens[src] += f.get("token_count", 0)
    total_cost = sum(estimate_cost(t, src) for src, t in by_source_tokens.items())

    return {
        "overview": {
            "total_prompts": stats.get("total_prompts", len(all_prompts)),
            "unique_prompts": len(texts),
            "sessions_scanned": stats.get("sessions_processed", 0),
            "sources": list({p.get("source", "") for p in all_prompts}),
            "date_range": (stats.get("earliest", ""), stats.get("latest", "")),
            "avg_compressibility": round(avg_compressibility, 3),
            "estimated_cost_display": format_cost(total_cost) if total_cost > 0 else None,
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
        "clusters": clusters_summary,
        "privacy": privacy,
    }
