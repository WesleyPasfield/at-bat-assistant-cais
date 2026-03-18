---
name: skill-generation
description: >
  Use this skill when generating or optimizing agent skills using optimize_anything. Triggered by
  questions about skill file structure, constructing an evaluator for skill generation, runtime skill
  loading, or storing skills in UC Volumes or Lakebase.
---

# Skill Generation Pattern with optimize_anything

## Core Principle

`optimize_anything` treats any text artifact as something that can be iteratively improved through evaluation and reflection. For agent skills, this means: you don't write skills manually — you provide the right inputs and let the system generate, evaluate, and refine them from your domain evidence.

## What is optimize_anything?

A declarative API from GEPA that optimizes any artifact representable as text. The core loop:

1. An **evaluator** scores a candidate artifact and returns diagnostic feedback (Actionable Side Information / ASI)
2. A **reflection LM** reads the ASI, diagnoses weaknesses, and proposes a targeted improvement
3. A **Pareto-efficient search** preserves candidates that excel on different dimensions
4. Repeat until budget is exhausted, yielding a Pareto frontier of optimized artifacts

For skill generation, use **Generalization mode** (with dataset + validation set) so skills must generalize to unseen examples.

## The 4 Input Artifacts

The quality of generated skills depends directly on the quality of these inputs. Each one gives the optimizer a different signal.

### 1. Tool Signatures (UC Function Definitions)

The complete set of UC function signatures your agent has access to. These tell the optimizer what the agent *can* do deterministically, so skills can reference specific tools and describe when/how to chain them. Without these, generated skills will be vague about which tools to use.

### 2. The Optimized System Prompt

The production prompt from GEPA optimization. This gives the optimizer the agent's current behavioral baseline. Skills should complement the system prompt, not duplicate it.

### 3. Aligned Judge Memory

The semantic guidelines and episodic examples from MemAlign. This is the **most important input** — it encodes the expert preferences that the initial rubric missed (the "last 20%"). Skills generated with this context directly address the gaps experts identified.

### 4. Evaluated Traces with Expert Feedback

The actual agent traces that experts scored and commented on. These ground the optimizer in reality — a guideline says "include sample sizes"; a trace shows exactly what a response without sample sizes looked like and why the expert scored it low.

## Constructing the Evaluator

The evaluator scores each candidate skill and returns ASI (diagnostic feedback). It needs to:

1. **Apply the skill to the agent** — load the candidate skill into the agent's context
2. **Run the agent on evaluation examples** — execute predictions with the skill active
3. **Score with the aligned judge** — use the same calibrated judge from prompt optimization
4. **Return both a score and diagnostic feedback** — the ASI guides the reflection LM toward targeted improvements

Use the aligned judge (not the base judge) and score on a diverse subset (not just one question type).

## Skill File Structure

Each generated skill is a directory with up to three files:

```
skill-name/
  skill.md       # The workflow: what to do, which tools, in what order
  gotcha.md      # The traps: what NOT to do, hard-won from evaluation
  examples.md    # (Optional) Concrete worked examples with tool sequences
```

### skill.md should contain:
- **Frontmatter** with name and description (trigger patterns)
- **Tools** — which UC functions this skill uses
- **Workflow** — step-by-step with decision points and fallback strategies
- **Quality Expectations** — what must be true about the output
- **Response Format** — how to structure the response
- **Before Responding checklist** — verification checks before returning

## Runtime Integration

### Skill Metadata in System Prompt
At agent startup, append only skill names and one-line descriptions (not full content) to the system prompt.

### On-Demand Loading
Full skill content loads only when the LLM decides to use it, via a `load_skill` tool that reads from UC Volumes or Lakebase.

### Execution Priority
When the LLM requests both `load_skill` and UC function calls in the same turn, execute only the skill loads first. The agent needs to read skill instructions before deciding which functions to call.

### Genie-Related Skills
Skills that guide Genie fallback behavior should be excluded from the system prompt and loaded dynamically within the Genie fallback node instead.

## Storing Skills

- **UC Volumes** — file-based, versioned alongside your catalog (source of truth)
- **Lakebase** — row-based, queryable, good for runtime loading from serving endpoints
- Use both: Volumes for version control, Lakebase for serving

## Reference Implementation

See `at-bat-assistant/notebooks/07-AgentSkillsGeneration.ipynb` for a working implementation of this pattern applied to a different use case (baseball hitting analysis). See `at-bat-assistant/example_skills/` for examples of the generated output (each with skill.md, gotcha.md, and examples.md).
