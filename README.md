# ai_router

Rule-based LLM router for specification, implementation, and review workflows.

This project routes tasks across multiple LLM providers by workflow stage and rule configuration. It is designed for teams that want more control over provider selection, fallback behavior, and review-oriented prompting.

## What it does

- Routes tasks by type and section rules
- Switches between local and API-based providers
- Supports fallback-oriented workflow design
- Keeps prompting and provider selection configurable
- Separates providers and routing rules for easier iteration

## Typical use cases

- Spec review workflows
- Code review and implementation support
- Multi-provider LLM orchestration
- Internal AI routing experiments
- Cost/performance-aware provider selection

## Stack

Python, local LLM integration, Claude API integration, rule-based routing

## Why this repo matters

Applied AI workflows usually need more control than a single model call. This repository shows how to route different tasks to different providers while keeping the logic explicit and modifiable.

## Quick start

```bash
python router.py
```

## Notes

This repository is a good fit for teams that need:
- multi-provider LLM workflows
- controllable routing logic
- fallback-aware AI systems
- review support flows
