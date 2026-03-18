---
name: evaluation-and-alignment
description: >
  Use this skill when designing an evaluation framework, building a judge, labeling agent traces, or
  aligning a judge to expert feedback with MemAlign. Triggered by questions about MLflow evaluation,
  judge rubrics, Review App labeling, or the 80/20 rubric alignment pattern.
---

# Evaluation and Judge Alignment Pattern

## Core Principle: The 80/20 Rubric

The evaluation judge you write initially is your **best directional guess** — it should be roughly 80% right. It captures the general shape of what "good" looks like in your domain. The remaining 20% — the specificity, the edge cases, the nuanced preferences that make an expert an expert — comes from **aligning the judge to actual expert feedback** using MemAlign.

This means you don't need a perfect rubric to start. You need a rubric that's directionally right and a process that refines it.

## Phase 1: Design the Initial Judge

Create a domain-specific judge using `mlflow.genai.judges.make_judge` that scores agent responses on a Likert scale (1-5).

**Guidelines for the initial rubric:**
- Focus on what matters most in your domain — accuracy? actionability? completeness? bias detection?
- Each level (1-5) should be distinguishable. If you can't tell a 3 from a 4, the criteria are too vague.
- Include the output quality dimensions that domain experts would naturally evaluate
- Don't try to enumerate every edge case — that's what alignment handles

Combine your custom judge with built-in scorers (RelevanceToQuery, Guidelines) for a multi-dimensional view. Register the judge to your MLflow experiment so it can be loaded later for alignment and optimization.

## Phase 2: Build the Evaluation Dataset

Generate a balanced set of ~30 evaluation questions via the Foundation Model API. The generation prompt should:
- Cover the full range of question types your agent will face
- Include questions answerable by UC functions AND questions requiring Genie fallback
- Use realistic entities and scenarios from your domain

Structure evaluation records in the format `evaluate()` expects: `{"inputs": {"input": [{"role": "user", "content": question}]}}`.

## Phase 3: Run Evaluation

Run `mlflow.genai.evaluate()` with your evaluation records, predict function, and scorers. After evaluation:
1. Tag successful traces with a marker (e.g., `eval: complete`)
2. Merge tagged traces into an MLflow GenAI dataset for labeling

## Phase 4: Expert Labeling via Review App

Set up the Review App with a label schema that matches your judge's criteria:
- Use the same 1-5 scale and the same grading language
- Enable the comment field — this is critical
- Create a labeling session and assign domain experts
- Add your evaluation dataset to the session

**The comments are where the value is.** When experts score a response and write *why* — "should have broken this down by individual, not aggregated" — that rationale is exactly what MemAlign distills into guidelines. Encourage experts to explain why, not just score. ~30 labeled traces is typically sufficient.

## Phase 5: Judge Alignment with MemAlign

MemAlign takes expert-labeled traces and produces:
1. **Semantic memory** — distilled guidelines that generalize expert preferences (e.g., "always include sample sizes alongside percentages")
2. **Episodic memory** — representative scored examples that anchor the judge's calibration

Create a `MemAlignOptimizer`, load the base judge, and call `base_judge.align(traces=labeled_traces, optimizer=optimizer)`.

After alignment, inspect `aligned_judge._semantic_memory` — these guidelines are the "last 20%," the specific, actionable preferences that distinguish domain expert evaluation from generic quality assessment. If the guidelines don't make sense or seem too generic, the expert comments may have been too sparse.

Update the aligned judge in the experiment. It's now ready to be used as the scorer for prompt optimization.

## Reference Implementation

See `at-bat-assistant/notebooks/04-Evaluation.ipynb` and `05-JudgeAlignment.ipynb` for a working implementation of this pattern applied to a different use case (baseball hitting analysis). The evaluation and alignment workflow is the same; the rubric criteria and domain are different.
