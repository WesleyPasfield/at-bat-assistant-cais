---
name: uc-function-design
description: >
  Use this skill when designing Unity Catalog functions to be exposed as deterministic agent tools via MCP.
  Triggered by questions about UC function naming, COMMENT annotations, parameter design, tool chaining,
  the 64-character name limit, or testing functions before agent integration.
---

# UC Function Design Pattern for Deterministic Agent Tools

## Core Principle

Every UC function is a contract between the agent and the data. The function signature — parameter names, types, and COMMENT annotations — is what the LLM sees when deciding which tool to call and how. Well-designed functions constrain the LLM's choices so that correct tool selection becomes the likely outcome, not a lucky one.

## What the LLM Actually Sees

When UC functions are exposed as tools via MCP, the LLM receives:
- The function name
- Parameter names, types, and COMMENT strings
- The top-level COMMENT (the function's docstring)

It does **not** see the SQL body. Your COMMENTs are doing all the work of guiding tool selection.

## Design Guidelines

### 1. Function Names: Verb-First and Specific
The name should tell the LLM the action and scope without reading the COMMENT.

### 2. Parameter COMMENTs Are Instructions
Don't just describe the type — tell the LLM how to populate it. Enumerate valid values, specify where to get IDs, and be explicit about edge cases (especially zero vs. null).

### 3. Function COMMENTs Define Selection Boundaries
The top-level COMMENT should specify when to use the function, what data it returns, prerequisites (other functions to call first), and what it does NOT cover.

### 4. Design for Tool Chaining
Some queries require multiple functions in sequence. Make the chain explicit in COMMENTs. The **embedding lookup → vector search query** two-step pattern is common: look up the vector for a known entity, then pass it to a similarity search function.

### 5. Return Structured Data
For complex results, return JSON strings via `to_json(collect_list(struct(...)))`. For simpler lookups, use `RETURNS TABLE` with explicit column definitions.

### 6. Handle the 64-Character Name Limit
UC function names exposed through the LangChain toolkit truncate to 64 characters. Plan naming conventions accordingly, or add a `_resolve_tool_name` / `_TOOL_NAME_SUFFIX_MAP` resolver to your agent code.

## Function Categories

A well-designed agent typically has functions in these categories:

| Category | Purpose |
|---|---|
| **Entity resolution** | Names → IDs |
| **Direct queries** | Structured retrieval with typed filters |
| **Contextual queries** | Direct queries + situational filters |
| **Embedding lookup** | Entity → vector |
| **Similarity search** | Vector → similar entities |
| **Aggregation** | Multi-entity analysis |
| **Batch operations** | Bulk data for downstream analysis |

Not every agent needs all categories. Design functions around the questions your users actually ask.

## Testing Before Agent Integration

Test each function directly in SQL with known inputs before exposing it to the agent. Verify correct results, sensible edge case behavior (nulls, missing data, empty results), and reasonable response times.

## Reference Implementation

See `at-bat-assistant/notebooks/02_create_agent_tooling.ipynb` for a working implementation of this pattern applied to a different use case (baseball hitting analysis). The function design principles are the same; the domain-specific functions and data are different.
