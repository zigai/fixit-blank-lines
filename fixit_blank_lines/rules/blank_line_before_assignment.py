from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from fixit import Invalid, LintRule, Valid

from fixit_blank_lines.rules.base import BaseBlankLinesRule
from fixit_blank_lines.utils import assignment_small_statement, has_separator, prepend_blank_line


class BlankLineBeforeAssignment(BaseBlankLinesRule, LintRule):
    """Require separators before assignment lines after non-assignment lines."""

    MESSAGE = (
        "BL210 Missing blank line before assignment statement "
        "that follows a non-assignment statement."
    )

    VALID = [
        Valid(
            """
            def f() -> int:
                value = 1
                other = value + 1
                return other
            """
        ),
        Valid(
            """
            def f() -> int:
                log_start()

                value = compute()
                return value
            """
        ),
        Valid(
            """
            def f() -> int:
                total = 0
                total += 1
                return total
            """
        ),
        Valid(
            '''
            def f() -> int:
                """Compute value."""
                value = compute()
                return value
            '''
        ),
    ]
    INVALID = [
        Invalid(
            """
            def f() -> int:
                log_start()
                value = compute()
                return value
            """,
            expected_replacement="""
            def f() -> int:
                log_start()

                value = compute()
                return value
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(values: list[int]) -> int:
                total = 0
                if values:
                    total += len(values)
                total += 1
                return total
            """,
            expected_replacement="""
            def f(values: list[int]) -> int:
                total = 0
                if values:
                    total += len(values)

                total += 1
                return total
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

        for index, statement in enumerate(body):
            if index == 0:
                continue

            if assignment_small_statement(statement) is None:
                continue

            if has_separator(statement):
                continue

            previous_statement = body[index - 1]
            if assignment_small_statement(previous_statement) is not None:
                continue

            if self._follows_suite_docstring(body, index, suite_can_have_docstring):
                continue

            self.report(
                statement,
                message=self.MESSAGE,
                replacement=prepend_blank_line(statement),
            )


__all__ = ["BlankLineBeforeAssignment"]
