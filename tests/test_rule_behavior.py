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
