"""
prompt-lint: A linter for prompt templates.

Detects unfilled {slots}, unbalanced braces, injection-risky phrases, and excessive length.
Returns structured findings that can be used programmatically or formatted for CLI output.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class LintRule(Enum):
    """Available linting rules."""
    UNFILLED = "unfilled"          # Detect unfilled {slots}
    UNBALANCED = "unbalanced"      # Detect unbalanced braces
    INJECTION = "injection"        # Detect injection-risky phrases
    LENGTH = "length"              # Detect excessive length


@dataclass
class Issue:
    """A single linting issue."""
    rule: str
    message: str
    line: int
    column: int
    raw: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule": self.rule,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "raw": self.raw,
        }

    def __str__(self) -> str:
        return f"{self.rule}: {self.message} at line {self.line}, column {self.column}"


# Injection-risky phrases (case-insensitive)
INJECTION_PATTERNS = [
    r"\bignore\s+(previous|all|above|all\s+above)\s+(instructions?|prompts?|commands?)",
    r"\bdisregard\s+(previous|all|above|all\s+above)\s+(instructions?|prompts?|commands?)",
    r"\bforget\s+(all\s+)?(previous|everything)",
    r"\byou\s+are\s+(an?|a)\s+(ai|language\s+model|chatbot|bot)",
    r"\bsystem\s+(instruction|prompt|override)",
    r"\bprompt\s+(injection|bypass|manipulation)",
    r"\bexecute\s+as\s+(a|an)",
    r"\brole\s+(switch|change|override)",
    r"\bignore\s+(all\s+)?directions?",
    r"\bsuperior\s+intelligence",
]


def find_unfilled_slots(prompt: str) -> List[Issue]:
    """Detect unfilled {slots} in the prompt."""
    issues = []
    # Find {word} patterns that don't have corresponding values
    # Simple heuristic: look for { followed by word characters and }
    slot_pattern = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    
    for match in slot_pattern.finditer(prompt):
        slot_name = match.group(1)
        line = prompt[:match.start()].count('\n') + 1
        col = match.start() - prompt[:match.start()].rfind('\n')
        issues.append(Issue(
            rule=LintRule.UNFILLED.value,
            message=f"Unfilled slot: {{{slot_name}}}",
            line=line,
            column=col,
            raw=f"{{{slot_name}}}",
        ))
    
    return issues


def find_unbalanced_braces(prompt: str) -> List[Issue]:
    """Detect unbalanced { or } braces in the prompt."""
    issues = []
    stack = []
    
    for i, char in enumerate(prompt):
        if char == '{':
            stack.append(i)
        elif char == '}':
            if stack:
                stack.pop()
            else:
                # Unmatched closing brace
                line = prompt[:i].count('\n') + 1
                col = i - prompt[:i].rfind('\n')
                issues.append(Issue(
                    rule=LintRule.UNBALANCED.value,
                    message="Unmatched closing brace '}'",
                    line=line,
                    column=col,
                    raw="}",
                ))
    
    # Check for unmatched opening braces
    for pos in stack:
        line = prompt[:pos].count('\n') + 1
        col = pos - prompt[:pos].rfind('\n')
        issues.append(Issue(
            rule=LintRule.UNBALANCED.value,
            message="Unmatched opening brace '{'",
            line=line,
            column=col,
            raw="{",
        ))
    
    return issues


def find_injection_risks(prompt: str) -> List[Issue]:
    """Detect potential prompt injection phrases."""
    issues = []
    prompt_lower = prompt.lower()
    
    for pattern in INJECTION_PATTERNS:
        for match in re.finditer(pattern, prompt_lower, re.IGNORECASE):
            line = prompt[:match.start()].count('\n') + 1
            col = match.start() - prompt[:match.start()].rfind('\n')
            # Extract the matched text for the raw field
            raw = match.group(0)
            issues.append(Issue(
                rule=LintRule.INJECTION.value,
                message=f"Potential prompt injection detected: '{raw}'",
                line=line,
                column=col,
                raw=raw,
            ))
    
    return issues


def check_length(prompt: str, max_length: int = 1000) -> List[Issue]:
    """Check if prompt exceeds maximum length."""
    issues = []
    if len(prompt) > max_length:
        # Report at the end of the prompt
        total_lines = prompt.count('\n') + 1
        last_newline = prompt.rfind('\n')
        col = len(prompt) - last_newline - 1 if last_newline != -1 else len(prompt)
        issues.append(Issue(
            rule=LintRule.LENGTH.value,
            message=f"Prompt length ({len(prompt)}) exceeds maximum ({max_length})",
            line=total_lines,
            column=col,
            raw=f"{len(prompt)}/{max_length}",
        ))
    return issues


def lint_prompt(
    prompt: str,
    rules: Optional[List[LintRule]] = None,
    max_length: int = 1000,
) -> List[Issue]:
    """
    Lint a prompt template and return a list of issues.
    
    Args:
        prompt: The prompt string to lint.
        rules: List of rules to apply. If None, applies all rules.
        max_length: Maximum allowed prompt length.
    
    Returns:
        List of Issue objects.
    """
    if rules is None:
        rules = list(LintRule)
    
    all_issues: List[Issue] = []
    
    if LintRule.UNFILLED in rules:
        all_issues.extend(find_unfilled_slots(prompt))
    
    if LintRule.UNBALANCED in rules:
        all_issues.extend(find_unbalanced_braces(prompt))
    
    if LintRule.INJECTION in rules:
        all_issues.extend(find_injection_risks(prompt))
    
    if LintRule.LENGTH in rules:
        all_issues.extend(check_length(prompt, max_length))
    
    # Sort issues by line, then column
    all_issues.sort(key=lambda x: (x.line, x.column))
    
    return all_issues


def format_issue(issue: Issue) -> str:
    """Format a single issue for CLI output."""
    return f"[{issue.rule}] line {issue.line}:{issue.column} - {issue.message}"


def format_issues_json(issues: List[Issue]) -> str:
    """Format issues as JSON."""
    return json.dumps([i.to_dict() for i in issues], indent=2)


def format_issues_text(issues: List[Issue]) -> str:
    """Format issues as human-readable text."""
    if not issues:
        return "No issues found."
    lines = [f"Found {len(issues)} issue(s):"]
    for issue in issues:
        lines.append(f"  - {format_issue(issue)}")
    return "\n".join(lines)


def lint_file(filepath: str, rules: List[LintRule], max_length: int) -> tuple[List[Issue], str]:
    """Lint a single file and return issues and content."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    issues = lint_prompt(content, rules, max_length)
    return issues, content


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Lint prompt templates for issues and risks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 prompt_lint.py prompt.txt
  python3 prompt_lint.py prompt1.txt prompt2.txt
  python3 prompt_lint.py prompt.txt --format json
  python3 prompt_lint.py prompt.txt --max-length 500
        """,
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='Prompt files to lint',
    )
    
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)',
    )
    
    parser.add_argument(
        '--max-length',
        type=int,
        default=1000,
        help='Maximum prompt length (default: 1000)',
    )
    
    parser.add_argument(
        '--rules',
        nargs='+',
        choices=['unfilled', 'unbalanced', 'injection', 'length'],
        default=None,
        help='Specific rules to run (default: all)',
    )
    
    args = parser.parse_args()
    
    # Map rule names to LintRule enums
    rules = None
    if args.rules:
        rule_map = {
            'unfilled': LintRule.UNFILLED,
            'unbalanced': LintRule.UNBALANCED,
            'injection': LintRule.INJECTION,
            'length': LintRule.LENGTH,
        }
        rules = [rule_map[r] for r in args.rules]
    
    all_issues: List[Issue] = []
    total_files = len(args.files)
    
    for filepath in args.files:
        try:
            issues, _ = lint_file(filepath, rules or list(LintRule), args.max_length)
            for issue in issues:
                issue.raw = f"{filepath}: {issue.raw}"
            all_issues.extend(issues)
        except FileNotFoundError:
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        except IOError as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Output results
    if args.format == 'json':
        print(format_issues_json(all_issues))
    else:
        print(format_issues_text(all_issues))
    
    # Exit with error code if issues found
    if all_issues:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
