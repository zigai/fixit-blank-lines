from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule, validate_non_negative_int
from rattle_blank_lines.utils import (
    assigned_names,
    compact_tail_run_before,
    has_separator,
    is_branch_statement,
    is_compact_guard_ladder_tail,
    is_terminal_exception_cleanup_run,
    prepend_blank_line,
    statement_reference_names,
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
        "compact_tail_max_statements": RuleSetting(
            int,
            default=2,
            validator=validate_non_negative_int,
        ),
        "allow_related_return_tails": RuleSetting(bool, default=True),
        "allow_guard_ladder_final_branch": RuleSetting(bool, default=True),
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
        Valid(
            """
            def f(created_at: object) -> object:
                payload = {"created_at": created_at}
                return ArchivedPost(created_at=created_at, payload=payload)
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

            if self._should_skip_branch(
                body,
                index,
                statement,
                suite_can_have_docstring=suite_can_have_docstring,
                suite_parent=suite_parent,
            ):
                continue

            self.report(
                statement,
                message=self.MESSAGE,
                replacement=prepend_blank_line(statement),
            )

    def _should_skip_branch(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        statement: cst.BaseStatement,
        *,
        suite_can_have_docstring: bool,
        suite_parent: cst.CSTNode | None,
    ) -> bool:
        return (
            not is_branch_statement(statement)
            or has_separator(statement)
            or self._follows_suite_docstring(body, index, suite_can_have_docstring)
            or is_terminal_exception_cleanup_run(body, index - 1, suite_parent)
            or (self._allow_related_return_tails() and self._is_compact_related_tail(body, index))
            or (
                self._allow_guard_ladder_final_branch()
                and is_compact_guard_ladder_tail(body, index)
            )
        )

    def _is_compact_related_tail(
        self,
        body: Sequence[cst.BaseStatement],
        branch_index: int,
    ) -> bool:
        if branch_index != len(body) - 1:
            return False

        _run_start, run = compact_tail_run_before(body, branch_index)
        branch_statement = body[branch_index]
        run_is_compact = (
            bool(run)
            and len(run) <= int(self.settings["compact_tail_max_statements"])
            and all(isinstance(statement, cst.SimpleStatementLine) for statement in run)
        )
        if not run_is_compact:
            return False

        assigned: set[str] = set()
        for statement in run:
            assigned.update(assigned_names(statement))

        references_assigned = bool(assigned) and bool(
            statement_reference_names(branch_statement).intersection(assigned)
        )
        if not references_assigned:
            return False

        plain_single_assignment_return = False

        if (
            isinstance(branch_statement, cst.SimpleStatementLine)
            and len(branch_statement.body) == 1
        ):
            branch = branch_statement.body[0]
            plain_single_assignment_return = (
                isinstance(branch, cst.Return)
                and isinstance(branch.value, cst.Name)
                and branch.value.value in assigned
                and len(run) == 1
            )

        return not plain_single_assignment_return

    def _allow_related_return_tails(self) -> bool:
        return bool(self.settings["allow_related_return_tails"])

    def _allow_guard_ladder_final_branch(self) -> bool:
        return bool(self.settings["allow_guard_ladder_final_branch"])


__all__ = ["BlankLineBeforeBranchInLargeSuite"]
