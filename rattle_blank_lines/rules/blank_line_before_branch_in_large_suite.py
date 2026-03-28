from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule, validate_non_negative_int
from rattle_blank_lines.utils import (
    has_separator,
    is_branch_statement,
    is_terminal_exception_cleanup_run,
    prepend_blank_line,
)


class BlankLineBeforeBranchInLargeSuite(BaseBlankLinesRule, LintRule):
    """Require branch statements to be visually separated in large suites."""

    CODE = "BL200"
    ALIASES = ("BlankLineBeforeBranchInLargeSuite",)
    MESSAGE = "BL200 Missing blank line before return/raise/break/continue in a large suite."
    SETTINGS = {
        "max_suite_non_empty_lines": RuleSetting(
            int,
            default=2,
            validator=validate_non_negative_int,
        ),
    }

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
        Valid(
            """
            def f(value: int) -> int:
                x = value + 1
                y = x + 1
                return y
            """,
            options={"max_suite_non_empty_lines": 3},
        ),
        Valid(
            """
            async def f() -> None:
                try:
                    work()
                except Exception:
                    cleanup_a()
                    cleanup_b()
                    await cleanup_c()
                    collector_id = None
                    raise
            """
        ),
        Valid(
            """
            async def f() -> None:
                try:
                    work()
                except Exception:
                    cleanup()
                    state = None
                    log_error()
                    raise
            """
        ),
        Valid(
            """
            async def f() -> None:
                try:
                    work()
                finally:
                    cleanup()
                    log_teardown()
                    return
            """
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
        Invalid(
            """
            def f(value: int) -> int:
                x = value + 1
                return x
            """,
            expected_replacement="""
            def f(value: int) -> int:
                x = value + 1

                return x
            """,
            expected_message=MESSAGE,
            options={"max_suite_non_empty_lines": 1},
        ),
    ]

    def visit_Module(self, node: cst.Module) -> None:
        self._set_source_lines(node)
        self._check_suite_body(node.body, suite_can_have_docstring=True)

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> None:
        self._check_suite_body(
            node.body,
            suite_can_have_docstring=self._suite_can_have_docstring(node),
            suite_parent=self.get_metadata(cst.metadata.ParentNodeProvider, node),
        )

    def _check_suite_body(
        self,
        body: Sequence[cst.BaseStatement],
        suite_can_have_docstring: bool,
        suite_parent: cst.CSTNode | None = None,
    ) -> None:
        if len(body) < 2:
            return

        max_suite_non_empty_lines = int(self.settings["max_suite_non_empty_lines"])
        if self._suite_non_empty_line_count(body) <= max_suite_non_empty_lines:
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

            if is_terminal_exception_cleanup_run(body, index - 1, suite_parent):
                continue

            self.report(
                statement,
                message=self.MESSAGE,
                replacement=prepend_blank_line(statement),
            )


__all__ = ["BlankLineBeforeBranchInLargeSuite"]
