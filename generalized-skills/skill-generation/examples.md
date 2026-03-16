## Examples

### Example 1: Extracting Tool Signatures

```python
tool_signatures = spark.sql(f"""
    SELECT function_name, data_type, full_data_type, comment
    FROM {catalog}.information_schema.routines
    WHERE routine_schema = '{schema}'
""").toPandas().to_string()
```

### Example 2: Assembling the 4 Input Artifacts

```python
from mlflow.genai.scorers import get_scorer

# 1. Tool signatures (extracted above)

# 2. Optimized system prompt
optimized_prompt = mlflow.genai.load_prompt(f"prompts:/{PROMPT_NAME}@production")

# 3. Aligned judge memory
aligned_judge = get_scorer(name="my_aligned_judge", experiment_id=EXPERIMENT_ID)

semantic_guidelines = "\n".join(
    f"- {g.guideline_text}" for g in aligned_judge._semantic_memory
)

episodic_examples = "\n".join(
    str(ex) for ex in aligned_judge._episodic_memory
)

# 4. Evaluated traces
traces = mlflow.search_traces(
    locations=[EXPERIMENT_ID],
    filter_string="tag.eval = 'complete'",
    return_type="list",
)
```

### Example 3: Building the Evaluator

```python
def skill_evaluator(candidate_skill_text, eval_examples):
    """Evaluate a candidate skill by running the agent with it loaded."""
    scores = []
    diagnostics = []

    for example in eval_examples:
        # Run agent with candidate skill in context
        result = agent_with_skill(candidate_skill_text, example["inputs"])

        # Score with aligned judge — not the base judge
        feedback = aligned_judge(
            inputs=example["inputs"],
            outputs=result,
            expectations=example.get("expectations"),
        )
        scores.append(feedback.value)
        diagnostics.append(feedback.rationale)

    return {
        "score": sum(scores) / len(scores),
        "asi": "\n".join(diagnostics),  # Actionable Side Information for reflection LM
    }
```

### Example 4: Running optimize_anything

```python
from mlflow.genai.optimize import optimize_anything

# Combine all context into a single string
context = f"""
## Available Tools
{tool_signatures}

## Current System Prompt
{optimized_prompt.template}

## Expert Quality Guidelines (from MemAlign)
{semantic_guidelines}

## Expert Examples
{episodic_examples}
"""

result = optimize_anything(
    target_description="Agent skill file that guides tool selection and response formatting for [your domain]",
    context=context,
    evaluator=skill_evaluator,
    train_data=train_subset,
    val_data=val_subset,  # Required for Generalization mode
    optimizer_config={
        "reflection_model": "databricks-claude-sonnet-4-5",
        "max_iterations": 50,
    },
)
```

### Example 5: Generated Skill File Structure

A well-generated skill.md follows this template:

```markdown
---
name: skill-name
description: >
  When to use this skill. Triggered by [specific query patterns].
---

# Skill Title

## Tools
- `catalog__schema__function_a`: What it does and when to call it
- `catalog__schema__function_b`: What it does, requires output of function_a

## Workflow
1. **Identify Entity**: Call `function_a`.
   - **IF lookup fails**: Retry with name variations. IF still fails, ask user.

2. **Get Details**: Call `function_b` with the ID from step 1.
   - **IF no data for requested period**: Automatically try previous period. State this explicitly.

3. **Analyze**: Use `parallel_tools` to fetch multiple dimensions simultaneously.

## Quality Expectations
- Every percentage must have a denominator (N). "45% usage (N=90)".
- Break down aggregates into specifics.
- Never output scaled/normalized values without raw equivalents.

## Response Format
- Data source attribution
- Structured breakdown
- Actionable recommendation with reasoning

## Before Responding (Mandatory)
- [ ] Sample sizes included for all percentages
- [ ] Aggregates broken down into specifics
- [ ] All values in human-readable units
- [ ] If period was changed, stated explicitly
```

### Example 6: Writing Skills to UC Volumes and Lakebase

```python
# Write to UC Volume (source of truth)
volume_path = f"/Volumes/{catalog}/{schema}/agent_skills/{skill_name}"
dbutils.fs.put(f"{volume_path}/skill.md", skill_content, overwrite=True)
dbutils.fs.put(f"{volume_path}/gotcha.md", gotcha_content, overwrite=True)

# Sync to Lakebase (serving cache)
import psycopg

with psycopg.connect(lakebase_conn_string) as conn:
    conn.execute(
        "INSERT INTO skills (name, skill_md, gotcha_md) VALUES (%s, %s, %s) "
        "ON CONFLICT (name) DO UPDATE SET skill_md = EXCLUDED.skill_md, gotcha_md = EXCLUDED.gotcha_md",
        (skill_name, skill_content, gotcha_content),
    )
```
