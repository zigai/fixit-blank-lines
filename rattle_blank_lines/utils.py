from __future__ import annotations

from collections.abc import Sequence

import libcst as cst

BRANCH_SMALL_STATEMENTS = (cst.Break, cst.Continue, cst.Raise, cst.Return)
HEADER_BLOCK_STATEMENTS = (cst.For, cst.If, cst.Match, cst.While, cst.With)
CONTROL_BLOCK_STATEMENTS = (cst.For, cst.If, cst.Match, cst.Try, cst.While, cst.With)
EXCEPTION_CLEANUP_PARENTS = (cst.ExceptHandler, cst.Finally)
DOCSTRING_VALUE_NODES = (cst.ConcatenatedString, cst.SimpleString)


class NameCollector(cst.CSTVisitor):
    """Collect all ``Name`` values below a node."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_ClassDef(self, _node: cst.ClassDef) -> bool:  # noqa: N802
        return False

    def visit_FunctionDef(self, _node: cst.FunctionDef) -> bool:  # noqa: N802
        return False

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        self.names.add(node.value)


class NestedNameCollector(cst.CSTVisitor):
    """Collect all ``Name`` values below a node, including nested defs/classes."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        self.names.add(node.value)


class AttributeReceiverCollector(cst.CSTVisitor):
    """Collect immediate receivers for attribute access chains."""

    def __init__(self) -> None:
        self.receivers: list[cst.BaseExpression] = []

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        self.receivers.append(node.value)
        return False


class ComparableExpressionCollector(cst.CSTVisitor):
    """Collect expressions that are useful for direct target-to-use comparisons."""

    def __init__(self) -> None:
        self.expressions: list[cst.BaseExpression] = []

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        self.expressions.append(node)
        return True

    def visit_Name(self, node: cst.Name) -> bool:  # noqa: N802
        self.expressions.append(node)
        return False

    def visit_Subscript(self, node: cst.Subscript) -> bool:  # noqa: N802
        self.expressions.append(node)
        return True


def collect_names(node: cst.CSTNode) -> set[str]:
    collector = NameCollector()
    node.visit(collector)
    return collector.names


def collect_names_including_nested(node: cst.CSTNode) -> set[str]:
    collector = NestedNameCollector()
    node.visit(collector)
    return collector.names


def collect_attribute_receivers(node: cst.CSTNode) -> list[cst.BaseExpression]:
    collector = AttributeReceiverCollector()
    node.visit(collector)
    return collector.receivers


def collect_comparable_expressions(node: cst.CSTNode) -> list[cst.BaseExpression]:
    collector = ComparableExpressionCollector()
    node.visit(collector)
    return collector.expressions


def is_blank_line(line: cst.EmptyLine) -> bool:
    return line.comment is None


def has_separator(statement: cst.BaseStatement) -> bool:
    return len(statement.leading_lines) > 0


def has_blank_line_separator(statement: cst.BaseStatement) -> bool:
    return bool(statement.leading_lines) and all(
        is_blank_line(line) for line in statement.leading_lines
    )


def prepend_blank_line(statement: cst.BaseStatement) -> cst.BaseStatement:
    return statement.with_changes(
        leading_lines=(cst.EmptyLine(indent=False), *statement.leading_lines)
    )


def remove_blank_leading_lines(statement: cst.BaseStatement) -> cst.BaseStatement:
    return statement.with_changes(
        leading_lines=tuple(line for line in statement.leading_lines if not is_blank_line(line))
    )


def is_branch_statement(statement: cst.BaseStatement) -> bool:
    if not isinstance(statement, cst.SimpleStatementLine):
        return False
    if len(statement.body) != 1:
        return False

    return isinstance(statement.body[0], BRANCH_SMALL_STATEMENTS)


def is_docstring_statement(statement: cst.BaseStatement) -> bool:
    if not isinstance(statement, cst.SimpleStatementLine):
        return False

    if len(statement.body) != 1:
        return False

    expression = statement.body[0]
    if not isinstance(expression, cst.Expr):
        return False

    return isinstance(expression.value, DOCSTRING_VALUE_NODES)


def assignment_small_statement(statement: cst.BaseStatement) -> cst.BaseSmallStatement | None:
    if not isinstance(statement, cst.SimpleStatementLine):
        return None

    if len(statement.body) != 1:
        return None

    small_statement = statement.body[0]
    if isinstance(small_statement, (cst.AnnAssign, cst.Assign, cst.AugAssign)):
        return small_statement

    return None


def extract_target_names(target: cst.BaseExpression) -> list[str]:
    if isinstance(target, cst.Name):
        return [target.value]

    if isinstance(target, (cst.List, cst.Tuple)):
        names: list[str] = []
        for element in target.elements:
            names.extend(extract_target_names(element.value))

        return names

    if isinstance(target, cst.StarredElement):
        return extract_target_names(target.value)

    return []


def extract_target_expressions(target: cst.BaseExpression) -> list[cst.BaseExpression]:
    if isinstance(target, (cst.Attribute, cst.Name, cst.Subscript)):
        return [target]

    if isinstance(target, (cst.List, cst.Tuple)):
        expressions: list[cst.BaseExpression] = []
        for element in target.elements:
            expressions.extend(extract_target_expressions(element.value))

        return expressions

    if isinstance(target, cst.StarredElement):
        return extract_target_expressions(target.value)

    return []


def target_reference_names(target: cst.BaseAssignTargetExpression) -> set[str]:
    if isinstance(target, cst.Name):
        return set()

    if isinstance(target, (cst.List, cst.Tuple)):
        names: set[str] = set()
        for element in target.elements:
            names.update(target_reference_names(element.value))

        return names

    if isinstance(target, cst.StarredElement):
        return target_reference_names(target.value)

    return collect_names(target)


def assigned_names(statement: cst.BaseStatement) -> set[str]:
    assignment = assignment_small_statement(statement)
    if assignment is None:
        return set()

    names: list[str] = []
    if isinstance(assignment, cst.Assign):
        for assign_target in assignment.targets:
            names.extend(extract_target_names(assign_target.target))
    elif isinstance(assignment, (cst.AnnAssign, cst.AugAssign)):
        names.extend(extract_target_names(assignment.target))

    return set(names)


def ordered_assigned_names(statement: cst.BaseStatement) -> list[str]:
    assignment = assignment_small_statement(statement)
    if assignment is None:
        return []

    names: list[str] = []
    if isinstance(assignment, cst.Assign):
        for assign_target in assignment.targets:
            names.extend(extract_target_names(assign_target.target))
    elif isinstance(assignment, (cst.AnnAssign, cst.AugAssign)):
        names.extend(extract_target_names(assignment.target))

    return names


def ordered_assigned_target_expressions(statement: cst.BaseStatement) -> list[cst.BaseExpression]:
    assignment = assignment_small_statement(statement)
    if assignment is None:
        return []

    expressions: list[cst.BaseExpression] = []
    if isinstance(assignment, cst.Assign):
        for assign_target in assignment.targets:
            expressions.extend(extract_target_expressions(assign_target.target))
    elif isinstance(assignment, (cst.AnnAssign, cst.AugAssign)):
        expressions.extend(extract_target_expressions(assignment.target))

    return expressions


def last_assigned_name(statement: cst.BaseStatement) -> str | None:
    names = ordered_assigned_names(statement)
    if not names:
        return None

    return names[-1]


def last_assigned_target_expression(statement: cst.BaseStatement) -> cst.BaseExpression | None:
    expressions = ordered_assigned_target_expressions(statement)
    if not expressions:
        return None

    return expressions[-1]


def assignment_reference_names(statement: cst.BaseStatement) -> set[str]:
    assignment = assignment_small_statement(statement)
    if assignment is None:
        return set()

    names: set[str] = set()
    if isinstance(assignment, cst.Assign):
        names.update(collect_names(assignment.value))
        for assign_target in assignment.targets:
            names.update(target_reference_names(assign_target.target))
    elif isinstance(assignment, cst.AnnAssign):
        if assignment.value is not None:
            names.update(collect_names(assignment.value))

        names.update(target_reference_names(assignment.target))
    elif isinstance(assignment, cst.AugAssign):
        names.update(collect_names(assignment.target))
        names.update(collect_names(assignment.value))

    return names


def assignment_consumed_names(statement: cst.BaseStatement) -> set[str]:
    assignment = assignment_small_statement(statement)
    if assignment is None:
        return set()

    names: set[str] = set()
    if isinstance(assignment, cst.Assign):
        names.update(collect_names(assignment.value))
    elif isinstance(assignment, cst.AnnAssign):
        if assignment.value is not None:
            names.update(collect_names(assignment.value))
    elif isinstance(assignment, cst.AugAssign):
        names.update(collect_names(assignment.target))
        names.update(collect_names(assignment.value))

    return names


def expression_statement_value(statement: cst.BaseStatement) -> cst.BaseExpression | None:
    if not isinstance(statement, cst.SimpleStatementLine):
        return None

    if len(statement.body) != 1:
        return None

    expression = statement.body[0]
    if not isinstance(expression, cst.Expr):
        return None

    return expression.value


def header_expression_nodes(statement: cst.BaseStatement) -> list[cst.CSTNode]:
    if isinstance(statement, cst.If):
        return [statement.test]
    if isinstance(statement, cst.While):
        return [statement.test]
    if isinstance(statement, cst.For):
        return [statement.iter]
    if isinstance(statement, cst.With):
        return [item.item for item in statement.items]
    if isinstance(statement, cst.Match):
        return [statement.subject]

    return []


def first_statement_in_suite(suite: cst.BaseSuite) -> cst.CSTNode | None:
    if isinstance(suite, cst.IndentedBlock):
        if not suite.body:
            return None

        return suite.body[0]

    if isinstance(suite, cst.SimpleStatementSuite):
        if not suite.body:
            return None

        return suite.body[0]

    return None


def first_statement_in_block(statement: cst.BaseStatement) -> cst.CSTNode | None:
    if isinstance(statement, (cst.For, cst.If, cst.Try, cst.While, cst.With)):
        return first_statement_in_suite(statement.body)

    if isinstance(statement, cst.Match):
        if not statement.cases:
            return None

        return first_statement_in_suite(statement.cases[0].body)

    return None


def is_header_block_statement(statement: cst.BaseStatement) -> bool:
    return isinstance(statement, HEADER_BLOCK_STATEMENTS)


def is_control_block_statement(statement: cst.BaseStatement) -> bool:
    return isinstance(statement, CONTROL_BLOCK_STATEMENTS)


def is_exception_cleanup_suite_parent(node: cst.CSTNode) -> bool:
    return isinstance(node, EXCEPTION_CLEANUP_PARENTS)


def is_terminal_exception_cleanup_run(
    body: list[cst.BaseStatement] | tuple[cst.BaseStatement, ...],
    start_index: int,
    suite_parent: cst.CSTNode | None,
) -> bool:
    if suite_parent is None or not is_exception_cleanup_suite_parent(suite_parent):
        return False
    if start_index < 0 or start_index >= len(body):
        return False
    if not is_branch_statement(body[-1]):
        return False

    return all(isinstance(statement, cst.SimpleStatementLine) for statement in body[start_index:])


def is_single_line_control_block(statement: cst.BaseStatement) -> bool:
    if isinstance(statement, cst.Match):
        return False
    if isinstance(statement, (cst.For, cst.If, cst.Try, cst.While, cst.With)):
        return isinstance(statement.body, cst.SimpleStatementSuite)

    return False


def _simple_if_test_subject(statement: cst.BaseStatement) -> cst.BaseExpression | None:
    if (
        not isinstance(statement, cst.If)
        or statement.orelse is not None
        or not isinstance(statement.body, cst.IndentedBlock)
        or len(statement.body.body) != 1
        or not isinstance(statement.test, cst.Comparison)
        or len(statement.test.comparisons) != 1
    ):
        return None

    return statement.test.left


def is_same_subject_simple_if_chain(
    current_statement: cst.BaseStatement,
    next_statement: cst.BaseStatement,
) -> bool:
    current_subject = _simple_if_test_subject(current_statement)
    if current_subject is None:
        return False

    next_subject = _simple_if_test_subject(next_statement)
    if next_subject is None:
        return False

    return current_subject.deep_equals(next_subject)


def _assert_reference_names(statement: cst.Assert) -> set[str]:
    names = collect_names(statement.test)
    if statement.msg is not None:
        names.update(collect_names(statement.msg))

    return names


def _branch_reference_names(statement: cst.Raise | cst.Return) -> set[str]:
    expression = statement.exc if isinstance(statement, cst.Raise) else statement.value
    if expression is None:
        return set()

    return collect_names(expression)


def small_statement_reference_names(statement: cst.BaseSmallStatement) -> set[str]:
    if isinstance(statement, cst.Assert):
        return _assert_reference_names(statement)
    if isinstance(statement, (cst.Assign, cst.AnnAssign, cst.AugAssign)):
        return assignment_reference_names(cst.SimpleStatementLine(body=[statement]))
    if isinstance(statement, cst.Expr):
        return collect_names(statement.value)
    if isinstance(statement, (cst.Raise, cst.Return)):
        return _branch_reference_names(statement)

    return set()


def small_statement_consumed_names(statement: cst.BaseSmallStatement) -> set[str]:
    if isinstance(statement, cst.Assert):
        return _assert_reference_names(statement)
    if isinstance(statement, (cst.Assign, cst.AnnAssign, cst.AugAssign)):
        return assignment_consumed_names(cst.SimpleStatementLine(body=[statement]))
    if isinstance(statement, cst.Expr):
        return collect_names(statement.value)
    if isinstance(statement, (cst.Raise, cst.Return)):
        return _branch_reference_names(statement)

    return set()


def statement_reference_names(statement: cst.BaseStatement) -> set[str]:
    if isinstance(statement, cst.SimpleStatementLine):
        names: set[str] = set()
        for small_statement in statement.body:
            names.update(small_statement_reference_names(small_statement))

        return names

    if is_control_block_statement(statement):
        names: set[str] = set()
        for expression in header_expression_nodes(statement):
            names.update(collect_names(expression))

        return names

    return set()


def statement_touches_name(statement: cst.BaseStatement, name: str) -> bool:
    return name in assigned_names(statement) or name in statement_reference_names(statement)


def statement_touches_target_expression(
    statement: cst.BaseStatement,
    target_expression: cst.BaseExpression,
) -> bool:
    assigned_target_expressions = ordered_assigned_target_expressions(statement)
    if any(
        assigned_target_expression.deep_equals(target_expression)
        for assigned_target_expression in assigned_target_expressions
    ):
        return True

    return any(
        expression.deep_equals(target_expression)
        for expression in collect_comparable_expressions(statement)
    )


def statement_consumed_names(statement: cst.BaseStatement) -> set[str]:
    if isinstance(statement, cst.SimpleStatementLine):
        names: set[str] = set()
        for small_statement in statement.body:
            names.update(small_statement_consumed_names(small_statement))

        return names

    if is_control_block_statement(statement):
        names: set[str] = set()
        for expression in header_expression_nodes(statement):
            names.update(collect_names(expression))

        return names

    return set()


def has_nontrivial_related_use(
    body: Sequence[cst.BaseStatement],
    assignment_index: int,
    *,
    lookahead: int,
) -> bool:
    if lookahead <= 0 or assignment_index < 0 or assignment_index >= len(body):
        return False

    names = assigned_names(body[assignment_index])
    if not names:
        return False

    for next_index in range(assignment_index + 1, min(len(body), assignment_index + 1 + lookahead)):
        statement = body[next_index]
        if not statement_reference_names(statement).intersection(names):
            continue

        if (
            is_branch_statement(statement)
            and isinstance(statement, cst.SimpleStatementLine)
            and len(statement.body) == 1
        ):
            branch = statement.body[0]
            if (
                isinstance(branch, cst.Return)
                and isinstance(branch.value, cst.Name)
                and branch.value.value in names
            ):
                continue

            if (
                isinstance(branch, cst.Raise)
                and isinstance(branch.exc, cst.Name)
                and branch.exc.value in names
            ):
                continue

        return True

    return False


def suite_statements(suite: cst.BaseSuite) -> list[cst.BaseStatement]:
    if isinstance(suite, cst.IndentedBlock):
        return list(suite.body)

    return []


def primary_body_statements(statement: cst.BaseStatement) -> list[cst.BaseStatement]:
    if isinstance(statement, (cst.For, cst.If, cst.Try, cst.While, cst.With)):
        return suite_statements(statement.body)
    if isinstance(statement, cst.Match) and statement.cases:
        return suite_statements(statement.cases[0].body)

    return []


def leading_block_body_statements(
    statement: cst.BaseStatement,
    *,
    limit: int,
) -> list[cst.BaseStatement]:
    if limit <= 0:
        return []

    return primary_body_statements(statement)[:limit]


def _leading_suite_statements(
    suite: cst.BaseSuite,
    *,
    limit: int,
) -> list[cst.BaseStatement]:
    if limit <= 0:
        return []

    return suite_statements(suite)[:limit]


def _if_branch_statement_groups(statement: cst.If) -> list[list[cst.BaseStatement]]:
    groups = [suite_statements(statement.body)]
    if statement.orelse is not None:
        groups.append(suite_statements(statement.orelse.body))

    return groups


def control_block_consumed_names_in_early_body(
    statement: cst.BaseStatement,
    *,
    limit: int,
) -> set[str]:
    if limit <= 0:
        return set()

    names: set[str] = set()
    if isinstance(statement, cst.If):
        for branch in _if_branch_statement_groups(statement):
            for branch_statement in branch[:limit]:
                names.update(statement_consumed_names(branch_statement))

        return names

    if isinstance(statement, (cst.For, cst.Try, cst.While, cst.With)):
        for body_statement in _leading_suite_statements(statement.body, limit=limit):
            names.update(statement_consumed_names(body_statement))

        return names

    if isinstance(statement, cst.Match):
        for case in statement.cases:
            for body_statement in _leading_suite_statements(case.body, limit=limit):
                names.update(statement_consumed_names(body_statement))

        return names

    return names


def flat_body_assigned_names(statement: cst.BaseStatement) -> set[str]:
    names: set[str] = set()
    for body_statement in primary_body_statements(statement):
        names.update(assigned_names(body_statement))

    return names


def contiguous_run_before(
    body: Sequence[cst.BaseStatement],
    index: int,
) -> tuple[int, list[cst.BaseStatement]]:
    if index <= 0:
        return 0, []

    start = index - 1
    while start > 0 and not has_separator(body[start]):
        start -= 1

    if has_separator(body[start]):
        start += 1

    return start, list(body[start:index])


def compact_tail_run_before(
    body: Sequence[cst.BaseStatement],
    branch_index: int,
) -> tuple[int, list[cst.BaseStatement]]:
    return contiguous_run_before(body, branch_index)


def is_compact_guard_if(statement: cst.BaseStatement) -> bool:
    if (
        not isinstance(statement, cst.If)
        or statement.orelse is not None
        or not isinstance(statement.body, cst.IndentedBlock)
    ):
        return False

    body_statements = statement.body.body
    if not 1 <= len(body_statements) <= 2:
        return False

    if not all(
        isinstance(body_statement, cst.SimpleStatementLine) for body_statement in body_statements
    ):
        return False

    return is_branch_statement(body_statements[-1])


def starts_compact_guard_ladder(
    body: Sequence[cst.BaseStatement],
    start_index: int,
) -> bool:
    if start_index < 0 or start_index >= len(body):
        return False

    index = start_index
    guard_count = 0
    while index < len(body):
        statement = body[index]
        if not is_compact_guard_if(statement):
            break

        guard_count += 1
        next_index = index + 1
        if next_index >= len(body):
            return guard_count >= 2
        if has_separator(body[next_index]):
            return guard_count >= 2

        if is_branch_statement(body[next_index]):
            return guard_count >= 2

        index = next_index

    return False


def is_compact_guard_ladder_tail(
    body: Sequence[cst.BaseStatement],
    branch_index: int,
) -> bool:
    if branch_index < 0 or branch_index >= len(body) or not is_branch_statement(body[branch_index]):
        return False

    _start_index, run = compact_tail_run_before(body, branch_index)
    run = [*run, body[branch_index]]
    if len(run) < 2:
        return False

    if assignment_small_statement(run[0]) is not None:
        run = run[1:]

    if len(run) < 2 or not is_branch_statement(run[-1]):
        return False

    return all(is_compact_guard_if(statement) for statement in run[:-1])


def is_pytest_raises_with(statement: cst.BaseStatement) -> bool:
    if not isinstance(statement, cst.With) or not statement.items:
        return False

    call = statement.items[0].item
    if not isinstance(call, cst.Call):
        return False

    func = call.func

    return (
        isinstance(func, cst.Attribute)
        and isinstance(func.value, cst.Name)
        and func.value.value == "pytest"
        and func.attr.value == "raises"
    )


def next_statement_inspects_with_assignment(
    current_statement: cst.BaseStatement,
    next_statement: cst.BaseStatement,
) -> bool:
    if not isinstance(current_statement, cst.With) or is_pytest_raises_with(current_statement):
        return False

    body_statements = primary_body_statements(current_statement)
    if not body_statements or not all(
        isinstance(body_statement, cst.SimpleStatementLine) for body_statement in body_statements
    ):
        return False

    names: set[str] = set()
    for body_statement in body_statements:
        names.update(assigned_names(body_statement))

    if not names:
        return False

    return bool(statement_reference_names(next_statement).intersection(names))


def next_control_block_consumes_assignment(
    body: Sequence[cst.BaseStatement],
    assignment_index: int,
    *,
    limit: int,
) -> bool:
    next_index = assignment_index + 1
    if limit <= 0 or next_index >= len(body):
        return False

    next_statement = body[next_index]
    if not is_control_block_statement(next_statement):
        return False

    assigned = assigned_names(body[assignment_index])
    if not assigned:
        return False

    return bool(
        control_block_consumed_names_in_early_body(
            next_statement,
            limit=limit,
        ).intersection(assigned)
    )


def previous_block_assigns_current_target(
    body: Sequence[cst.BaseStatement],
    assignment_index: int,
) -> bool:
    if assignment_index <= 0 or assignment_index >= len(body):
        return False

    current_names = assigned_names(body[assignment_index])
    if not current_names:
        return False

    previous_statement = body[assignment_index - 1]
    if not is_control_block_statement(previous_statement):
        return False

    return bool(flat_body_assigned_names(previous_statement).intersection(current_names))


def next_local_definition_uses_assignment(
    body: Sequence[cst.BaseStatement],
    assignment_index: int,
) -> bool:
    next_index = assignment_index + 1
    if next_index >= len(body):
        return False

    assigned = assigned_names(body[assignment_index])
    if not assigned:
        return False

    next_statement = body[next_index]
    if not isinstance(next_statement, (cst.ClassDef, cst.FunctionDef)):
        return False

    return bool(collect_names_including_nested(next_statement).intersection(assigned))


def control_block_ends_with_loop_exit(statement: cst.BaseStatement) -> bool:
    if not isinstance(statement, (cst.If, cst.Match, cst.Try)):
        return False

    if isinstance(statement, cst.Try):
        body = suite_statements(statement.body)
    elif isinstance(statement, cst.Match):
        if not statement.cases:
            return False

        body = suite_statements(statement.cases[0].body)
    else:
        body = suite_statements(statement.body)

    if not body or not is_branch_statement(body[-1]):
        return False

    branch = body[-1]
    if not isinstance(branch, cst.SimpleStatementLine) or len(branch.body) != 1:
        return False

    return isinstance(branch.body[0], (cst.Break, cst.Continue))


def _suite_is_single_pass(suite: cst.BaseSuite) -> bool:
    if isinstance(suite, cst.IndentedBlock):
        statements = suite.body
        if len(statements) != 1:
            return False

        statement = statements[0]

        return (
            isinstance(statement, cst.SimpleStatementLine)
            and len(statement.body) == 1
            and isinstance(statement.body[0], cst.Pass)
        )

    if isinstance(suite, cst.SimpleStatementSuite):
        return len(suite.body) == 1 and isinstance(suite.body[0], cst.Pass)

    return False


def is_pass_only_try(statement: cst.BaseStatement) -> bool:
    return (
        isinstance(statement, cst.Try)
        and bool(statement.handlers)
        and statement.orelse is None
        and statement.finalbody is None
        and all(_suite_is_single_pass(handler.body) for handler in statement.handlers)
    )


def count_non_empty_lines(source_lines: list[str], start_line: int, end_line: int) -> int:
    if not source_lines:
        return 0

    safe_start = max(start_line, 1)
    safe_end = min(end_line, len(source_lines))
    if safe_end < safe_start:
        return 0

    count = 0
    for line_number in range(safe_start, safe_end + 1):
        if source_lines[line_number - 1].strip():
            count += 1

    return count


__all__ = [
    "BRANCH_SMALL_STATEMENTS",
    "CONTROL_BLOCK_STATEMENTS",
    "HEADER_BLOCK_STATEMENTS",
    "AttributeReceiverCollector",
    "NameCollector",
    "NestedNameCollector",
    "assigned_names",
    "assignment_consumed_names",
    "assignment_reference_names",
    "assignment_small_statement",
    "collect_attribute_receivers",
    "collect_names",
    "collect_names_including_nested",
    "compact_tail_run_before",
    "contiguous_run_before",
    "control_block_consumed_names_in_early_body",
    "control_block_ends_with_loop_exit",
    "count_non_empty_lines",
    "expression_statement_value",
    "extract_target_names",
    "first_statement_in_block",
    "first_statement_in_suite",
    "flat_body_assigned_names",
    "has_blank_line_separator",
    "has_nontrivial_related_use",
    "has_separator",
    "header_expression_nodes",
    "is_blank_line",
    "is_branch_statement",
    "is_compact_guard_if",
    "is_compact_guard_ladder_tail",
    "is_control_block_statement",
    "is_docstring_statement",
    "is_header_block_statement",
    "is_pass_only_try",
    "is_pytest_raises_with",
    "is_same_subject_simple_if_chain",
    "is_single_line_control_block",
    "last_assigned_name",
    "leading_block_body_statements",
    "next_control_block_consumes_assignment",
    "next_local_definition_uses_assignment",
    "next_statement_inspects_with_assignment",
    "ordered_assigned_names",
    "prepend_blank_line",
    "previous_block_assigns_current_target",
    "primary_body_statements",
    "remove_blank_leading_lines",
    "starts_compact_guard_ladder",
    "statement_consumed_names",
    "statement_reference_names",
    "statement_touches_name",
    "suite_statements",
    "target_reference_names",
]
