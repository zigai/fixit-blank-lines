from __future__ import annotations

from fixit import Invalid, LintRule, Valid

from fixit_blank_lines.rules.base import BaseBlockHeaderCuddleRule


class BlockHeaderCuddleRelaxed(BaseBlockHeaderCuddleRule, LintRule):
    """Allow cuddling only when assignment prep feeds the next block."""

    STRICT = False
    MESSAGE = (
        "BL300 Illegal cuddle before block header. "
        "The final prep assignment must feed the block header or first body statement."
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
