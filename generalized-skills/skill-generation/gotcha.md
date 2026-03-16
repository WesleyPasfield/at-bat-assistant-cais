## Gotchas

1. **DO NOT omit any of the 4 input artifacts.** Each serves a distinct purpose: tool signatures tell the optimizer what's possible, the optimized prompt provides behavioral baseline, aligned judge memory encodes expert preferences, and evaluated traces provide grounding examples. Dropping any one produces noticeably weaker skills. The aligned judge memory is the most important — it's the only input that carries the "last 20%" expert specificity.

2. **CRITICAL: The evaluator must return ASI (Actionable Side Information), not just a score.** The score tells the optimizer how good the candidate is; the ASI (judge rationale) tells it *why* and *what to fix*. An evaluator that returns only numeric scores gives the reflection LM nothing to work with — it will make random changes instead of targeted improvements.

3. **NEVER let the optimizer generate skills without the tool signatures.** Without knowing which UC functions exist, their parameter types, and their COMMENTs, generated skills will describe vague workflows like "look up the data" instead of precise tool chains like "call `lookup_entity_by_name` first, then use the returned ID to call `get_entity_details`."

4. **MUST use a validation set (Generalization mode).** If you only provide training data, the optimizer can produce skills that overfit to specific examples. The validation set ensures skills generalize to unseen questions. Split your data into train and val subsets before running optimize_anything.

5. **DO NOT store skills only in UC Volumes or only in Lakebase.** Volumes are good for version control and human review; Lakebase is good for runtime loading from serving endpoints. Write to both — Volumes are the source of truth, Lakebase is the serving cache.

6. **NEVER put full skill content in the system prompt.** Only skill metadata (name + one-line description) belongs in the system prompt. Full content loads on demand via `load_skill`. Loading all skills upfront bloats context and degrades the LLM's ability to select the right skill.

7. **MUST exclude Genie-related skills from the system prompt.** Skills that guide Genie fallback behavior should only be loaded in the Genie fallback node. If they're in the system prompt, they influence the UC-first routing decision and can cause the agent to skip UC functions in favor of Genie for questions that should be handled deterministically.

8. **CRITICAL: Enforce skill-first execution ordering.** When the LLM requests `load_skill` and UC function calls in the same turn, only execute `load_skill` first. If you execute both in parallel, the UC function calls run without the benefit of skill instructions — they may use wrong parameters, wrong tool chains, or miss required steps the skill would have specified.
