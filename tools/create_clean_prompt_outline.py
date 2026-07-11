# FILE: tools/create_clean_prompt_outline.py

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # ~/ai_router を指す想定
out_path = BASE_DIR / "pkps" / "clean_prompt_outline.txt"

content = """# Clean Prompting Outline (Essential Items Only)

# Prompting Basics
Prompting best practices
Be clear, direct, and detailed
Prompt engineering overview
Prompt engineering – How-to Guides
Use examples (multishot prompting)
Use XML tags to structure prompts
Giving Claude a role with a system prompt

# Reasoning / Thinking
Let Claude think (Chain-of-thought)
Extended thinking tips

# System Prompt Design
System Prompts
Modifying system prompts
Keep Claude in character with role prompting and prefilling
Prefill Claude's response for greater output control

# Llama Prompt Format
Llama Models

# Code Workflows
Common workflows
Claude Code Analytics API

# Context / Memory
Memory tool
Context editing
"""

out_path.write_text(content, encoding="utf-8")
print(f"written: {out_path}")
