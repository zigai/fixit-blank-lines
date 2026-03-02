from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from fixit import Invalid, LintRule, Valid

from fixit_blank_lines.rules.base import BaseBlankLinesRule
from fixit_blank_lines.utils import has_separator, is_branch_statement, prepend_blank_line


class BlankLineBeforeBranchInLargeSuite(BaseBlankLinesRule, LintRule):
    """Require branch statements to be visually separated in large suites."""

    BRANCH_MAX_LINES = 2
    MESSAGE = (
        "BL200 Missing blank line before return/raise/break/continue "
        "in a suite larger than 2 non-empty lines."
    )

    VALID = [
        Valid(
            """
            def f(value: int) -> int:
                x = value + 1
                y = x + 1

                return y
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                x = value + 1
                return x
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                x = value + 1
                y = x + 1
                z = y + 1
                # comment separator
                return z
            """
        ),
        Valid(
            '''
            def f() -> int:
                """Return constant."""
                return 1
                value = 2
            '''
        ),
    ]
    INVALID = [
        Invalid(
            """
            def f(value: int) -> int:
                x = value + 1
                y = x + 1
                z = y + 1
                return z
            """,
            expected_replacement="""
            def f(value: int) -> int:
                x = value + 1
                y = x + 1
                z = y + 1

                return z
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(values: list[int]) -> int:
                total = 0
                for value in values:
                    total += value
                raise ValueError(total)
            """,
            expected_replacement="""
            def f(values: list[int]) -> int:
                total = 0
                for value in values:
                    total += value

                raise ValueError(total)
            """,
            expected_message=MESSAGE,
        ),
    ]

    def visit_Module(self, node: cst.Module) -> None:
        self._set_source_lines(node)
        self._check_suite_body(node.body, suite_can_have_docstring=True)

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> None:
        self._check_suite_body(
            node.body,
            suite_can_have_docstring=self._suite_can_have_docstring(node),
        )

    def _check_suite_body(
        self,
        body: Sequence[cst.BaseStatement],
        suite_can_have_docstring: bool,
    ) -> None:
        if len(body) < 2:
            return

        if self._suite_non_empty_line_count(body) <= self.BRANCH_MAX_LINES:
            return

        for index, statement in enumerate(body):
            if index == 0:
                continue

            if not is_branch_statement(statement):
                continue

            if has_separator(statement):
                continue

            if self._follows_suite_docstring(body, index, suite_can_have_docstring):
                continue

            self.report(
                statement,
                message=self.MESSAGE,
                replacement=prepend_blank_line(statement),
            )


__all__ = ["BlankLineBeforeBranchInLargeSuite"]
