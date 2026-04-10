"""Standalone launcher for E10 — use with nohup + caffeinate for background runs.

Usage:
    cd ~/projects/ctxray && \\
    nohup caffeinate -i uv run python experiments/run_e10_launcher.py \\
        > /tmp/e10.log 2>&1 &

Progress:
    tail -f /tmp/e10.log
    python3 -c "import json; d=json.load(open('.output/experiments/e10_checkpoint.json')); \\
                print(f'{d[\\\"total_cells\\\"]}/3000 cells done')"

Resume: just re-run. The checkpoint-resume loop skips completed cells.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate import MODELS, check_model, run_e10  # noqa: E402

E10_MODELS: list[str] = [
    "gpu_qcoder",      # qwen2.5-coder:1.5b — base E9 anchor
    "gpu_gemma4b",     # gemma3:4b         — mid dense
    "gpu_llama8b",     # llama3.1:8b       — fizzbuzz U-curve model
    "gpu_qwen9b",      # qwen3.5:9b        — cross-family (think:false)
    "gpu_phi4_14b",    # phi4:14b          — dense frontier
]


def main() -> None:
    # Pre-flight: all models reachable
    for mk in E10_MODELS:
        if not check_model(mk):
            print(f"ERROR: {MODELS[mk]['name']} not available at {MODELS[mk]['host']}")
            sys.exit(1)
    print(f"All {len(E10_MODELS)} models reachable. Starting E10 run with k=10.")
    run_e10(E10_MODELS, k=10)
    print("E10 run complete.")


if __name__ == "__main__":
    main()
