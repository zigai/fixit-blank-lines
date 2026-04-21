from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule, validate_non_negative_int
from rattle_blank_lines.utils import (
    assignment_small_statement,
    control_block_ends_with_continue,
    flat_body_assigned_names,
    has_nontrivial_related_use,
    has_separator,
    is_branch_statement,
    is_compact_guard_if,
    is_control_block_statement,
    is_header_block_statement,
    is_pass_only_try,
    is_pytest_raises_with,
    is_same_subject_simple_if_chain,
    is_single_line_control_block,
    next_statement_inspects_with_assignment,
    prepend_blank_line,
    statement_reference_names,
)


class BlankLineAfterControlBlock(BaseBlankLinesRule, LintRule):
    """Require separation after multiline control-flow block statements."""

    CODE = "BL350"
    ALIASES = ("BlankLineAfterControlBlock",)
    MESSAGE = "BL350 Missing blank line after multiline control-flow block statement."
    SETTINGS = {
        "related_use_lookahead": RuleSetting(
            int,
            default=2,
            validator=validate_non_negative_int,
        ),
        "allow_compact_guard_ladders": RuleSetting(bool, default=True),
        "allow_pytest_raises_clusters": RuleSetting(bool, default=True),
        "allow_with_immediate_inspection": RuleSetting(bool, default=True),
    }

    VALID = [
        Valid(
            """
            def f(value: int) -> int:
                if value > 0:
                    value += 1

                return value
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                if value > 0:
                    value += 1
                # comment separator
                return value
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                if value > 0: return value
                return 0
            """
        ),
        Valid(
            """
            def load_config(text: str, format_name: str) -> object:
                if format_name == "json":
                    return json.loads(text)
                if format_name == "toml":
                    return tomllib.loads(text)
                if format_name == "yaml":
                    return _load_yaml_text(text)

                raise ValueError(format_name)
            """
        ),
        Valid(
            """
            def normalize(parts: list[str], values: list[str]) -> None:
                for part in values:
                    if part == "..":
                        parts.pop()
                        continue
                    parts.append(part)
            """
        ),
        Valid(
            """
            def render(parser: object, capsys: object) -> object:
                try:
                    parser.run()
                except SystemExit:
                    pass
                out = capsys.readouterr()
                return out
            """
        ),
        Valid(
            """
            def f() -> None:
                with pytest.raises(ValueError):
                    parse("x")
                with pytest.raises(TypeError):
                    parse(3)
            """
        ),
        Valid(
            """
            def f(path: str) -> None:
                with open(path) as handle:
                    content = handle.read()
                assert content
            """
        ),
        Valid(
            """
            def f(width: int | None, columns: list[str]) -> list[str]:
                if width is not None:
                    template = f"{width:02d}"
                    columns.append(template)
                columns.append(template if width is not None else "default")
                return columns
            """
        ),
        Valid(
            """
            def f(flag: bool, label: str) -> str:
                if not flag:
                    return label
                cleaned = label.strip()
                return cleaned
            """
        ),
        Valid(
            """
            def f(shell_name: str, interactive: bool) -> list[str]:
                if shell_name == "zsh":
                    return ["-lic"]
                if interactive:
                    return ["-ic"]

                return ["-lc"]
            """
        ),
        Valid(
            """
            def f(primary: str | None, fallback: str | None) -> str:
                if primary is not None:
                    return primary
                if fallback is not None:
                    return fallback

                return "guest"
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            def f(value: int) -> int:
                if value > 0:
                    value += 1
                return value
            """,
            expected_replacement="""
            def f(value: int) -> int:
                if value > 0:
                    value += 1

                return value
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(values: list[int]) -> int:
                total = 0
                for value in values:
                    total += value
                return total
            """,
            expected_replacement="""
            def f(values: list[int]) -> int:
                total = 0
                for value in values:
                    total += value

                return total
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(value: int, other: int) -> int:
                if value > 0:
                    log(value)
                    audit(value)
                    return value
                if other > 0:
                    return other
                return 0
            """,
            expected_replacement="""
            def f(value: int, other: int) -> int:
                if value > 0:
                    log(value)
                    audit(value)
                    return value
                if other > 0:
                    return other

                return 0
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(flag: bool, label: str) -> str:
                if not flag:
                    return label
                return label.strip()
            """,
            expected_replacement="""
            def f(flag: bool, label: str) -> str:
                if not flag:
                    return label

                return label.strip()
            """,
            expected_message=MESSAGE,
        ),
    ]

    def visit_Module(self, node: cst.Module) -> None:
        self._set_source_lines(node)
        self._check_suite_body(node.body)

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> None:
        self._check_suite_body(node.body)

    def _check_suite_body(self, body: Sequence[cst.BaseStatement]) -> None:
        if len(body) < 2:
            return

        for index in range(len(body) - 1):
            current_statement = body[index]
            next_statement = body[index + 1]

            if self._should_skip_pair(body, index, current_statement, next_statement):
                continue

            self.report(
                next_statement,
                message=self.MESSAGE,
                position=self._first_line_range(next_statement),
                replacement=prepend_blank_line(next_statement),
            )

    def _should_skip_pair(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        current_statement: cst.BaseStatement,
        next_statement: cst.BaseStatement,
    ) -> bool:
        return (
            not is_control_block_statement(current_statement)
            or is_single_line_control_block(current_statement)
            or is_header_block_statement(next_statement)
            or assignment_small_statement(next_statement) is not None
            or is_same_subject_simple_if_chain(current_statement, next_statement)
            or has_separator(next_statement)
            or self._is_pytest_raises_cluster(current_statement, next_statement)
            or self._is_compact_guard_transition(current_statement, next_statement)
            or self._is_related_simple_fallthrough(current_statement, next_statement)
            or self._is_with_immediate_inspection(current_statement, next_statement)
            or self._is_related_assignment_fallthrough(body, index, next_statement)
            or control_block_ends_with_continue(current_statement)
            or (
                is_pass_only_try(current_statement)
                and isinstance(next_statement, cst.SimpleStatementLine)
            )
        )

    def _is_pytest_raises_cluster(
        self,
        current_statement: cst.BaseStatement,
        next_statement: cst.BaseStatement,
    ) -> bool:
        return (
            self._allow_pytest_raises_clusters()
            and is_pytest_raises_with(current_statement)
            and is_pytest_raises_with(next_statement)
        )

    def _is_compact_guard_transition(
        self,
        current_statement: cst.BaseStatement,
        next_statement: cst.BaseStatement,
    ) -> bool:
        if not self._allow_compact_guard_ladders() or not is_compact_guard_if(current_statement):
            return False

        return is_compact_guard_if(next_statement)

    def _is_with_immediate_inspection(
        self,
        current_statement: cst.BaseStatement,
        next_statement: cst.BaseStatement,
    ) -> bool:
        return self._allow_with_immediate_inspection() and next_statement_inspects_with_assignment(
            current_statement,
            next_statement,
        )

    def _is_related_simple_fallthrough(
        self,
        current_statement: cst.BaseStatement,
        next_statement: cst.BaseStatement,
    ) -> bool:
        if (
            is_compact_guard_if(current_statement)
            or is_branch_statement(next_statement)
            or assignment_small_statement(next_statement) is not None
            or not isinstance(next_statement, cst.SimpleStatementLine)
        ):
            return False

        assigned = flat_body_assigned_names(current_statement)
        if not assigned:
            return False

        return bool(statement_reference_names(next_statement).intersection(assigned))

    def _is_related_assignment_fallthrough(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        next_statement: cst.BaseStatement,
    ) -> bool:
        if is_compact_guard_if(body[index]):
            return False

        return assignment_small_statement(
            next_statement
        ) is not None and has_nontrivial_related_use(
            body,
            index + 1,
            lookahead=self._related_use_lookahead(),
        )

    def _related_use_lookahead(self) -> int:
        return int(self.settings["related_use_lookahead"])

    def _allow_compact_guard_ladders(self) -> bool:
        return bool(self.settings["allow_compact_guard_ladders"])

    def _allow_pytest_raises_clusters(self) -> bool:
        return bool(self.settings["allow_pytest_raises_clusters"])

    def _allow_with_immediate_inspection(self) -> bool:
        return bool(self.settings["allow_with_immediate_inspection"])


__all__ = ["BlankLineAfterControlBlock"]
