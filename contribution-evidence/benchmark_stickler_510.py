"""Reproduce #510 ANLS timings without changing the checkout.

Run from the target checkout with its Python environment:
  .venv/bin/python ../benchmark_stickler_510.py > ../benchmark_stickler_510.json

Fixtures and model construction are outside timed regions. The two distance
implementations alternate each repeat; all other code and inputs stay identical.
"""

import inspect
import json
import platform
import statistics
import subprocess
import timeit
from pathlib import Path

import rapidfuzz
from rapidfuzz.distance import Levenshtein

import stickler
from stickler import ANLSStarComparator, ComparableField, ExactComparator, StructuredModel
from stickler.comparators.levenshtein import LevenshteinComparator


def original_dp(s1: str, s2: str) -> int:
    """Unchanged distance implementation from dev at cf907738."""
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2 + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(
                    1 + min((distances[i1], distances[i1 + 1], distances_[-1]))
                )
        distances = distances_
    return distances[-1]


def rapidfuzz_distance(s1: str, s2: str) -> int:
    return Levenshtein.distance(s1, s2)


class LineItem(StructuredModel):
    metadata: dict[str, str] = ComparableField(comparator=ANLSStarComparator())


class Document(StructuredModel):
    items: list[LineItem] = ComparableField()


def main():
    imported_path = inspect.getfile(stickler)
    checkout = Path(imported_path).resolve().parents[2]
    cpu_model = next(
        (line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
         if line.startswith("model name")),
        platform.processor(),
    )
    flat_truth = {f"key-{i:03d}": f"value-{i:03d}-original" for i in range(200)}
    flat_prediction = {key: value[:-1] + "1" for key, value in flat_truth.items()}
    line_truth = Document(items=[
        LineItem(metadata={f"key-{j:02d}": f"item-{i:02d}-value-{j:02d}" for j in range(30)})
        for i in range(20)
    ])
    line_prediction = Document(items=[
        LineItem(metadata={key: value + "x" for key, value in item.metadata.items()})
        for item in reversed(line_truth.items)
    ])
    anls = ANLSStarComparator()
    exact = ExactComparator()
    canonical_truth = json.dumps(flat_truth, sort_keys=True, separators=(",", ":"))
    canonical_prediction = json.dumps(flat_prediction, sort_keys=True, separators=(",", ":"))
    tasks = {
        "flat_200_keys": (lambda: anls.compare(flat_truth, flat_prediction), 20),
        "hungarian_20_items_30_keys": (lambda: line_truth.compare_with(line_prediction), 2),
        "exact_precomputed_canonical_json": (
            lambda: exact.compare(canonical_truth, canonical_prediction), 100000
        ),
    }
    original = LevenshteinComparator.__dict__["_levenshtein_distance"]
    implementations = {"python_dp": original_dp, "rapidfuzz": rapidfuzz_distance}
    results = {}
    try:
        for name, (task, number) in tasks.items():
            outputs = {}
            timings = {name: [] for name in implementations}
            for impl_name, impl in implementations.items():
                LevenshteinComparator._levenshtein_distance = staticmethod(impl)
                outputs[impl_name] = task()
            assert outputs["python_dp"] == outputs["rapidfuzz"], name
            for repeat in range(7):
                order = list(implementations)
                if repeat % 2:
                    order.reverse()
                for impl_name in order:
                    LevenshteinComparator._levenshtein_distance = staticmethod(implementations[impl_name])
                    timings[impl_name].append(timeit.timeit(task, number=number) / number * 1000)
            medians = {key: statistics.median(samples) for key, samples in timings.items()}
            output = outputs["rapidfuzz"]
            results[name] = {
                "iterations_per_repeat": number,
                "repeats": 7,
                "ms_per_call_samples": timings,
                "median_ms_per_call": medians,
                "speedup": medians["python_dp"] / medians["rapidfuzz"],
                "score": output["overall_score"] if isinstance(output, dict) else output,
                "exact_full_output_equal": True,
            }
    finally:
        LevenshteinComparator._levenshtein_distance = original
    print(json.dumps({
        "imported_stickler": imported_path,
        "checkout_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip(),
        "baseline_distance_from": "cf90773855035fa7ac3d8bd0932dbea3367dc151",
        "python": platform.python_version(),
        "rapidfuzz": rapidfuzz.__version__,
        "platform": platform.platform(),
        "cpu_model": cpu_model,
        "fixture": {
            "flat": "200 keys; value-NNN-original versus value-NNN-origina1 (18 chars)",
            "list": "20 LineItem models, each a 30-key dict; item-NN-value-NN (16 chars) versus same plus x; prediction list reversed",
            "timing": "Fixture/model/JSON construction excluded; public compare()/compare_with() calls; 7 alternating repeats; timeit disables GC inside each timing",
        },
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
