#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Setup script for workshop pattern skills
#
# Copies generalized skill directories into the target project and
# configures Claude Code and Codex to pick them up automatically.
#
# Usage:
#   bash /path/to/generalized-skills/setup.sh /path/to/your-project
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIRS=(
    "agent-architecture"
    "evaluation-and-alignment"
    "prompt-optimization"
    "skill-generation"
    "uc-function-design"
)

# ── Validate arguments ──────────────────────────────────────────────
if [ $# -lt 1 ]; then
    echo "Usage: bash setup.sh <target-project-directory>"
    echo ""
    echo "Example:"
    echo "  bash generalized-skills/setup.sh /path/to/your-project"
    exit 1
fi

TARGET_DIR="$(cd "$1" && pwd)"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: $TARGET_DIR is not a directory"
    exit 1
fi

echo "Setting up workshop pattern skills in: $TARGET_DIR"
echo ""

# ── Verify all skill directories exist ──────────────────────────────
for d in "${SKILL_DIRS[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$d/skill.md" ]; then
        echo "Error: Missing skill file $SCRIPT_DIR/$d/skill.md"
        exit 1
    fi
    if [ ! -f "$SCRIPT_DIR/$d/gotcha.md" ]; then
        echo "Error: Missing gotcha file $SCRIPT_DIR/$d/gotcha.md"
        exit 1
    fi
done

# ── Copy skill directories ──────────────────────────────────────────
SKILLS_DIR="$TARGET_DIR/generalized-skills"
mkdir -p "$SKILLS_DIR"

for d in "${SKILL_DIRS[@]}"; do
    mkdir -p "$SKILLS_DIR/$d"
    cp "$SCRIPT_DIR/$d/skill.md" "$SKILLS_DIR/$d/skill.md"
    cp "$SCRIPT_DIR/$d/gotcha.md" "$SKILLS_DIR/$d/gotcha.md"
    # examples.md is optional
    if [ -f "$SCRIPT_DIR/$d/examples.md" ]; then
        cp "$SCRIPT_DIR/$d/examples.md" "$SKILLS_DIR/$d/examples.md"
    fi
done

echo "Copied ${#SKILL_DIRS[@]} skill directories to $SKILLS_DIR/"

# ── Create or append to CLAUDE.md ───────────────────────────────────
CLAUDE_MD="$TARGET_DIR/CLAUDE.md"
CLAUDE_BLOCK="## Workshop Pattern Skills

These pattern skills describe how to build compound AI agents on Databricks with MLflow.
Read them before building — they describe the architecture, evaluation, optimization, and tooling patterns.
Each skill has a skill.md (the workflow), gotcha.md (common traps), and optionally examples.md.

- generalized-skills/agent-architecture/ — UC-first routing, Genie fallback, parallel MCP, Lakebase memory
- generalized-skills/evaluation-and-alignment/ — Judge design, 80/20 rubric approach, MemAlign alignment
- generalized-skills/prompt-optimization/ — Evaluation dataset construction, GEPA prompt optimization
- generalized-skills/skill-generation/ — optimize_anything artifacts, evaluator design, runtime skill integration
- generalized-skills/uc-function-design/ — Typed UC functions with COMMENTs for deterministic agent tools

## Reference Implementation

The at-bat-assistant/ directory contains a working implementation of a DIFFERENT use case (baseball hitting analysis).
Use it as a code reference for how these patterns are implemented, not as a template to copy from.
The architecture and optimization workflow are the same; the tools and domain are different."

if [ -f "$CLAUDE_MD" ]; then
    if grep -q "Workshop Pattern Skills" "$CLAUDE_MD" 2>/dev/null; then
        echo "CLAUDE.md already contains workshop skills section — skipping"
    else
        echo "" >> "$CLAUDE_MD"
        echo "$CLAUDE_BLOCK" >> "$CLAUDE_MD"
        echo "Appended workshop skills section to existing CLAUDE.md"
    fi
else
    echo "$CLAUDE_BLOCK" > "$CLAUDE_MD"
    echo "Created CLAUDE.md"
fi

# ── Create or append to AGENTS.md (Codex) ───────────────────────────
AGENTS_MD="$TARGET_DIR/AGENTS.md"
AGENTS_BLOCK="## Workshop Pattern Skills

These pattern skills describe how to build compound AI agents on Databricks with MLflow.
Read them before building — they describe the architecture, evaluation, optimization, and tooling patterns.
Each skill has a skill.md (the workflow), gotcha.md (common traps), and optionally examples.md.

- generalized-skills/agent-architecture/ — UC-first routing, Genie fallback, parallel MCP, Lakebase memory
- generalized-skills/evaluation-and-alignment/ — Judge design, 80/20 rubric approach, MemAlign alignment
- generalized-skills/prompt-optimization/ — Evaluation dataset construction, GEPA prompt optimization
- generalized-skills/skill-generation/ — optimize_anything artifacts, evaluator design, runtime skill integration
- generalized-skills/uc-function-design/ — Typed UC functions with COMMENTs for deterministic agent tools

## Reference Implementation

The at-bat-assistant/ directory contains a working implementation of a DIFFERENT use case (baseball hitting analysis).
Use it as a code reference for how these patterns are implemented, not as a template to copy from.
The architecture and optimization workflow are the same; the tools and domain are different."

if [ -f "$AGENTS_MD" ]; then
    if grep -q "Workshop Pattern Skills" "$AGENTS_MD" 2>/dev/null; then
        echo "AGENTS.md already contains workshop skills section — skipping"
    else
        echo "" >> "$AGENTS_MD"
        echo "$AGENTS_BLOCK" >> "$AGENTS_MD"
        echo "Appended workshop skills section to existing AGENTS.md"
    fi
else
    echo "$AGENTS_BLOCK" > "$AGENTS_MD"
    echo "Created AGENTS.md"
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "Setup complete. Your project now has:"
echo "  generalized-skills/   — 5 skill directories (each with skill.md + gotcha.md)"
echo "  CLAUDE.md             — Claude Code will read this automatically"
echo "  AGENTS.md             — Codex will read this automatically"
echo ""
echo "Both tools will now use the pattern skills as context when building."
