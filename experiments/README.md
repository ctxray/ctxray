# ctxray experiment harness

Run the same prompt-quality experiments we used to calibrate ctxray's scoring
against **your own Ollama model**, and (optionally) share the results so we can
extend the cross-model comparison.

Current baseline dataset covers 11 models (qwen3 0.6B–32B, llama3.2 1/3B,
llama3.1 8B, gemma2 2/9B, gemma4 26B). Gaps: Mistral, Phi, DeepSeek, Granite,
Mixtral, anything >32B. **One contributed run fills a gap.**

## Prerequisites

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) (or swap `uv run python` for `python`)
- A running [Ollama](https://ollama.com/) instance with at least one model pulled

## Quick start (5–15 minutes per model)

```bash
git clone https://github.com/ctxray/ctxray.git
cd ctxray
uv venv && uv pip install -e ".[dev]"

# Pull a model if you don't have one
ollama pull mistral:7b

# Run the specificity-gradient experiment (E9) against it
uv run python experiments/validate.py e9 --model-name mistral:7b
```

That runs **4 coding tasks × 4 specificity levels × k=3 repetitions = 48
Ollama calls**. On an M2 Mac with a 7B model it takes about 5–10 minutes. On
a GPU with a 14B model, roughly the same.

Result lands at:

```
.output/experiments/e9_specificity_custom_<sanitized_name>.json
```

## Experiments you can run

| Command | What it measures | Calls | Time (7B on M2) |
|---|---|---|---|
| `e0 --model-name <m>` | Sanity: draft vs strong prompts diverge on pass rate | ~20 | ~2 min |
| `e1 --model-name <m>` | Score-vs-quality correlation (30 prompts × 5 tiers) | ~150 | ~15 min |
| `e9 --model-name <m>` | Specificity gradient (4 levels × 4 tasks × k=3) | ~48 | ~5–10 min |
| `e10 --model-name <m>` | Full specificity decomposition (10 tasks × 6 levels × k=10) | ~600 | ~1 hour+ |

**If you only run one, run `e9`.** It's the cleanest single-model signal and
slots straight into the existing cross-model comparison table.

## Non-default host

If your Ollama runs somewhere else (remote box, custom port):

```bash
uv run python experiments/validate.py e9 \
    --model-name llama3.1:70b \
    --host http://gpu-box.local:11434
```

## Sharing results

The output JSON contains **zero PII** — just model name, pass rates, ctxray
scores, and prompt lengths. Full details + schema + submission process:
**[contributed/README.md](contributed/README.md)**. The short version:

1. **Paste the JSON into a GitHub issue** titled
   `Contributed E9 run: <model-name>` — fastest, lowest friction
2. **Open a PR** adding the file to `experiments/contributed/` — credited in
   the commit history

We'll aggregate contributed runs into a public leaderboard + dataset.
Contributors are credited by GitHub handle. See
[`contributed/example_gemma3_1b.json`](contributed/example_gemma3_1b.json)
for an example output.

## Open questions a single contributed run can help answer

- Does the filler-word / compression threshold move for **Mistral**'s tokenizer
  family? (All 11 baseline models are Qwen/Llama/Gemma — no Mistral line.)
- Do **MoE** models (Mixtral, Qwen3-MoE, DeepSeek-V2) behave like their dense
  size, or like their active-param count?
- Where does the complexity-penalty curve actually flatten? Baseline data says
  ~8B, but only 2 models above that — very likely wrong.
- Is the U-curve on position bias universal or architecture-specific?

## Reproducibility notes

- `temperature=0.0`, `num_predict=1024` — deterministic decoding
- `think: false` auto-set for qwen3 reasoning models (they emit empty
  `response` otherwise)
- Code extraction: regex-extracted from the first fenced code block, or
  raw response as fallback
- Grading: pass rate from `run_test()` executing the extracted function
  against 3 test cases per task
- Seeds: none needed — temperature 0 is deterministic for the same model
  revision

## Bug reports

If the harness crashes or gives obviously wrong scores, open an issue with:
- `ollama --version`
- Model name + `ollama show <model>` output
- Full stderr
