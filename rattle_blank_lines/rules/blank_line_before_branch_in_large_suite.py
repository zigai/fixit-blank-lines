from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule, validate_non_negative_int
from rattle_blank_lines.utils import (
    assigned_names,
    compact_tail_run_before,
    has_blank_line_separator,
    has_separator,
    is_branch_statement,
    is_compact_guard_ladder_tail,
    is_control_block_statement,
    is_terminal_exception_cleanup_run,
    prepend_blank_line,
    remove_blank_leading_lines,
    statement_reference_names,
)


class BlankLineBeforeBranchInLargeSuite(BaseBlankLinesRule, LintRule):
    """Require branch statements to be visually separated in large suites."""

    CODE = "BL200"
    ALIASES = ("BlankLineBeforeBranchInLargeSuite",)
    MESSAGE = "BL200 Missing blank line before return/raise/break/continue in a large suite."
    EXTRA_MESSAGE = (
        "BL200 Unnecessary blank line before returning an immediately preceding annotated binding."
    )
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
            def f(parts: list[str]) -> dict[str, int]:
                cleaned = [part.strip() for part in parts]
                joined = ",".join(cleaned)
                payload: dict[str, int] = {"count": len(cleaned), "width": len(joined)}
                return payload
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
        Valid(
            """
            def f(values: list[int]) -> int:
                total = 0
                for value in values:
                    total += value
                return total
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
                message = str(total)
                flag = bool(message)
                raise RuntimeError("boom")
            """,
            expected_replacement="""
            def f(values: list[int]) -> int:
                total = 0
                message = str(total)
                flag = bool(message)

                raise RuntimeError("boom")
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
            options={
                "allow_related_return_tails": False,
                "max_suite_non_empty_lines": 1,
            },
        ),
        Invalid(
            """
            def f(parts: list[str]) -> dict[str, int]:
                cleaned = [part.strip() for part in parts]
                joined = ",".join(cleaned)
                payload: dict[str, int] = {"count": len(cleaned), "width": len(joined)}

                return payload
            """,
            expected_replacement="""
            def f(parts: list[str]) -> dict[str, int]:
                cleaned = [part.strip() for part in parts]
                joined = ",".join(cleaned)
                payload: dict[str, int] = {"count": len(cleaned), "width": len(joined)}
                return payload
            """,
            expected_message=EXTRA_MESSAGE,
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

            if self._should_remove_branch_separator(
                body,
                index,
                statement,
            ):
                self.report(
                    statement,
                    message=self.EXTRA_MESSAGE,
                    position=self._branch_anchor_range(statement),
                    replacement=remove_blank_leading_lines(statement),
                )

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
                position=self._branch_anchor_range(statement),
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
            or is_control_block_statement(body[index - 1])
            or self._follows_suite_docstring(body, index, suite_can_have_docstring)
            or is_terminal_exception_cleanup_run(body, index - 1, suite_parent)
            or (self._allow_related_return_tails() and self._is_compact_related_tail(body, index))
            or (
                self._allow_guard_ladder_final_branch()
                and is_compact_guard_ladder_tail(body, index)
            )
        )

    def _should_remove_branch_separator(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        statement: cst.BaseStatement,
    ) -> bool:
        return (
            is_branch_statement(statement)
            and has_blank_line_separator(statement)
            and self._is_immediate_annotated_return_binding(body, index, statement)
        )

    def _is_compact_related_tail(
        self,
        body: Sequence[cst.BaseStatement],
        branch_index: int,
    ) -> bool:
        if branch_index != len(body) - 1:
            return False

        branch_statement = body[branch_index]
        if self._is_immediate_annotated_return_binding(body, branch_index, branch_statement):
            return True

        _run_start, run = compact_tail_run_before(body, branch_index)
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

    def _is_immediate_annotated_return_binding(
        self,
        body: Sequence[cst.BaseStatement],
        branch_index: int,
        branch_statement: cst.BaseStatement,
    ) -> bool:
        if not (
            isinstance(branch_statement, cst.SimpleStatementLine)
            and len(branch_statement.body) == 1
        ):
            return False

        branch = branch_statement.body[0]
        if not (isinstance(branch, cst.Return) and isinstance(branch.value, cst.Name)):
            return False

        previous_statement = body[branch_index - 1]
        if not (
            isinstance(previous_statement, cst.SimpleStatementLine)
            and len(previous_statement.body) == 1
        ):
            return False

        previous = previous_statement.body[0]
        if not (
            isinstance(previous, cst.AnnAssign)
            and previous.value is not None
            and isinstance(previous.target, cst.Name)
        ):
            return False

        return previous.target.value == branch.value.value

    def _allow_related_return_tails(self) -> bool:
        return bool(self.settings["allow_related_return_tails"])

    def _allow_guard_ladder_final_branch(self) -> bool:
        return bool(self.settings["allow_guard_ladder_final_branch"])


__all__ = ["BlankLineBeforeBranchInLargeSuite"]
