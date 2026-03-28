from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from rattle import Invalid, LintRule, RuleSetting, Valid

from rattle_blank_lines.rules.base import BaseBlockHeaderCuddleRule, validate_non_negative_int


class BlockHeaderCuddleRelaxed(BaseBlockHeaderCuddleRule, LintRule):
    """Allow cuddling only when preceding setup directly feeds the next block."""

    CODE = "BL300"
    ALIASES = ("BlockHeaderCuddleRelaxed",)
    STRICT = False
    BODY_USAGE_LOOKAHEAD = 4
    SETTINGS = {
        "body_usage_lookahead": RuleSetting(
            int,
            default=4,
            validator=validate_non_negative_int,
        ),
        "setup_run_lookback": RuleSetting(
            int,
            default=3,
            validator=validate_non_negative_int,
        ),
        "allow_setup_before_compact_guard_ladder": RuleSetting(bool, default=True),
    }
    MESSAGE = (
        "BL300 Illegal cuddle before block header. "
        "The preceding setup must directly feed the upcoming block."
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
        Valid(
            """
            def f(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
                merged = dict(base)
                for key, value in override.items():
                    if key not in merged:
                        merged[key] = value
                        continue
                    merged[key] = value

                return merged
            """
        ),
        Valid(
            """
            def f(directory: str) -> None:
                queue = Queue()
                queue.put(directory)
                while not queue.empty():
                    item = queue.get()
                    visit(item)
            """
        ),
        Valid(
            """
            def f(shell_name: str) -> list[str]:
                interactive = shell_name == "zsh"
                if shell_name == "zsh":
                    return ["-lic"]
                if interactive:
                    return ["-ic"]
                return ["-lc"]
            """
        ),
        Valid(
            """
            def f(candidate: object, parser_input: str, style: object) -> object:
                display_value = parser_input or str(candidate)
                if supports_live_interaction():
                    highlight(display_value, style)
                else:
                    summarize(display_value, style)
                return candidate
            """
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
        Invalid(
            """
            def f(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
                merged = dict(base)
                for key, value in override.items():
                    log_key(key)
                    audit(value)
                    publish(key, value)
                    notify_team(key)
                    merged[key] = value

                return merged
            """,
            expected_replacement="""
            def f(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
                merged = dict(base)

                for key, value in override.items():
                    log_key(key)
                    audit(value)
                    publish(key, value)
                    notify_team(key)
                    merged[key] = value

                return merged
            """,
            expected_message=MESSAGE,
        ),
        Invalid(
            """
            def f(default_value: object) -> object:
                prompt_kwargs: dict[str, object] = {}
                if default_value:
                    prompt_kwargs["placeholder"] = str(default_value)
                return prompt_kwargs
            """,
            expected_replacement="""
            def f(default_value: object) -> object:
                prompt_kwargs: dict[str, object] = {}

                if default_value:
                    prompt_kwargs["placeholder"] = str(default_value)
                return prompt_kwargs
            """,
            expected_message=MESSAGE,
        ),
    ]


__all__ = ["BlockHeaderCuddleRelaxed"]
