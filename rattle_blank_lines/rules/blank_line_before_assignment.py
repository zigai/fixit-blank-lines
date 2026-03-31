from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from libcst.metadata import ParentNodeProvider
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule, validate_non_negative_int
from rattle_blank_lines.utils import (
    assigned_names,
    assignment_small_statement,
    collect_attribute_receivers,
    expression_statement_value,
    has_blank_line_separator,
    has_nontrivial_related_use,
    has_separator,
    is_compact_guard_if,
    is_control_block_statement,
    is_terminal_exception_cleanup_run,
    next_control_block_consumes_assignment,
    next_local_definition_uses_assignment,
    prepend_blank_line,
    remove_blank_leading_lines,
)


class BlankLineBeforeAssignment(BaseBlankLinesRule, LintRule):
    """Require separators before assignments that do not continue the local flow."""

    CODE = "BL210"
    ALIASES = ("BlankLineBeforeAssignment",)
    MESSAGE = (
        "BL210 Missing blank line before assignment statement "
        "that follows a non-assignment statement."
    )
    EXTRA_MESSAGE = (
        "BL210 Unnecessary blank line before assignment statement "
        "that continues a compact local flow."
    )
    SETTINGS = {
        "short_control_flow_max_statements": RuleSetting(
            int,
            default=3,
            validator=validate_non_negative_int,
        ),
        "related_use_lookahead": RuleSetting(
            int,
            default=2,
            validator=validate_non_negative_int,
        ),
        "allow_local_helper_capture": RuleSetting(bool, default=True),
        "allow_post_guard_continuation": RuleSetting(bool, default=True),
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
                log_value(value)
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
        Valid(
            """
            def f(output: object) -> None:
                output.write("ok")
                bar = output.bars["task"]
                assert bar.n == 1
            """
        ),
        Valid(
            """
            def f() -> None:
                assert output.exists()
                payload = json.loads(output.read_text())
                assert "themes" in payload
            """
        ),
        Valid(
            """
            def f(name: str | None) -> object:
                configure_logging()
                logger_name = "default" if name is None else name
                return make_logger(logger_name)
            """
        ),
        Valid(
            """
            def f(flag: bool, value: str) -> str:
                if not flag:
                    return value
                normalized = value.strip()
                return normalized
            """
        ),
        Valid(
            """
            def f(candidate: object, parser_input: str, style: object) -> object:
                validate(candidate)
                display_value = parser_input or str(candidate)
                if supports_live_interaction():
                    highlight(display_value, style)
                else:
                    summarize(display_value, style)
                return candidate
            """
        ),
        Valid(
            """
            def f(monkeypatch: object) -> dict[str, object]:
                monkeypatch.setenv("TOKEN", "abc")
                calls: dict[str, object] = {}
                class FakeRepo:
                    def __init__(self) -> None:
                        calls["created"] = True
                return calls
            """
        ),
        Valid(
            """
            def f(logger: logging.Logger, handler: logging.Handler) -> None:
                logger.addHandler(handler)
                logger.propagate = False
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
    ]
    INVALID = [
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
        Invalid(
            """
            def f(candidate: object) -> object:
                validate(candidate)
                display_value = str(candidate)
                if supports_live_interaction():
                    highlight(candidate)
                return candidate
            """,
            expected_replacement="""
            def f(candidate: object) -> object:
                validate(candidate)

                display_value = str(candidate)
                if supports_live_interaction():
                    highlight(candidate)
                return candidate
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(logger: logging.Logger, handler: logging.Handler) -> None:
                logger.addHandler(handler)

                logger.propagate = False
            """,
            expected_replacement="""
            def f(logger: logging.Logger, handler: logging.Handler) -> None:
                logger.addHandler(handler)
                logger.propagate = False
            """,
            expected_message=EXTRA_MESSAGE,
        ),
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
            expected_message=EXTRA_MESSAGE,
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

            if self._should_remove_assignment_separator(
                body,
                index,
                suite_parent=suite_parent,
            ):
                self.report(
                    statement,
                    message=self.EXTRA_MESSAGE,
                    position=self._first_line_range(statement),
                    replacement=remove_blank_leading_lines(statement),
                )

                continue

            if has_separator(statement):
                continue

            if self._should_skip_assignment(
                body,
                index,
                suite_can_have_docstring=suite_can_have_docstring,
                suite_parent=suite_parent,
            ):
                continue

            self.report(
                statement,
                message=self.MESSAGE,
                position=self._first_line_range(statement),
                replacement=prepend_blank_line(statement),
            )

    def _should_remove_assignment_separator(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        *,
        suite_parent: cst.CSTNode | None,
    ) -> bool:
        return has_blank_line_separator(body[index]) and (
            self._continues_same_receiver_setup(body, index)
            or self._is_terminal_simple_return_tail(body, index, suite_parent=suite_parent)
        )

    def _should_skip_assignment(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        *,
        suite_can_have_docstring: bool,
        suite_parent: cst.CSTNode | None,
    ) -> bool:
        previous_statement = body[index - 1]
        related_use = has_nontrivial_related_use(
            body,
            index,
            lookahead=self._related_use_lookahead(),
        )
        return (
            assignment_small_statement(previous_statement) is not None
            or self._follows_suite_docstring(body, index, suite_can_have_docstring)
            or is_terminal_exception_cleanup_run(body, index, suite_parent)
            or self._continues_same_receiver_setup(body, index)
            or self._is_terminal_simple_return_tail(body, index, suite_parent=suite_parent)
            or next_control_block_consumes_assignment(
                body,
                index,
                limit=self._related_use_lookahead(),
            )
            or (
                self._allow_local_helper_capture()
                and next_local_definition_uses_assignment(body, index)
            )
            or (
                self._allow_post_guard_continuation()
                and index > 0
                and is_compact_guard_if(body[index - 1])
                and (related_use or self._has_direct_following_branch_use(body, index))
            )
            or related_use
        )

    def _continues_same_receiver_setup(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
    ) -> bool:
        if index <= 0:
            return False

        assignment = assignment_small_statement(body[index])
        if assignment is None:
            return False

        if isinstance(assignment, cst.Assign):
            current_targets = [target.target for target in assignment.targets]
        elif isinstance(assignment, (cst.AnnAssign, cst.AugAssign)):
            current_targets = [assignment.target]
        else:
            return False

        current_receivers = [
            receiver
            for target in current_targets
            for receiver in collect_attribute_receivers(target)
        ]
        if not current_receivers:
            return False

        previous_receivers = [
            receiver
            for expression in self._receiver_setup_expressions(body[index - 1])
            for receiver in collect_attribute_receivers(expression)
        ]
        if not previous_receivers:
            return False

        return any(
            previous_receiver.deep_equals(current_receiver)
            for previous_receiver in previous_receivers
            for current_receiver in current_receivers
        )

    def _receiver_setup_expressions(
        self,
        statement: cst.BaseStatement,
    ) -> list[cst.BaseExpression]:
        expressions: list[cst.BaseExpression] = []

        expression = expression_statement_value(statement)
        if expression is not None:
            expressions.append(expression)

        assignment = assignment_small_statement(statement)
        if isinstance(assignment, cst.Assign):
            expressions.append(assignment.value)
            expressions.extend(target.target for target in assignment.targets)

            return expressions

        if isinstance(assignment, cst.AnnAssign):
            expressions.append(assignment.target)
            if assignment.value is not None:
                expressions.append(assignment.value)

            return expressions

        if isinstance(assignment, cst.AugAssign):
            expressions.append(assignment.target)
            expressions.append(assignment.value)

        return expressions

    def _is_terminal_simple_return_tail(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        *,
        suite_parent: cst.CSTNode | None,
    ) -> bool:
        if not isinstance(suite_parent, cst.FunctionDef):
            return False

        if index != len(body) - 2:
            return False

        next_statement = body[index + 1]
        if not (
            isinstance(next_statement, cst.SimpleStatementLine)
            and len(next_statement.body) == 1
            and isinstance(next_statement.body[0], cst.Return)
            and self._has_direct_following_branch_use(body, index)
        ):
            return False

        previous_statement = body[index - 1]
        if not (
            isinstance(previous_statement, cst.SimpleStatementLine)
            and len(previous_statement.body) == 1
            and (index == 1 or has_separator(previous_statement))
        ):
            return False

        return all(
            self._node_non_empty_line_count(statement) == 1
            for statement in (previous_statement, body[index])
        )

    def _related_use_lookahead(self) -> int:
        return int(self.settings["related_use_lookahead"])

    def _allow_local_helper_capture(self) -> bool:
        return bool(self.settings["allow_local_helper_capture"])

    def _allow_post_guard_continuation(self) -> bool:
        return bool(self.settings["allow_post_guard_continuation"])

    def _has_direct_following_branch_use(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
    ) -> bool:
        next_index = index + 1
        if next_index >= len(body):
            return False

        statement = body[next_index]
        if not isinstance(statement, cst.SimpleStatementLine) or len(statement.body) != 1:
            return False

        branch = statement.body[0]
        names = assigned_names(body[index])
        if not names:
            return False

        return (
            isinstance(branch, cst.Return)
            and isinstance(branch.value, cst.Name)
            and branch.value.value in names
        ) or (
            isinstance(branch, cst.Raise)
            and isinstance(branch.exc, cst.Name)
            and branch.exc.value in names
        )


__all__ = ["BlankLineBeforeAssignment"]
