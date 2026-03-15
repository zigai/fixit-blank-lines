from fixit_blank_lines import rules as rule_pack
from fixit_blank_lines.rules import BlankLineBeforeAssignment
from fixit_blank_lines.rules.block_header_cuddle_strict import BlockHeaderCuddleStrict
from fixit_blank_lines.rules.match_case_separation import MatchCaseSeparation


def test_default_rule_pack_exposes_only_default_rules() -> None:
    assert "BlankLineBeforeAssignment" in rule_pack.__all__
    assert hasattr(rule_pack, "BlankLineBeforeAssignment")
    assert BlankLineBeforeAssignment is rule_pack.BlankLineBeforeAssignment


def test_opt_in_rules_are_not_exported_from_default_rule_pack() -> None:
    assert "BlockHeaderCuddleStrict" not in rule_pack.__all__
    assert not hasattr(rule_pack, "BlockHeaderCuddleStrict")
    assert "MatchCaseSeparation" not in rule_pack.__all__
    assert not hasattr(rule_pack, "MatchCaseSeparation")


def test_opt_in_rules_remain_importable_from_explicit_modules() -> None:
    assert (
        BlockHeaderCuddleStrict.__module__ == "fixit_blank_lines.rules.block_header_cuddle_strict"
    )
    assert MatchCaseSeparation.__module__ == "fixit_blank_lines.rules.match_case_separation"
