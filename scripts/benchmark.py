from __future__ import annotations

import time
from pathlib import Path

from alp.format import parse_module
from alp.vm import run_module


def bench(path: Path, iterations: int) -> float:
    module = parse_module(path.read_bytes())
    start = time.perf_counter()
    for _ in range(iterations):
        run_module(module)
    end = time.perf_counter()
    return end - start


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sample = root / "samples" / "add.alp"
    iterations = 50000
    elapsed = bench(sample, iterations)
    print(f"program={sample.name} iterations={iterations} elapsed_s={elapsed:.6f}")
    print(f"ops_per_sec={iterations/elapsed:.2f}")


if __name__ == "__main__":
    main()
