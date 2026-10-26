# WSL test baseline

This folder records how django-helpdesk's existing tests performed before changes to the project's CI or tests. Use it as a reference when comparing later runs.

## Run 01

Collected locally on 26 October 2026 in VS Code using WSL2, Python 3.12.3, Django 5.2.18, and coverage.py 7.17.0.

- Commit: `8c7b9ff92f018a394c6faa972e4328ad178b80b9`
- Tests: 503 total; 501 passed and 2 skipped. Exit code: 0.
- Time: 24 seconds for the full coverage command; Django reported 17.812 seconds for the test run.
- Statement coverage: 81.57%.
- Branch coverage: 67.13%.
- Combined statement and branch coverage: 78.44% (rounded to 78% in the text report).

## How it was collected

A Linux virtual environment was created with `python3 -m venv .venv` and activated with `source .venv/bin/activate`. Dependencies were installed with:

```bash
python -m pip install -e . --group test "Django~=5.2.0"
```

The existing `quicktest.py` suite was run with `PYTHONHASHSEED=0` under coverage.py. These were the main collection commands; test output and reports were saved in `run-01`:

```bash
export PYTHONHASHSEED=0
python -m coverage run quicktest.py
python -m coverage report
python -m coverage json
python -m coverage html
```

The full command was timed using Bash's `SECONDS` variable, and its exit code was recorded. Coverage uses the repository's existing `pyproject.toml` settings, including branch measurement and migration exclusions.

## Saved files

- `run-01/tests.log`: full test output and final test summary.
- `run-01/run-info.txt`: command exit code and elapsed time.
- `run-01/coverage.txt`, `coverage.json`, and `htmlcov/index.html`: text, JSON, and browsable coverage reports.
- `run-01/commit.txt`, `python.txt`, `packages.txt`, and `platform.txt`: code revision and environment, recorded using `git rev-parse HEAD`, `python --version`, `pip freeze`, and `uname -a`.
- `run-01/working-tree.txt`: output of `git status --short` before collection. It is empty because the working tree was clean.

Keep `run-01` as the original snapshot and save future results in separate folders such as `run-02`. This is one local run; CI timings and test stability need their own measurements.

## First CI run

The inherited GitHub Actions workflow ran on 26 October 2026. All nine Python/Django jobs passed their formatting checks and tests.

- [Pull request run](https://github.com/olivercatania/django-helpdesk-CICD/actions/runs/40388774400)
- [Run on main after merging](https://github.com/olivercatania/django-helpdesk-CICD/actions/runs/40389632013)

These runs record the CI baseline before changes to the workflow. The local WSL baseline remains in `run-01`.