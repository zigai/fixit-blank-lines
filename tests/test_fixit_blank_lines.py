from fixit_blank_lines import rules as rule_pack
from fixit_blank_lines.rules import (
    BlankLineAfterControlBlock,
    BlankLineBeforeBranchInLargeSuite,
    BlockHeaderCuddleRelaxed,
    BlockHeaderCuddleStrict,
    NoSuiteLeadingTrailingBlankLines,
)
from fixit_blank_lines.rules.blank_line_before_assignment import BlankLineBeforeAssignment
from fixit_blank_lines.rules.match_case_separation import MatchCaseSeparation


def test_rules_are_importable() -> None:
    assert NoSuiteLeadingTrailingBlankLines.__name__ == "NoSuiteLeadingTrailingBlankLines"
    assert BlankLineBeforeAssignment.__name__ == "BlankLineBeforeAssignment"
    assert BlankLineBeforeBranchInLargeSuite.__name__ == "BlankLineBeforeBranchInLargeSuite"
    assert BlockHeaderCuddleRelaxed.__name__ == "BlockHeaderCuddleRelaxed"
    assert BlockHeaderCuddleStrict.__name__ == "BlockHeaderCuddleStrict"
    assert BlankLineAfterControlBlock.__name__ == "BlankLineAfterControlBlock"


def test_match_case_rule_is_opt_in() -> None:
    assert "MatchCaseSeparation" not in rule_pack.__all__
    assert not hasattr(rule_pack, "MatchCaseSeparation")
    assert MatchCaseSeparation.__name__ == "MatchCaseSeparation"


def test_blank_line_before_assignment_is_opt_in() -> None:
    assert "BlankLineBeforeAssignment" not in rule_pack.__all__
    assert not hasattr(rule_pack, "BlankLineBeforeAssignment")
    assert BlankLineBeforeAssignment.__name__ == "BlankLineBeforeAssignment"


def test_rule_threshold_defaults() -> None:
    assert BlankLineBeforeBranchInLargeSuite.BRANCH_MAX_LINES == 2
    assert MatchCaseSeparation.CASE_MAX_LINES == 2


def test_rule_fixtures_are_non_trivial() -> None:
    assert len(NoSuiteLeadingTrailingBlankLines.VALID) >= 2
    assert len(NoSuiteLeadingTrailingBlankLines.INVALID) >= 2
    assert len(BlankLineBeforeAssignment.VALID) >= 3
    assert len(BlankLineBeforeAssignment.INVALID) >= 2
    assert len(BlankLineBeforeBranchInLargeSuite.VALID) >= 3
    assert len(BlankLineBeforeBranchInLargeSuite.INVALID) >= 2
    assert len(BlockHeaderCuddleRelaxed.VALID) >= 3
    assert len(BlockHeaderCuddleRelaxed.INVALID) >= 3
    assert len(BlockHeaderCuddleStrict.VALID) >= 2
    assert len(BlockHeaderCuddleStrict.INVALID) >= 2
    assert len(BlankLineAfterControlBlock.VALID) >= 3
    assert len(BlankLineAfterControlBlock.INVALID) >= 2
    assert len(MatchCaseSeparation.VALID) >= 2
    assert len(MatchCaseSeparation.INVALID) >= 2
