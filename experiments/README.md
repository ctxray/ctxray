# ctxray experiment harness

Run prompt-specificity experiments against **your own Ollama model** and share
the results so we can extend the cross-model comparison into the model
families that existing literature hasn't covered.

## Prior art

This harness is a replication and extension of **PartialOrderEval** (Zi et al.
2025, [arXiv:2508.03678](https://arxiv.org/abs/2508.03678), ACL IJCNLP 2025).
Zi et al. established the core finding that prompt specificity and model scale
interact for code generation — larger models consistently outperform smaller
ones at every specificity level, and specificity disproportionately helps
weaker models. Their sweep covers Qwen2.5-Coder 1.5B/3B/7B/14B and Llama-3.x
1B/3B/8B/**70B** on HumanEval + ParEval tasks.

**ctxray's ongoing baseline extends PartialOrderEval in four directions they
did not cover:**

1. **Reasoning-RL models** (DeepSeek-R1-Distill, Qwen3-QwQ)
2. **MoE models** (Mixtral, Qwen3-MoE, DeepSeek-V2/V3)
3. **Gemma, Phi, Mistral, Granite, and other families** they did not test
4. **Sub-1B territory** (below their smallest model)

Our current dataset covers 11 dense models (qwen3 0.6B–32B, llama3.2 1/3B,
llama3.1 8B, gemma2 2/9B, gemma4 26B). **One contributed run in any of the
four gap directions above is a real extension** to the published literature.

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

## Preview your contribution alongside baseline

After running `validate.py e9 --model-name <yours>`, drop the output JSON
into `experiments/contributed/` and run:

```bash
uv run python experiments/aggregate.py
```

You'll see a markdown table with your model merged into the cross-model
comparison. Useful to sanity-check your run before opening an issue or PR.

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
[`contributed/qwen3_5_27b.json`](contributed/qwen3_5_27b.json) for the
primary example output (fills the qwen3.5 9B→26B dense gap; shows zero
improvement from 9B to 27B, the kind of finding the extended sweep is
meant to surface).

## Open questions — the gaps PartialOrderEval did NOT cover

Zi et al. 2508.03678 tested Qwen2.5-Coder and Llama-3.x (dense) on HumanEval
and ParEval code tasks. The following questions are **genuinely open** because
they're outside that sweep:

- **Reasoning-RL models** (DeepSeek-R1-Distill, Qwen3-QwQ): does RL
  post-training flatten the vague→task_io gradient? A reasoning model that
  "thinks through" underspecified prompts should be less specificity-sensitive
  than same-base dense models. Untested.
- **MoE models** (Mixtral, Qwen3-MoE-A30B, DeepSeek-V2/V3): do they behave
  like their dense equivalent at total parameters, or at active parameters?
  PartialOrderEval only tested dense.
- **Mistral tokenizer family**: PartialOrderEval stayed within
  Qwen/Llama tokenizers. Does Mistral's different tokenizer shift the
  specificity threshold? Also untested.
- **Gemma, Phi, Granite, Yi**: these families are absent from the published
  sweep. Any contributed run adds a family to the matrix.
- **Sub-1B territory**: PartialOrderEval's smallest is 1B. Our data goes to
  0.6B. Does the U-curve (extra specificity *hurts* small models) appear at
  an even sharper angle below 1B?
- **Non-coding tasks**: PartialOrderEval uses HumanEval + ParEval (both code).
  The specificity gradient might be qualitatively different on NL, math, or
  multi-step reasoning tasks — ctxray scoring claims task generality but has
  only been calibrated on code. (This is a planned future experiment; one
  contributed run in non-coding territory would kickstart it.)

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
