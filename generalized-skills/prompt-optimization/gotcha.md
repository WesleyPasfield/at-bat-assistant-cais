## Gotchas

1. **DO NOT reuse the evaluation dataset from the alignment phase.** The optimization dataset should be separate, larger (~100 questions vs ~30), and include expected response descriptions. The alignment dataset was scored by experts; the optimization dataset is scored by the aligned judge. Mixing them creates data leakage — you'd be optimizing against examples the judge was calibrated on.

2. **CRITICAL: The predict function MUST use `mlflow.genai.load_prompt()` with the same URI passed to `prompt_uris`.** GEPA intercepts this call to inject candidate prompts. If you hardcode the system prompt or load it from a file instead, GEPA will run but never actually change the prompt — you'll get identical scores across all candidates and waste your entire scorer budget.

3. **NEVER run GEPA without checkpointing to Delta.** Each run takes significant time and scorer calls. If the notebook is interrupted (rate limits, cluster timeout, etc.), without checkpointing you restart from zero. Save results after every run and check for completed runs at the start of each iteration.

4. **MUST exclude guardrail-skipped rows from the objective function.** If your model endpoint has content guardrails, domain-specific terminology may trigger false positives. Guardrail-blocked rows should return the current running average (neutral score), not a zero or NaN, so they don't penalize or boost candidates unfairly.

5. **DO NOT use overlapping subsets.** GEPA runs on disjoint subsets to prevent overfitting. If subsets overlap, the optimizer may find prompts that are highly tuned to the shared questions but fail on novel ones. Shuffle the pool with a fixed random seed, then slice into non-overlapping chunks.

6. **NEVER optimize against the base judge.** Always use the aligned judge from MemAlign. The base judge doesn't encode the expert preferences discovered during alignment. Optimizing against it produces prompts that score well on generic criteria but miss the domain-specific quality signals that matter.

7. **MUST validate the best prompt manually before promoting to `@production`.** Read the optimized prompt text. Occasionally GEPA produces a prompt that scores well on the subset but contains degenerate patterns (excessive repetition, contradictory instructions). A quick human review catches these before downstream notebooks consume the prompt.
