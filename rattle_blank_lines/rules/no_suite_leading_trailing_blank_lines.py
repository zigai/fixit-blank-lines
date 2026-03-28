from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from rattle import Invalid, LintRule, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule
from rattle_blank_lines.utils import is_blank_line


class NoSuiteLeadingTrailingBlankLines(BaseBlankLinesRule, LintRule):
    """Disallow leading/trailing empty lines at suite boundaries."""

    ALIASES = ("NoSuiteLeadingTrailingBlankLines",)
    LEADING_MESSAGE = "BL100 Leading blank lines in a suite are not allowed."
    TRAILING_MESSAGE = "BL101 Trailing blank lines in a suite are not allowed."

    VALID = [
        Valid(
            """
            def f() -> int:
                value = 1
                return value
            """
        ),
        Valid(
            """
            def f() -> int:
                # comment lines are separators, not blank lines
                value = 1
                return value
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            def f() -> int:

                value = 1
                return value
            """,
            expected_replacement="""
            def f() -> int:
                value = 1
                return value
            """,
            expected_message=LEADING_MESSAGE,
        ),
        Invalid(
            """
            def f() -> int:
                value = 1
                return value

            """,
            expected_replacement="""
            def f() -> int:
                value = 1
                return value
            """,
            expected_message=TRAILING_MESSAGE,
        ),
    ]

    def visit_Module(self, node: cst.Module) -> None:
        self._set_source_lines(node)
        self._check_suite(node, node.body, node.footer)

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> None:
        self._check_suite(node, node.body, node.footer)

    def _check_suite(
        self,
        suite: cst.Module | cst.IndentedBlock,
        body: Sequence[cst.BaseStatement],
        footer: Sequence[cst.EmptyLine],
    ) -> None:
        if body:
            first_statement = body[0]
            drop_count = 0
            for leading_line in first_statement.leading_lines:
                if is_blank_line(leading_line):
                    drop_count += 1
                    continue

                break

            if drop_count > 0:
                replacement = first_statement.with_changes(
                    leading_lines=tuple(first_statement.leading_lines[drop_count:])
                )
                self.report(
                    first_statement,
                    message=self.LEADING_MESSAGE,
                    replacement=replacement,
                )

        keep_count = len(footer)
        while keep_count > 0 and is_blank_line(footer[keep_count - 1]):
            keep_count -= 1

        if keep_count != len(footer):
            replacement = suite.with_changes(footer=tuple(footer[:keep_count]))
            self.report(
                suite,
                message=self.TRAILING_MESSAGE,
                replacement=replacement,
            )


__all__ = ["NoSuiteLeadingTrailingBlankLines"]
