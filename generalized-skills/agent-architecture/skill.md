---
name: agent-architecture
description: >
  Use this skill when designing or implementing a compound AI agent on Databricks with MLflow.
  Triggered by questions about agent routing, UC-first tool selection, Genie fallback, parallel MCP execution,
  Lakebase conversation memory, or LangGraph state machine architecture.
---

# Agent Architecture Pattern: UC-First Routing with Genie Fallback

## Core Principle

When accuracy is paramount, deterministic tools should always be tried first. An LLM should never guess at something that can be computed exactly. This architecture enforces that principle through a routing pattern that prioritizes structured, typed queries over natural language interpretation.

## Architecture Overview

```
User Query → UC Functions (Parallel MCP) → Sufficiency Evaluation → [Sufficient] → Response
                                                                  ↓
                                                          [Partial / Insufficient]
                                                                  ↓
                                                   Genie Fallback (unanswered parts only)
                                                                  ↓
                                                        Synthesize → Response
```

## Key Components

### 1. UC-First Tool Routing

Unity Catalog functions handle precise, typed queries. The LLM selects which functions to call and with what parameters, but the computation itself is deterministic SQL — no hallucination risk on the data retrieval side.

**Why UC functions first:**
- Schema-governed with typed parameters — the function signature constrains what the LLM can ask for
- Results are exact query results, not LLM interpretations
- Traceable and auditable — every tool call is logged with its parameters and results
- Functions can be shared, permissioned, and versioned through Unity Catalog

### 2. Sufficiency Evaluation Node

After UC function results return, a dedicated evaluation step categorizes the response:
- **Fully answered** — all parts of the user's question are addressed by tool results → synthesize and respond
- **Partially answered** — some parts addressed, others not → send only the unanswered parts to Genie
- **Not answered** — no relevant tool results → send the full question to Genie

This is a LangGraph state machine node that inspects tool outputs against the original query.

### 3. Genie Fallback (Targeted)

The Genie Space handles freeform NL-to-SQL for questions the UC functions cannot answer. Critically, it only receives the **unanswered portions** of the query, not the full question. This prevents Genie from duplicating work already done by UC functions and reduces the surface area for NL-to-SQL errors.

### 4. Parallel MCP Tool Execution

When the LLM requests multiple tools in one turn, each call gets a fresh workspace client and MCP client (credentials cached at module load). A `ThreadPoolExecutor` dispatches calls concurrently. Each thread gets its own MCP session — sessions must not be shared across threads. Connection pooling should be used for database connections.

### 5. Lakebase Conversation Memory

Lakebase (managed PostgreSQL) serves as the LangGraph checkpoint store, enabling:
- Multi-turn conversation persistence across serving endpoint replicas
- Stateless endpoint scaling — any replica can pick up any conversation
- Schema isolation for checkpoint tables (e.g., a dedicated `checkpoint` schema)

Run `checkpointer.setup()` once to create the checkpoint tables before first use.

### 6. Skill-First Execution (for agents with skills)

When skills are present:
- Skill metadata (name + description) is appended to the system prompt at startup
- Full skill content loads on demand via a `load_skill` tool
- When the LLM requests both `load_skill` and UC function calls in the same turn, only the skill calls execute first so the agent reads skill instructions before selecting functions
- Genie-related skills are excluded from the system prompt and loaded dynamically in the Genie fallback node instead

## Agent Framework

The agent is an **MLflow ResponsesAgent** backed by a **LangGraph state machine**. This gives you:
- MLflow's deployment, tracing, and evaluation infrastructure
- LangGraph's explicit state management for routing logic
- The Responses API format for input/output standardization

## When to Use This Pattern

This pattern is appropriate when:
- **Accuracy > creativity** — the domain penalizes wrong answers more than it rewards novel ones
- **Structured data exists** — you have tables/functions that can answer a meaningful subset of questions exactly
- **Domain experts can define tool boundaries** — you know which questions should be deterministic vs. freeform
- **Auditability matters** — stakeholders need to trace how an answer was produced

## Reference Implementation

See `at-bat-assistant/notebooks/03_create_agent_definition.ipynb` for a working implementation of this pattern applied to a different use case (baseball hitting analysis). The architecture is the same; the tools and domain are different.
