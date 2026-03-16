## Gotchas

1. **DO NOT try to write the perfect rubric upfront.** The initial judge is your directional best guess — 80% right. If you spend hours perfecting rubric language before running MemAlign, you're doing the optimizer's job manually. Write what you know, evaluate, label, align. The specificity comes from expert feedback, not from you staring at rubric text.

2. **CRITICAL: The label schema instructions must match the judge's criteria.** If your `make_judge` uses a 1-5 scale where 5 means "excellent strategic advantage" but your Review App label schema says 5 means "perfectly formatted", experts will score against different criteria than the judge. This creates garbage alignment. Copy the rubric language directly.

3. **NEVER skip the comment field.** Set `enable_comment=True` on the label schema. The numeric score tells MemAlign *how much* the expert liked it; the comment tells it *why*. Without comments, MemAlign produces vague guidelines. With comments like "should have broken this down by individual, not aggregated," it produces precise, actionable ones.

4. **MUST tag traces before creating datasets.** The flow is: evaluate → tag successful traces (`eval: complete`) → merge tagged traces into a GenAI dataset → create labeling session from the dataset. If you skip tagging, you'll include failed/errored traces in the labeling session, which wastes expert time and pollutes alignment.

5. **DO NOT use the base judge for downstream optimization.** After alignment, always load the aligned judge (same name, from the experiment) for prompt optimization and skill generation. The base judge lacks the semantic guidelines and episodic memory that encode expert preferences. Using it produces prompts/skills optimized against generic criteria, not your domain's.

6. **NEVER align with fewer than ~20 labeled traces.** MemAlign needs enough examples to generalize guidelines. With 5-10 traces, it overfits to specific examples rather than extracting transferable patterns. ~30 labeled traces is the sweet spot — enough for generalization, feasible for expert time.

7. **MUST verify alignment by inspecting semantic memory.** After `base_judge.align()`, read through `aligned_judge._semantic_memory`. If the guidelines don't make sense or seem too generic, the expert comments may have been too sparse. This is your sanity check before using the aligned judge for optimization.
