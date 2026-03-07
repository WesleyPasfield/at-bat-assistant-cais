# At-Bat Assistant

A compound AI agent for baseball hitting analysis, built on Databricks with MLflow, LangGraph, and Unity Catalog. Helps batters prepare for pitcher matchups using pitch-level Statcast tracking data.

Includes an end-to-end optimization loop where domain experts label a small set of agent traces (30 in this demo) with quality scores and short rationales. From those labels, the system automatically produces:

1. A calibrated evaluation judge (via MemAlign)
2. An optimized system prompt (via GEPA, using the aligned judge as the scorer)
3. Composable agent skills (via GEPA's `optimize_anything`)

The judge is calibrated before optimization begins, so all downstream changes are grounded in the expert's quality criteria.

![Pipeline Overview](assets/atbatassistant.png)

## Agent Architecture

The agent is an MLflow ResponsesAgent backed by a LangGraph state machine.

- **UC-first tool routing.** UC functions handle precise, typed queries (count tendencies, matchup history, similarity search). A sufficiency evaluation node categorizes the response as fully answered, partially answered, or not answered. If insufficient, a Genie Space handles the unanswered parts via natural language SQL.
- **Parallel tool execution.** When the LLM requests multiple tools in one turn, each call gets a fresh workspace client and MCP client (credentials cached at module load). A `ThreadPoolExecutor` dispatches calls in parallel.
- **Per-thread conversation memory.** Lakebase (managed PostgreSQL) serves as the LangGraph checkpoint store, supporting multi-turn interaction across serving endpoint replicas.
- **Skill-first execution.** At startup, skill metadata (name + description) is appended to the system prompt. Full skill content loads on demand via a `load_skill` tool. When the LLM requests both `load_skill` and UC function calls in the same turn, only the skill calls execute first so the agent reads skill instructions before selecting functions.

## Prerequisites

- A Databricks workspace with Unity Catalog, a SQL Warehouse, a Genie Space, a Lakebase instance, a Vector Search endpoint, and a Model Serving endpoint
- MLflow 3+ (MemAlign, GEPA, Prompt Registry, Review App)
- A Databricks secret scope for infrastructure credentials

## Getting Started

1. Clone this repository
2. Open the notebooks in a Databricks workspace
3. Run `00_setup.ipynb` to configure your environment (creates `config/atbat_assistant.json` used by all subsequent notebooks)
4. Follow notebooks in order through `09`

`00_setup.ipynb` documents the required secrets and configuration in detail.

## Pipeline

### Build (Notebooks 00-04)

**00 - Setup.** Secrets, catalog/schema, Lakebase, Genie Space, and vector search are configured through a shared JSON config file. All workspace-specific identifiers come from a Databricks secret scope.

**01 - Data Collection.** Pitch-level Statcast data is processed into query-ready pitcher and batter feature tables in Delta, with MinMax-scaled embedding vectors indexed for similarity search. `01b` handles incremental updates for new season data.

**02 - Tool Definition.** Each capability is a schema-governed UC function with typed parameters and coverage docstrings. These include count tendencies, pitcher tendencies with runners, head-to-head matchup history, player name lookup, and embedding-based similarity search.

**03 - Agent Definition.** LangGraph state machine with UC-first routing, a sufficiency evaluation node, Genie fallback, parallel MCP tool execution, and Lakebase conversation memory. The system prompt is loaded from the MLflow Prompt Registry.

**04 - Evaluation.** Synthetic evaluation dataset generated via Foundation Model API calls. The agent is scored with built-in metrics plus a custom 1-5 judge over tool usage, factual accuracy, and actionability. Traces are tagged and merged into a versioned dataset, then surfaced in the MLflow Review App for expert labeling.

### Optimize (Notebooks 05-09)

**05 - Judge Alignment.** MemAlign aligns the judge to expert-labeled traces, producing generalizable guidelines (semantic memory) and scored examples (episodic memory). See `example_aligned_judge/` for the base vs aligned judge output.

**06 - Prompt Optimization.** GEPA runs against a synthetic optimization dataset using the aligned judge as the scorer. The best prompt is promoted to the production alias in the Prompt Registry. See `example_responses/system_prompts.md` for before and after prompts.

**07 - Skill Generation.** `optimize_anything` takes four inputs (tool signatures, the optimized prompt, aligned-judge memory, and evaluated traces with expert feedback) and iteratively refines modular skill files. See `example_skills/` for the generated output.

**08 - Agent with Skills.** The agent from notebook 03 is extended with runtime skill loading. Skill metadata is appended to the system prompt at startup; full content loads on demand. Genie-related skills are excluded from the prompt and loaded dynamically in the Genie fallback node instead.

**09 - Held-Out Evaluation.** Compares agent configurations (baseline, optimized prompt, optimized prompt + skills) on the same held-out question set with the same aligned judge. See `example_responses/agent_responses.md` for side-by-side response comparisons.

## Repository Structure

```
notebooks/                              # Core pipeline notebooks (run in order)
  00_setup.ipynb
  01_collect_data_and_upload_to_databricks.ipynb
  01b_collect_incremental_data.ipynb
  02_create_agent_tooling.ipynb
  03_create_agent_definition.ipynb
  04-Evaluation.ipynb
  05-JudgeAlignment.ipynb
  06-PromptOptimization.ipynb
  07-AgentSkillsGeneration.ipynb
  08_create_agent_with_skills.ipynb
  09-Evaluation.ipynb

app/                                    # Streamlit chat app (deployed as Databricks App)
  atbat-assistant/
    app.py
    app.yaml
    requirements.txt
    run.sh

example_skills/                         # The 7 generated skills
  situational-pitching-analysis/        # Runner-on-base scenarios
  pitcher-scouting-report/              # Full arsenal breakdowns
  h2h-matchups/                         # Head-to-head pitcher-batter analysis
  similar-player-finder/                # Embedding-based similarity search
  roster-strategy/                      # Team composition
  lineup-optimization/                  # Batting order decisions
  league-analysis-genie/                # Genie fallback for league-wide queries
    Each contains: skill.md, gotcha.md, examples.md

example_aligned_judge/                  # Base judge rubric vs aligned judge output
example_responses/                      # Before/after response and prompt comparisons
assets/                                 # Images
```

## Technologies

| Component | What |
|---|---|
| Agent framework | [MLflow ResponsesAgent](https://mlflow.org/docs/latest/llms/responses-agent/index.html) + [LangGraph](https://langchain-ai.github.io/langgraph/) |
| Tool execution | [Unity Catalog Functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function.html) via [Managed MCP](https://docs.databricks.com/aws/en/generative-ai/agent-framework/mcp-tools.html) |
| NL fallback | [Databricks Genie](https://docs.databricks.com/aws/en/genie/index.html) |
| Conversation memory | [Lakebase](https://docs.databricks.com/aws/en/oltp/index.html) (LangGraph checkpoint store) |
| Judge alignment | [MemAlign](https://mlflow.org/docs/latest/llms/memalign/index.html) |
| Prompt optimization | [GEPA](https://mlflow.org/docs/latest/llms/prompt-optimization/index.html) |
| Skill generation | [GEPA optimize_anything](https://mlflow.org/docs/latest/llms/prompt-optimization/index.html) |
| Tracking | [MLflow](https://mlflow.org/) |
| Chat UI | [Streamlit](https://streamlit.io/) (Databricks App) |
| Data source | [MLB Statcast](https://baseballsavant.mlb.com/statcast_search) via pybaseball |
