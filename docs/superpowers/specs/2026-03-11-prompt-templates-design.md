# Prompt Templates — Design Spec

## Summary

Add `reprompt save` and `reprompt templates` commands for saving and reusing prompt templates. Plain text storage, auto-naming, category tagging.

## Commands

```bash
reprompt save "debug auth — login returns 401"          # save with auto-name
reprompt save "debug auth..." --name auth-debug          # save with custom name
reprompt save "debug auth..." --category debug           # save with category
reprompt templates                                       # list all saved
reprompt templates --category debug                      # filter by category
reprompt templates --json                                # JSON output
```

## Data Model

New SQLite table `prompt_templates`:

```sql
CREATE TABLE IF NOT EXISTS prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    category TEXT DEFAULT 'other',
    usage_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
)
```

## Auto-naming

When `--name` is omitted:
1. Auto-categorize the text using existing `categorize_prompt()`
2. Take first 3 significant words (skip stop words)
3. Join with hyphens: `"debug-auth-login"`
4. If name collision, append `-2`, `-3`, etc.

## Terminal Output

```
reprompt templates

Your Prompt Templates (5 saved)

  #  Name              Category   Text                                    Used
  1  auth-debug        debug      debug auth — login returns 401          3
  2  add-pagination    implement  add pagination to search results...     1
  3  test-user-svc     test       add unit tests for user service...      0
```

## Architecture

- New: `src/reprompt/core/templates.py` — `save_template()`, `list_templates()`, `get_template()`
- New: `tests/test_templates.py` — unit tests
- Modify: `src/reprompt/storage/db.py` — add table creation + CRUD methods
- Modify: `src/reprompt/cli.py` — add `save` and `templates` commands
- Modify: `src/reprompt/output/terminal.py` — add `render_templates()`

## No new dependencies
