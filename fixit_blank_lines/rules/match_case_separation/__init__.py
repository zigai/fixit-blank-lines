from __future__ import annotations

from itertools import pairwise

import libcst as cst
from fixit import Invalid, LintRule, Valid
from libcst.metadata import PositionProvider

from fixit_blank_lines.rules.base import BaseBlankLinesRule


class MatchCaseSeparation(BaseBlankLinesRule, LintRule):
    """Require spacing before the next case after large case bodies."""

    CASE_MAX_LINES = 2
    MESSAGE = (
        "BL400 Missing separator between match cases. "
        "Case bodies larger than 2 non-empty lines should be separated from the next case."
    )

    VALID = [
        Valid(
            """
            def f(value: int) -> int:
                match value:
                    case 1:
                        return 1
                    case _:
                        return 0
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                match value:
                    case 1:
                        a = 1
                        b = 2
                        c = 3

                    case _:
                        return 0
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            def f(value: int) -> int:
                match value:
                    case 1:
                        a = 1
                        b = 2
                        c = 3
                    case _:
                        return 0
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(value: int) -> int:
                match value:
                    case 1:
                        first = 1
                        second = 2
                        third = 3
                    case 2:
                        return 2
                    case _:
                        return 0
            """,
            expected_message=MESSAGE,
        ),
    ]

    def visit_Match(self, node: cst.Match) -> None:
        if len(node.cases) < 2:
            return

        for current_case, next_case in pairwise(node.cases):
            if self._node_non_empty_line_count(current_case.body) <= self.CASE_MAX_LINES:
                continue

            current_position = self.get_metadata(PositionProvider, current_case)
            next_position = self.get_metadata(PositionProvider, next_case)
            if next_position.start.line > current_position.end.line + 1:
                continue

            self.report(next_case, message=self.MESSAGE)


__all__ = ["MatchCaseSeparation"]
