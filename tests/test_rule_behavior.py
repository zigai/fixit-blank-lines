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
        assert runner.apply_replacements(reports).code == _dedent(case.expected_replacement)


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
