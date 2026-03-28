from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from libcst.metadata import CodePosition, CodeRange, ParentNodeProvider, PositionProvider

from rattle_blank_lines.utils import (
    assignment_small_statement,
    collect_attribute_receivers,
    collect_comparable_expressions,
    collect_names,
    contiguous_run_before,
    control_block_consumed_names_in_early_body,
    count_non_empty_lines,
    expression_statement_value,
    first_statement_in_block,
    has_separator,
    header_expression_nodes,
    is_compact_guard_if,
    is_docstring_statement,
    is_header_block_statement,
    last_assigned_name,
    last_assigned_target_expression,
    leading_block_body_statements,
    prepend_blank_line,
    starts_compact_guard_ladder,
    statement_reference_names,
    statement_touches_name,
    statement_touches_target_expression,
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

    def _line_end_column(self, line_number: int) -> int:
        source_lines = self._source_lines()
        if 1 <= line_number <= len(source_lines):
            return len(source_lines[line_number - 1])

        return 0

    def _first_line_range(self, node: cst.CSTNode) -> CodeRange:
        position = self.get_metadata(PositionProvider, node)
        return CodeRange(
            start=position.start,
            end=CodePosition(
                line=position.start.line,
                column=self._line_end_column(position.start.line),
            ),
        )

    def _range_for_keyword(self, node: cst.CSTNode, keyword: str) -> CodeRange:
        position = self.get_metadata(PositionProvider, node)
        return CodeRange(
            start=position.start,
            end=CodePosition(
                line=position.start.line,
                column=position.start.column + len(keyword),
            ),
        )

    def _branch_anchor_range(self, statement: cst.BaseStatement) -> CodeRange:
        if isinstance(statement, cst.SimpleStatementLine) and len(statement.body) == 1:
            branch = statement.body[0]
            keyword = {
                cst.Break: "break",
                cst.Continue: "continue",
                cst.Raise: "raise",
                cst.Return: "return",
            }.get(type(branch))
            if keyword is not None:
                return self._range_for_keyword(statement, keyword)

        return self._first_line_range(statement)

    def _block_header_anchor_range(self, statement: cst.BaseStatement) -> CodeRange:
        keyword = {
            cst.For: "for",
            cst.If: "if",
            cst.Match: "match",
            cst.Try: "try",
            cst.While: "while",
            cst.With: "with",
        }.get(type(statement))
        if keyword is not None:
            return self._range_for_keyword(statement, keyword)

        return self._first_line_range(statement)

    def _match_case_anchor_range(self, case: cst.MatchCase) -> CodeRange:
        return self._range_for_keyword(case, "case")

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
                position=self._block_header_anchor_range(statement),
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

        if not self.STRICT and self._shares_immediate_receiver_subject(
            body, block_index, block_statement
        ):
            return True

        candidate_run = self._assignment_run(body, block_index)
        has_assignment_run = bool(candidate_run) and all(
            assignment_small_statement(statement) is not None for statement in candidate_run
        )
        last_name = last_assigned_name(candidate_run[-1]) if has_assignment_run else None
        if last_name is not None and self._block_is_related_to_name(block_statement, last_name):
            return True

        last_target_expression = (
            last_assigned_target_expression(candidate_run[-1]) if has_assignment_run else None
        )
        if last_target_expression is not None and self._block_is_related_to_target_expression(
            block_statement,
            last_target_expression,
        ):
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

    def _header_uses_target_expression(
        self,
        statement: cst.BaseStatement,
        target_expression: cst.BaseExpression,
    ) -> bool:
        return any(
            expression.deep_equals(target_expression)
            for header_expression in header_expression_nodes(statement)
            for expression in collect_comparable_expressions(header_expression)
        )

    def _first_body_statement_uses_name(self, statement: cst.BaseStatement, name: str) -> bool:
        if isinstance(statement, cst.If):
            return name in control_block_consumed_names_in_early_body(statement, limit=1)

        first_statement = first_statement_in_block(statement)
        if first_statement is None:
            return False

        return name in collect_names(first_statement)

    def _first_body_statement_uses_target_expression(
        self,
        statement: cst.BaseStatement,
        target_expression: cst.BaseExpression,
    ) -> bool:
        first_statement = first_statement_in_block(statement)
        if first_statement is None:
            return False

        return any(
            expression.deep_equals(target_expression)
            for expression in collect_comparable_expressions(first_statement)
        )

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

    def _early_body_statement_uses_target_expression(
        self,
        statement: cst.BaseStatement,
        target_expression: cst.BaseExpression,
    ) -> bool:
        if self._body_usage_lookahead() <= 0:
            return False

        for body_statement in leading_block_body_statements(
            statement,
            limit=self._body_usage_lookahead(),
        ):
            if any(
                expression.deep_equals(target_expression)
                for expression in collect_comparable_expressions(body_statement)
            ):
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

    def _block_uses_target_expression(
        self,
        statement: cst.BaseStatement,
        target_expression: cst.BaseExpression,
    ) -> bool:
        return (
            self._header_uses_target_expression(statement, target_expression)
            or (
                self.ALLOW_FIRST_BODY_USAGE
                and self._first_body_statement_uses_target_expression(
                    statement,
                    target_expression,
                )
            )
            or self._early_body_statement_uses_target_expression(statement, target_expression)
        )

    def _early_body_statement_touches_name(self, statement: cst.BaseStatement, name: str) -> bool:
        if self._body_usage_lookahead() <= 0:
            return False

        for body_statement in leading_block_body_statements(
            statement,
            limit=self._body_usage_lookahead(),
        ):
            if statement_touches_name(body_statement, name):
                return True

        return False

    def _early_body_statement_touches_target_expression(
        self,
        statement: cst.BaseStatement,
        target_expression: cst.BaseExpression,
    ) -> bool:
        if self._body_usage_lookahead() <= 0:
            return False

        for body_statement in leading_block_body_statements(
            statement,
            limit=self._body_usage_lookahead(),
        ):
            if statement_touches_target_expression(body_statement, target_expression):
                return True

        return False

    def _block_is_related_to_name(self, statement: cst.BaseStatement, name: str) -> bool:
        return self._block_uses_name(statement, name) or self._early_body_statement_touches_name(
            statement,
            name,
        )

    def _block_is_related_to_target_expression(
        self,
        statement: cst.BaseStatement,
        target_expression: cst.BaseExpression,
    ) -> bool:
        return self._block_uses_target_expression(
            statement,
            target_expression,
        ) or self._early_body_statement_touches_target_expression(
            statement,
            target_expression,
        )

    def _shares_immediate_receiver_subject(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
        block_statement: cst.BaseStatement,
    ) -> bool:
        if block_index <= 0:
            return False

        previous_expression = expression_statement_value(body[block_index - 1])
        if previous_expression is None:
            return False

        previous_receivers = collect_attribute_receivers(previous_expression)
        if not previous_receivers:
            return False

        return any(
            previous_receiver.deep_equals(block_receiver)
            for header_expression in header_expression_nodes(block_statement)
            for previous_receiver in previous_receivers
            for block_receiver in collect_attribute_receivers(header_expression)
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
        ) and self._block_is_related_to_name(block_statement, last_name)

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

        return trailing_run_uses_name and self._block_is_related_to_name(
            block_statement,
            last_name,
        )


def validate_non_negative_int(value: object) -> object:
    if value < 0:
        raise ValueError("must be greater than or equal to 0")

    return value


__all__: list[str] = [
    "BaseBlankLinesRule",
    "BaseBlockHeaderCuddleRule",
    "validate_non_negative_int",
]
