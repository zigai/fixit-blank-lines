from __future__ import annotations

from itertools import pairwise

import libcst as cst
from libcst.metadata import PositionProvider
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlankLinesRule, validate_non_negative_int


class MatchCaseSeparation(BaseBlankLinesRule, LintRule):
    """Require spacing before the next case after large case bodies."""

    CODE = "BL400"
    ALIASES = ("MatchCaseSeparation",)
    MESSAGE = "BL400 Missing separator between match cases after a large case body."
    SETTINGS = {
        "max_case_non_empty_lines": RuleSetting(
            int,
            default=2,
            validator=validate_non_negative_int,
        ),
    }

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
            """,
            options={"max_case_non_empty_lines": 3},
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
        Invalid(
            """
            def f(value: int) -> int:
                match value:
                    case 1:
                        a = 1
                        b = 2
                    case _:
                        return 0
            """,
            expected_message=MESSAGE,
            options={"max_case_non_empty_lines": 1},
        ),
    ]

    def visit_Match(self, node: cst.Match) -> None:
        if len(node.cases) < 2:
            return

        max_case_non_empty_lines = int(self.settings["max_case_non_empty_lines"])
        for current_case, next_case in pairwise(node.cases):
            if self._node_non_empty_line_count(current_case.body) <= max_case_non_empty_lines:
                continue
            current_position = self.get_metadata(PositionProvider, current_case)
            next_position = self.get_metadata(PositionProvider, next_case)
            if next_position.start.line > current_position.end.line + 1:
                continue

            self.report(
                next_case,
                message=self.MESSAGE,
                position=self._match_case_anchor_range(next_case),
            )


__all__ = ["MatchCaseSeparation"]
