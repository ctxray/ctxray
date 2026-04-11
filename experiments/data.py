"""Test prompts and coding tasks for assumption validation experiments.

6 tasks x 5 tiers = 30 prompts for E1.
Tasks chosen for mix of familiarity (well-known vs niche) to test
whether prompt quality matters MORE for less-familiar tasks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TestCase:
    call: str       # e.g. "fizzbuzz(5)"
    expected: str   # exact repr of expected return value


@dataclass
class Task:
    name: str
    func_name: str
    tests: list[TestCase]
    prompts: dict[str, str]   # tier -> prompt text


TASKS: list[Task] = [
    # --- Task 1: fizzbuzz (very well-known) ---
    Task(
        name="fizzbuzz",
        func_name="fizzbuzz",
        tests=[
            TestCase("fizzbuzz(1)", "['1']"),
            TestCase("fizzbuzz(5)", "['1', '2', 'Fizz', '4', 'Buzz']"),
            TestCase(
                "fizzbuzz(15)",
                "['1', '2', 'Fizz', '4', 'Buzz', 'Fizz', '7', '8', 'Fizz', "
                "'Buzz', '11', 'Fizz', '13', '14', 'FizzBuzz']",
            ),
        ],
        prompts={
            "draft": "fizzbuzz",
            "basic": "Write a fizzbuzz function in Python.",
            "good": (
                "Write a Python function fizzbuzz(n) that returns a list of strings "
                "for numbers 1 to n. Divisible by 3 returns 'Fizz', by 5 returns "
                "'Buzz', both returns 'FizzBuzz', else str(number)."
            ),
            "strong": (
                "Write a Python function `fizzbuzz(n: int) -> list[str]`.\n\n"
                "Rules:\n"
                "- Divisible by 3 only: 'Fizz'\n"
                "- Divisible by 5 only: 'Buzz'\n"
                "- Divisible by both 3 and 5: 'FizzBuzz'\n"
                "- Otherwise: the number as a string\n\n"
                "Return a list for numbers 1 through n inclusive.\n\n"
                "Example: fizzbuzz(5) returns ['1', '2', 'Fizz', '4', 'Buzz']"
            ),
            "expert": (
                "You are a Python developer writing clean, well-tested code.\n\n"
                "Implement `fizzbuzz(n: int) -> list[str]` that returns FizzBuzz "
                "results for numbers 1 to n.\n\n"
                "Constraints:\n"
                "- Must handle n=0 by returning an empty list\n"
                "- Must return strings, not integers\n"
                "- Must check divisibility by 15 before checking 3 or 5\n\n"
                "Input: integer n >= 0\n"
                "Output: list of strings\n\n"
                "Examples:\n"
                "```python\n"
                "fizzbuzz(0)  # returns []\n"
                "fizzbuzz(3)  # returns ['1', '2', 'Fizz']\n"
                "fizzbuzz(15) # last element is 'FizzBuzz'\n"
                "```\n\n"
                "Edge case: n=0 should return an empty list, not an error."
            ),
        },
    ),

    # --- Task 2: reverse_words (moderately known) ---
    Task(
        name="reverse_words",
        func_name="reverse_words",
        tests=[
            TestCase("reverse_words('hello world')", "'world hello'"),
            TestCase("reverse_words('single')", "'single'"),
            TestCase("reverse_words('  a  b  c  ')", "'c b a'"),
        ],
        prompts={
            "draft": "reverse the words",
            "basic": "Write a Python function to reverse the words in a string.",
            "good": (
                "Write a Python function reverse_words(s) that reverses the order "
                "of words in a string. Strip extra whitespace. "
                "Example: reverse_words('hello world') returns 'world hello'."
            ),
            "strong": (
                "Write `reverse_words(s: str) -> str` that reverses word order.\n\n"
                "Requirements:\n"
                "- Split on whitespace\n"
                "- Strip leading/trailing spaces\n"
                "- Collapse multiple spaces between words\n\n"
                "Examples:\n"
                "- reverse_words('hello world') -> 'world hello'\n"
                "- reverse_words('  a  b  ') -> 'b a'"
            ),
            "expert": (
                "You are writing a text processing utility in Python.\n\n"
                "Implement `reverse_words(s: str) -> str` that reverses word order "
                "in a string.\n\n"
                "Constraints:\n"
                "- Must strip leading and trailing whitespace\n"
                "- Must collapse multiple spaces to single space\n"
                "- Must preserve original word content (case-sensitive)\n\n"
                "Input: any string, may contain multiple spaces\n"
                "Output: words in reverse order, single-space separated\n\n"
                "```python\n"
                "reverse_words('hello world')   # 'world hello'\n"
                "reverse_words('  a  b  c  ')   # 'c b a'\n"
                "reverse_words('single')        # 'single'\n"
                "```\n\n"
                "Edge case: empty string returns empty string."
            ),
        },
    ),

    # --- Task 3: flatten (moderately known, requires recursion) ---
    Task(
        name="flatten",
        func_name="flatten",
        tests=[
            TestCase("flatten([1, [2, 3]])", "[1, 2, 3]"),
            TestCase("flatten([1, [2, [3, [4]]]])", "[1, 2, 3, 4]"),
            TestCase("flatten([])", "[]"),
        ],
        prompts={
            "draft": "flatten list",
            "basic": "Write a Python function to flatten a nested list.",
            "good": (
                "Write a Python function flatten(lst) that recursively flattens "
                "a nested list into a single flat list. "
                "Example: flatten([1, [2, [3]]]) returns [1, 2, 3]."
            ),
            "strong": (
                "Write `flatten(lst: list) -> list` that recursively flattens "
                "nested lists.\n\n"
                "Requirements:\n"
                "- Handle arbitrary nesting depth\n"
                "- Preserve element order\n"
                "- Non-list elements remain as-is\n\n"
                "Examples:\n"
                "- flatten([1, [2, [3]]]) -> [1, 2, 3]\n"
                "- flatten([]) -> []"
            ),
            "expert": (
                "You are implementing a utility function for data processing.\n\n"
                "Implement `flatten(lst: list) -> list` that recursively flattens "
                "arbitrarily nested lists.\n\n"
                "Constraints:\n"
                "- Must handle arbitrary nesting depth without stack overflow "
                "for reasonable inputs\n"
                "- Must preserve element order (depth-first)\n"
                "- Non-list items should be included as-is\n\n"
                "Input: a list that may contain nested lists\n"
                "Output: flat list with all non-list elements\n\n"
                "```python\n"
                "flatten([1, [2, [3, [4]]]])  # [1, 2, 3, 4]\n"
                "flatten([])                   # []\n"
                "flatten([1, 2, 3])            # [1, 2, 3]\n"
                "```\n\n"
                "Edge case: empty list returns empty list. "
                "Already-flat list returns itself unchanged."
            ),
        },
    ),

    # --- Task 4: two_sum (extremely well-known, LeetCode #1) ---
    Task(
        name="two_sum",
        func_name="two_sum",
        tests=[
            TestCase("two_sum([2, 7, 11, 15], 9)", "(0, 1)"),
            TestCase("two_sum([3, 2, 4], 6)", "(1, 2)"),
            TestCase("two_sum([1, 5, 3, 7], 12)", "(1, 3)"),
        ],
        prompts={
            "draft": "two sum",
            "basic": "Write a two_sum function in Python.",
            "good": (
                "Write a Python function two_sum(nums, target) that returns "
                "the indices of two numbers that add up to target. "
                "Assume exactly one solution exists. Return a tuple of indices."
            ),
            "strong": (
                "Write `two_sum(nums: list[int], target: int) -> tuple[int, int]`.\n\n"
                "Requirements:\n"
                "- Return indices as a tuple (i, j) where i < j\n"
                "- Assume exactly one valid solution\n"
                "- Use O(n) time complexity with a hash map\n\n"
                "Example: two_sum([2, 7, 11, 15], 9) returns (0, 1)"
            ),
            "expert": (
                "You are solving a classic algorithm problem efficiently.\n\n"
                "Implement `two_sum(nums: list[int], target: int) -> tuple[int, int]` "
                "that finds two indices whose values sum to target.\n\n"
                "Constraints:\n"
                "- Must return a tuple (i, j) with i < j\n"
                "- Exactly one solution exists for each input\n"
                "- Must use O(n) time (hash map approach)\n"
                "- Do not use the same element twice\n\n"
                "Input: list of integers and a target integer\n"
                "Output: tuple of two indices\n\n"
                "```python\n"
                "two_sum([2, 7, 11, 15], 9)  # (0, 1)\n"
                "two_sum([3, 2, 4], 6)       # (1, 2)\n"
                "```\n\n"
                "Edge case: list with negative numbers should still work."
            ),
        },
    ),

    # --- Task 5: run_length_encode (less well-known, specific format) ---
    Task(
        name="run_length_encode",
        func_name="run_length_encode",
        tests=[
            TestCase("run_length_encode('aabbc')", "[('a', 2), ('b', 2), ('c', 1)]"),
            TestCase("run_length_encode('aaaa')", "[('a', 4)]"),
            TestCase("run_length_encode('abc')", "[('a', 1), ('b', 1), ('c', 1)]"),
        ],
        prompts={
            "draft": "encode string",
            "basic": "Write a run-length encoding function in Python.",
            "good": (
                "Write a Python function run_length_encode(s) that performs "
                "run-length encoding on a string. Return a list of (char, count) "
                "tuples. Example: run_length_encode('aabbc') returns "
                "[('a', 2), ('b', 2), ('c', 1)]."
            ),
            "strong": (
                "Write `run_length_encode(s: str) -> list[tuple[str, int]]`.\n\n"
                "Run-length encoding compresses consecutive identical characters.\n\n"
                "Requirements:\n"
                "- Return list of (character, count) tuples\n"
                "- Preserve character order\n"
                "- Each tuple: (single char as str, int count >= 1)\n\n"
                "Examples:\n"
                "- run_length_encode('aabbc') -> [('a', 2), ('b', 2), ('c', 1)]\n"
                "- run_length_encode('aaaa') -> [('a', 4)]"
            ),
            "expert": (
                "You are building a data compression utility.\n\n"
                "Implement `run_length_encode(s: str) -> list[tuple[str, int]]` "
                "that performs run-length encoding.\n\n"
                "Constraints:\n"
                "- Must return list of (char, count) tuples\n"
                "- Characters must be single-character strings\n"
                "- Counts must be positive integers\n"
                "- Must handle empty string (return empty list)\n\n"
                "Input: a string of characters\n"
                "Output: list of (str, int) tuples\n\n"
                "```python\n"
                "run_length_encode('aabbc')  # [('a', 2), ('b', 2), ('c', 1)]\n"
                "run_length_encode('')       # []\n"
                "run_length_encode('x')      # [('x', 1)]\n"
                "```\n\n"
                "Edge case: empty string returns empty list. "
                "Single character returns list with one tuple."
            ),
        },
    ),

    # --- Task 6: chunk_list (less well-known, practical utility) ---
    Task(
        name="chunk_list",
        func_name="chunk_list",
        tests=[
            TestCase("chunk_list([1, 2, 3, 4, 5], 2)", "[[1, 2], [3, 4], [5]]"),
            TestCase("chunk_list([1, 2, 3], 3)", "[[1, 2, 3]]"),
            TestCase("chunk_list([], 5)", "[]"),
        ],
        prompts={
            "draft": "split list into chunks",
            "basic": "Write a Python function to split a list into chunks of size n.",
            "good": (
                "Write a Python function chunk_list(lst, n) that splits a list "
                "into sublists of size n. The last chunk may be smaller. "
                "Example: chunk_list([1,2,3,4,5], 2) returns [[1,2], [3,4], [5]]."
            ),
            "strong": (
                "Write `chunk_list(lst: list, n: int) -> list[list]`.\n\n"
                "Requirements:\n"
                "- Split lst into consecutive sublists of size n\n"
                "- Last chunk may have fewer than n elements\n"
                "- Preserve element order\n"
                "- n must be positive integer\n\n"
                "Examples:\n"
                "- chunk_list([1,2,3,4,5], 2) -> [[1,2], [3,4], [5]]\n"
                "- chunk_list([], 5) -> []"
            ),
            "expert": (
                "You are building a batch processing utility.\n\n"
                "Implement `chunk_list(lst: list, n: int) -> list[list]` "
                "that splits a list into consecutive chunks of size n.\n\n"
                "Constraints:\n"
                "- n must be a positive integer\n"
                "- Last chunk may contain fewer than n elements\n"
                "- Must preserve original element order\n"
                "- Must not modify the input list\n\n"
                "Input: a list and chunk size n > 0\n"
                "Output: list of sublists\n\n"
                "```python\n"
                "chunk_list([1,2,3,4,5], 2)  # [[1,2], [3,4], [5]]\n"
                "chunk_list([1,2,3], 3)      # [[1,2,3]]\n"
                "chunk_list([], 5)           # []\n"
                "```\n\n"
                "Edge case: empty list returns empty list regardless of n."
            ),
        },
    ),
]


TIERS = ["draft", "basic", "good", "strong", "expert"]


def get_e0_pairs() -> list[tuple[str, str, Task]]:
    """5 draft + 5 strong prompts for sanity check."""
    pairs: list[tuple[str, str, Task]] = []
    for task in TASKS[:5]:
        pairs.append(("draft", task.prompts["draft"], task))
        pairs.append(("strong", task.prompts["strong"], task))
    return pairs


def get_e1_all() -> list[tuple[str, str, Task]]:
    """All 30 prompts (6 tasks x 5 tiers) for correlation analysis."""
    pairs: list[tuple[str, str, Task]] = []
    for task in TASKS:
        for tier in TIERS:
            pairs.append((tier, task.prompts[tier], task))
    return pairs


# ---------------------------------------------------------------------------
# E9: Specificity Gradient
# ---------------------------------------------------------------------------
# 4 specificity levels, all plain text (no role, no markdown, no XML).
# Isolates specificity from structure — only the amount of task detail changes.

SPECIFICITY_LEVELS = ["vague", "task_only", "task_io", "full_spec"]

E9_PROMPTS: dict[str, dict[str, str]] = {
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
        "full_spec": (
            "Write a Python function fizzbuzz(n) that returns a list of strings "
            "for numbers 1 to n inclusive. Divisible by 3 only: 'Fizz'. "
            "Divisible by 5 only: 'Buzz'. Divisible by both 3 and 5: 'FizzBuzz'. "
            "Otherwise: the number as a string. Check divisibility by 15 before "
            "checking 3 or 5 separately. Handle n=0 by returning an empty list. "
            "Example: fizzbuzz(5) returns ['1', '2', 'Fizz', '4', 'Buzz']. "
            "Example: fizzbuzz(15) last element is 'FizzBuzz'."
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
        "full_spec": (
            "Write a Python function flatten(lst) that recursively flattens "
            "arbitrarily nested lists into a single flat list. Non-list items "
            "are included as-is. Preserve element order depth-first. "
            "Handle empty list by returning empty list. Handle already-flat "
            "list by returning it unchanged. "
            "Example: flatten([1, [2, [3, [4]]]]) returns [1, 2, 3, 4]. "
            "Example: flatten([]) returns []."
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
        "full_spec": (
            "Write a Python function two_sum(nums, target) that returns a "
            "tuple of two indices (i, j) where i < j and nums[i] + nums[j] "
            "equals target. Assume exactly one valid solution exists. Do not "
            "use the same element twice. Use a hash map for O(n) time. "
            "Example: two_sum([2, 7, 11, 15], 9) returns (0, 1). "
            "Example: two_sum([3, 2, 4], 6) returns (1, 2)."
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
        "full_spec": (
            "Write a Python function run_length_encode(s) that performs "
            "run-length encoding on a string. Return a list of tuples where "
            "each tuple is (character as str, count as int) for consecutive "
            "identical characters. Preserve character order. Handle empty "
            "string by returning empty list. "
            "Example: run_length_encode('aabbc') returns [('a', 2), ('b', 2), ('c', 1)]. "
            "Example: run_length_encode('aaaa') returns [('a', 4)]. "
            "Example: run_length_encode('') returns []."
        ),
    },
}

# Map task names to Task objects for E9
_TASK_BY_NAME = {t.name: t for t in TASKS}


def get_e9_prompts() -> list[tuple[str, str, str, Task]]:
    """E9 specificity gradient: (level, task_name, prompt, Task) tuples."""
    pairs: list[tuple[str, str, str, Task]] = []
    for task_name, levels in E9_PROMPTS.items():
        task = _TASK_BY_NAME[task_name]
        for level in SPECIFICITY_LEVELS:
            pairs.append((level, task_name, levels[level], task))
    return pairs
