"""Concurrent simulated-device fleet campaign helpers."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable


def run_concurrently(jobs: Iterable[tuple[str, str]], workers: int,
                     runner: Callable[[str, str], dict]) -> list[dict]:
    """Run (device_id, scenario) jobs concurrently; results are returned in input order."""
    items = list(jobs)
    results: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(runner, device, scenario): index
                      for index, (device, scenario) in enumerate(items)}
        for future in as_completed(future_map):
            results[future_map[future]] = future.result()
    return [results[i] for i in range(len(items))]
