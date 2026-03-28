@_:
  just --list

_require-uv:
  @uv --version > /dev/null || (echo "Please install uv: https://docs.astral.sh/uv/" && exit 1)

_require-hatch:
  @hatch --version > /dev/null || (echo "Please install hatch: uv tool install hatch" && exit 1)

# check code style and potential issues
lint: _require-uv
  uv run ruff check .
  uv run rattle lint .

# format code
format: _require-uv
  uv run ruff format .

# fix automatically fixable linting issues
fix: _require-uv
  uv run ruff check --fix .
  uv run rattle fix --automatic .

# run tests across all supported Python versions
test: _require-hatch
  hatch run test:test

# run only the Rattle lint rules against the repository
rattle-lint: _require-uv
  uv run rattle lint .

# apply automatic fixes from the Rattle rule pack
rattle-fix: _require-uv
  uv run rattle fix --automatic .

# run inline VALID/INVALID rule fixtures through Rattle's built-in test runner
rattle-test: _require-uv
  uv run rattle test rattle_blank_lines.rules rattle_blank_lines.rules.block_header_cuddle_strict rattle_blank_lines.rules.match_case_separation

# validate the repository's Rattle configuration
rattle-validate-config: _require-uv
  uv run rattle validate-config pyproject.toml

# build the package
build: _require-uv
  uv build

# setup or update local dev environment, keeps previously installed extras
sync: _require-uv
  uv sync --inexact --extra dev
  uv run pre-commit install

# run tests with coverage and show a coverage report
coverage:
  uv run coverage run -m pytest
  uv run coverage report

# clean build artifacts and caches
clean:
  rm -rf .venv .pytest_cache .mypy_cache .ruff_cache
  find . -type d -name "__pycache__" -exec rm -r {} +

# static type check with mypy
typecheck: _require-uv
    uv run mypy

# check code for common misspellings
spell: _require-uv
    uv run codespell

# run all quality checks
check: format lint rattle-test rattle-validate-config coverage typecheck spell

# list available recipes
help:
    just --list

alias fmt := format
alias cov := coverage
alias mypy := typecheck
alias dev := sync
