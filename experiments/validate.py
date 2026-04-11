"""
Assumption validation experiments for ctxray model-specific scoring.

Validates core hypotheses before building model-specific features:
  H1: ctxray score predicts output quality (E0 + E1)
  H2: Different models have different format preferences (E2)
  H4: Position bias exists and follows U-curve (E3)
  H5: Different models have different position curves (E3)
  H3: Compression tolerance is model-dependent (E4)

Usage:
    uv run python experiments/validate.py e0                # Sanity check
    uv run python experiments/validate.py e1                # Score vs Quality
    uv run python experiments/validate.py e2                # Format sensitivity
    uv run python experiments/validate.py e3                # Position sensitivity
    uv run python experiments/validate.py e4                # Compression tolerance
    uv run python experiments/validate.py e9                # Specificity gradient (PC GPU)
    uv run python experiments/validate.py all               # All experiments (local)
    uv run python experiments/validate.py e0 --model qwen3  # Pre-defined model key

External contributors — run against any Ollama model you have locally:
    uv run python experiments/validate.py e9 --model-name mistral:7b
    uv run python experiments/validate.py e9 --model-name phi4:14b --host http://localhost:11434

    --model-name   any name accepted by `ollama run` (e.g. mistral:7b, phi4:14b)
    --host         Ollama API base URL (default: http://localhost:11434)

    Results go to .output/experiments/e9_specificity_custom_<name>.json.
    See experiments/README.md for how to share results.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from statistics import mean

# Add project src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data import TASKS, TIERS, Task, TestCase, get_e0_pairs, get_e1_all, get_e9_prompts, SPECIFICITY_LEVELS

from ctxray.core.compress import compress_text
from ctxray.core.extractors import extract_features
from ctxray.core.scorer import get_tier, score_prompt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PC_GPU_HOST = "http://pc.tail43495e.ts.net:11434"

MODELS: dict[str, dict[str, str]] = {
    # Boundary-capability models (for E3/E4 position + compression experiments)
    "qcoder": {
        "name": "qwen2.5-coder:1.5b",
        "host": "http://localhost:11434",
    },
    "gemma1b": {
        "name": "gemma3:1b",
        "host": "http://localhost:11434",
    },
    # Original models (for E0/E1/E2 backward compat)
    "qwen3": {
        "name": "qwen3.5:9b",
        "host": "http://localhost:11434",
    },
    "gemma4": {
        "name": "gemma4:e4b",
        "host": "http://localhost:11434",
    },
    # PC GPU models (RTX 5070 Ti via Tailscale — for E7/E8/E9)
    "gpu_qcoder": {
        "name": "qwen2.5-coder:1.5b",
        "host": PC_GPU_HOST,
    },
    "gpu_gemma1b": {
        "name": "gemma3:1b",
        "host": PC_GPU_HOST,
    },
    "gpu_phi4": {
        "name": "phi4-mini:latest",
        "host": PC_GPU_HOST,
    },
    "gpu_gemma4b": {
        "name": "gemma3:4b",
        "host": PC_GPU_HOST,
    },
    # Mid-range and frontier models (for future cross-validation)
    "gpu_qwen9b": {
        "name": "qwen3.5:9b",
        "host": PC_GPU_HOST,
    },
    "gpu_llama8b": {
        "name": "llama3.1:8b",
        "host": PC_GPU_HOST,
    },
    "gpu_gemma26b": {
        "name": "gemma4:26b",
        "host": PC_GPU_HOST,
    },
    "gpu_phi4_14b": {
        "name": "phi4:14b",
        "host": PC_GPU_HOST,
    },
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / ".output" / "experiments"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------


def ollama_generate(
    model_key: str,
    prompt: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: int = 300,
) -> tuple[str, float]:
    """Call Ollama and return (response_text, elapsed_seconds)."""
    cfg = MODELS[model_key]
    url = f"{cfg['host']}/api/generate"

    wrapped = f"Respond with only Python code. No explanations.\n\n{prompt}"

    body: dict = {
        "model": cfg["name"],
        "prompt": wrapped,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    # Disable thinking for qwen3 reasoning models via Ollama native API
    # (text-flag /no_think is ignored by qwen3.5 — all tokens go to thinking
    # field, response comes back empty). Ollama 0.20+ supports `think: false`.
    # Check the real model name, not the internal key — contributor runs via
    # --model-name use the opaque key "custom" regardless of the model family.
    if "qwen" in cfg["name"].lower():
        body["think"] = False

    payload = json.dumps(body).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            text = data.get("response", "")
            # Legacy safety: strip any residual think tags in text body
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            return text, time.monotonic() - t0
    except Exception as e:
        return f"ERROR: {e}", time.monotonic() - t0


def check_model(model_key: str) -> bool:
    """Check if model is available."""
    cfg = MODELS[model_key]
    url = f"{cfg['host']}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            names = [m["name"] for m in data.get("models", [])]
            return cfg["name"] in names
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Code extraction and execution
# ---------------------------------------------------------------------------


def extract_function(response: str, func_name: str) -> str | None:
    """Extract Python function from model response."""
    # Try code block first
    for m in re.finditer(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL):
        code = m.group(1)
        if f"def {func_name}" in code:
            return code
    # Try raw response
    lines = response.split("\n")
    capture = []
    in_func = False
    for line in lines:
        if re.match(rf"\s*def {func_name}\s*\(", line):
            in_func = True
            capture = [line]
        elif in_func:
            if line.strip() == "" or line[0] in " \t":
                capture.append(line)
            else:
                break
    return "\n".join(capture) if capture else None


def run_test(code: str, func_name: str, test: TestCase) -> bool:
    """Execute code + test case, return True if output matches expected."""
    script = f"{code}\n\n_result = {test.call}\nprint(repr(_result))"
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        actual = result.stdout.strip()
        return actual == test.expected
    except Exception:
        return False


def evaluate_prompt(model_key: str, prompt_text: str, task: Task) -> dict:
    """Run model on prompt, test output, return result dict."""
    response, elapsed = ollama_generate(model_key, prompt_text)

    code = extract_function(response, task.func_name)
    if code is None:
        # Try the whole response as code
        code = response

    passed = 0
    total = len(task.tests)
    for tc in task.tests:
        if run_test(code, task.func_name, tc):
            passed += 1

    return {
        "pass_rate": passed / total if total else 0.0,
        "passed": passed,
        "total": total,
        "elapsed": round(elapsed, 1),
        "response_len": len(response),
        "code_extracted": code is not None and f"def {task.func_name}" in code,
    }


# ---------------------------------------------------------------------------
# ctxray scoring helper
# ---------------------------------------------------------------------------


def ctxray_score(text: str) -> dict:
    """Score a prompt with ctxray and return summary."""
    dna = extract_features(text, source="experiment", session_id="validate")
    breakdown = score_prompt(dna)
    return {
        "total": breakdown.total,
        "tier": get_tier(breakdown.total),
        "clarity": breakdown.clarity,
        "context": breakdown.context,
        "position": breakdown.position,
        "structure": breakdown.structure,
        "repetition": breakdown.repetition,
    }


# ---------------------------------------------------------------------------
# E0: Sanity Check
# ---------------------------------------------------------------------------


def run_e0(model_key: str) -> dict:
    """E0: 10 prompts (5 draft + 5 strong), verify quality difference."""
    print(f"\n{'=' * 60}")
    print(f"  E0: Sanity Check — {MODELS[model_key]['name']}")
    print(f"{'=' * 60}\n")

    pairs = get_e0_pairs()
    results = []

    for tier, prompt, task in pairs:
        score = ctxray_score(prompt)
        print(
            f"  [{tier:6s}] {task.name:20s} | ctxray={score['total']:5.1f} ({score['tier']:6s})",
            end="",
        )
        sys.stdout.flush()

        eval_result = evaluate_prompt(model_key, prompt, task)
        status = (
            "PASS"
            if eval_result["pass_rate"] == 1.0
            else ("PARTIAL" if eval_result["pass_rate"] > 0 else "FAIL")
        )
        print(
            f" | {eval_result['passed']}/{eval_result['total']} {status} | {eval_result['elapsed']:.1f}s"
        )

        results.append(
            {
                "tier": tier,
                "task": task.name,
                "prompt": prompt[:80],
                "ctxray_score": score["total"],
                "ctxray_tier": score["tier"],
                "pass_rate": eval_result["pass_rate"],
                **eval_result,
            }
        )

    # Analyze
    draft_rates = [r["pass_rate"] for r in results if r["tier"] == "draft"]
    strong_rates = [r["pass_rate"] for r in results if r["tier"] == "strong"]
    draft_avg = mean(draft_rates)
    strong_avg = mean(strong_rates)

    print(f"\n  {'─' * 50}")
    print(f"  Draft  avg pass_rate: {draft_avg:.2f}")
    print(f"  Strong avg pass_rate: {strong_avg:.2f}")
    print(f"  Delta:                {strong_avg - draft_avg:+.2f}")

    if strong_avg > draft_avg:
        print("\n  RESULT: Strong prompts produce better code. Proceed to E1.")
    elif strong_avg == draft_avg == 1.0:
        print("\n  RESULT: Both tiers pass all tests. Model may be too capable")
        print("          for these tasks. Consider harder tasks or weaker model.")
    else:
        print("\n  RESULT: No quality difference detected. Investigate further.")

    output = {
        "model": model_key,
        "results": results,
        "draft_avg": draft_avg,
        "strong_avg": strong_avg,
    }
    _save(output, f"e0_{_output_tag(model_key)}.json")
    return output


# ---------------------------------------------------------------------------
# E1: Score ↔ Quality Correlation
# ---------------------------------------------------------------------------


def run_e1(model_key: str) -> dict:
    """E1: 30 prompts across 5 tiers. Compute correlation."""
    print(f"\n{'=' * 60}")
    print(f"  E1: Score vs Quality Correlation — {MODELS[model_key]['name']}")
    print(f"{'=' * 60}\n")

    all_prompts = get_e1_all()
    results = []

    for i, (tier, prompt, task) in enumerate(all_prompts):
        score = ctxray_score(prompt)
        print(f"  [{i + 1:2d}/30] {tier:6s} {task.name:20s} | ctxray={score['total']:5.1f}", end="")
        sys.stdout.flush()

        eval_result = evaluate_prompt(model_key, prompt, task)
        print(f" | pass_rate={eval_result['pass_rate']:.2f} | {eval_result['elapsed']:.1f}s")

        results.append(
            {
                "tier": tier,
                "task": task.name,
                "ctxray_score": score["total"],
                "pass_rate": eval_result["pass_rate"],
            }
        )

    # Compute correlation
    scores = [r["ctxray_score"] for r in results]
    rates = [r["pass_rate"] for r in results]

    pearson_r = _pearson(scores, rates)
    spearman_rho = _spearman(scores, rates)

    # Per-tier summary
    print(f"\n  {'─' * 50}")
    print("  Per-tier avg pass_rate:")
    for tier in TIERS:
        tier_rates = [r["pass_rate"] for r in results if r["tier"] == tier]
        tier_scores = [r["ctxray_score"] for r in results if r["tier"] == tier]
        print(f"    {tier:6s}: score={mean(tier_scores):5.1f}  pass_rate={mean(tier_rates):.2f}")

    print(f"\n  Pearson r:  {pearson_r:+.3f}")
    print(f"  Spearman p: {spearman_rho:+.3f}")

    if pearson_r > 0.5:
        print("\n  GO: Strong correlation. Static scoring predicts quality.")
    elif pearson_r > 0.3:
        print("\n  CAUTION: Moderate correlation. Weights need tuning.")
    else:
        print("\n  NO-GO: Weak correlation. Re-examine scoring methodology.")

    output = {
        "model": model_key,
        "results": results,
        "pearson_r": pearson_r,
        "spearman_rho": spearman_rho,
    }
    _save(output, f"e1_{_output_tag(model_key)}.json")
    return output


# ---------------------------------------------------------------------------
# E2: Format Sensitivity
# ---------------------------------------------------------------------------

_XML_TEMPLATE = (
    "<task>\n{task}\n</task>\n\n"
    "<constraints>\n{constraints}\n</constraints>\n\n"
    "<examples>\n{examples}\n</examples>"
)
_MD_TEMPLATE = "## Task\n{task}\n\n## Constraints\n{constraints}\n\n## Examples\n{examples}"
_YAML_TEMPLATE = "task: |\n  {task}\nconstraints: |\n  {constraints}\nexamples: |\n  {examples}"
_PLAIN_TEMPLATE = "{task}\n\n{constraints}\n\n{examples}"


def _make_format_variants(task: Task) -> dict[str, str]:
    """Take the 'good' prompt and reformat into 4 formats with same content."""
    # Extract components from the strong prompt
    prompt = task.prompts["strong"]
    # Simple decomposition: first line = task, bullet points = constraints, last lines = examples
    lines = prompt.strip().split("\n")
    task_line = lines[0] if lines else ""
    constraints_lines = [l for l in lines if l.startswith("- ")]
    example_lines = [
        l for l in lines if "example" in l.lower() or "->" in l or "returns" in l.lower()
    ]

    task_text = task_line.strip("`").strip()
    constraints_text = (
        "\n".join(constraints_lines) if constraints_lines else "No specific constraints."
    )
    examples_text = "\n".join(example_lines) if example_lines else "No examples."

    return {
        "xml": _XML_TEMPLATE.format(
            task=task_text, constraints=constraints_text, examples=examples_text
        ),
        "markdown": _MD_TEMPLATE.format(
            task=task_text, constraints=constraints_text, examples=examples_text
        ),
        "yaml": _YAML_TEMPLATE.format(
            task=task_text, constraints=constraints_text, examples=examples_text
        ),
        "plain": _PLAIN_TEMPLATE.format(
            task=task_text, constraints=constraints_text, examples=examples_text
        ),
    }


def run_e2(model_keys: list[str]) -> dict:
    """E2: Same content in 4 formats, 2 models. Measure format preference."""
    print(f"\n{'=' * 60}")
    print("  E2: Format Sensitivity")
    print(f"{'=' * 60}\n")

    results = []
    # Model-first loop to minimize Ollama model swaps
    for model_key in model_keys:
        print(f"  --- Model: {MODELS[model_key]['name']} ---")
        for task in TASKS:
            variants = _make_format_variants(task)
            for fmt_name, fmt_prompt in variants.items():
                print(f"  {task.name:20s} | {fmt_name:8s} | {model_key:6s}", end="")
                sys.stdout.flush()
                eval_result = evaluate_prompt(model_key, fmt_prompt, task)
                print(
                    f" | pass_rate={eval_result['pass_rate']:.2f} | {eval_result['elapsed']:.1f}s"
                )
                results.append(
                    {
                        "task": task.name,
                        "format": fmt_name,
                        "model": model_key,
                        "pass_rate": eval_result["pass_rate"],
                        "elapsed": eval_result["elapsed"],
                    }
                )

    # Analyze: per model, which format wins?
    print(f"\n  {'─' * 50}")
    print("  Format preference by model (avg pass_rate):\n")
    for model_key in model_keys:
        print(f"  {model_key}:")
        for fmt in ["xml", "markdown", "yaml", "plain"]:
            rates = [
                r["pass_rate"] for r in results if r["model"] == model_key and r["format"] == fmt
            ]
            avg = mean(rates) if rates else 0
            bar = "█" * int(avg * 20)
            print(f"    {fmt:10s}: {avg:.2f} {bar}")
        print()

    output = {"models": model_keys, "results": results}
    _save(output, "e2_format.json")
    return output


# ---------------------------------------------------------------------------
# E3: Position Sensitivity
# ---------------------------------------------------------------------------


# Critical constraints per task — the one piece of info that determines test pass/fail
_CRITICAL_CONSTRAINTS: dict[str, str] = {
    "fizzbuzz": "IMPORTANT: Check divisibility by 15 BEFORE checking 3 or 5 separately. Numbers divisible by both 3 and 5 must return 'FizzBuzz', not 'Fizz' or 'Buzz'.",
    "reverse_words": "IMPORTANT: You must strip all leading and trailing whitespace, and collapse multiple consecutive spaces into a single space between words.",
    "flatten": "IMPORTANT: The function must handle arbitrary nesting depth recursively. A nested list like [1, [2, [3, [4]]]] must become [1, 2, 3, 4].",
    "two_sum": "IMPORTANT: Return the result as a tuple (i, j) where i < j, not a list. The indices must be ordered smallest first.",
    "run_length_encode": "IMPORTANT: Each element in the result must be a tuple of (character, count) where character is a single-char string and count is an integer. Example: ('a', 3) not ['a', 3].",
    "chunk_list": "IMPORTANT: The last chunk may have fewer than n elements. Do not pad it. chunk_list([1,2,3,4,5], 2) returns [[1,2],[3,4],[5]] not [[1,2],[3,4],[5,None]].",
}

# Relevant context blocks — realistic code documentation to create 4K+ token prompts.
# Each block is ~100-150 words. 15 blocks ≈ 1500-2000 words ≈ 3000-4000 tokens.
_CONTEXT_BLOCKS: list[str] = [
    "This function will be used in a data processing pipeline that handles both small and large inputs. Performance matters but correctness is the top priority. The pipeline processes batches of 10,000+ items during peak hours, so the function should be efficient but not at the cost of readability.",
    "The codebase follows PEP 8 conventions. Type hints are appreciated but not required. The function should work with Python 3.10+. We use pytest for testing and ruff for linting. All public functions need docstrings.",
    "Other team members will maintain this code, so readability is important. Use descriptive variable names and add a brief docstring explaining the function's purpose. Avoid clever one-liners that sacrifice clarity.",
    "The function should handle empty inputs gracefully without raising exceptions. An empty input should return an appropriate empty result. This is a hard requirement from the API contract.",
    "This is part of a utility library that is well-tested. Your implementation will be validated against a comprehensive test suite covering normal and edge cases. The CI pipeline runs all tests on every push.",
    "Previous implementations had bugs with boundary conditions. Pay special attention to off-by-one errors and the handling of single-element inputs. The QA team specifically tests these scenarios.",
    "The module already imports the following: os, sys, json, re, typing, dataclasses, pathlib, collections, itertools, functools. You can use any of these without additional imports. Do not add external dependencies.",
    "The function will be called from both synchronous and asynchronous contexts. It should be a regular synchronous function — the async wrapper is handled by the caller. Do not use async/await in your implementation.",
    "Memory usage should be reasonable. For large inputs, prefer generators or iterative approaches over building large intermediate data structures. However, the final return value can be a fully materialized list.",
    "The function signature and return type must match the specification exactly. The test suite uses isinstance checks and compares return values with == operator. Do not return a subclass or wrapper type.",
    "Error handling: do not catch generic exceptions. If invalid input is provided (wrong type, negative numbers where positive expected), let Python's built-in TypeError or ValueError propagate naturally.",
    "Thread safety is not required — the function will only be called from a single thread. You do not need locks, queues, or any synchronization primitives.",
    "Documentation standards: the docstring should include a one-line summary, a blank line, then a longer description if needed. Parameters and return value should be documented using Google-style docstrings.",
    "The function will be deployed to production after code review. Reviewers will check for: correctness, edge case handling, readability, and adherence to the coding standards described in this document.",
    "Performance benchmark: the function should complete in under 10ms for inputs of size 1000. Do not use recursion for problems that can be solved iteratively, as Python's recursion limit is 1000 by default.",
]


def _make_position_variants(task: Task) -> dict[str, str]:
    """Create 5 position variants by moving a CRITICAL CONSTRAINT through context.

    Redesigned from v1: the full task description is always present.
    Only one critical constraint moves between 5 positions in a block
    of relevant (non-filler) context paragraphs.
    """
    base = task.prompts["strong"]  # full task description, always at top
    critical = _CRITICAL_CONSTRAINTS.get(task.name, "")
    if not critical:
        return {}

    # Use ALL 15 context blocks for ~4K token prompt (position bias needs length)
    blocks = list(_CONTEXT_BLOCKS)
    n = len(blocks)

    variants = {}
    for pos_name, insert_idx in [
        ("0%", 0),
        ("25%", n // 4),
        ("50%", n // 2),
        ("75%", 3 * n // 4),
        ("100%", n),
    ]:
        parts = list(blocks)
        parts.insert(insert_idx, critical)
        context_section = "\n\n".join(parts)
        variants[pos_name] = f"{base}\n\n{context_section}"

    return variants


def run_e3(model_keys: list[str]) -> dict:
    """E3: Key instruction at 5 positions, 2 models. Plot U-curves."""
    print(f"\n{'=' * 60}")
    print("  E3: Position Sensitivity")
    print(f"{'=' * 60}\n")

    results = []
    # Model-first loop to minimize Ollama model swaps
    for model_key in model_keys:
        print(f"  --- Model: {MODELS[model_key]['name']} ---")
        for task in TASKS[:4]:  # 4 tasks to keep runtime reasonable
            variants = _make_position_variants(task)
            for pos_name, pos_prompt in variants.items():
                print(f"  {task.name:20s} | pos={pos_name:4s} | {model_key:6s}", end="")
                sys.stdout.flush()
                eval_result = evaluate_prompt(model_key, pos_prompt, task)
                print(
                    f" | pass_rate={eval_result['pass_rate']:.2f} | {eval_result['elapsed']:.1f}s"
                )
                results.append(
                    {
                        "task": task.name,
                        "position": pos_name,
                        "model": model_key,
                        "pass_rate": eval_result["pass_rate"],
                    }
                )

    # Analyze: position curve per model
    print(f"\n  {'─' * 50}")
    print("  Position curves (avg pass_rate):\n")
    positions = ["0%", "25%", "50%", "75%", "100%"]
    for model_key in model_keys:
        print(f"  {model_key}:")
        for pos in positions:
            rates = [
                r["pass_rate"] for r in results if r["model"] == model_key and r["position"] == pos
            ]
            avg = mean(rates) if rates else 0
            bar = "█" * int(avg * 20)
            print(f"    {pos:4s}: {avg:.2f} {bar}")
        print()

    output = {"models": model_keys, "results": results}
    _save(output, "e3_position.json")
    return output


# ---------------------------------------------------------------------------
# E4: Compression Tolerance
# ---------------------------------------------------------------------------


def run_e4(model_keys: list[str]) -> dict:
    """E4: Original vs compressed prompts, 2 models."""
    print(f"\n{'=' * 60}")
    print("  E4: Compression Tolerance")
    print(f"{'=' * 60}\n")

    # Verbose filler injected into prompts to create real compression opportunity.
    # These are the kind of hedging/filler phrases ctxray's compress engine removes.
    _VERBOSE_FILLERS = [
        "I was wondering if you could perhaps help me with this task. ",
        "Basically, what I need is essentially the following. ",
        "It would be really great if you could make sure to carefully consider all aspects. ",
        "Please note that this is quite important and I would appreciate your attention to detail. ",
        "In terms of the implementation, I think it would be best if you could try to ",
        "make it as clean and efficient as possible, if that makes sense. ",
        "I should mention that we've been having some issues with this kind of thing lately. ",
        "So basically, to summarize what I'm looking for, I need you to ",
        "just go ahead and implement the following functionality. ",
        "I hope this makes sense and please let me know if you have any questions about it. ",
    ]

    results = []
    # Precompute compression variants: inject verbose filler then compress
    compression_pairs = []
    for task in TASKS:
        base = task.prompts["strong"]
        # Inject filler before and after the core prompt (~200 extra words)
        verbose = "".join(_VERBOSE_FILLERS) + "\n\n" + base + "\n\n" + "".join(_VERBOSE_FILLERS[:5])
        compressed_result = compress_text(verbose)
        savings = compressed_result.savings_pct
        if savings >= 3.0:  # only test if meaningful compression occurred
            compression_pairs.append(
                (task, "verbose", verbose, compressed_result.compressed, savings)
            )
            print(
                f"  [prep] {task.name:20s} | {len(verbose):4d}→{len(compressed_result.compressed):4d} chars | savings={savings:.1f}%"
            )

    # Model-first loop to minimize Ollama model swaps
    for model_key in model_keys:
        print(f"  --- Model: {MODELS[model_key]['name']} ---")
        for task, tier, original, compressed, savings in compression_pairs:
            for variant_name, variant_text in [("original", original), ("compressed", compressed)]:
                print(
                    f"  {task.name:15s} {tier:6s} | {variant_name:10s} | {model_key:6s}",
                    end="",
                )
                sys.stdout.flush()
                eval_result = evaluate_prompt(model_key, variant_text, task)
                print(
                    f" | pass_rate={eval_result['pass_rate']:.2f} | {eval_result['elapsed']:.1f}s"
                )
                results.append(
                    {
                        "task": task.name,
                        "tier": tier,
                        "variant": variant_name,
                        "model": model_key,
                        "pass_rate": eval_result["pass_rate"],
                        "savings_pct": savings if variant_name == "compressed" else 0.0,
                    }
                )

    # Analyze
    print(f"\n  {'─' * 50}")
    print("  Compression impact by model:\n")
    for model_key in model_keys:
        orig_rates = [
            r["pass_rate"]
            for r in results
            if r["model"] == model_key and r["variant"] == "original"
        ]
        comp_rates = [
            r["pass_rate"]
            for r in results
            if r["model"] == model_key and r["variant"] == "compressed"
        ]
        if orig_rates and comp_rates:
            orig_avg = mean(orig_rates)
            comp_avg = mean(comp_rates)
            delta = comp_avg - orig_avg
            print(f"  {model_key}:")
            print(f"    Original:   {orig_avg:.2f}")
            print(f"    Compressed: {comp_avg:.2f}")
            print(
                f"    Delta:      {delta:+.2f} {'(compression helps)' if delta > 0 else '(compression hurts)' if delta < 0 else '(no effect)'}"
            )
            print()

    output = {"models": model_keys, "results": results}
    _save(output, "e4_compression.json")
    return output


# ---------------------------------------------------------------------------
# E9: Specificity Gradient
# ---------------------------------------------------------------------------


def run_e9(model_keys: list[str], k: int = 3) -> dict:
    """E9: Specificity gradient — isolate specificity from structure.

    4 specificity levels x 4 tasks x N models x k repetitions.
    All prompts are plain text (no role, no markdown). Only the amount
    of task detail varies.
    """
    print(f"\n{'=' * 60}")
    print(f"  E9: Specificity Gradient (k={k})")
    print(f"  Models: {', '.join(MODELS[mk]['name'] for mk in model_keys)}")
    print(f"{'=' * 60}\n")

    e9_prompts = get_e9_prompts()

    # Show ctxray scores for each prompt
    print("  ctxray scores per specificity level:")
    for level, task_name, prompt, _task in e9_prompts:
        sc = ctxray_score(prompt)
        print(f"    {task_name:20s} {level:10s} → {sc['total']:5.1f} ({sc['tier']})")
    print()

    results = []

    # Model-first loop to minimize Ollama model swaps
    for model_key in model_keys:
        model_name = MODELS[model_key]["name"]
        print(f"  --- Model: {model_name} ---")

        for level, task_name, prompt, task in e9_prompts:
            pass_rates = []
            for rep in range(k):
                eval_result = evaluate_prompt(model_key, prompt, task)
                pass_rates.append(eval_result["pass_rate"])

            avg_rate = mean(pass_rates)
            status = (
                "PASS" if avg_rate >= 0.9
                else ("PARTIAL" if avg_rate > 0.1 else "FAIL")
            )
            print(
                f"    {task_name:20s} {level:10s} | "
                f"k={k}: {' '.join(f'{r:.2f}' for r in pass_rates)} | "
                f"avg={avg_rate:.2f} {status}"
            )
            sys.stdout.flush()

            results.append({
                "task": task_name,
                "level": level,
                "model": model_key,
                "model_name": model_name,
                "pass_rates": pass_rates,
                "avg_pass_rate": avg_rate,
                "ctxray_score": ctxray_score(prompt)["total"],
                "prompt_len": len(prompt),
            })

    # ── Analysis ──
    print(f"\n  {'─' * 60}")
    print("  Specificity impact by model:\n")

    for model_key in model_keys:
        model_name = MODELS[model_key]["name"]
        print(f"  {model_name}:")
        for level in SPECIFICITY_LEVELS:
            rates = [
                r["avg_pass_rate"]
                for r in results
                if r["model"] == model_key and r["level"] == level
            ]
            if rates:
                avg = mean(rates)
                print(f"    {level:10s}: {avg:.2f}")
        # Delta vague → full
        vague_rates = [
            r["avg_pass_rate"]
            for r in results
            if r["model"] == model_key and r["level"] == "vague"
        ]
        full_rates = [
            r["avg_pass_rate"]
            for r in results
            if r["model"] == model_key and r["level"] == "full_spec"
        ]
        if vague_rates and full_rates:
            delta = mean(full_rates) - mean(vague_rates)
            print(f"    {'delta':10s}: {delta:+.2f} (vague → full_spec)")
        print()

    # Cross-model summary
    print(f"  {'─' * 60}")
    print("  Cross-model specificity gradient:\n")
    print(f"    {'Level':<12s}", end="")
    for mk in model_keys:
        print(f"  {MODELS[mk]['name']:>12s}", end="")
    print()
    for level in SPECIFICITY_LEVELS:
        print(f"    {level:<12s}", end="")
        for mk in model_keys:
            rates = [
                r["avg_pass_rate"]
                for r in results
                if r["model"] == mk and r["level"] == level
            ]
            avg = mean(rates) if rates else 0
            print(f"  {avg:>12.2f}", end="")
        print()

    # Serialize with real model names (not internal keys) so contributed
    # runs are self-describing and can be aggregated without the MODELS dict.
    serialized_models = [MODELS[mk]["name"] for mk in model_keys]
    output = {
        "experiment": "e9_specificity",
        "k": k,
        "models": serialized_models,
        "total_calls": len(results) * k,
        "results": results,
    }
    # Use model-range suffix to avoid overwriting previous runs.
    # Custom contributor runs get their own sanitized-name suffix so multiple
    # contributions coexist in .output/experiments/.
    if len(model_keys) == 1 and MODELS[model_keys[0]].get("is_custom"):
        suffix = _output_tag(model_keys[0])
    elif any("26b" in MODELS[mk]["name"] or "27b" in MODELS[mk]["name"] for mk in model_keys):
        suffix = "frontier"
    elif any("9b" in MODELS[mk]["name"] or "8b" in MODELS[mk]["name"] for mk in model_keys):
        suffix = "midrange"
    else:
        suffix = "small"
    _save(output, f"e9_specificity_{suffix}.json")
    return output


# ---------------------------------------------------------------------------
# E10: Specificity Decomposition (10 tasks × 6 levels, checkpoint-resumable)
# ---------------------------------------------------------------------------


def _save_e10_checkpoint(
    path: Path,
    results: list[dict],
    model_keys: list[str],
    k: int,
) -> None:
    """Write E10 checkpoint atomically (tmp then rename)."""
    data = {
        "experiment": "e10_specificity",
        "k": k,
        "models": model_keys,
        "total_cells": len(results),
        "completed_cells": results,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def run_e10(
    model_keys: list[str],
    *,
    k: int = 10,
    checkpoint_path: Path | None = None,
) -> dict:
    """E10: Specificity decomposition — 10 tasks × 6 levels with resume.

    Decomposes the old E9 full_spec level into three additive variants:
      - task_io_constraints: task_io + explicit evaluation-order constraints
      - task_io_edge       : task_io + edge case mentions
      - full_spec          : task_io + both

    Writes the checkpoint after every completed (model, task, level) cell so
    an interrupted run can resume without reprocessing completed cells.
    """
    from data_e10 import (
        E10_ALL_TASKS,
        E10_LEVELS,
        E10_PROMPTS,
        E10_TAGS,
        get_e10_prompts,
    )

    if checkpoint_path is None:
        # Custom contributor runs get their own checkpoint so they don't
        # collide with the built-in multi-model E10 run.
        if len(model_keys) == 1 and MODELS[model_keys[0]].get("is_custom"):
            checkpoint_path = (
                OUTPUT_DIR / f"e10_checkpoint_{_output_tag(model_keys[0])}.json"
            )
        else:
            checkpoint_path = OUTPUT_DIR / "e10_checkpoint.json"

    # Resume from existing checkpoint if present
    completed: set[tuple[str, str, str]] = set()
    all_results: list[dict] = []
    if checkpoint_path.exists():
        try:
            existing = json.loads(checkpoint_path.read_text())
            all_results = list(existing.get("completed_cells", []))
            completed = {
                (r["model"], r["task"], r["level"]) for r in all_results
            }
            print(f"  Resuming from checkpoint: {len(completed)} cells already done")
        except Exception as e:  # noqa: BLE001
            print(f"  Warning: checkpoint load failed ({e}); starting fresh")

    e10_prompts = get_e10_prompts()
    total_cells = len(model_keys) * len(e10_prompts)

    print(f"\n{'=' * 60}")
    print(f"  E10: Specificity Decomposition (k={k})")
    print(f"  Models: {', '.join(MODELS[mk]['name'] for mk in model_keys)}")
    print(f"  {len(E10_ALL_TASKS)} tasks × {len(E10_LEVELS)} levels × k={k}")
    print(f"  Total cells: {total_cells} (remaining: {total_cells - len(completed)})")
    print(f"  Checkpoint: {checkpoint_path}")
    print(f"{'=' * 60}\n")

    if not completed:
        # First run: print ctxray scores once as sanity check
        print("  ctxray scores per (task, level):")
        for task in E10_ALL_TASKS:
            tag = E10_TAGS[task.name]
            for level in E10_LEVELS:
                prompt = E10_PROMPTS[task.name][level]
                sc = ctxray_score(prompt)
                print(
                    f"    {task.name:<22} [{tag[:7]:<7}] {level:<22} → "
                    f"{sc['total']:5.1f} ({sc['tier']})"
                )
        print()

    # Model-first outer loop to minimize Ollama model swaps
    for model_key in model_keys:
        model_name = MODELS[model_key]["name"]
        print(f"  --- Model: {model_name} ---")

        for level, task_name, prompt, task in e10_prompts:
            cell_key = (model_key, task_name, level)
            if cell_key in completed:
                continue

            pass_rates = []
            for _rep in range(k):
                eval_result = evaluate_prompt(model_key, prompt, task)
                pass_rates.append(eval_result["pass_rate"])

            avg_rate = mean(pass_rates)
            sc_total = ctxray_score(prompt)["total"]
            row = {
                "model": model_key,
                "model_name": model_name,
                "task": task_name,
                "tag": E10_TAGS[task_name],
                "level": level,
                "pass_rates": pass_rates,
                "avg_pass_rate": avg_rate,
                "min_pass_rate": min(pass_rates),
                "max_pass_rate": max(pass_rates),
                "ctxray_score": sc_total,
                "prompt_len": len(prompt),
                "k": k,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            all_results.append(row)
            completed.add(cell_key)

            status = (
                "PASS" if avg_rate >= 0.9
                else ("PARTIAL" if avg_rate > 0.1 else "FAIL")
            )
            done = len(completed)
            print(
                f"  [{done:>4}/{total_cells}] {model_name:<22} "
                f"{task_name:<22} {level:<22} k={k} avg={avg_rate:.2f} {status}"
            )
            sys.stdout.flush()

            # Atomic checkpoint after every cell
            _save_e10_checkpoint(checkpoint_path, all_results, model_keys, k)

    print(f"\n  E10 complete: {len(all_results)} cells saved to {checkpoint_path}")
    return {"completed_cells": all_results}


# ---------------------------------------------------------------------------
# Statistics helpers (stdlib only, no scipy needed)
# ---------------------------------------------------------------------------


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(x)
    if n < 3:
        return 0.0
    mx, my = mean(x), mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den_x = sum((xi - mx) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - my) ** 2 for yi in y) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def _spearman(x: list[float], y: list[float]) -> float:
    """Spearman rank correlation."""

    def _rank(vals: list[float]) -> list[float]:
        sorted_vals = sorted(enumerate(vals), key=lambda t: t[1])
        ranks = [0.0] * len(vals)
        for rank, (idx, _) in enumerate(sorted_vals, 1):
            ranks[idx] = float(rank)
        return ranks

    return _pearson(_rank(x), _rank(y))


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _sanitize_model_name(name: str) -> str:
    """Turn 'mistral:7b-instruct' into 'mistral_7b_instruct' for filenames."""
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()


def _output_tag(model_key: str) -> str:
    """Return a filename-safe tag for a model key.

    For pre-defined keys (qcoder, gpu_qwen9b, ...) returns the key as-is so
    existing output filenames stay stable. For contributor-injected custom
    entries, returns ``custom_<sanitized-model-name>`` so multiple contributors
    don't overwrite each other's results.
    """
    cfg = MODELS.get(model_key, {})
    if cfg.get("is_custom"):
        return f"custom_{_sanitize_model_name(cfg['name'])}"
    return model_key


def _save(data: dict, filename: str) -> None:
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n  Results saved: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(args: list[str]) -> tuple[str, str, str | None, str | None]:
    """Parse CLI args. Returns (experiment, model_key, custom_name, custom_host)."""
    experiment = args[0]
    model_key = "qcoder"  # default: boundary model
    custom_name: str | None = None
    custom_host: str | None = None

    i = 1
    while i < len(args):
        a = args[i]
        if a == "--model" and i + 1 < len(args):
            model_key = args[i + 1]
            i += 2
        elif a == "--model-name" and i + 1 < len(args):
            custom_name = args[i + 1]
            i += 2
        elif a == "--host" and i + 1 < len(args):
            custom_host = args[i + 1]
            i += 2
        else:
            i += 1

    return experiment, model_key, custom_name, custom_host


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    experiment, model_key, custom_name, custom_host = _parse_args(args)

    # Contributor path: --model-name <n> [--host <url>] injects a custom entry
    # into MODELS and makes it the target for single-model experiments.
    if custom_name is not None:
        host = custom_host or "http://localhost:11434"
        MODELS["custom"] = {
            "name": custom_name,
            "host": host,
            "is_custom": True,
        }
        model_key = "custom"
        print(f"  Custom model: {custom_name} @ {host}")
    elif custom_host is not None:
        print("  ERROR: --host requires --model-name")
        sys.exit(1)

    # Boundary models for E3/E4 (fast, at the capability threshold)
    both_models = ["qcoder", "gemma1b"]

    # GPU models for the built-in E9/E10 multi-model runs (PC via Tailscale,
    # not reachable by external contributors — they should use --model-name).
    gpu_models = ["gpu_qcoder", "gpu_gemma1b", "gpu_phi4", "gpu_gemma4b"]

    # Select models for each experiment, preferring the injected custom entry
    # when the contributor provided --model-name.
    using_custom = model_key == "custom"

    if experiment == "e9":
        e9_models = ["custom"] if using_custom else gpu_models
        check_keys = e9_models
    elif experiment == "e9-frontier":
        e9_models = (
            ["custom"] if using_custom else ["gpu_qwen9b", "gpu_llama8b", "gpu_gemma26b"]
        )
        check_keys = e9_models
    elif experiment == "e10":
        e10_models = (
            ["custom"]
            if using_custom
            else ["gpu_qcoder", "gpu_gemma4b", "gpu_llama8b", "gpu_qwen9b", "gpu_phi4_14b"]
        )
        check_keys = e10_models
    elif experiment in ("e2", "e3", "e4"):
        # Multi-model dense experiments: custom runs solo against itself.
        models_for_exp = ["custom"] if using_custom else both_models
        check_keys = models_for_exp
    elif experiment in ("e0", "e1"):
        check_keys = [model_key]
    else:
        check_keys = both_models

    for mk in check_keys:
        if not check_model(mk):
            print(f"  ERROR: Model {MODELS[mk]['name']} not available at {MODELS[mk]['host']}")
            print(f"  Available models: check with curl {MODELS[mk]['host']}/api/tags")
            sys.exit(1)

    if experiment == "e0":
        run_e0(model_key)
    elif experiment == "e1":
        run_e1(model_key)
    elif experiment == "e2":
        run_e2(models_for_exp)
    elif experiment == "e3":
        run_e3(models_for_exp)
    elif experiment == "e4":
        run_e4(models_for_exp)
    elif experiment == "e9":
        run_e9(e9_models)
    elif experiment == "e9-frontier":
        run_e9(e9_models)
    elif experiment == "e10":
        run_e10(e10_models, k=10)
    elif experiment == "all":
        run_e0(model_key)
        run_e1(model_key)
        run_e2(both_models)
        run_e3(both_models)
        run_e4(both_models)
    else:
        print(f"  Unknown experiment: {experiment}")
        print("  Available: e0, e1, e2, e3, e4, e9, e9-frontier, e10, all")
        sys.exit(1)


if __name__ == "__main__":
    main()
