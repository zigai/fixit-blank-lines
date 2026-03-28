from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from rattle import Invalid, LintRule, Valid

from rattle_blank_lines.rules.base import BaseBlockHeaderCuddleRule


class BlockHeaderCuddleRelaxed(BaseBlockHeaderCuddleRule, LintRule):
    """Allow cuddling when the previous assignment feeds the next block."""

    CODE = "BL300"
    ALIASES = ("BlockHeaderCuddleRelaxed",)
    STRICT = False
    MESSAGE = (
        "BL300 Illegal cuddle before block header. "
        "The immediately previous assignment must feed the block header or first body statement."
    )

    VALID = [
        Valid(
            """
            def f(value: int) -> int:
                prepared = value + 1
                if prepared > 0:
                    return prepared

                return 0
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                prepared = value + 1
                if value > 0:
                    result = prepared
                    return result

                return 0
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                log_start()
                prepared = value + 1
                if prepared > 0:
                    return prepared

                return 0
            """
        ),
        Valid(
            """
            def f(value: int) -> int:
                prepared = value + 1
                not_used = value + 2

                if value > 0:
                    return value

                return prepared
            """
        ),
        Valid(
            '''
            def f(value: int) -> int:
                """Compute value."""
                if value > 0:
                    return value

                return 0
            '''
        ),
    ]

    def _assignment_run(
        self,
        body: Sequence[cst.BaseStatement],
        block_index: int,
    ) -> Sequence[cst.BaseStatement]:
        return body[block_index - 1 : block_index]

    INVALID = [
        Invalid(
            """
            def f(value: int) -> int:
                prepared = value + 1
                if value > 0:
                    return value

                return 0
            """,
            expected_replacement="""
            def f(value: int) -> int:
                prepared = value + 1

                if value > 0:
                    return value

                return 0
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(value: int) -> int:
                prepared = value + 1
                log(prepared)
                if prepared > 0:
                    return prepared

                return 0
            """,
            expected_replacement="""
            def f(value: int) -> int:
                prepared = value + 1
                log(prepared)

                if prepared > 0:
                    return prepared

                return 0
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(value: int) -> int:
                prepared = value + 1
                trailing = value + 2
                if prepared > 0:
                    return prepared

                return 0
            """,
            expected_replacement="""
            def f(value: int) -> int:
                prepared = value + 1
                trailing = value + 2

                if prepared > 0:
                    return prepared

                return 0
            """,
            expected_message=MESSAGE,
        ),
    ]


__all__ = ["BlockHeaderCuddleRelaxed"]
