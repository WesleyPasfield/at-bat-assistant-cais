## Examples

### Example 1: Evaluation Dataset Record Structure

Each record has an input and an expected response description:

```python
pool_entry = {
    "inputs": {
        "input": [{"role": "user", "content": "the question"}]
    },
    "expectations": {
        "expected_response": "1-2 sentence description of what a good answer contains"
    },
}
```

### Example 2: Generating and Persisting the Question Pool

```python
from openai import OpenAI
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
client = w.serving_endpoints.get_open_ai_client()

response = client.chat.completions.create(
    model="your-judge-model",
    messages=[{"role": "user", "content": GENERATION_PROMPT}],
    temperature=0.9,
    max_tokens=30000,
)

# Parse and persist to Delta for reproducibility
spark.createDataFrame(pool_rows).write.mode("overwrite").saveAsTable(
    "catalog.schema.optimization_pool"
)
```

### Example 3: Guardrail-Safe Scorer Wrapper

Domain terminology may trigger model endpoint guardrails. Wrap the judge to handle this gracefully:

```python
from mlflow.genai.scorers import Scorer
from mlflow.entities import Feedback

GUARDRAIL_SENTINEL = -1.0

class GuardrailSafeScorer(Scorer):
    name: str = "my_aligned_judge"
    _delegate: object = None

    class Config:
        underscore_attrs_are_private = True

    def __init__(self, delegate, **kwargs):
        super().__init__(**kwargs)
        self._delegate = delegate

    def __call__(self, *, inputs=None, outputs=None, expectations=None, trace=None):
        try:
            return self._delegate(inputs=inputs, outputs=outputs,
                                  expectations=expectations, trace=trace)
        except Exception as e:
            if "guardrail" in str(e).lower():
                return Feedback(name=self.name, value=GUARDRAIL_SENTINEL,
                                rationale="GUARDRAIL_SKIP")
            raise
```

### Example 4: Predict Function Factory

The factory pattern lets you swap agent modules and prompt URIs without rewriting the predict function:

```python
import importlib
import mlflow

def predict_fn_factory(agent_module_name, prompt_uri):
    mod = importlib.import_module(agent_module_name)
    agent = mod.AGENT

    def predict_fn(input):
        # GEPA intercepts this call to inject candidate prompts
        prompt = mlflow.genai.load_prompt(prompt_uri)
        system_content = prompt.format()

        user_message = input["input"][0]["content"]
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message},
        ]

        result = agent.predict({"input": messages})
        return extract_response_text(result)

    return predict_fn
```

### Example 5: Objective Function with Guardrail Handling

```python
def make_objective_function(judge_name, subset_size):
    counter = {"scores": [], "skipped": 0, "total": 0}

    def objective_function(scores):
        feedback = scores.get(judge_name)
        raw_score = float(feedback.feedback.value)
        counter["total"] += 1

        # Guardrail-skipped rows return current mean (neutral)
        if raw_score == GUARDRAIL_SENTINEL:
            counter["skipped"] += 1
            if counter["scores"]:
                return sum(counter["scores"]) / len(counter["scores"])
            return float("nan")

        normalized = raw_score / 5.0
        counter["scores"].append(normalized)
        return normalized

    return objective_function
```

### Example 6: Running GEPA with Checkpointing

```python
from mlflow.genai.optimize import GepaPromptOptimizer

for run_idx in range(N_RUNS):
    if is_already_done("base", run_idx):
        continue  # Resume from checkpoint

    result = mlflow.genai.optimize_prompts(
        predict_fn=predict_fn,
        train_data=subsets[run_idx],
        prompt_uris=[seed_prompt.uri],
        optimizer=GepaPromptOptimizer(
            reflection_model="databricks-claude-sonnet-4-5",
            max_metric_calls=100,
            display_progress_bar=True,
        ),
        scorers=[aligned_judge],
        aggregation=objective_fn,
    )

    results.append({
        "run_idx": run_idx,
        "initial_score": result.initial_eval_score,
        "final_score": result.final_eval_score,
        "prompt_template": result.optimized_prompts[0].template,
    })
    # Checkpoint to Delta after every run
    save_checkpoint(results)
```

### Example 7: Register and Promote the Best Prompt

```python
best_run = max(results, key=lambda r: r["final_score"])

new_prompt = mlflow.genai.register_prompt(
    name=PROMPT_NAME,
    template=best_run["prompt_template"],
    commit_message=f"GEPA optimized (score: {best_run['initial_score']:.3f} -> {best_run['final_score']:.3f})",
)

mlflow.genai.set_prompt_alias(
    name=PROMPT_NAME,
    alias="production",
    version=new_prompt.version,
)
```
