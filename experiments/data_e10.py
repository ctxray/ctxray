"""E10: Specificity gradient — 10 tasks x 6 levels.

Tests whether marginal specificity components (constraints vs. edge cases)
drive per-model pass rate improvements beyond task_io.

Decomposes the old E9 full_spec level into three additive variants:
  - task_io_constraints: task_io + explicit evaluation-order constraints
  - task_io_edge       : task_io + edge case mentions
  - full_spec          : task_io + both

Balanced 5 constraints-sensitive + 5 control tasks for unbiased aggregate.

4 existing E9 tasks preserve their E9 task_only and task_io wording verbatim
so the llama3.1:8b fizzbuzz bug trigger (DeMorgan inversion at task_io) is
still present and can be directly tested against task_io_constraints.

See memory/experiment_e1_validation.md for E0-E9 background.
"""

from __future__ import annotations

from data import TASKS, Task, TestCase  # reuse E1-E9 types

E10_LEVELS: list[str] = [
    "vague",
    "task_only",
    "task_io",
    "task_io_constraints",
    "task_io_edge",
    "full_spec",
]

# Task tagging for post-hoc subset analysis.
# constraints_sensitive = overlapping rules, preconditions, or scope ambiguity
# control = trivial transformations where constraints should contribute ~0
E10_TAGS: dict[str, str] = {
    "fizzbuzz": "constraints_sensitive",
    "is_palindrome": "constraints_sensitive",
    "run_length_encode": "constraints_sensitive",
    "longest_common_prefix": "constraints_sensitive",
    "binary_search": "constraints_sensitive",
    "flatten": "control",
    "two_sum": "control",
    "unique_elements": "control",
    "run_length_decode": "control",
    "sum_even": "control",
}

# Six new Task definitions (4 existing tasks reused from data.TASKS)
E10_NEW_TASKS: list[Task] = [
    Task(
        name="is_palindrome",
        func_name="is_palindrome",
        tests=[
            TestCase("is_palindrome('racecar')", "True"),
            TestCase("is_palindrome('hello')", "False"),
            TestCase("is_palindrome('')", "True"),
            TestCase("is_palindrome('a')", "True"),
        ],
        prompts={},
    ),
    Task(
        name="binary_search",
        func_name="binary_search",
        tests=[
            TestCase("binary_search([1, 3, 5, 7, 9], 5)", "2"),
            TestCase("binary_search([1, 3, 5, 7, 9], 4)", "-1"),
            TestCase("binary_search([], 1)", "-1"),
            TestCase("binary_search([1], 1)", "0"),
        ],
        prompts={},
    ),
    Task(
        name="unique_elements",
        func_name="unique_elements",
        tests=[
            TestCase("unique_elements([1, 2, 2, 3, 1, 4])", "[1, 2, 3, 4]"),
            TestCase("unique_elements([])", "[]"),
            TestCase("unique_elements(['a', 'b', 'a'])", "['a', 'b']"),
        ],
        prompts={},
    ),
    Task(
        name="longest_common_prefix",
        func_name="longest_common_prefix",
        tests=[
            TestCase("longest_common_prefix(['flower', 'flow', 'flight'])", "'fl'"),
            TestCase("longest_common_prefix([])", "''"),
            TestCase("longest_common_prefix(['dog', 'racecar'])", "''"),
            TestCase("longest_common_prefix(['a'])", "'a'"),
        ],
        prompts={},
    ),
    Task(
        name="run_length_decode",
        func_name="run_length_decode",
        tests=[
            TestCase("run_length_decode([('a', 2), ('b', 1), ('c', 3)])", "'aabccc'"),
            TestCase("run_length_decode([])", "''"),
            TestCase("run_length_decode([('x', 1)])", "'x'"),
        ],
        prompts={},
    ),
    Task(
        name="sum_even",
        func_name="sum_even",
        tests=[
            TestCase("sum_even([1, 2, 3, 4])", "6"),
            TestCase("sum_even([])", "0"),
            TestCase("sum_even([1, 3, 5])", "0"),
            TestCase("sum_even([2, 4, 6])", "12"),
        ],
        prompts={},
    ),
]

# Build combined task registry (4 existing + 6 new = 10)
_E10_NAMES = set(E10_TAGS.keys())
E10_ALL_TASKS: list[Task] = [t for t in TASKS if t.name in _E10_NAMES] + E10_NEW_TASKS

assert len(E10_ALL_TASKS) == 10, f"Expected 10 tasks, got {len(E10_ALL_TASKS)}"
assert {t.name for t in E10_ALL_TASKS} == _E10_NAMES, "Task name mismatch"


E10_PROMPTS: dict[str, dict[str, str]] = {
    "fizzbuzz": {
        "vague": "write fizzbuzz",
        "task_only": (
            "Write a Python function fizzbuzz(n) that returns FizzBuzz results "
            "for numbers 1 to n."
        ),
        "task_io": (
            "Write a Python function fizzbuzz(n) that returns a list of strings "
            "for numbers 1 to n. Divisible by 3 returns 'Fizz', by 5 returns "
            "'Buzz', both returns 'FizzBuzz', otherwise the number as a string. "
            "Example: fizzbuzz(5) returns ['1', '2', 'Fizz', '4', 'Buzz']."
        ),
        "task_io_constraints": (
            "Write a Python function fizzbuzz(n) that returns a list of strings "
            "for numbers 1 to n. Divisible by 3 returns 'Fizz', by 5 returns "
            "'Buzz', both returns 'FizzBuzz', otherwise the number as a string. "
            "Example: fizzbuzz(5) returns ['1', '2', 'Fizz', '4', 'Buzz']. "
            "You must check divisibility by 15 before checking 3 or 5 separately."
        ),
        "task_io_edge": (
            "Write a Python function fizzbuzz(n) that returns a list of strings "
            "for numbers 1 to n. Divisible by 3 returns 'Fizz', by 5 returns "
            "'Buzz', both returns 'FizzBuzz', otherwise the number as a string. "
            "Example: fizzbuzz(5) returns ['1', '2', 'Fizz', '4', 'Buzz']. "
            "Handle an empty list case: n=0 returns an empty list."
        ),
        "full_spec": (
            "Write a Python function fizzbuzz(n) that returns a list of strings "
            "for numbers 1 to n. Divisible by 3 returns 'Fizz', by 5 returns "
            "'Buzz', both returns 'FizzBuzz', otherwise the number as a string. "
            "Example: fizzbuzz(5) returns ['1', '2', 'Fizz', '4', 'Buzz']. "
            "You must check divisibility by 15 before checking 3 or 5 separately. "
            "Handle an empty list case: n=0 returns an empty list."
        ),
    },
    "flatten": {
        "vague": "flatten a list",
        "task_only": (
            "Write a Python function flatten(lst) that flattens a nested list "
            "into a single flat list."
        ),
        "task_io": (
            "Write a Python function flatten(lst) that recursively flattens a "
            "nested list into a single flat list. Non-list elements stay as-is. "
            "Example: flatten([1, [2, [3]]]) returns [1, 2, 3]."
        ),
        "task_io_constraints": (
            "Write a Python function flatten(lst) that recursively flattens a "
            "nested list into a single flat list. Non-list elements stay as-is. "
            "Example: flatten([1, [2, [3]]]) returns [1, 2, 3]. "
            "You must preserve depth-first order of non-list elements."
        ),
        "task_io_edge": (
            "Write a Python function flatten(lst) that recursively flattens a "
            "nested list into a single flat list. Non-list elements stay as-is. "
            "Example: flatten([1, [2, [3]]]) returns [1, 2, 3]. "
            "Handle empty list input by returning an empty list."
        ),
        "full_spec": (
            "Write a Python function flatten(lst) that recursively flattens a "
            "nested list into a single flat list. Non-list elements stay as-is. "
            "Example: flatten([1, [2, [3]]]) returns [1, 2, 3]. "
            "You must preserve depth-first order of non-list elements. "
            "Handle empty list input by returning an empty list."
        ),
    },
    "two_sum": {
        "vague": "two sum problem",
        "task_only": (
            "Write a Python function two_sum(nums, target) that finds two "
            "numbers in the list that add up to target."
        ),
        "task_io": (
            "Write a Python function two_sum(nums, target) that returns the "
            "indices of two numbers that add up to target as a tuple. "
            "Assume exactly one solution exists. "
            "Example: two_sum([2, 7, 11, 15], 9) returns (0, 1)."
        ),
        "task_io_constraints": (
            "Write a Python function two_sum(nums, target) that returns the "
            "indices of two numbers that add up to target as a tuple. "
            "Assume exactly one solution exists. "
            "Example: two_sum([2, 7, 11, 15], 9) returns (0, 1). "
            "Use a hash map for O(n) time and do not use the same index twice."
        ),
        "task_io_edge": (
            "Write a Python function two_sum(nums, target) that returns the "
            "indices of two numbers that add up to target as a tuple. "
            "Assume exactly one solution exists. "
            "Example: two_sum([2, 7, 11, 15], 9) returns (0, 1). "
            "The input nums is guaranteed to be a non-empty list with at least two elements."
        ),
        "full_spec": (
            "Write a Python function two_sum(nums, target) that returns the "
            "indices of two numbers that add up to target as a tuple. "
            "Assume exactly one solution exists. "
            "Example: two_sum([2, 7, 11, 15], 9) returns (0, 1). "
            "Use a hash map for O(n) time and do not use the same index twice. "
            "The input nums is guaranteed to be a non-empty list with at least two elements."
        ),
    },
    "run_length_encode": {
        "vague": "encode a string",
        "task_only": (
            "Write a Python function run_length_encode(s) that performs "
            "run-length encoding on a string."
        ),
        "task_io": (
            "Write a Python function run_length_encode(s) that performs "
            "run-length encoding. Return a list of (char, count) tuples for "
            "consecutive identical characters. "
            "Example: run_length_encode('aabbc') returns [('a', 2), ('b', 2), ('c', 1)]."
        ),
        "task_io_constraints": (
            "Write a Python function run_length_encode(s) that performs "
            "run-length encoding. Return a list of (char, count) tuples for "
            "consecutive identical characters. "
            "Example: run_length_encode('aabbc') returns [('a', 2), ('b', 2), ('c', 1)]. "
            "You must emit exactly one tuple per maximal run of identical consecutive characters."
        ),
        "task_io_edge": (
            "Write a Python function run_length_encode(s) that performs "
            "run-length encoding. Return a list of (char, count) tuples for "
            "consecutive identical characters. "
            "Example: run_length_encode('aabbc') returns [('a', 2), ('b', 2), ('c', 1)]. "
            "Handle empty string input by returning an empty list."
        ),
        "full_spec": (
            "Write a Python function run_length_encode(s) that performs "
            "run-length encoding. Return a list of (char, count) tuples for "
            "consecutive identical characters. "
            "Example: run_length_encode('aabbc') returns [('a', 2), ('b', 2), ('c', 1)]. "
            "You must emit exactly one tuple per maximal run of identical consecutive characters. "
            "Handle empty string input by returning an empty list."
        ),
    },
    "is_palindrome": {
        "vague": "palindrome check",
        "task_only": (
            "Write a Python function is_palindrome(s) that checks if a string "
            "is a palindrome."
        ),
        "task_io": (
            "Write a Python function is_palindrome(s) that returns True if s "
            "reads the same forwards and backwards. "
            "Example: is_palindrome('racecar') returns True."
        ),
        "task_io_constraints": (
            "Write a Python function is_palindrome(s) that returns True if s "
            "reads the same forwards and backwards. "
            "Example: is_palindrome('racecar') returns True. "
            "Use strict character comparison without case normalization or whitespace removal."
        ),
        "task_io_edge": (
            "Write a Python function is_palindrome(s) that returns True if s "
            "reads the same forwards and backwards. "
            "Example: is_palindrome('racecar') returns True. "
            "Handle empty string input and single character input by returning True."
        ),
        "full_spec": (
            "Write a Python function is_palindrome(s) that returns True if s "
            "reads the same forwards and backwards. "
            "Example: is_palindrome('racecar') returns True. "
            "Use strict character comparison without case normalization or whitespace removal. "
            "Handle empty string input and single character input by returning True."
        ),
    },
    "binary_search": {
        "vague": "binary search",
        "task_only": (
            "Write a Python function binary_search(arr, target) that finds "
            "target in a sorted array."
        ),
        "task_io": (
            "Write a Python function binary_search(arr, target) that returns "
            "the index of target in a sorted array, or -1 if not found. "
            "Example: binary_search([1, 3, 5, 7, 9], 5) returns 2."
        ),
        "task_io_constraints": (
            "Write a Python function binary_search(arr, target) that returns "
            "the index of target in a sorted array, or -1 if not found. "
            "Example: binary_search([1, 3, 5, 7, 9], 5) returns 2. "
            "You must assume arr is sorted ascending and use iterative halving "
            "of the search range."
        ),
        "task_io_edge": (
            "Write a Python function binary_search(arr, target) that returns "
            "the index of target in a sorted array, or -1 if not found. "
            "Example: binary_search([1, 3, 5, 7, 9], 5) returns 2. "
            "Handle empty array input by returning -1, and return -1 when "
            "target is not present."
        ),
        "full_spec": (
            "Write a Python function binary_search(arr, target) that returns "
            "the index of target in a sorted array, or -1 if not found. "
            "Example: binary_search([1, 3, 5, 7, 9], 5) returns 2. "
            "You must assume arr is sorted ascending and use iterative halving "
            "of the search range. "
            "Handle empty array input by returning -1, and return -1 when "
            "target is not present."
        ),
    },
    "unique_elements": {
        "vague": "unique elements",
        "task_only": (
            "Write a Python function unique_elements(lst) that returns the "
            "unique elements of a list."
        ),
        "task_io": (
            "Write a Python function unique_elements(lst) that returns the "
            "unique elements of lst in their first-occurrence order. "
            "Example: unique_elements([1, 2, 2, 3, 1, 4]) returns [1, 2, 3, 4]."
        ),
        "task_io_constraints": (
            "Write a Python function unique_elements(lst) that returns the "
            "unique elements of lst in their first-occurrence order. "
            "Example: unique_elements([1, 2, 2, 3, 1, 4]) returns [1, 2, 3, 4]. "
            "You must preserve first-occurrence order and drop later duplicates."
        ),
        "task_io_edge": (
            "Write a Python function unique_elements(lst) that returns the "
            "unique elements of lst in their first-occurrence order. "
            "Example: unique_elements([1, 2, 2, 3, 1, 4]) returns [1, 2, 3, 4]. "
            "Handle empty list input by returning an empty list."
        ),
        "full_spec": (
            "Write a Python function unique_elements(lst) that returns the "
            "unique elements of lst in their first-occurrence order. "
            "Example: unique_elements([1, 2, 2, 3, 1, 4]) returns [1, 2, 3, 4]. "
            "You must preserve first-occurrence order and drop later duplicates. "
            "Handle empty list input by returning an empty list."
        ),
    },
    "longest_common_prefix": {
        "vague": "longest common prefix",
        "task_only": (
            "Write a Python function longest_common_prefix(strs) that finds "
            "the longest common prefix of a list of strings."
        ),
        "task_io": (
            "Write a Python function longest_common_prefix(strs) that returns "
            "the longest string that is a prefix of every string in strs. "
            "Example: longest_common_prefix(['flower', 'flow', 'flight']) returns 'fl'."
        ),
        "task_io_constraints": (
            "Write a Python function longest_common_prefix(strs) that returns "
            "the longest string that is a prefix of every string in strs. "
            "Example: longest_common_prefix(['flower', 'flow', 'flight']) returns 'fl'. "
            "You must compare characters column-by-column from index 0 and stop "
            "at the first mismatch."
        ),
        "task_io_edge": (
            "Write a Python function longest_common_prefix(strs) that returns "
            "the longest string that is a prefix of every string in strs. "
            "Example: longest_common_prefix(['flower', 'flow', 'flight']) returns 'fl'. "
            "Handle empty list input by returning an empty string, and return "
            "an empty string when strings share no common prefix."
        ),
        "full_spec": (
            "Write a Python function longest_common_prefix(strs) that returns "
            "the longest string that is a prefix of every string in strs. "
            "Example: longest_common_prefix(['flower', 'flow', 'flight']) returns 'fl'. "
            "You must compare characters column-by-column from index 0 and stop "
            "at the first mismatch. "
            "Handle empty list input by returning an empty string, and return "
            "an empty string when strings share no common prefix."
        ),
    },
    "run_length_decode": {
        "vague": "run length decode",
        "task_only": (
            "Write a Python function run_length_decode(lst) that decodes a "
            "run-length-encoded list into a string."
        ),
        "task_io": (
            "Write a Python function run_length_decode(lst) that takes a list "
            "of (char, count) tuples and returns the decoded string. "
            "Example: run_length_decode([('a', 2), ('b', 1)]) returns 'aab'."
        ),
        "task_io_constraints": (
            "Write a Python function run_length_decode(lst) that takes a list "
            "of (char, count) tuples and returns the decoded string. "
            "Example: run_length_decode([('a', 2), ('b', 1)]) returns 'aab'. "
            "You must repeat each character by its count in the order given."
        ),
        "task_io_edge": (
            "Write a Python function run_length_decode(lst) that takes a list "
            "of (char, count) tuples and returns the decoded string. "
            "Example: run_length_decode([('a', 2), ('b', 1)]) returns 'aab'. "
            "Handle empty list input by returning an empty string."
        ),
        "full_spec": (
            "Write a Python function run_length_decode(lst) that takes a list "
            "of (char, count) tuples and returns the decoded string. "
            "Example: run_length_decode([('a', 2), ('b', 1)]) returns 'aab'. "
            "You must repeat each character by its count in the order given. "
            "Handle empty list input by returning an empty string."
        ),
    },
    "sum_even": {
        "vague": "sum even numbers",
        "task_only": (
            "Write a Python function sum_even(lst) that sums the even "
            "numbers in a list."
        ),
        "task_io": (
            "Write a Python function sum_even(lst) that returns the sum of "
            "all even integers in lst. "
            "Example: sum_even([1, 2, 3, 4]) returns 6."
        ),
        "task_io_constraints": (
            "Write a Python function sum_even(lst) that returns the sum of "
            "all even integers in lst. "
            "Example: sum_even([1, 2, 3, 4]) returns 6. "
            "Include only integers where n % 2 == 0 in the sum."
        ),
        "task_io_edge": (
            "Write a Python function sum_even(lst) that returns the sum of "
            "all even integers in lst. "
            "Example: sum_even([1, 2, 3, 4]) returns 6. "
            "Handle empty list input by returning 0, and a list with no even numbers returns 0."
        ),
        "full_spec": (
            "Write a Python function sum_even(lst) that returns the sum of "
            "all even integers in lst. "
            "Example: sum_even([1, 2, 3, 4]) returns 6. "
            "Include only integers where n % 2 == 0 in the sum. "
            "Handle empty list input by returning 0, and a list with no even numbers returns 0."
        ),
    },
}

# Validation: every task has every level
_missing_tasks = set(E10_TAGS) - set(E10_PROMPTS)
assert not _missing_tasks, f"Missing prompts for tasks: {_missing_tasks}"
for _task_name, _by_level in E10_PROMPTS.items():
    _missing = set(E10_LEVELS) - set(_by_level)
    assert not _missing, f"{_task_name}: missing levels {_missing}"


def get_e10_prompts() -> list[tuple[str, str, str, Task]]:
    """Flatten E10_PROMPTS into (level, task_name, prompt, task) tuples.

    Order: task-first then level-first, so a model-first outer loop in the
    runner yields all levels per task before swapping to the next task.
    """
    result = []
    for task in E10_ALL_TASKS:
        for level in E10_LEVELS:
            result.append((level, task.name, E10_PROMPTS[task.name][level], task))
    return result
