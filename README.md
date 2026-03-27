# rattle-blank-lines

[Rattle](https://github.com/zigai/rattle) rules for blank-line and statement-cuddling policy checks in Python.
The distribution and repository name are `rattle-blank-lines`.
The project keeps the historical `fixit_blank_lines` package path for compatibility.

## Installation

```sh
pip install "git+https://github.com/zigai/rattle-blank-lines.git"
```

```sh
uv add "git+https://github.com/zigai/rattle-blank-lines.git"
```

## Quick Start

Add the rule pack to your project configuration:

```toml
[tool.rattle]
root = true
enable = ["fixit_blank_lines.rules"]
```

This enables the default rule pack. Rattle keeps its built-in `rattle.rules` enabled by default; add `disable = ["rattle.rules"]` if you want to run only this rule pack.

Run linting and autofix:

```sh
rattle lint <path>
rattle lint --diff <path>
rattle fix --automatic <path>
```

For in-file suppressions, use Rattle comments:
- `# lint-ignore: RuleName`
- `# lint-fixme: RuleName`

## Configurable Rules

Rattle supports per-rule settings under `[tool.rattle.options]`. This package exposes short rule selectors via codes and class-name aliases.

```toml
[tool.rattle.options]
BL200 = { max_suite_non_empty_lines = 2 }
BL210 = { short_control_flow_max_statements = 3 }
BL400 = { max_case_non_empty_lines = 2 }
```

These values match the default behavior, so you only need to set them when you want to override the defaults.

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
In suites larger than `max_suite_non_empty_lines` non-empty lines, requires a blank line before `return`/`raise`/`break`/`continue`. The default is `2`.

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
Allows assignment-before-block cuddling only when the immediately previous assignment feeds the block header or first body statement.
The first statement after a suite docstring is exempt (Ruff `D202` compatibility).

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

### BlockHeaderCuddleStrict (BL301)
Stricter cuddle mode. Like BL300, the first statement after a suite docstring is exempt.

Opt in with `fixit_blank_lines.rules.block_header_cuddle_strict`, and disable `BL300` if you want BL301 instead of BL300.

```toml
[tool.rattle]
root = true
enable = [
  "fixit_blank_lines.rules",
  "fixit_blank_lines.rules.block_header_cuddle_strict",
]
disable = [
  "BL300",
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
Requires a separator after multiline control-flow blocks.

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
Requires a separator before an assignment when it follows a non-assignment statement,
except when the assignment directly follows a suite docstring.
Short control-flow suites (`if`/`for`/`while`/`with`/`try`/`match`) with at most `short_control_flow_max_statements` statements are exempt. The default is `3`.

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
Requires a separator before the next `case` when a `case` body is larger than `max_case_non_empty_lines` non-empty lines. The default is `2`.

This rule is opt-in and is not included by `enable = ["fixit_blank_lines.rules"]`.
You can enable it with `enable = ["fixit_blank_lines.rules.match_case_separation"]`.

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
