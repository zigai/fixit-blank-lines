from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest
from fixit import Config, Invalid, QualifiedRule, Valid
from fixit.config import find_rules
from fixit.engine import LintRunner
from fixit.rule import LintRule

from fixit_blank_lines.rules import (
    BlankLineAfterControlBlock,
    BlankLineBeforeBranchInLargeSuite,
    BlockHeaderCuddleRelaxed,
    BlockHeaderCuddleStrict,
    NoSuiteLeadingTrailingBlankLines,
)
from fixit_blank_lines.rules.blank_line_before_assignment import BlankLineBeforeAssignment
from fixit_blank_lines.rules.match_case_separation import MatchCaseSeparation

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


def _run_rule(rule_cls: type[LintRule], source: str) -> tuple[LintRunner, list]:
    path = Path("fixture.py")
    runner = LintRunner(path, _dedent(source).encode())
    reports = list(runner.collect_violations([rule_cls()], Config(path=path)))

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
    _, reports = _run_rule(rule_cls, case.code)
    assert reports == []


@pytest.mark.parametrize(("rule_cls", "case"), INVALID_CASES)
def test_invalid_fixtures_produce_expected_reports(
    rule_cls: type[LintRule],
    case: Invalid,
) -> None:
    runner, reports = _run_rule(rule_cls, case.code)

    assert reports

    if case.expected_message is not None:
        assert all(report.message == case.expected_message for report in reports)

    if case.expected_replacement is not None:
        assert runner.apply_replacements(reports).code == _dedent(case.expected_replacement)


def test_rule_discovery_only_returns_concrete_rules() -> None:
    discovered = {rule.__name__ for rule in find_rules(QualifiedRule("fixit_blank_lines.rules"))}
    assert "BaseBlankLinesRule" not in discovered
    assert "BaseBlockHeaderCuddleRule" not in discovered
