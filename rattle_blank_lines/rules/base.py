from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from libcst.metadata import ParentNodeProvider, PositionProvider

from rattle_blank_lines.utils import (
    assignment_small_statement,
    collect_names,
    contiguous_run_before,
    control_block_consumed_names_in_early_body,
    count_non_empty_lines,
    first_statement_in_block,
    has_separator,
    header_expression_nodes,
    is_compact_guard_if,
    is_docstring_statement,
    is_header_block_statement,
    last_assigned_name,
    leading_block_body_statements,
    prepend_blank_line,
    starts_compact_guard_ladder,
    statement_reference_names,
)


class BaseBlankLinesRule:
    """Shared helpers for statement-sequence blank-line checks."""

    METADATA_DEPENDENCIES = (ParentNodeProvider, PositionProvider)

    _source_lines_cache: list[str]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

    def _set_source_lines(self, node: cst.Module) -> None:
        self._source_lines_cache = node.code.splitlines()

    def visit_Module(self, node: cst.Module) -> None:
        self._set_source_lines(node)

    def _source_lines(self) -> list[str]:
        return getattr(self, "_source_lines_cache", [])

    def _suite_non_empty_line_count(self, body: Sequence[cst.BaseStatement]) -> int:
        if not body:
            return 0

        start_line = self.get_metadata(PositionProvider, body[0]).start.line
        end_line = self.get_metadata(PositionProvider, body[-1]).end.line

        return count_non_empty_lines(self._source_lines(), start_line, end_line)

    def _node_non_empty_line_count(self, node: cst.CSTNode) -> int:
        position = self.get_metadata(PositionProvider, node)
        return count_non_empty_lines(self._source_lines(), position.start.line, position.end.line)

    def _suite_can_have_docstring(self, suite: cst.Module | cst.IndentedBlock) -> bool:
        if isinstance(suite, cst.Module):
            return True

        parent = self.get_metadata(ParentNodeProvider, suite)

        return isinstance(parent, (cst.ClassDef, cst.FunctionDef))

    def _follows_suite_docstring(
        self,
        body: Sequence[cst.BaseStatement],
        index: int,
        suite_can_have_docstring: bool,
    ) -> bool:
        return (
            suite_can_have_docstring
            and index == 1
            and len(body) > 1
            and is_docstring_statement(body[0])
        )


class BaseBlockHeaderCuddleRule(BaseBlankLinesRule):
    """Shared implementation for block-header cuddling constraints."""

    STRICT = False
    ALLOW_FIRST_BODY_USAGE = True
    BODY_USAGE_LOOKAHEAD = 0
    MESSAGE = "BL300 Illegal cuddle before block header."

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

            if self._follows_suite_docstring(body, index, suite_can_have_docstring):
                continue

            if not is_header_block_statement(statement):
                continue

            if has_separator(statement):
                continue

            if self._is_allowed_cuddle(body, index, statement):
                continue

            self.report(
                statement,
                message=self.MESSAGE,
                replacement=prepend_blank_line(statement),
            )

    def _is_allowed_cuddle(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
        block_statement: cst.BaseStatement,
    ) -> bool:
        if not self.STRICT and self._has_immediate_setup_bridge(body, block_index, block_statement):
            return True

        if not self.STRICT and self._continues_compact_guard_ladder(
            body, block_index, block_statement
        ):
            return True

        candidate_run = self._assignment_run(body, block_index)
        has_assignment_run = bool(candidate_run) and all(
            assignment_small_statement(statement) is not None for statement in candidate_run
        )
        last_name = last_assigned_name(candidate_run[-1]) if has_assignment_run else None
        if last_name is not None and self._block_uses_name(block_statement, last_name):
            return True

        return (not self.STRICT) and self._is_allowed_setup_run_cuddle(
            body,
            block_index,
            block_statement,
        )

    def _assignment_run(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
    ) -> Sequence[cst.BaseStatement]:
        if self.STRICT:
            return body[block_index - 1 : block_index]

        run_start = block_index - 1
        while run_start > 0 and not has_separator(body[run_start]):
            run_start -= 1

        return body[run_start:block_index]

    def _header_uses_name(self, statement: cst.BaseStatement, name: str) -> bool:
        return any(
            name in collect_names(expression) for expression in header_expression_nodes(statement)
        )

    def _first_body_statement_uses_name(self, statement: cst.BaseStatement, name: str) -> bool:
        if isinstance(statement, cst.If):
            return name in control_block_consumed_names_in_early_body(statement, limit=1)

        first_statement = first_statement_in_block(statement)
        if first_statement is None:
            return False

        return name in collect_names(first_statement)

    def _early_body_statement_uses_name(self, statement: cst.BaseStatement, name: str) -> bool:
        if self._body_usage_lookahead() <= 0:
            return False

        if isinstance(statement, cst.If):
            return name in control_block_consumed_names_in_early_body(
                statement,
                limit=self._body_usage_lookahead(),
            )

        for body_statement in leading_block_body_statements(
            statement,
            limit=self._body_usage_lookahead(),
        ):
            if name in statement_reference_names(body_statement):
                return True

        return False

    def _body_usage_lookahead(self) -> int:
        settings = getattr(self, "settings", {})
        try:
            return int(settings["body_usage_lookahead"])
        except KeyError:
            return self.BODY_USAGE_LOOKAHEAD

    def _setup_run_lookback(self) -> int:
        settings = getattr(self, "settings", {})
        try:
            return int(settings["setup_run_lookback"])
        except KeyError:
            return 3

    def _allow_setup_before_compact_guard_ladder(self) -> bool:
        settings = getattr(self, "settings", {})
        try:
            return bool(settings["allow_setup_before_compact_guard_ladder"])
        except KeyError:
            return True

    def _block_uses_name(self, statement: cst.BaseStatement, name: str) -> bool:
        return (
            self._header_uses_name(statement, name)
            or (
                self.ALLOW_FIRST_BODY_USAGE
                and self._first_body_statement_uses_name(statement, name)
            )
            or self._early_body_statement_uses_name(statement, name)
        )

    def _is_guard_ladder_setup_cuddle(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
        assignment_position: int,
        trailing_run: Sequence[cst.BaseStatement],
    ) -> bool:
        return (
            assignment_position == 0
            and not trailing_run
            and self._allow_setup_before_compact_guard_ladder()
            and starts_compact_guard_ladder(body, block_index)
        )

    def _continues_compact_guard_ladder(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
        block_statement: cst.BaseStatement,
    ) -> bool:
        return (
            block_index > 0
            and is_compact_guard_if(block_statement)
            and is_compact_guard_if(body[block_index - 1])
            and starts_compact_guard_ladder(body, block_index - 1)
        )

    def _has_immediate_setup_bridge(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
        block_statement: cst.BaseStatement,
    ) -> bool:
        if block_index < 2:
            return False

        assignment_statement = body[block_index - 2]
        last_name = last_assigned_name(assignment_statement)
        if last_name is None:
            return False

        return self._is_setup_continuation_statement(
            body[block_index - 1],
            last_name,
        ) and self._block_uses_name(block_statement, last_name)

    def _is_setup_continuation_statement(
        self,
        statement: cst.BaseStatement,
        name: str,
    ) -> bool:
        if not isinstance(statement, cst.SimpleStatementLine) or len(statement.body) != 1:
            return False

        expr = statement.body[0]
        if not isinstance(expr, cst.Expr):
            return False

        value = expr.value.func if isinstance(expr.value, cst.Call) else expr.value

        return (
            isinstance(value, cst.Attribute)
            and isinstance(value.value, cst.Name)
            and value.value.value == name
        )

    def _is_allowed_setup_run_cuddle(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
        block_statement: cst.BaseStatement,
    ) -> bool:
        lookback = self._setup_run_lookback()
        if lookback <= 0:
            return False

        _run_start, run = contiguous_run_before(body, block_index)
        if not run:
            return False

        run = run[-lookback:]
        assignment_positions = [
            position
            for position, statement in enumerate(run)
            if assignment_small_statement(statement) is not None
        ]
        if len(assignment_positions) != 1:
            return False

        assignment_position = assignment_positions[0]
        assignment_statement = run[assignment_position]
        last_name = last_assigned_name(assignment_statement)
        if last_name is None:
            return False

        trailing_run = run[assignment_position + 1 :]
        if self._is_guard_ladder_setup_cuddle(body, block_index, assignment_position, trailing_run):
            return True

        trailing_run_uses_name = bool(trailing_run) and all(
            self._is_setup_continuation_statement(statement, last_name)
            for statement in trailing_run
        )

        return trailing_run_uses_name and self._block_uses_name(block_statement, last_name)


def validate_non_negative_int(value: object) -> object:
    if value < 0:
        raise ValueError("must be greater than or equal to 0")

    return value


__all__: list[str] = [
    "BaseBlankLinesRule",
    "BaseBlockHeaderCuddleRule",
    "validate_non_negative_int",
]
