# LV7 Test Suites

LV7 uses pytest as the execution layer and `configs/test_suites.json` as the suite manifest.
Use `training/run_test_suite.py` to rerun common groups and record suite usage.

## List Suites

```powershell
python training\run_test_suite.py --list
```

## Run A Suite

```powershell
python training\run_test_suite.py --suite fast
python training\run_test_suite.py --suite runtime
python training\run_test_suite.py --suite v1_5_baseline
python training\run_test_suite.py --suite benchmark_smoke
```

Pass extra pytest args after `--`:

```powershell
python training\run_test_suite.py --suite runtime -- -q -x
```

## Usage History

By default, suite runs append:

- `reports/test_suites/test_suite_history.jsonl`
- `reports/test_suites/test_suite_summary.json`

The summary tracks total recorded runs, recent runs, and the most-used suites.
Use `--no-record` for local checks that should not update history.

## Adding Tests

Add the pytest file under `tests/`, then add it to one or more suites in `configs/test_suites.json`.
Every suite path is validated by `tests/test_run_test_suite.py`.

## Benchmark Lane

`benchmark_smoke` is the current local benchmark lane. It covers the LV7 scoring and eval harness tests without pulling in external benchmark frameworks.

External AI benchmark projects should only be added when they have pinned inputs, deterministic scoring, and local commands that do not mutate LV7 artifacts by default.
