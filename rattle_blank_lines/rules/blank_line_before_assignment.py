from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from libcst.metadata import ParentNodeProvider
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule, validate_non_negative_int
from rattle_blank_lines.utils import (
    assignment_small_statement,
    has_separator,
    is_control_block_statement,
    is_terminal_exception_cleanup_run,
    prepend_blank_line,
)


class BlankLineBeforeAssignment(BaseBlankLinesRule, LintRule):
    """Require separators before assignment lines after non-assignment lines."""

    CODE = "BL210"
    ALIASES = ("BlankLineBeforeAssignment",)
    MESSAGE = (
        "BL210 Missing blank line before assignment statement "
        "that follows a non-assignment statement."
    )
    SETTINGS = {
        "short_control_flow_max_statements": RuleSetting(
            int,
            default=3,
            validator=validate_non_negative_int,
        ),
    }

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
        Valid(
            """
            def f(backend: object, archiver: object, writer: object) -> None:
                if needs_status:
                    log_status(backend=backend, archiver=archiver, writer=writer)
                    last_status_time = loop.time()
            """
        ),
        Valid(
            """
            def f() -> None:
                if needs_status:
                    log_status()
                    update_metrics()
                    last_status_time = loop.time()
            """
        ),
        Valid(
            """
            def f() -> None:
                if needs_status:
                    log_status()
                    update_metrics()
                    refresh_cache()
                    last_status_time = loop.time()
            """,
            options={"short_control_flow_max_statements": 4},
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
        Invalid(
            """
            def f(value: int) -> int:
                if value > 0:
                    log_status(value)
                    update_metrics(value)
                    adjusted = value + 1
                    return adjusted

                return value
            """,
            expected_replacement="""
            def f(value: int) -> int:
                if value > 0:
                    log_status(value)
                    update_metrics(value)

                    adjusted = value + 1
                    return adjusted

                return value
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f() -> None:
                if needs_status:
                    log_status()
                    last_status_time = loop.time()
            """,
            expected_replacement="""
            def f() -> None:
                if needs_status:
                    log_status()

                    last_status_time = loop.time()
            """,
            expected_message=MESSAGE,
            options={"short_control_flow_max_statements": 1},
        ),
    ]

    def visit_Module(self, node: cst.Module) -> None:
        self._set_source_lines(node)
        self._check_suite_body(
            node.body,
            suite_can_have_docstring=True,
            skip_short_control_flow_suite=False,
        )

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> None:
        parent = self.get_metadata(ParentNodeProvider, node)
        short_control_flow_max_statements = int(self.settings["short_control_flow_max_statements"])
        self._check_suite_body(
            node.body,
            suite_can_have_docstring=self._suite_can_have_docstring(node),
            suite_parent=parent,
            skip_short_control_flow_suite=(
                is_control_block_statement(parent)
                and len(node.body) <= short_control_flow_max_statements
            ),
        )

    def _check_suite_body(
        self,
        body: Sequence[cst.BaseStatement],
        suite_can_have_docstring: bool,
        skip_short_control_flow_suite: bool,
        suite_parent: cst.CSTNode | None = None,
    ) -> None:
        if skip_short_control_flow_suite:
            return

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

            if is_terminal_exception_cleanup_run(body, index, suite_parent):
                continue

            self.report(
                statement,
                message=self.MESSAGE,
                replacement=prepend_blank_line(statement),
            )


__all__ = ["BlankLineBeforeAssignment"]
