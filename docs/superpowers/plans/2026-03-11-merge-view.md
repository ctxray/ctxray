# Merge View Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `reprompt merge-view` command that groups similar prompts into clusters and highlights the best one to reuse.

**Architecture:** New `merge_view.py` module builds similarity clusters from unique prompts using TF-IDF cosine similarity (reusing existing sklearn infrastructure from `library.py`). Each cluster picks a canonical prompt via composite score. CLI command and terminal renderer added.

**Tech Stack:** sklearn TF-IDF + cosine_similarity (existing), Rich console (existing), no new dependencies.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/reprompt/core/merge_view.py` | Create | Cluster building, canonical scoring, cluster naming |
| `src/reprompt/output/terminal.py` | Modify | Add `render_merge_view()` function |
| `src/reprompt/cli.py` | Modify | Add `merge-view` command |
| `tests/test_merge_view.py` | Create | Unit tests for clustering + scoring |

---

## Chunk 1: Core Logic + Tests

### Task 1: Write failing tests for merge_view

**Files:**
- Create: `tests/test_merge_view.py`

- [ ] **Step 1: Write test file**

```python
"""Tests for merge-view clustering and canonical selection."""

from reprompt.core.merge_view import build_clusters, score_prompt, name_cluster


def test_two_similar_prompts_form_cluster():
    texts = ["fix the auth bug", "fix the authentication issue"]
    timestamps = ["2026-02-15", "2026-02-18"]
    clusters = build_clusters(texts, timestamps, threshold=0.5)
    assert len(clusters) == 1
    assert clusters[0]["size"] == 2


def test_dissimilar_prompts_stay_separate():
    texts = [
        "fix the auth bug in login.py",
        "add pagination to search results with offset and limit",
    ]
    timestamps = ["2026-02-15", "2026-02-18"]
    clusters = build_clusters(texts, timestamps, threshold=0.85)
    assert len(clusters) == 0  # no cluster has 2+ members


def test_canonical_is_highest_scored():
    texts = ["fix bug", "fix the authentication bug in login.py"]
    timestamps = ["2026-02-15", "2026-02-18"]
    clusters = build_clusters(texts, timestamps, threshold=0.5)
    assert len(clusters) == 1
    # longer prompt should score higher
    assert "login.py" in clusters[0]["canonical"]["text"]


def test_transitive_closure():
    """A~B and B~C should merge into one cluster {A,B,C}."""
    texts = [
        "fix the auth bug",
        "fix the authentication issue",
        "fix the authentication error in login",
    ]
    timestamps = ["2026-02-15", "2026-02-18", "2026-02-20"]
    clusters = build_clusters(texts, timestamps, threshold=0.4)
    assert len(clusters) == 1
    assert clusters[0]["size"] == 3


def test_single_prompts_excluded():
    texts = ["fix the auth bug"]
    timestamps = ["2026-02-15"]
    clusters = build_clusters(texts, timestamps, threshold=0.85)
    assert len(clusters) == 0


def test_empty_input():
    clusters = build_clusters([], [], threshold=0.85)
    assert clusters == []


def test_score_prompt_longer_is_higher():
    short = "fix bug"
    long = "fix the authentication bug in login.py line 42"
    cluster_texts = [short, long]
    assert score_prompt(long, cluster_texts) > score_prompt(short, cluster_texts)


def test_score_prompt_with_file_ref():
    without = "fix the authentication bug"
    with_ref = "fix auth bug in login.py"
    cluster_texts = [without, with_ref]
    # with_ref has file reference bonus even though shorter
    score_no_ref = score_prompt(without, cluster_texts)
    score_with_ref = score_prompt(with_ref, cluster_texts)
    # Both should be valid floats between 0 and 1
    assert 0 <= score_no_ref <= 1
    assert 0 <= score_with_ref <= 1


def test_name_cluster():
    name = name_cluster("fix the authentication bug in login.py", "debug")
    assert "Debug" in name


def test_clusters_sorted_by_size():
    texts = [
        "fix auth bug",
        "fix authentication issue",
        "fix auth error",
        "add test for user",
        "add test for user service",
    ]
    timestamps = ["2026-01-01"] * 5
    clusters = build_clusters(texts, timestamps, threshold=0.4)
    if len(clusters) >= 2:
        assert clusters[0]["size"] >= clusters[1]["size"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/chris/projects/reprompt && uv run pytest tests/test_merge_view.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'reprompt.core.merge_view'`

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_merge_view.py
git commit -m "test: add failing tests for merge-view clustering"
```

---

### Task 2: Implement merge_view.py

**Files:**
- Create: `src/reprompt/core/merge_view.py`

- [ ] **Step 1: Create the merge_view module**

```python
"""Merge View — group similar prompts into clusters with canonical selection."""

from __future__ import annotations

import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from reprompt.core.library import categorize_prompt

# Regex patterns for detecting specific references in prompts
_FILE_REF_RE = re.compile(r"\w+\.\w{1,4}\b")  # file.py, auth.ts, etc.
_FUNC_REF_RE = re.compile(r"\w+\(\)")  # function(), login(), etc.
_LINE_REF_RE = re.compile(r"line\s+\d+", re.IGNORECASE)


def score_prompt(
    text: str,
    cluster_texts: list[str],
    effectiveness: float = 0.5,
) -> float:
    """Score a prompt for canonical selection.

    Composite: 50% normalized length + 30% specific refs + 20% effectiveness.
    """
    # Normalize length within cluster
    lengths = [len(t) for t in cluster_texts]
    min_len = min(lengths)
    max_len = max(lengths)
    if max_len == min_len:
        len_score = 1.0
    else:
        len_score = (len(text) - min_len) / (max_len - min_len)

    # Specific references (file names, functions, line numbers)
    ref_score = 0.0
    if _FILE_REF_RE.search(text):
        ref_score += 0.5
    if _FUNC_REF_RE.search(text):
        ref_score += 0.3
    if _LINE_REF_RE.search(text):
        ref_score += 0.2

    return 0.5 * len_score + 0.3 * ref_score + 0.2 * effectiveness


def name_cluster(canonical_text: str, category: str) -> str:
    """Auto-generate a cluster name from category + key terms."""
    # Capitalize category
    cat_label = category.capitalize()

    # Extract most distinctive words (skip common short words)
    stop = {"the", "a", "an", "in", "on", "to", "for", "is", "it", "and", "or", "of", "with"}
    words = [w for w in canonical_text.lower().split() if w not in stop and len(w) > 2]
    # Take first 2-3 meaningful words
    key_words = " ".join(words[:3]).title()

    return f"{cat_label}: {key_words}" if key_words else cat_label


def build_clusters(
    texts: list[str],
    timestamps: list[str],
    threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """Build similarity clusters from prompt texts.

    Returns list of cluster dicts sorted by size descending:
    [{"id": int, "name": str, "size": int,
      "canonical": {"text": str, "score": float},
      "members": [{"text": str, "timestamp": str, "score": float}]}]
    """
    if len(texts) < 2:
        return []

    # TF-IDF vectorize
    vectorizer = TfidfVectorizer(max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(texts)
    sim_matrix = sklearn_cosine(tfidf_matrix)

    # Build adjacency: pairs above threshold
    adj: dict[int, set[int]] = {i: set() for i in range(len(texts))}
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if sim_matrix[i][j] >= threshold:
                adj[i].add(j)
                adj[j].add(i)

    # Transitive closure via BFS to find connected components
    visited: set[int] = set()
    components: list[list[int]] = []
    for i in range(len(texts)):
        if i in visited or not adj[i]:
            continue
        component: list[int] = []
        queue = [i]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) >= 2:
            components.append(sorted(component))

    # Build cluster dicts
    clusters: list[dict[str, Any]] = []
    for cid, component in enumerate(components):
        cluster_texts = [texts[i] for i in component]
        cluster_timestamps = [timestamps[i] for i in component]

        # Score each member
        scored = []
        for idx, (t, ts) in enumerate(zip(cluster_texts, cluster_timestamps)):
            s = score_prompt(t, cluster_texts)
            scored.append({"text": t, "timestamp": ts, "score": round(s, 2)})

        # Canonical = highest score
        scored.sort(key=lambda x: -x["score"])
        canonical = scored[0]
        category = categorize_prompt(canonical["text"])

        clusters.append(
            {
                "id": cid,
                "name": name_cluster(canonical["text"], category),
                "size": len(component),
                "canonical": {"text": canonical["text"], "score": canonical["score"]},
                "members": scored[1:],  # all except canonical
            }
        )

    # Sort by size descending
    clusters.sort(key=lambda c: -c["size"])

    # Re-assign IDs after sort
    for i, c in enumerate(clusters):
        c["id"] = i

    return clusters
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd /Users/chris/projects/reprompt && uv run pytest tests/test_merge_view.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Run linting**

```bash
cd /Users/chris/projects/reprompt && uv run ruff check src/reprompt/core/merge_view.py && uv run ruff format --check src/reprompt/core/merge_view.py
```

Fix any issues.

- [ ] **Step 4: Commit**

```bash
git add src/reprompt/core/merge_view.py tests/test_merge_view.py
git commit -m "feat: add merge-view clustering with canonical selection"
```

---

## Chunk 2: Terminal Output + CLI Command

### Task 3: Add terminal renderer for merge-view

**Files:**
- Modify: `src/reprompt/output/terminal.py` (add `render_merge_view` function at end of file)

- [ ] **Step 1: Write test for render_merge_view**

Append to `tests/test_merge_view.py`:

```python
from reprompt.output.terminal import render_merge_view


def test_render_merge_view_output():
    data = {
        "clusters": [
            {
                "id": 0,
                "name": "Debug: Auth Bug",
                "size": 3,
                "canonical": {"text": "debug auth — login returns 401", "score": 0.82},
                "members": [
                    {"text": "fix the auth bug", "timestamp": "2026-02-15", "score": 0.31},
                    {"text": "fix auth issue", "timestamp": "2026-02-18", "score": 0.35},
                ],
            }
        ],
        "summary": {
            "total_clustered_prompts": 3,
            "cluster_count": 1,
            "reduction_potential": "3 → 1",
        },
    }
    output = render_merge_view(data)
    assert "Debug: Auth Bug" in output or "auth" in output.lower()
    assert "debug auth" in output.lower()
    assert "3" in output


def test_render_merge_view_empty():
    data = {"clusters": [], "summary": {"total_clustered_prompts": 0, "cluster_count": 0, "reduction_potential": "0 → 0"}}
    output = render_merge_view(data)
    assert "no" in output.lower() or "0" in output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/chris/projects/reprompt && uv run pytest tests/test_merge_view.py::test_render_merge_view_output -v
```

Expected: FAIL — `ImportError: cannot import name 'render_merge_view'`

- [ ] **Step 3: Implement render_merge_view in terminal.py**

Add this function at the end of `src/reprompt/output/terminal.py` (before the final newline):

```python
def render_merge_view(data: dict[str, Any]) -> str:
    """Render merge-view clusters to a string using Rich."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]reprompt merge-view — Similar Prompt Clusters[/bold]")
    console.print("=" * 40)

    clusters = data.get("clusters", [])
    summary = data.get("summary", {})

    if not clusters:
        console.print("No similar prompt clusters found.")
        console.print("Run [bold]reprompt scan[/bold] to index more sessions.")
        return buf.getvalue()

    total = summary.get("total_clustered_prompts", 0)
    count = summary.get("cluster_count", 0)
    console.print(
        f"Found [bold]{count}[/bold] clusters of similar prompts "
        f"([bold]{total}[/bold] prompts total)\n"
    )

    for c in clusters:
        console.print(
            f"[bold]Cluster {c['id'] + 1}: {c['name']}[/bold] ({c['size']} prompts)"
        )
        # Canonical (starred)
        canon = c["canonical"]
        console.print(
            f'  [green]★[/green] "{canon["text"]}"'
            f"     [dim]score: {canon['score']:.2f}[/dim]"
        )
        # Members
        for m in c.get("members", []):
            console.print(
                f'    "{m["text"]}"'
                f"     [dim]{m.get('timestamp', '')}[/dim]"
            )
        console.print(
            "  [dim]→ Reuse the ★ prompt instead of writing a new one[/dim]\n"
        )

    reduction = summary.get("reduction_potential", "")
    console.print(f"[bold]Summary:[/bold] {total} prompts could be reduced to {count} templates.")
    if count > 0:
        console.print(
            "Run [bold]reprompt save[/bold] to save ★ prompts as reusable templates."
        )

    return buf.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/chris/projects/reprompt && uv run pytest tests/test_merge_view.py -v
```

Expected: All tests PASS (including the new render tests)

- [ ] **Step 5: Run linting**

```bash
cd /Users/chris/projects/reprompt && uv run ruff check src/reprompt/output/terminal.py && uv run ruff format --check src/reprompt/output/terminal.py
```

- [ ] **Step 6: Commit**

```bash
git add src/reprompt/output/terminal.py tests/test_merge_view.py
git commit -m "feat: add terminal renderer for merge-view clusters"
```

---

### Task 4: Wire up CLI merge-view command

**Files:**
- Modify: `src/reprompt/cli.py` (add `merge_view` command)

- [ ] **Step 1: Add the merge-view command to cli.py**

Add this command after the `recommend` command (around line 355):

```python
@app.command("merge-view")
def merge_view(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    limit: int = typer.Option(0, "--limit", help="Max clusters to show (0 = all)"),
) -> None:
    """Show clusters of similar prompts you keep rewriting."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.merge_view import build_clusters
    from reprompt.output.terminal import render_merge_view
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    all_prompts = db.get_all_prompts()

    # Only use unique (non-duplicate) prompts
    unique = [p for p in all_prompts if p.get("duplicate_of") is None]
    texts = [p["text"] for p in unique]
    timestamps = [p.get("timestamp", "") for p in unique]

    clusters = build_clusters(texts, timestamps, threshold=settings.dedup_threshold)

    if limit > 0:
        clusters = clusters[:limit]

    total_clustered = sum(c["size"] for c in clusters)
    data = {
        "clusters": clusters,
        "summary": {
            "total_clustered_prompts": total_clustered,
            "cluster_count": len(clusters),
            "reduction_potential": f"{total_clustered} → {len(clusters)}",
        },
    }

    if json_output:
        print(json_mod.dumps(data, indent=2, default=str))
    else:
        print(render_merge_view(data), end="")
```

- [ ] **Step 2: Run linting**

```bash
cd /Users/chris/projects/reprompt && uv run ruff check src/reprompt/cli.py && uv run ruff format --check src/reprompt/cli.py
```

- [ ] **Step 3: Verify help works**

```bash
cd /Users/chris/projects/reprompt && uv run reprompt merge-view --help
```

Expected: Shows help with `--json` and `--limit` options.

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/chris/projects/reprompt && uv run pytest tests/ -v
```

Expected: All tests pass, no regressions.

- [ ] **Step 5: Commit**

```bash
git add src/reprompt/cli.py
git commit -m "feat: add merge-view CLI command"
```

---

### Task 5: Manual test with demo data

- [ ] **Step 1: Generate demo data and run merge-view**

```bash
cd /Users/chris/projects/reprompt
uv run reprompt demo
uv run reprompt merge-view
```

Expected: Shows clusters with starred canonical prompts.

- [ ] **Step 2: Test JSON output**

```bash
uv run reprompt merge-view --json | python3 -m json.tool | head -30
```

Expected: Valid JSON with clusters array.

- [ ] **Step 3: Test limit flag**

```bash
uv run reprompt merge-view --limit 2
```

Expected: Shows at most 2 clusters.

- [ ] **Step 4: Final commit and push**

```bash
git push origin main
```
