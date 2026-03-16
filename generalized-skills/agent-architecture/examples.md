## Examples

### Example 1: Fully Answered by UC Functions

**User Query**: A specific, structured question that maps directly to a UC function's parameters.

**Flow**:
1. LLM selects the appropriate UC function(s) and provides typed parameters
2. Tool(s) execute via MCP (in parallel if multiple)
3. Sufficiency evaluation: **Fully answered** — all parts of the query addressed
4. Agent synthesizes tool results into a response

**Key**: Genie is never called. The response is grounded entirely in deterministic query results.

### Example 2: Partially Answered — Genie Fills the Gap

**User Query**: A compound question where part is answerable by UC functions and part requires freeform SQL.

**Flow**:
1. LLM selects UC function(s) for the structured part
2. Tools execute in parallel
3. Sufficiency evaluation: **Partially answered** — identifies which sub-questions remain
4. Only the unanswered sub-question is sent to Genie
5. Genie generates SQL, executes, returns results
6. Agent synthesizes both UC function results and Genie results into a unified response

**Key**: The Genie query is scoped to only what UC functions couldn't answer.

### Example 3: Skill-Guided Tool Selection

**User Query**: A complex analytical question that matches a known skill pattern.

**Flow**:
1. LLM recognizes the query matches a skill description from the system prompt
2. LLM requests both `load_skill("relevant-skill")` and UC function calls
3. **Only `load_skill` executes first** — skill content is loaded into context
4. With skill instructions now available, the LLM re-evaluates and issues the correct sequence of UC function calls (the skill may specify a different tool chain than the LLM would have chosen without guidance)
5. Tools execute in parallel
6. Sufficiency evaluation proceeds as normal

**Key**: The skill changes the agent's tool selection behavior by providing workflow instructions before function calls execute.

### Example 4: Full Genie Fallback

**User Query**: An open-ended analytical question with no matching UC function.

**Flow**:
1. LLM attempts to match the query to UC functions — no good fit
2. Sufficiency evaluation: **Not answered**
3. Full question is sent to Genie
4. Genie generates SQL against the underlying tables, executes, returns results
5. Agent formats the Genie results into a response

**Key**: This is the expected path for questions that require ad-hoc SQL analytics. The UC-first attempt is fast and cheap — the cost of trying and finding no match is minimal.
