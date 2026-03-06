# At-Bat Assistant - Streamlit App

A Streamlit chat interface for the At-Bat Assistant agent, deployed as a Databricks App.

## Prerequisites

1. The agent must be deployed via notebook `03_create_agent_definition.ipynb` (cells 18-20)
2. The serving endpoint must be in a **Ready** state

## Deploying as a Databricks App

### 1. Create the App

In the Databricks workspace, go to **Apps** > **Create App** and point it to this directory.

### 2. Configure Environment Variables

The app requires the following environment variable set in the Databricks App configuration:

| Variable | Required | Description |
|---|---|---|
| `SERVING_ENDPOINT_NAME` | **Yes** | The model serving endpoint name. Found in the endpoint URL: `https://<workspace>/serving-endpoints/<endpoint-name>/invocations` |

The endpoint name follows the pattern `agents_<catalog>-<schema>-<model>`, where dots in the UC model name become hyphens. For example:

- UC model: `my_catalog.at_bat_assistant.atbat_assistant`
- Endpoint: `agents_my_catalog-at_bat_assistant-atbat_assistant`

Notebook 03's deploy cell prints the exact endpoint name after deployment.

### 3. Set the Environment Variable

In the Databricks App settings UI:
1. Click **Edit** on your app
2. Under **Environment Variables**, add `SERVING_ENDPOINT_NAME` with your endpoint name
3. Save and restart the app

### 4. Verify

After the app starts, it should connect to the serving endpoint. If you see a 404 `ENDPOINT_NOT_FOUND` error, double-check that:
- The `SERVING_ENDPOINT_NAME` value matches exactly (case-sensitive)
- The serving endpoint is in a **Ready** state
- The app has been restarted after setting the env var

## Files

| File | Description |
|---|---|
| `app.py` | Streamlit application code |
| `app.yaml` | Databricks App configuration (start command) |
| `requirements.txt` | Python dependencies |
| `run.sh` | Local run script |
