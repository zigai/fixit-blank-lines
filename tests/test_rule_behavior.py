from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest
from rattle import Config, Invalid, LintRule, Valid
from rattle.config import QualifiedRule, find_rules, resolve_rule_settings
from rattle.engine import LintRunner

from rattle_blank_lines.rules import (
    BlankLineAfterControlBlock,
    BlankLineBeforeBranchInLargeSuite,
    BlockHeaderCuddleRelaxed,
    NoSuiteLeadingTrailingBlankLines,
)
from rattle_blank_lines.rules.blank_line_before_assignment import BlankLineBeforeAssignment
from rattle_blank_lines.rules.block_header_cuddle_strict import BlockHeaderCuddleStrict
from rattle_blank_lines.rules.match_case_separation import MatchCaseSeparation

RULE_CLASSES: tuple[type[LintRule], ...] = (
    NoSuiteLeadingTrailingBlankLines,
    BlankLineBeforeAssignment,
    BlankLineBeforeBranchInLargeSuite,
    BlockHeaderCuddleRelaxed,
    BlockHeaderCuddleStrict,
    BlankLineAfterControlBlock,
    MatchCaseSeparation,
)

DEFAULT_RULE_PACK: tuple[type[LintRule], ...] = (
    NoSuiteLeadingTrailingBlankLines,
    BlankLineBeforeAssignment,
    BlankLineBeforeBranchInLargeSuite,
    BlockHeaderCuddleRelaxed,
    BlankLineAfterControlBlock,
)


def _dedent(source: str) -> str:
    return textwrap.dedent(re.sub(r"\A\n", "", source))


def _as_valid(case: str | Valid) -> Valid:
    if isinstance(case, str):
        return Valid(code=case)

    return case


def _as_invalid(case: str | Invalid) -> Invalid:
    if isinstance(case, str):
        return Invalid(code=case)

    return case


def _run_rule(
    rule_cls: type[LintRule],
    source: str,
    options: dict[str, str | int | float | bool | list[str | int | float | bool]] | None = None,
) -> tuple[LintRunner, list]:
    path = Path("fixture.py")
    rule = rule_cls()
    if options is not None:
        rule.configure(options)
    runner = LintRunner(path, _dedent(source).encode())
    reports = list(runner.collect_violations([rule], Config(path=path, root=Path.cwd())))

    return runner, reports


def _run_rules(
    rule_classes: tuple[type[LintRule], ...],
    source: str,
) -> tuple[LintRunner, list]:
    path = Path("fixture.py")
    rules = [rule_cls() for rule_cls in rule_classes]
    runner = LintRunner(path, _dedent(source).encode())
    reports = list(runner.collect_violations(rules, Config(path=path, root=Path.cwd())))

    return runner, reports


VALID_CASES = [
    pytest.param(
        rule_cls,
        _as_valid(case),
        id=f"{rule_cls.__name__}.VALID[{index}]",
    )
    for rule_cls in RULE_CLASSES
    for index, case in enumerate(rule_cls.VALID)
]

INVALID_CASES = [
    pytest.param(
        rule_cls,
        _as_invalid(case),
        id=f"{rule_cls.__name__}.INVALID[{index}]",
    )
    for rule_cls in RULE_CLASSES
    for index, case in enumerate(rule_cls.INVALID)
]


@pytest.mark.parametrize(("rule_cls", "case"), VALID_CASES)
def test_valid_fixtures_produce_no_reports(rule_cls: type[LintRule], case: Valid) -> None:
    _, reports = _run_rule(rule_cls, case.code, case.options)
    assert reports == []


@pytest.mark.parametrize(("rule_cls", "case"), INVALID_CASES)
def test_invalid_fixtures_produce_expected_reports(
    rule_cls: type[LintRule],
    case: Invalid,
) -> None:
    runner, reports = _run_rule(rule_cls, case.code, case.options)

    assert reports

    if case.expected_message is not None:
        assert all(report.message == case.expected_message for report in reports)

    if case.expected_replacement is not None:
        fixed_code = runner.apply_replacements(reports).code
        assert fixed_code == _dedent(case.expected_replacement)

        _, fixed_reports = _run_rule(rule_cls, fixed_code, case.options)
        assert fixed_reports == []


def test_rule_discovery_only_returns_concrete_rules() -> None:
    discovered = {rule.__name__ for rule in find_rules(QualifiedRule("rattle_blank_lines.rules"))}
    assert "BaseBlankLinesRule" not in discovered
    assert "BaseBlockHeaderCuddleRule" not in discovered
    assert "BlockHeaderCuddleStrict" not in discovered
    assert "MatchCaseSeparation" not in discovered


def test_strict_rule_can_be_enabled_explicitly() -> None:
    discovered = {
        rule.__name__
        for rule in find_rules(QualifiedRule("rattle_blank_lines.rules.block_header_cuddle_strict"))
    }
    assert discovered == {"BlockHeaderCuddleStrict"}


def test_match_case_rule_can_be_enabled_explicitly() -> None:
    discovered = {
        rule.__name__
        for rule in find_rules(QualifiedRule("rattle_blank_lines.rules.match_case_separation"))
    }
    assert discovered == {"MatchCaseSeparation"}


def test_rule_settings_resolve_from_code_selectors() -> None:
    path = Path("fixture.py")
    config = Config(
        path=path,
        root=Path.cwd(),
        options={
            "BL200": {"max_suite_non_empty_lines": 4},
            "BL210": {"short_control_flow_max_statements": 1},
            "BL400": {"max_case_non_empty_lines": 5},
        },
    )

    resolved = resolve_rule_settings(
        config,
        {
            BlankLineBeforeBranchInLargeSuite,
            BlankLineBeforeAssignment,
            MatchCaseSeparation,
        },
    )

    assert resolved == {
        BlankLineBeforeBranchInLargeSuite: {"max_suite_non_empty_lines": 4},
        BlankLineBeforeAssignment: {"short_control_flow_max_statements": 1},
        MatchCaseSeparation: {"max_case_non_empty_lines": 5},
    }


def test_bl200_reports_branch_keyword_instead_of_full_multiline_return() -> None:
    _, reports = _run_rule(
        BlankLineBeforeBranchInLargeSuite,
        """
        def f(value: int) -> dict[str, int]:
            first = value + 1
            second = first + 1
            return {
                "first": first,
                "second": second,
            }
        """,
        {"allow_related_return_tails": False},
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.range.start.line == 4
    assert report.range.end.line == 4
    assert report.range.end.column - report.range.start.column == len("return")


def test_bl200_allows_typed_result_binding_immediately_before_return() -> None:
    _, reports = _run_rule(
        BlankLineBeforeBranchInLargeSuite,
        """
        def f(parts: list[str]) -> dict[str, int]:
            cleaned = [part.strip() for part in parts]
            joined = ",".join(cleaned)
            payload: dict[str, int] = {"count": len(cleaned), "width": len(joined)}
            return payload
        """,
    )

    assert reports == []


def test_bl100_allows_ruff_style_blank_line_before_nested_loop_handler() -> None:
    _, reports = _run_rule(
        NoSuiteLeadingTrailingBlankLines,
        """
        def f(keys: str) -> None:
            for key in keys:

                @register(key)
                def handle() -> None:
                    print(key)
        """,
    )

    assert reports == []


def test_bl100_keeps_class_body_compact_at_suite_start() -> None:
    _, reports = _run_rule(
        NoSuiteLeadingTrailingBlankLines,
        """
        class Handler:

            def handle(self) -> None:
                print("x")
        """,
    )

    assert len(reports) == 1
    assert reports[0].message == NoSuiteLeadingTrailingBlankLines.LEADING_MESSAGE


def test_bl210_reports_first_line_of_multiline_assignment() -> None:
    _, reports = _run_rule(
        BlankLineBeforeAssignment,
        """
        def f(value: int) -> dict[str, int]:
            log_value(value)
            payload = {
                "value": value,
            }
            return payload
        """,
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.range.start.line == 3
    assert report.range.end.line == 3


def test_default_rule_pack_converges_after_guard_to_assignment_fix() -> None:
    runner, reports = _run_rules(
        DEFAULT_RULE_PACK,
        """
        def f(flag: bool, label: str) -> str:
            if not flag:
                return label
            cleaned = label.strip()
            return cleaned
        """,
    )

    assert reports

    fixed_code = runner.apply_replacements(reports).code
    assert fixed_code == _dedent(
        """
        def f(flag: bool, label: str) -> str:
            if not flag:
                return label

            cleaned = label.strip()

            return cleaned
        """
    )

    _, fixed_reports = _run_rules(DEFAULT_RULE_PACK, fixed_code)
    assert fixed_reports == []


def test_default_rule_pack_allows_compact_terminal_simple_return_tail() -> None:
    _, reports = _run_rules(
        DEFAULT_RULE_PACK,
        """
        def f() -> int:
            log_start()
            value = compute()
            return value
        """,
    )

    assert reports == []


def test_default_rule_pack_allows_ruff_style_nested_definition_at_loop_start() -> None:
    _, reports = _run_rules(
        DEFAULT_RULE_PACK,
        """
        def f(digits: str) -> None:
            for digit in digits:

                @register(digit)
                def handle() -> None:
                    print(digit)
        """,
    )

    assert reports == []


def test_default_rule_pack_converges_after_nested_loop_tail_return() -> None:
    runner, reports = _run_rules(
        DEFAULT_RULE_PACK,
        """
        def f(items: list[int]) -> tuple[int, ...]:
            result: list[int] = []
            if items:
                for item in items:
                    if item % 2 == 0:
                        result.append(item)
                return tuple(result)

            return ()
        """,
    )

    assert reports

    fixed_code = runner.apply_replacements(reports).code
    _, fixed_reports = _run_rules(DEFAULT_RULE_PACK, fixed_code)
    assert fixed_reports == []


def test_default_rule_pack_converges_after_nested_guard_chain_assignment_followup() -> None:
    runner, reports = _run_rules(
        DEFAULT_RULE_PACK,
        """
        def f(values: list[str]) -> dict[str, str]:
            result: dict[str, str] = {}
            for value in values:
                if value == "":
                    continue
                if value.startswith("#"):
                    cleaned = value.removeprefix("#")
                    if not cleaned:
                        continue
                    value = cleaned
                result[value] = value

            return result
        """,
    )

    assert reports

    fixed_code = runner.apply_replacements(reports).code
    _, fixed_reports = _run_rules(DEFAULT_RULE_PACK, fixed_code)
    assert fixed_reports == []


def test_bl300_reports_block_header_line_only() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(default_value: object) -> object:
            prepared = default_value
            if default_value:
                log(default_value)
            return prepared
        """,
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.range.start.line == 3
    assert report.range.end.line == 3
    assert report.range.end.column - report.range.start.column == len("if")


def test_bl300_allows_same_result_slot_guarded_overwrite() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(override_name: str | None) -> str:
            display_name = "guest"
            if override_name is not None:
                display_name = override_name
            return display_name
        """,
    )

    assert reports == []


def test_bl300_allows_compact_guard_ladder_before_separated_main_path_return() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(primary: str | None, fallback: str | None) -> str:
            if primary is not None:
                return primary
            if fallback is not None:
                return fallback

            return "guest"
        """,
    )

    assert reports == []


def test_bl300_allows_container_initialized_before_guarded_mutation() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(default_value: object) -> dict[str, object]:
            prompt_kwargs: dict[str, object] = {}
            if default_value:
                prompt_kwargs["placeholder"] = str(default_value)
            return prompt_kwargs
        """,
    )

    assert reports == []


def test_bl300_allows_immediate_same_receiver_setup_and_guard() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f() -> None:
            session = build_session()
            session.refresh()
            if session.is_stale():
                reset_session(session)
                return
            cleanup()
        """,
    )

    assert reports == []


def test_bl300_allows_immediate_subscript_update_and_guard() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(slots: dict[str, int], key: str) -> None:
            slots[key] -= 1
            if slots[key] < 0:
                raise ValueError(key)
        """,
    )

    assert reports == []


def test_bl300_allows_immediate_attribute_assignment_and_guard() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(session: object) -> None:
            session.ready = compute_ready_flag()
            if session.ready:
                start(session)
        """,
    )

    assert reports == []


def test_bl300_allows_immediate_same_receiver_rhs_and_guard() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(task_state: object) -> None:
            total = 0.0
            total += task_state.total
            if task_state.completed is not None:
                consume(task_state.completed, total)
        """,
    )

    assert reports == []


def test_bl300_allows_expression_setup_before_related_match() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(registry: object, handler: object) -> object:
            registry.attach(handler)
            match registry.mode:
                case "primary":
                    return registry.dispatch("x")
                case _:
                    return registry.dispatch("fallback")
        """,
    )

    assert reports == []


def test_bl300_allows_expression_setup_before_related_with_block() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(tracker: object) -> object:
            tracker.prepare("job")
            with tracker.capture() as snapshot:
                tracker.enable()
                return tracker.finish(), snapshot
        """,
    )

    assert reports == []


def test_bl300_allows_tuple_unpack_before_related_guard() -> None:
    _, reports = _run_rule(
        BlockHeaderCuddleRelaxed,
        """
        def f(subject: object) -> None:
            left, candidate, payload = inspect_subject(subject)
            if not isinstance(candidate, ExpectedNode):
                raise UnexpectedNodeError(f"Unexpected node type: {type(candidate)!r}")
            consume(left, payload)
        """,
    )

    assert reports == []


def test_bl350_reports_first_line_of_following_multiline_statement() -> None:
    _, reports = _run_rule(
        BlankLineAfterControlBlock,
        """
        def f(value: int) -> dict[str, int]:
            if value > 0:
                value += 1
            return {
                "value": value,
            }
        """,
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.range.start.line == 4
    assert report.range.end.line == 4


def test_bl350_allows_related_expression_fallthrough() -> None:
    _, reports = _run_rule(
        BlankLineAfterControlBlock,
        """
        def f(width: int | None, columns: list[str]) -> list[str]:
            if width is not None:
                template = f"{width:02d}"
                columns.append(template)
            columns.append(template if width is not None else "default")
            return columns
        """,
    )

    assert reports == []


def test_default_rule_pack_keeps_loop_cleanup_compact_but_separates_phases() -> None:
    runner, reports = _run_rules(
        DEFAULT_RULE_PACK,
        """
        def f(stream: object) -> tuple[object, ...]:
            captured: list[object] = []
            while stream.tokens:
                token = stream.tokens[0]
                if token == "<STOP>":
                    stream.tokens.pop(0)
                    captured.extend(stream.tokens)
                    stream.tokens.clear()
                    break
                if stream.is_boundary(token):
                    break
                captured.append(stream.tokens.pop(0))
            return tuple(captured)
        """,
    )

    fixed_code = runner.apply_replacements(reports).code
    assert fixed_code == _dedent(
        """
        def f(stream: object) -> tuple[object, ...]:
            captured: list[object] = []
            while stream.tokens:
                token = stream.tokens[0]
                if token == "<STOP>":
                    stream.tokens.pop(0)
                    captured.extend(stream.tokens)
                    stream.tokens.clear()
                    break

                if stream.is_boundary(token):
                    break

                captured.append(stream.tokens.pop(0))

            return tuple(captured)
        """
    )

    _, fixed_reports = _run_rules(DEFAULT_RULE_PACK, fixed_code)
    assert fixed_reports == []


def test_default_rule_pack_keeps_tuple_unpack_attached_to_guard_then_separates_main_flow() -> None:
    runner, reports = _run_rules(
        DEFAULT_RULE_PACK,
        """
        def f(subject: object) -> None:
            left, candidate, payload = inspect_subject(subject)
            if not isinstance(candidate, ExpectedNode):
                raise UnexpectedNodeError(f"Unexpected node type: {type(candidate)!r}")
            resolved_name = left if left is not None else (candidate.name or "")
            consume(resolved_name, payload)
        """,
    )

    fixed_code = runner.apply_replacements(reports).code
    assert fixed_code == _dedent(
        """
        def f(subject: object) -> None:
            left, candidate, payload = inspect_subject(subject)
            if not isinstance(candidate, ExpectedNode):
                raise UnexpectedNodeError(f"Unexpected node type: {type(candidate)!r}")

            resolved_name = left if left is not None else (candidate.name or "")
            consume(resolved_name, payload)
        """
    )

    _, fixed_reports = _run_rules(DEFAULT_RULE_PACK, fixed_code)
    assert fixed_reports == []


def test_bl200_allows_compact_cleanup_break_tail() -> None:
    _, reports = _run_rule(
        BlankLineBeforeBranchInLargeSuite,
        """
        def f(stream: object, captured: list[str]) -> None:
            while stream.tokens:
                if stream.tokens[0] == "<STOP>":
                    stream.tokens.pop(0)
                    captured.extend(stream.tokens)
                    stream.tokens.clear()
                    break
        """,
    )

    assert reports == []


def test_bl400_reports_case_keyword_only() -> None:
    _, reports = _run_rule(
        MatchCaseSeparation,
        """
        def f(value: int) -> int:
            match value:
                case 1:
                    first = 1
                    second = 2
                    third = 3
                case _:
                    return 0
        """,
    )

    assert len(reports) == 1
    report = reports[0]
    assert report.range.start.line == 7
    assert report.range.end.line == 7
    assert report.range.end.column - report.range.start.column == len("case")
