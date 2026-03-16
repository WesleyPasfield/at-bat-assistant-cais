## Gotchas

1. **NEVER write a function COMMENT that only describes what the function returns.** The LLM uses the COMMENT to decide *when* to call it. "Returns a table of results" tells the LLM nothing. "Use this when the user asks about X, requires entity ID from lookup_entity_by_name first" tells it everything.

2. **CRITICAL: Parameter COMMENTs must handle zero/null ambiguity.** If a parameter can legitimately be 0, say so explicitly: "If the value is 0, you must provide 0 rather than nothing." LLMs frequently omit parameters with value 0, treating them as "not specified." This produces wrong query results silently — no error, just wrong data.

3. **DO NOT create one monolithic function that takes many optional parameters.** An LLM struggles to correctly populate 8+ parameters, especially when some are conditionally required. Split into focused functions: one for the base query, another that adds contextual filters. More functions with clear boundaries > fewer functions with complex signatures.

4. **MUST enable Change Data Feed (CDF) on source tables before creating Vector Search indices.** Without CDF, the index creation will fail. This is easy to forget because the error message isn't always clear.

5. **NEVER expose raw embedding vectors to end users.** Embedding columns contain scaled/normalized values (e.g., 0.0-1.0) that are meaningless without context. Functions that return embeddings should be designed for agent-internal use (chaining to similarity search), not for display. If users need the underlying metrics, create a separate function that returns raw values.

6. **MUST test functions with real data before agent integration.** Run each function directly in SQL with known inputs and verify the results match expectations. Pay special attention to edge cases: empty results (entity doesn't exist in that time period), null handling, and functions that depend on other functions' output.

7. **DO NOT assume the LLM will infer tool chains from function names alone.** If function B requires the output of function A, state this explicitly in function B's COMMENT: "Requires entity ID — use lookup_entity_by_name first." Without this, the LLM will try to call function B with a name string instead of an ID, producing empty results or errors.

8. **CRITICAL: Keep the 64-character name limit in mind from the start.** If `catalog.schema.function_name` exceeds 64 characters when prefixed by the LangChain toolkit, the name gets truncated. Plan your catalog/schema/function naming convention to stay under the limit, or add `_resolve_tool_name` and `_TOOL_NAME_SUFFIX_MAP` to your agent code from the beginning.
