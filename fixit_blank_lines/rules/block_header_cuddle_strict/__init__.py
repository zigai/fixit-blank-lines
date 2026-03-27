from __future__ import annotations

from rattle import Invalid, LintRule, Valid

from fixit_blank_lines.rules.base import BaseBlockHeaderCuddleRule


class BlockHeaderCuddleStrict(BaseBlockHeaderCuddleRule, LintRule):
    """Strict variant: only the immediately previous assignment may cuddle."""

    CODE = "BL301"
    ALIASES = ("BlockHeaderCuddleStrict",)
    STRICT = True
    ALLOW_FIRST_BODY_USAGE = False
    MESSAGE = (
        "BL301 Illegal cuddle before block header in strict mode. "
        "Only the immediately previous assignment may feed the block header."
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
                    return value

                return 0
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
                header_value = value + 1
                trailing = value + 2
                if header_value > 0:
                    return header_value

                return 0
            """,
            expected_replacement="""
            def f(value: int) -> int:
                header_value = value + 1
                trailing = value + 2

                if header_value > 0:
                    return header_value

                return 0
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(value: int) -> int:
                prepared = value + 1
                if value > 0:
                    result = prepared
                    return result

                return 0
            """,
            expected_replacement="""
            def f(value: int) -> int:
                prepared = value + 1

                if value > 0:
                    result = prepared
                    return result

                return 0
            """,
            expected_message=MESSAGE,
        ),
    ]


__all__ = ["BlockHeaderCuddleStrict"]
