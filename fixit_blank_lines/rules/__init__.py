"""Public Fixit rules for blank-line and statement-cuddling policy."""

from fixit_blank_lines.rules.blank_line_after_control_block import BlankLineAfterControlBlock
from fixit_blank_lines.rules.blank_line_before_assignment import BlankLineBeforeAssignment
from fixit_blank_lines.rules.blank_line_before_branch_in_large_suite import (
    BlankLineBeforeBranchInLargeSuite,
)
from fixit_blank_lines.rules.block_header_cuddle_relaxed import BlockHeaderCuddleRelaxed
from fixit_blank_lines.rules.no_suite_leading_trailing_blank_lines import (
    NoSuiteLeadingTrailingBlankLines,
)

__all__ = [
    "BlankLineAfterControlBlock",
    "BlankLineBeforeAssignment",
    "BlankLineBeforeBranchInLargeSuite",
    "BlockHeaderCuddleRelaxed",
    "NoSuiteLeadingTrailingBlankLines",
]
