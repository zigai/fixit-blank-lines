# fixit-blank-lines

Reusable [Fixit](https://fixit.readthedocs.io/) rules for blank-line and statement-cuddling policy checks.

## Installation

```sh
pip install "git+https://github.com/zigai/flake8-blank-lines.git"
```

```sh
uv add "git+https://github.com/zigai/flake8-blank-lines.git"
```

## Quick Start

Add the rule pack to your project configuration:

```toml
[tool.fixit]
root = true
enable = ["fixit_blank_lines.rules"]
disable = [
  "fixit_blank_lines.rules:BlockHeaderCuddleStrict",
]
```

Run linting and autofix:

```sh
fixit lint <path>
fixit lint --diff <path>
fixit fix --automatic <path>
```

For in-file suppressions, use Fixit comments:
- `# lint-ignore: RuleName`
- `# lint-fixme: RuleName`

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

### BlankLineBeforeAssignment (BL210)
Requires a separator before an assignment when it follows a non-assignment statement.

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

### BlankLineBeforeBranchInLargeSuite (BL200)
In suites larger than 2 non-empty lines, requires a blank line before `return`/`raise`/`break`/`continue`.

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
Allows assignment-before-block cuddling only when the final prep assignment feeds the block header or first body statement.

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
Stricter cuddle mode: only the immediately previous assignment may feed the block header.

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

### MatchCaseSeparation (BL400, disabled by default)
Requires a separator before the next `case` when a `case` body is larger than 2 non-empty lines.

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
[MIT](https://github.com/zigai/flake8-blank-lines/LICENSE)
