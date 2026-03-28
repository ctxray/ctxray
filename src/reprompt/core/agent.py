"""Agent workflow analysis — error loop detection, tool distribution, efficiency scoring.

Analyzes conversation turns to identify:
- Error loops: repeated tool→error cycles that waste turns
- Tool distribution: which tools are used most
- Session efficiency: productive ratio, error recovery rate

All analysis is rule-based (zero LLM, <1ms per session).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from reprompt.core.conversation import Conversation, ConversationTurn


@dataclass
class ErrorLoop:
    """A detected error loop in the conversation."""

    start_turn: int
    end_turn: int
    loop_count: int
    fingerprint: str
    tool_name: str
    description: str


@dataclass
class AgentEfficiency:
    """Session-level efficiency metrics."""

    total_turns: int
    user_turns: int
    tool_calls: int
    errors: int
    error_loops: int
    turns_in_loops: int
    productive_ratio: float  # (total - turns_in_loops) / total
    tools_per_user_turn: float
    error_recovery_rate: float  # loops_resolved / total_loops
    duration_seconds: int
    session_type: str | None


@dataclass
class AgentReport:
    """Full agent analysis for one session."""

    session_id: str
    source: str
    project: str | None
    efficiency: AgentEfficiency
    tool_distribution: dict[str, int]
    error_loops: list[ErrorLoop]
    top_files: list[str]


@dataclass
class AggregateAgentReport:
    """Multi-session agent analysis rollup."""

    sessions_analyzed: int
    period_start: str
    period_end: str
    total_turns: int
    total_tool_calls: int
    total_errors: int
    total_error_loops: int
    productive_ratio: float
    avg_turns_per_session: float
    avg_duration_seconds: float
    tool_distribution: dict[str, int]
    error_loops: list[ErrorLoop]
    sessions: list[AgentReport]


def _build_fingerprint(turn: ConversationTurn) -> str | None:
    """Build a fingerprint string for an assistant turn's tool calls.

    Returns None for turns without tool calls (text-only responses).
    """
    if not turn.tool_names:
        return None

    parts: list[str] = []
    for i, name in enumerate(turn.tool_names):
        # Get target from tool_use_paths if available, else use tool name only
        target = ""
        if i < len(turn.tool_use_paths):
            # Use basename of file path for shorter fingerprints
            target = turn.tool_use_paths[i].rsplit("/", 1)[-1]
        suffix = ":err" if turn.has_error else ""
        parts.append(f"{name}({target}){suffix}" if target else f"{name}{suffix}")

    return "→".join(parts)


def detect_error_loops(turns: list[ConversationTurn]) -> list[ErrorLoop]:
    """Detect error loops in a sequence of conversation turns.

    Looks for repeated fingerprint patterns in assistant turns:
    - Single-step: same fingerprint >=3 times consecutively
    - Two-step: same (A, B) pair >=2 times consecutively (4+ turns)
    """
    # Build fingerprint sequence for assistant turns only
    asst_turns = [(t.turn_index, _build_fingerprint(t)) for t in turns if t.role == "assistant"]
    # Filter out None fingerprints (text-only turns)
    fps = [(idx, fp) for idx, fp in asst_turns if fp is not None]

    if len(fps) < 3:
        return []

    loops: list[ErrorLoop] = []
    used: set[int] = set()  # Turn indices already in a detected loop

    # Pass 1: Detect two-step loops (A, B, A, B, ...)
    i = 0
    while i < len(fps) - 3:
        a_idx, a_fp = fps[i]
        b_idx, b_fp = fps[i + 1]
        if a_fp == b_fp:
            i += 1
            continue  # Same fingerprint — handle in single-step pass

        # Check for (A, B) repetitions
        repeat_count = 1
        j = i + 2
        while j + 1 < len(fps) and fps[j][1] == a_fp and fps[j + 1][1] == b_fp:
            repeat_count += 1
            j += 2

        if repeat_count >= 2:
            end_idx = fps[j - 1][0] if j <= len(fps) else fps[-1][0]
            primary_tool = a_fp.split("(")[0].split(":")[0] if "(" in a_fp else a_fp.rstrip(":err")
            loop = ErrorLoop(
                start_turn=a_idx,
                end_turn=end_idx,
                loop_count=repeat_count,
                fingerprint=f"{a_fp}→{b_fp}",
                tool_name=primary_tool,
                description=f"{a_fp} → {b_fp} loop x{repeat_count}",
            )
            loops.append(loop)
            for k in range(i, min(i + repeat_count * 2, len(fps))):
                used.add(fps[k][0])
            i = j
        else:
            i += 1

    # Pass 2: Detect single-step loops (A, A, A, ...)
    i = 0
    while i < len(fps):
        if fps[i][0] in used:
            i += 1
            continue

        run_start = i
        j = i + 1
        while j < len(fps) and fps[j][1] == fps[i][1] and fps[j][0] not in used:
            j += 1
        run_length = j - run_start

        if run_length >= 3:
            fp = fps[i][1]
            assert fp is not None  # already filtered None above
            primary_tool = fp.split("(")[0].split(":")[0] if "(" in fp else fp.rstrip(":err")
            loop = ErrorLoop(
                start_turn=fps[run_start][0],
                end_turn=fps[j - 1][0],
                loop_count=run_length,
                fingerprint=fp,
                tool_name=primary_tool,
                description=f"{fp} loop x{run_length}",
            )
            loops.append(loop)

        i = j

    return loops


def compute_tool_distribution(turns: list[ConversationTurn]) -> dict[str, int]:
    """Count tool usage across all assistant turns, sorted by frequency."""
    counter: Counter[str] = Counter()
    for t in turns:
        if t.role == "assistant":
            counter.update(t.tool_names)
    return dict(counter.most_common())


def compute_efficiency(
    turns: list[ConversationTurn],
    error_loops: list[ErrorLoop],
    duration_seconds: int = 0,
    session_type: str | None = None,
) -> AgentEfficiency:
    """Compute session-level efficiency metrics."""
    user_turns = [t for t in turns if t.role == "user"]
    asst_turns = [t for t in turns if t.role == "assistant"]
    total_tool_calls = sum(t.tool_calls for t in asst_turns)
    total_errors = sum(1 for t in asst_turns if t.has_error)

    # Count turns wasted in loops
    loop_turn_indices: set[int] = set()
    for loop in error_loops:
        for t in turns:
            if loop.start_turn <= t.turn_index <= loop.end_turn:
                loop_turn_indices.add(t.turn_index)
    turns_in_loops = len(loop_turn_indices)

    total = len(turns)
    productive = (total - turns_in_loops) / total if total > 0 else 1.0
    tools_per_user = total_tool_calls / len(user_turns) if user_turns else 0.0

    # Error recovery: a loop is "resolved" if the session continues after it
    resolved = (
        sum(1 for loop in error_loops if loop.end_turn < turns[-1].turn_index) if turns else 0
    )
    recovery_rate = resolved / len(error_loops) if error_loops else 1.0

    return AgentEfficiency(
        total_turns=total,
        user_turns=len(user_turns),
        tool_calls=total_tool_calls,
        errors=total_errors,
        error_loops=len(error_loops),
        turns_in_loops=turns_in_loops,
        productive_ratio=round(productive, 2),
        tools_per_user_turn=round(tools_per_user, 1),
        error_recovery_rate=round(recovery_rate, 2),
        duration_seconds=duration_seconds,
        session_type=session_type,
    )


def analyze_session(conversation: Conversation) -> AgentReport:
    """Full agent analysis for a single session."""
    from reprompt.core.session_type import detect_session_type

    session_type = detect_session_type(conversation)
    type_str = session_type.value if session_type else None

    error_loops = detect_error_loops(conversation.turns)
    tool_dist = compute_tool_distribution(conversation.turns)
    efficiency = compute_efficiency(
        conversation.turns,
        error_loops,
        duration_seconds=conversation.duration_seconds or 0,
        session_type=type_str,
    )

    # Top files from tool_use_paths
    file_counter: Counter[str] = Counter()
    for t in conversation.turns:
        file_counter.update(t.tool_use_paths)
    top_files = [f for f, _ in file_counter.most_common(10)]

    return AgentReport(
        session_id=conversation.session_id,
        source=conversation.source,
        project=conversation.project,
        efficiency=efficiency,
        tool_distribution=tool_dist,
        error_loops=error_loops,
        top_files=top_files,
    )


def analyze_sessions(conversations: list[Conversation]) -> AggregateAgentReport:
    """Multi-session rollup analysis."""
    reports = [analyze_session(c) for c in conversations]

    all_loops: list[ErrorLoop] = []
    tool_totals: Counter[str] = Counter()
    total_turns = 0
    total_tools = 0
    total_errors = 0
    total_duration = 0
    total_loop_turns = 0

    for r in reports:
        total_turns += r.efficiency.total_turns
        total_tools += r.efficiency.tool_calls
        total_errors += r.efficiency.errors
        total_duration += r.efficiency.duration_seconds
        total_loop_turns += r.efficiency.turns_in_loops
        tool_totals.update(r.tool_distribution)
        for loop in r.error_loops:
            all_loops.append(loop)

    n = len(reports)
    productive = (total_turns - total_loop_turns) / total_turns if total_turns > 0 else 1.0

    timestamps = []
    for c in conversations:
        if c.start_time:
            timestamps.append(c.start_time)
        if c.end_time:
            timestamps.append(c.end_time)
    timestamps.sort()

    return AggregateAgentReport(
        sessions_analyzed=n,
        period_start=timestamps[0] if timestamps else "",
        period_end=timestamps[-1] if timestamps else "",
        total_turns=total_turns,
        total_tool_calls=total_tools,
        total_errors=total_errors,
        total_error_loops=len(all_loops),
        productive_ratio=round(productive, 2),
        avg_turns_per_session=round(total_turns / n, 1) if n else 0,
        avg_duration_seconds=round(total_duration / n, 1) if n else 0,
        tool_distribution=dict(tool_totals.most_common()),
        error_loops=all_loops,
        sessions=reports,
    )
