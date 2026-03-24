#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from mar_bench.optimizer import run_mutation_loop


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = run_mutation_loop(root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
