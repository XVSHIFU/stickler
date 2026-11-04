# Stickler #510 benchmark evidence

Run `uv sync --frozen` in a checkout containing the #510 implementation. Save `benchmark_stickler_510.py` in the checkout's parent directory, then run:

```sh
uv run --frozen python ../benchmark_stickler_510.py > ../benchmark_stickler_510.json
```

The script prints the actual imported package path and alternates the original edit-distance implementation from `cf907738` with RapidFuzz in the same process. Fixture creation is excluded, and full public outputs must be exactly equal before timing. Results use seven repeats. The JSON records the local test-only HEAD when measured; the two distance implementations are supplied explicitly by the script.

On Python 3.12.14 / RapidFuzz 3.14.3 / Linux / AMD EPYC 9V74:

| Scenario | Python DP median | RapidFuzz median | Speedup |
| --- | ---: | ---: | ---: |
| 200-key mapping, 18-character values | 11.323 ms | 2.053 ms | 5.51x |
| 20 line items, 30-key dictionaries | 675.990 ms | 154.511 ms | 4.38x |

Timings are fixture- and hardware-dependent, not a universal guarantee. This evidence branch is separate from the contribution PR to keep the production diff focused.
