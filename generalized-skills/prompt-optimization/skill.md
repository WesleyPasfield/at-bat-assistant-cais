---
name: prompt-optimization
description: >
  Use this skill when optimizing an agent's system prompt using GEPA. Triggered by questions about
  building an optimization dataset, running GEPA, selecting the best prompt, or registering a prompt
  to the MLflow Prompt Registry.
---

# Prompt Optimization Pattern with GEPA

## Core Principle

Prompt optimization is only as good as the evaluation dataset and the judge scoring it. GEPA automates the search for better prompts, but the quality of inputs — a diverse evaluation dataset and a calibrated aligned judge — determines the ceiling.

## Step 1: Construct the Evaluation Dataset

The optimization dataset is **separate from your evaluation dataset** (used in evaluation-and-alignment). It should be larger (~100 questions) and structured for GEPA's disjoint subset approach.

### What Makes a Good Optimization Dataset

**Diversity of question types:**
- Questions answerable by UC functions (deterministic tools)
- Questions requiring Genie fallback (NL-to-SQL)
- Questions requiring multiple tools in combination
- Simple factual lookups and complex analytical questions
- Questions that test edge cases (missing data, ambiguous entities, cross-domain reasoning)

**Include expected responses:** Each example should have both an input and a brief expected response description. This gives the judge a reference point.

**Persist the pool to Delta** for reproducibility and resilience across interruptions.

### Sizing

| Parameter | Recommended | Why |
|---|---|---|
| Pool size | ~100 questions | Large enough for diversity |
| Subsets | 5 disjoint subsets of 20 | Prevents overfitting to narrow question sets |
| Scorer calls/run | ~100 | Budget per GEPA run |

## Step 2: Load the Aligned Judge

Load the aligned judge from MemAlign (see evaluation-and-alignment). This is your scorer — always use the aligned judge, never the base judge, for optimization.

If your model serving endpoint has input guardrails, wrap the judge in a guardrail-safe scorer that returns a sentinel value for blocked requests rather than crashing the optimization.

## Step 3: Define the Predict Function

GEPA needs a predict function that takes an input and returns a string. Use a factory pattern that binds to a specific agent module and prompt URI.

**Key detail:** GEPA intercepts `mlflow.genai.load_prompt()` calls to inject candidate prompts. Your predict function must load the prompt via this API using the URI passed to `prompt_uris` — this is how GEPA swaps in its candidates. If you hardcode the prompt or load it another way, GEPA will never actually test new candidates.

## Step 4: Define the Objective Function

The objective function translates per-example judge scores into an aggregate signal:
- Normalize scores to 0-1 range (divide by your scale max)
- Exclude guardrail-skipped rows from the running average
- Log progress at subset boundaries

## Step 5: Run GEPA Optimization

Run multiple independent passes on disjoint subsets. Checkpoint results to Delta after every run for resilience against rate limits and interruptions. If the notebook is interrupted, re-running resumes from where it left off.

## Step 6: Select and Register the Best Prompt

Find the best run by final score, register to the MLflow Prompt Registry, and promote to `@production`. The optimized prompt is consumed by skill generation and the skills-enhanced agent.

## Reference Implementation

See `at-bat-assistant/notebooks/06-PromptOptimization.ipynb` for a working implementation of this pattern applied to a different use case (baseball hitting analysis). The GEPA mechanics and checkpointing approach are the same; the evaluation dataset and domain are different.
