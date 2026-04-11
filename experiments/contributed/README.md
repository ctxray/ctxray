# Contributed experiment runs

This directory collects runs of the ctxray experiment harness against models
the core dataset doesn't cover. Anyone with a local Ollama can contribute one.

## Baseline coverage (11 models)

qwen3 0.6B · qwen3 4B · qwen3 8B · qwen3 14B · qwen3 32B ·
llama3.2 1B · llama3.2 3B · llama3.1 8B · gemma2 2B · gemma2 9B · gemma4 26B

**Notable gaps:** Mistral family, Phi family, DeepSeek, Granite, Mixtral,
Qwen3-MoE, anything >32B dense, anything fine-tuned.

## How to contribute (5–15 minutes)

```bash
git clone https://github.com/ctxray/ctxray.git
cd ctxray
uv venv && uv pip install -e ".[dev]"

# Pull any model you want to test (or use one you already have)
ollama pull mistral:7b

# Run the specificity-gradient experiment
uv run python experiments/validate.py e9 --model-name mistral:7b
```

Output lands at:

```
.output/experiments/e9_specificity_custom_<sanitized-name>.json
```

See [../README.md](../README.md) for other experiments (e0, e1, e10) and
non-default Ollama hosts.

## Two ways to submit

### Option A — GitHub issue (fastest)

Open an issue titled `Contributed E9 run: <model-name>` and paste the JSON
as a code block. We'll commit it to this directory on your behalf with
your GitHub handle in the commit message.

### Option B — Pull request

1. Copy your JSON into `experiments/contributed/<sanitized-name>.json`
   (same sanitized name the harness uses for the filename)
2. Open a PR — the commit history is the attribution

## JSON schema

Every file in this directory follows the same shape. Minimal example (see
`qwen3_5_27b.json` for a real one):

```json
{
  "experiment": "e9_specificity",
  "k": 3,
  "models": ["gemma3:1b"],
  "total_calls": 48,
  "results": [
    {
      "task": "fizzbuzz",
      "level": "vague",
      "model": "custom",
      "model_name": "gemma3:1b",
      "pass_rates": [0.0, 0.0, 0.0],
      "avg_pass_rate": 0.0,
      "ctxray_score": 29.2,
      "prompt_len": 15
    }
  ]
}
```

**Aggregators should key on `model_name`, not `model`.** The internal `model`
field is `"custom"` for contributed runs; `model_name` is the real
`ollama run` identifier.

## Privacy

These runs contain **zero user data**. Only model identifier, pass rates,
prompt scores, and prompt lengths. The prompts themselves are the fixed
E9 set from `experiments/data.py`, not anything from your session history.

## What happens to contributed data

- Aggregated into a public cross-model comparison table (in this repo)
- Used to refine the model-specific scoring thresholds in `src/ctxray/core/scorer.py`
- Cited in the growing list of open findings — contributors credited by GitHub handle
- **Not** used for any commercial or proprietary purpose. This directory
  is the canonical source; there is no private copy.

## First contribution — fills the qwen3.5 9B→27B gap

[`qwen3_5_27b.json`](qwen3_5_27b.json) — qwen3.5:27b E9 run. Key finding:

| Model | vague | task_only | task_io | full_spec |
|---|---:|---:|---:|---:|
| `qwen3.5:9b` (baseline) | 0.25 | 0.50 | 0.92 | 0.92 |
| `qwen3.5:27b` (this run) | 0.25 | 0.50 | 0.92 | 0.92 |

**Identical.** Scaling qwen3.5 from 9B → 27B (3× parameters) produces zero
improvement on E9 once the prompt reaches task_io specificity. This is a
real data point about where prompt quality matters vs where raw scale
matters — the kind of cross-family comparison only contributed runs can
build.
