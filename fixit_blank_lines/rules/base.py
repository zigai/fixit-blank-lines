from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from libcst.metadata import ParentNodeProvider, PositionProvider

from fixit_blank_lines.utils import (
    assignment_small_statement,
    collect_names,
    count_non_empty_lines,
    first_statement_in_block,
    has_separator,
    header_expression_nodes,
    is_docstring_statement,
    is_header_block_statement,
    last_assigned_name,
    prepend_blank_line,
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
        candidate_run = self._assignment_run(body, block_index)
        if not candidate_run:
            return False

        if not all(
            assignment_small_statement(statement) is not None for statement in candidate_run
        ):
            return False

        last_name = last_assigned_name(candidate_run[-1])
        if last_name is None:
            return False

        if self._header_uses_name(block_statement, last_name):
            return True

        return self.ALLOW_FIRST_BODY_USAGE and self._first_body_statement_uses_name(
            block_statement, last_name
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
        first_statement = first_statement_in_block(statement)
        if first_statement is None:
            return False

        return name in collect_names(first_statement)


def validate_non_negative_int(value: object) -> object:
    if value < 0:
        raise ValueError("must be greater than or equal to 0")

    return value


__all__: list[str] = [
    "BaseBlankLinesRule",
    "BaseBlockHeaderCuddleRule",
    "validate_non_negative_int",
]
