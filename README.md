# prompt-lint

A small, self-contained Python linter for prompt templates. Detects unfilled slots, unbalanced braces, injection-risky phrases, and excessive length.

## Installation

No installation required. `prompt-lint` is a single-file Python module with no third-party dependencies.

```bash
# Clone or copy the prompt_lint.py file
python3 prompt_lint.py --help
```

## Usage

### Command-line interface

```bash
# Lint a single prompt file
python3 prompt_lint.py prompt.txt

# Lint multiple files
python3 prompt_lint.py prompt1.txt prompt2.txt

# Lint with custom max length
python3 prompt_lint.py prompt.txt --max-length 500
```

### Programmatic usage

```python
from prompt_lint import lint_prompt, LintRule, Issue

# Default linting (all rules enabled)
issues = lint_prompt("Hello, {name}!")
for issue in issues:
    print(f"{issue.rule}: {issue.message} at line {issue.line}")

# Custom rules
rules = [LintRule.UNFILLED, LintRule.LENGTH]
issues = lint_prompt("Dangerous: {instruction}", rules=rules)
```

## Rules

| Rule | Description |
|------|-------------|
| `unfilled` | Detects unfilled `{slots}` like `{name}` without a value |
| `unbalanced` | Detects unbalanced `{` or `}` braces |
| `injection` | Detects injection-risky phrases (e.g., "Ignore previous instructions") |
| `length` | Reports prompts exceeding the maximum length |

## Output format

```json
[
  {
    "rule": "unfilled",
    "message": "Unfilled slot: {name}",
    "line": 1,
    "column": 8
  },
  {
    "rule": "injection",
    "message": "Potential prompt injection detected: 'Ignore previous instructions'",
    "line": 1,
    "column": 10
  }
]
```

## License

MIT License
