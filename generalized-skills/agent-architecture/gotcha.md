## Gotchas

1. **DO NOT share MCP sessions across threads.** Each parallel tool call needs its own workspace client and MCP client. Reusing sessions causes auth errors and race conditions. Credentials should be cached at module load (e.g., 50-minute TTL for OAuth tokens), but sessions must be per-thread.

2. **NEVER skip the sufficiency evaluation node.** It's tempting to always call Genie as a "backup" regardless of UC function results. This wastes latency and introduces NL-to-SQL error risk on questions that were already answered deterministically. The whole point of UC-first is that Genie only fires when needed.

3. **CRITICAL: Genie receives only the unanswered parts.** If the user asks a compound question and UC functions answer half of it, do not send the full question to Genie. Reformulate to include only the unanswered portion. Sending the full question causes Genie to duplicate work and potentially contradict the UC function results.

4. **MUST run `checkpointer.setup()` before first use of Lakebase memory.** This creates the checkpoint tables. If you skip this, the agent will fail on the first multi-turn conversation. Use a dedicated `checkpoint` schema with the connection string option `options='-c search_path=checkpoint'`.

5. **DO NOT load all skill content into the system prompt at startup.** Only load skill metadata (name + one-line description). Full skill content loads on demand via `load_skill`. Loading everything upfront bloats the context window and degrades tool selection accuracy.

6. **NEVER let UC function calls execute in the same batch as `load_skill` calls.** When both appear in one turn, execute `load_skill` first. The agent needs to read skill instructions before deciding which UC functions to call and with what parameters. This is an execution ordering constraint in your LangGraph state machine.
