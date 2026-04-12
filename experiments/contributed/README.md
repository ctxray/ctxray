# Contributed experiment runs

This directory collects runs of the ctxray E9 specificity-gradient experiment
harness against models that neither our baseline nor the published
**PartialOrderEval** (Zi et al. 2025,
[arXiv:2508.03678](https://arxiv.org/abs/2508.03678)) dataset covers.

PartialOrderEval established the core specificity-gradient finding on
Qwen2.5-Coder (1.5B/3B/7B/14B) and Llama-3.x (1B/3B/8B/**70B**) for code
generation. The contributed collection here **extends** that work into
directions they did not test.

## What's already covered (skip these)

- **PartialOrderEval (2508.03678)**: Qwen2.5-Coder 1.5B/3B/7B/14B, Llama-3.x
  1B/3B/8B/70B, code tasks (HumanEval + ParEval)
- **Our ctxray baseline (11 models)**: qwen3 0.6B/4B/8B/14B/32B, llama3.2
  1B/3B, llama3.1 8B, gemma2 2B/9B, gemma4 26B

## High-value gap directions

These are the model categories where a single contributed run is a **real
extension** to the published literature:

1. **Reasoning-RL models**: DeepSeek-R1-Distill variants, Qwen3-QwQ,
   gpt-oss reasoning mode — PartialOrderEval did not test any reasoning model
2. **MoE models**: Mixtral 8x7B/22B, Qwen3-MoE-A30B, DeepSeek-V2/V3 —
   PartialOrderEval tested only dense
3. **Mistral family**: any Mistral dense model — zero Mistral data in either
   dataset
4. **Phi family**: phi4 (14B+) — PartialOrderEval didn't include Phi
5. **Gemma family**: gemma3:12b/27b, gemma4 variants not in baseline
6. **Granite, Yi, Tulu, Nemotron**: any of these families
7. **Fine-tuned / community models**: anything derived from a base we have
   data for, to measure fine-tuning effects

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

## v2 dataset (2026-04-10)

12 models run with **two methodology bugs fixed** — see the v2 section below
for details. The full cross-model snapshot:

| Model | vague | task_only | task_io | full_spec | Δ | Notes |
|---|---:|---:|---:|---:|---:|---|
| `qwen2.5-coder:1.5b` | 0.08 | 0.42 | 0.72 | 0.67 | +0.58 | **real U-curve** at full_spec |
| `gemma3:1b` | 0.00 | 0.25 | 0.92 | 1.00 | +1.00 | |
| `qwen3.5:4b` | 0.00 | 0.50 | 1.00 | 1.00 | +1.00 | |
| `gemma3:4b` | 0.25 | 0.50 | 1.00 | 1.00 | +0.75 | |
| `phi4-mini:latest` | 0.00 | 0.33 | 0.94 | 1.00 | +1.00 | lowest task_only |
| `llama3.1:8b` | 0.00 | 0.50 | 0.83 | 1.00 | +1.00 | task_io below ceiling (fizzbuzz DeMorgan bug) |
| `deepseek-r1:8b` | 0.00 | 0.50 | 1.00 | 1.00 | +1.00 | **reasoning RL** — same base as llama3.1:8b, +0.17 at task_io |
| `qwen3.5:9b` | 0.25 | 0.50 | 1.00 | 1.00 | +0.75 | |
| `phi4:14b` | 0.00 | 0.50 | 1.00 | 1.00 | +1.00 | |
| `gemma4:26b` | 0.00 | 0.50 | 1.00 | 1.00 | +1.00 | MoE per project spec |
| `qwen3.5:27b` | 0.25 | 0.50 | 1.00 | 1.00 | +0.75 | |
| `qwen3.5:35b-a3b` | 0.25 | 0.50 | 1.00 | 1.00 | +0.75 | **MoE** (3B active) — identical to same-family dense |

### Key v2 findings

- **qwen3.5 intra-family scale plateau (9B+)**: qwen3.5:9b, 27b, and
  35b-a3b (MoE) all score identically at 0.25/0.50/1.00/1.00. Scaling
  from 9B to 27B (3×) within a single family produces zero E9 improvement.
  qwen3.5:4b differs at vague (0.00 instead of 0.25) but matches at
  task_io+ (1.00/1.00), so the plateau starts at 9B, not 4B.
- **MoE behaves like total size, not active size**: qwen3.5:35b-a3b (3B
  active params) scores identically to qwen3.5:27b (dense). If MoE
  behaved like its active-param count (3B), it should look like qwen3.5:4b
  (which it does, but qwen3.5:4b also matches qwen3.5:27b, making the
  test vacuous). A cleaner MoE-vs-active comparison needs models outside
  the plateau range — Mixtral 8x7B (active 12B) vs a 12B dense is the
  next logical experiment.
- **Reasoning RL flattens the low end**: deepseek-r1:8b at task_io = 1.00
  vs llama3.1:8b (same base) = 0.83. At full_spec both reach 1.00.
  Reasoning helps task_io recovery specifically, not ceiling.
- **qwen2.5-coder:1.5b real U-curve**: the only real specificity-hurts
  signal in the v2 dataset. Coder-specialized 1.5B model drops from 0.72
  (task_io) to 0.67 (full_spec). Worth investigating whether this is
  specific to coder fine-tuning or generalizes to other small specialized
  models.
- **gemma3:1b U-curve was a v1 test artifact**: v1 showed gemma3:1b
  dropping from 0.92 (task_io) to 0.67 (full_spec). v2 shows 0.92 → 1.00.
  The v1 "U-curve" was entirely the two_sum test case bug capping scores
  at 0.67. Corrected data removes the artifact.

### v2 methodology corrections (see `~/projects/knowledge/sessions/2026-04-10-ctxray-e9-contributor-bootstrap/` for full write-up)

Two bugs discovered during failure-mode analysis on the v1 baseline:

1. **`experiments/data.py` two_sum test case bug**: `TestCase("two_sum([1, 5, 3, 7], 8)", "(1, 3)")` was mathematically impossible (5+7=12, not 8). This silently capped every correct model at 0.67 pass rate on two_sum across all v1 data, and two_sum was 42% of all v1 failures. Fixed by changing target from 8 to 12 so `(1, 3)` becomes the unique valid pair (minimum-delta fix preserving the original expected value).
2. **`experiments/validate.py` num_predict truncation**: the `max_tokens=1024` default in `ollama_generate` truncated reasoning-model outputs when thinking tokens consumed the budget. deepseek-r1:8b scored 0.00 on flatten full_spec in v1 solely because R1's `<think>` tokens filled 1024 before any code was emitted. Fixed by bumping default to 4096.

**v1 data is archived** at `.output/experiments/v1/` and should NOT be used for research claims going forward. v2 (this directory) is the canonical ctxray E9 dataset.
