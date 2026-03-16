## Examples

### Example 1: Creating a Custom Judge

```python
from mlflow.genai.judges import make_judge

my_judge = make_judge(
    name="my_domain_judge",
    instructions=(
        "Evaluate if the response in {{ outputs }} appropriately addresses "
        "the question in {{ inputs }}. [Your domain-specific criteria here]. "
        "Your grading criteria should be: "
        " 1: [What makes a response completely unacceptable in your domain] "
        " 2: [What makes it mostly unacceptable] "
        " 3: [What makes it somewhat acceptable] "
        " 4: [What makes it mostly acceptable] "
        " 5: [What makes it completely acceptable]"
    ),
    feedback_value_type=float,
    model="databricks-claude-sonnet-4-5",
)
```

### Example 2: Combining Multiple Scorers

```python
from mlflow.genai.scorers import Guidelines, RelevanceToQuery

scorers = [
    RelevanceToQuery(),                    # Built-in: is the response relevant?
    Guidelines(                            # Domain-specific language/style
        name="domain_language",
        guidelines="The response must use domain-appropriate terminology accurately."
    ),
    my_judge,                              # Your custom 1-5 Likert judge
]

# Register the judge to the experiment
registered_judge = my_judge.register(experiment_id=EXPERIMENT_ID)
```

### Example 3: Running Evaluation and Tagging Traces

```python
from mlflow.genai import evaluate

results = evaluate(
    data=eval_records,
    predict_fn=my_predict_fn,
    scorers=scorers,
)

# Tag successful traces for downstream use
import mlflow

ok_trace_ids = results.result_df.loc[results.result_df["state"] == "OK", "trace_id"]
for trace_id in ok_trace_ids:
    mlflow.set_trace_tag(trace_id=trace_id, key="eval", value="complete")

# Merge into a GenAI dataset
from mlflow.genai.datasets import create_dataset
eval_dataset = create_dataset(name="my_eval_dataset")
eval_dataset = eval_dataset.merge_records(traces_df)
```

### Example 4: Setting Up the Review App for Expert Labeling

```python
from mlflow.genai import create_labeling_session, get_review_app
from mlflow.genai import label_schemas

# Create a label schema matching your judge's criteria
schema = label_schemas.create_label_schema(
    name="my_label_schema",
    type="feedback",
    title="Response Quality",
    input=label_schemas.InputNumeric(min_value=1.0, max_value=5.0),
    instruction="[Same criteria as your judge, formatted for human readers]",
    enable_comment=True,  # Critical — expert rationales drive alignment
)

# Create a labeling session
session = create_labeling_session(
    name="expert_review",
    assigned_users=["expert@company.com"],
    label_schemas=["my_label_schema"],
)
session = session.add_dataset(dataset_name="my_eval_dataset")
```

### Example 5: Running MemAlign and Inspecting Results

```python
from mlflow.genai.judges.optimizers import MemAlignOptimizer
from mlflow.genai.scorers import get_scorer, ScorerSamplingConfig

# Load the base judge
base_judge = get_scorer(name="my_domain_judge")

# Create the optimizer
optimizer = MemAlignOptimizer(
    reflection_lm="databricks-claude-sonnet-4-5",
    retrieval_k=3,
    embedding_model="databricks-gte-large-en",
)

# Load labeled traces
labeled_traces = mlflow.search_traces(
    locations=[EXPERIMENT_ID],
    filter_string="tag.eval = 'complete'",
    return_type="list",
)

# Align
aligned_judge = base_judge.align(traces=labeled_traces, optimizer=optimizer)

# Inspect semantic memory — these are the "last 20%"
for guideline in aligned_judge._semantic_memory:
    print(guideline.guideline_text)

# Update the aligned judge in the experiment
aligned_judge.update(
    experiment_id=EXPERIMENT_ID,
    sampling_config=ScorerSamplingConfig(sample_rate=0.0),
)
```

### Example 6: Before vs After Alignment

**Base judge guidelines** (what you wrote — directionally right):
> "Evaluate if the response appropriately analyzes the available data and provides an actionable recommendation. The response should be accurate, contextually relevant, and give a strategic advantage."

**Aligned judge guidelines** (what MemAlign learned from expert feedback):
> 1. Always include the total count alongside usage rates or percentages.
> 2. When presenting scaled or normalized data, always provide the raw values or explicitly clarify the unit of measurement.
> 3. Aggregate statistics should be broken down by individual entity when the user asks for a group-wide distribution.
> 4. Verify data accuracy against general domain knowledge (e.g., typical ranges for key metrics).
> 5. Do not present data split by categories if the data source did not explicitly provide that breakdown.
> 6. When analyzing compositions, explicitly define which specific types are included in broader categories.
> 7. When providing recommendations, explain the 'why' behind the choice, such as specific weaknesses or advantages.

The base judge would score a response that aggregates when it should break down by individual as a 3 or 4. The aligned judge, guided by guideline #3, would correctly score it as a 2 — matching what the domain expert would say.
