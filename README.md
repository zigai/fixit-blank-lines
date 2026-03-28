# rattle-blank-lines

[![Tests](https://github.com/zigai/rattle-blank-lines/actions/workflows/tests.yml/badge.svg)](https://github.com/zigai/rattle-blank-lines/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/rattle-blank-lines.svg)](https://badge.fury.io/py/rattle-blank-lines)
![Supported versions](https://img.shields.io/badge/python-3.12+-blue.svg)
[![Downloads](https://static.pepy.tech/badge/rattle-blank-lines)](https://pepy.tech/project/rattle-blank-lines)
[![license](https://img.shields.io/github/license/zigai/rattle-blank-lines.svg)](https://github.com/zigai/rattle-blank-lines/blob/master/LICENSE)

[Rattle](https://github.com/zigai/rattle) rules for blank-line and statement-cuddling policy checks in Python.

## Installation

```sh
pip install rattle-blank-lines
```

```sh
uv add rattle-blank-lines
```

## Quick Start

Add the rule pack to your project configuration:

```toml
[tool.rattle]
root = true
enable = ["rattle_blank_lines.rules"]
```

This adds the `rattle_blank_lines` rules.
Rattle's built-in `rattle.rules` stay enabled unless you disable them.

If you want to run only `rattle_blank_lines`, also set `disable = ["rattle.rules"]`.

Run linting and autofix:

```sh
rattle lint <path>
rattle lint --diff <path>
rattle fix <path>
```

For in-file suppressions, use Rattle comments:
- `# lint-ignore: BlankLineBeforeAssignment`
- `# lint-fixme: BlankLineBeforeAssignment`

## Rules

### NoSuiteLeadingTrailingBlankLines (BL100, BL101)
Removes leading and trailing blank lines at suite boundaries.

Before:
```python
def f() -> int:

    value = 1
    return value
```

After:
```python
def f() -> int:
    value = 1
    return value
```


### BlankLineBeforeBranchInLargeSuite (BL200)
Requires a blank line before `return`/`raise`/`break`/`continue` in larger suites.

Before:
```python
def f(value: int) -> int:
    x = value + 1
    y = x + 1
    z = y + 1
    return z
```

After:
```python
def f(value: int) -> int:
    x = value + 1
    y = x + 1
    z = y + 1

    return z
```

### BlockHeaderCuddleRelaxed (BL300)
Allows cuddling before a block when the setup still belongs to the same step.
The first statement after a suite docstring is exempt.

Before:
```python
def f(value: int) -> int:
    prepared = value + 1
    if value > 0:
        return value

    return 0
```

After:
```python
def f(value: int) -> int:
    prepared = value + 1

    if value > 0:
        return value

    return 0
```

Also allowed:
```python
def f(override_name: str | None) -> str:
    display_name = "guest"
    if override_name is not None:
        display_name = override_name
    return display_name
```

```python
def f(slots: dict[str, int], key: str) -> None:
    slots[key] -= 1
    if slots[key] < 0:
        raise ValueError(key)
```

### BlockHeaderCuddleStrict (BL301)
Stricter cuddle mode. The first statement after a suite docstring is exempt.

Opt in with `rattle_blank_lines.rules.block_header_cuddle_strict:BlockHeaderCuddleStrict`, and disable `BlockHeaderCuddleRelaxed` if you want BL301 instead of BL300.

```toml
[tool.rattle]
root = true
enable = [
  "rattle_blank_lines.rules",
  "rattle_blank_lines.rules.block_header_cuddle_strict:BlockHeaderCuddleStrict",
]
disable = [
  "BlockHeaderCuddleRelaxed",
]
```

Before:
```python
def f(value: int) -> int:
    header_value = value + 1
    trailing = value + 2
    if header_value > 0:
        return header_value

    return 0
```

After:
```python
def f(value: int) -> int:
    header_value = value + 1
    trailing = value + 2

    if header_value > 0:
        return header_value

    return 0
```

### BlankLineAfterControlBlock (BL350)
Requires a blank line after multiline control-flow blocks.
Some compact patterns stay together, such as guard ladders, `with pytest.raises(...)` clusters, and immediate inspection after `with`.

Before:
```python
def f(value: int) -> int:
    if value > 0:
        value += 1
    return value
```

After:
```python
def f(value: int) -> int:
    if value > 0:
        value += 1

    return value
```

### BlankLineBeforeAssignment (BL210)
Requires a blank line before an assignment after a non-assignment statement.
Docstring-following assignments and some compact follow-up flows stay together.

Before:
```python
def f() -> int:
    log_start()
    value = compute()
    return value
```

After:
```python
def f() -> int:
    log_start()

    value = compute()
    return value
```

### MatchCaseSeparation (BL400)
Requires a blank line before the next `case` after a larger case body.

This rule is opt-in and is not included by `enable = ["rattle_blank_lines.rules"]`.
You can enable it with `enable = ["rattle_blank_lines.rules.match_case_separation:MatchCaseSeparation"]`.

Before:
```python
def f(value: int) -> int:
    match value:
        case 1:
            a = 1
            b = 2
            c = 3
        case _:
            return 0
```

## Rule Options

```toml
[tool.rattle.options]

[tool.rattle.options.BlankLineBeforeBranchInLargeSuite]
max_suite_non_empty_lines = 2
compact_tail_max_statements = 2
allow_related_return_tails = true
allow_guard_ladder_final_branch = true

[tool.rattle.options.BlankLineBeforeAssignment]
short_control_flow_max_statements = 3
related_use_lookahead = 2
allow_local_helper_capture = true
allow_post_guard_continuation = true

[tool.rattle.options.BlockHeaderCuddleRelaxed]
body_usage_lookahead = 4
setup_run_lookback = 3
allow_setup_before_compact_guard_ladder = true

[tool.rattle.options.BlankLineAfterControlBlock]
related_use_lookahead = 2
allow_compact_guard_ladders = true
allow_pytest_raises_clusters = true
allow_with_immediate_inspection = true

[tool.rattle.options.MatchCaseSeparation]
max_case_non_empty_lines = 2
```

After:
```python
def f(value: int) -> int:
    match value:
        case 1:
            a = 1
            b = 2
            c = 3

        case _:
            return 0
```


## License
[MIT](https://github.com/zigai/rattle-blank-lines/LICENSE)
