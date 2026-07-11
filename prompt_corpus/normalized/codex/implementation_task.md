## Task
Implement role-based fallback logic in router.py according to the provided specification.

## Target Files

Files you MUST modify:
- router.py

Files you MUST NOT modify:
- any other files

## Instructions
1. Implement provider fallback strictly based on role.
2. Attempt providers sequentially in existing order.
3. Catch exceptions raised by providers.
4. Return immediately on first successful provider execution.
5. Raise an exception only if all providers fail.
6. Preserve all existing behavior for successful executions.

## Output Requirements
- Output FULL updated file content
- No explanations
- No markdown
