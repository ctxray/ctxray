# Merge View — Design Spec

## Summary

Add `reprompt merge-view` command that groups semantically similar prompts into clusters and highlights the best one to reuse, helping users see their repetition patterns and reduce redundancy.

## Command Interface

```bash
reprompt merge-view              # terminal output
reprompt merge-view --json       # JSON output
reprompt merge-view --limit 5    # show top 5 clusters only (default: all)
```

## Data Flow

```
DB (unique prompts, no duplicates) → TF-IDF vectorize all texts
  → compute pairwise cosine similarity matrix
  → group pairs above threshold (0.85, from settings.dedup_threshold)
  → transitive closure: if A~B and B~C, merge {A,B,C} into one cluster
  → filter clusters with < 2 members
  → sort clusters by size descending
  → pick canonical prompt per cluster (composite score)
  → render (terminal / JSON)
```

## Canonical Prompt Selection

Each prompt in a cluster gets a composite score:

```python
score = (
    0.5 * normalize(len(text))           # longer = more specific
    + 0.3 * has_specific_refs(text)       # 1.0 if contains file.py, func(), line N
    + 0.2 * effectiveness(text)           # from DB if available, else 0.5
)
```

- `normalize(length)`: min-max normalize across the cluster, so longest = 1.0
- `has_specific_refs`: regex check for `\w+\.\w+` (file extensions), `\w+\(\)` (function calls), `line \d+`
- `effectiveness`: from `prompt_patterns` table if matched, otherwise default 0.5

Highest score in each cluster = canonical (marked with star).

## Terminal Output Format

```
reprompt merge-view

Found 8 clusters of similar prompts (32 prompts total)

Cluster 1: Authentication Debugging (5 prompts)
  ★ "debug auth — login returns 401 instead of JWT"     score: 0.82
    "fix the auth bug"                                   2026-02-15
    "fix the authentication issue"                       2026-02-18
    "fix auth middleware"                                 2026-03-01
    "the auth is broken again"                           2026-03-05
  → Reuse the ★ prompt instead of writing a new one

Summary: 32 prompts could be reduced to 8 templates.
```

## Cluster Naming

Auto-generate cluster name from the canonical prompt's category + most distinctive TF-IDF term:
- Category from `categorize_prompt()` (existing function)
- Top TF-IDF term from the cluster's texts
- Format: "{Category}: {Top Term}" e.g. "Debug: Authentication"

## JSON Output

```json
{
  "clusters": [
    {
      "id": 0,
      "name": "Debug: Authentication",
      "size": 5,
      "canonical": {
        "text": "debug auth — login returns 401 instead of JWT",
        "score": 0.82
      },
      "members": [
        {"text": "fix the auth bug", "timestamp": "2026-02-15", "score": 0.31},
        {"text": "fix the authentication issue", "timestamp": "2026-02-18", "score": 0.35}
      ]
    }
  ],
  "summary": {
    "total_clustered_prompts": 32,
    "cluster_count": 8,
    "reduction_potential": "32 → 8"
  }
}
```

## Architecture

### New file: `src/reprompt/core/merge_view.py`

Public functions:
- `build_clusters(texts, timestamps, threshold) -> list[Cluster]` — main logic
- `score_prompt(text, cluster_texts, effectiveness) -> float` — composite scoring
- `name_cluster(canonical_text, category) -> str` — auto-name generation

### New file: `tests/test_merge_view.py`

Test cases:
- Two similar prompts form a cluster
- Dissimilar prompts stay separate
- Canonical is the highest-scored prompt
- Transitive closure works (A~B, B~C → one cluster)
- Single prompts excluded (threshold 2+)
- Empty input returns empty clusters
- JSON output is valid
- Cluster naming works

### Modify: `src/reprompt/cli.py`

Add `merge_view` command with `--json` and `--limit` options.

### Modify: `src/reprompt/output/terminal.py`

Add `render_merge_view(data) -> str` function.

### Reuses existing code

- `TfidfEmbedder` from `embeddings/tfidf.py` for vectorization
- `cosine_similarity` from sklearn
- `categorize_prompt` from `core/library.py`
- `PromptDB` for reading prompts and effectiveness data

## No new dependencies

Everything uses existing sklearn + stdlib.
