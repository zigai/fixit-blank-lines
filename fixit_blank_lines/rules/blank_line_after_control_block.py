from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import libcst as cst
from rattle import Invalid, LintRule, Valid

from fixit_blank_lines.rules.base import BaseBlankLinesRule
from fixit_blank_lines.utils import (
    has_separator,
    is_control_block_statement,
    is_same_subject_simple_if_chain,
    is_single_line_control_block,
    prepend_blank_line,
)


class BlankLineAfterControlBlock(BaseBlankLinesRule, LintRule):
    """Require separation after multiline control-flow block statements."""

    CODE = "BL350"
    ALIASES = ("BlankLineAfterControlBlock",)
    MESSAGE = "BL350 Missing blank line after multiline control-flow block statement."

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
                    return value
                if other > 0:
                    return other

                return 0
            """,
            expected_replacement="""
            def f(value: int, other: int) -> int:
                if value > 0:
                    return value

                if other > 0:
                    return other

                return 0
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

        for current_statement, next_statement in pairwise(body):
            if not is_control_block_statement(current_statement):
                continue

            if is_single_line_control_block(current_statement):
                continue

            if is_same_subject_simple_if_chain(current_statement, next_statement):
                continue

            if has_separator(next_statement):
                continue

            self.report(
                next_statement,
                message=self.MESSAGE,
                replacement=prepend_blank_line(next_statement),
            )


__all__ = ["BlankLineAfterControlBlock"]
