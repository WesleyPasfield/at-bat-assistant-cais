import streamlit as st
import json
import os
import requests
import re
import random
import uuid
from databricks.sdk import WorkspaceClient
from mlflow.deployments import get_deploy_client

# Derive endpoint name from UC model name: catalog.schema.model -> agents_catalog-schema-model
_UC_MODEL_NAME = os.getenv("UC_MODEL_NAME", "")
if _UC_MODEL_NAME:
    _default_endpoint = f"agents_{_UC_MODEL_NAME.replace('.', '-')}"
else:
    _default_endpoint = "agents_atbat_assistant"
SERVING_ENDPOINT_NAME = os.getenv("SERVING_ENDPOINT_NAME", _default_endpoint)


# Example prompts used as clickable starter chips
STARTER_PROMPTS = [
    {"label": "Pitcher matchup", "prompt": "How might Aaron Nola pitch to Mookie Betts?"},
    {"label": "Similar pitches", "prompt": "What pitches are similar to Paul Skenes' Fastball?"},
    {"label": "Batter comps", "prompt": "What batters are similar to Kyle Schwarber?"},
    {"label": "Count tendencies", "prompt": "How does Max Fried pitch to lefties in 0-2 counts?"},
    {"label": "Runner situations", "prompt": "How does Max Scherzer pitch to righties with a runner on 2nd?"},
    {"label": "Team matchups", "prompt": "Who are the toughest Dodgers relievers vs righties?"},
]

BASEBALL_SPINNERS = [
    "Calling the bullpen...",
    "Checking the scouting report...",
    "Asking the pitching coach...",
    "Setting the lineup card...",
    "Reviewing the spray chart...",
    "Studying the film...",
    "Checking statcast...",
    "Getting the sign...",
    "Rounding the bases...",
]

PLACEHOLDER_EXAMPLES = [s["prompt"] for s in STARTER_PROMPTS]

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Global */
html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
@media (min-width: 1100px) {
    .block-container { padding-right: 320px !important; }
}

/* Hide default Streamlit chrome */
header[data-testid="stHeader"] { background: transparent; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Hide the Databricks RUNNING status badge and Stop button */
[class*="StatusWidget"], [data-testid="stStatusWidget"] {
    visibility: hidden !important;
}

/* Hero header - full width banner */
.hero-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.2rem;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -10%;
    width: 250px;
    height: 250px;
    background: radial-gradient(circle, rgba(251,191,36,0.12) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0 0 0.2rem 0;
    position: relative;
    z-index: 1;
}
.hero-subtitle {
    font-size: 0.88rem;
    color: #94a3b8;
    margin: 0;
    position: relative;
    z-index: 1;
}

/* Starter prompt chips - styled via HTML, not st.button */
.starter-section { margin-bottom: 1.5rem; }
.starter-label {
    color: #64748b;
    font-size: 0.85rem;
    margin-bottom: 0.6rem;
}
.starter-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.starter-chip {
    display: inline-block;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
    color: #334155;
    border-radius: 20px;
    padding: 8px 16px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: default;
    transition: all 0.15s ease;
}

/* Style Streamlit buttons as chips */
.stButton > button {
    border: 1px solid #e2e8f0 !important;
    background: #f8fafc !important;
    color: #334155 !important;
    border-radius: 20px !important;
    padding: 0.4rem 1rem !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    border-color: #3b82f6 !important;
    background: #eff6ff !important;
    color: #1d4ed8 !important;
}

/* Chat messages */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    padding: 0.8rem;
    margin-bottom: 0.5rem;
}

/* Tool activity panel - right sidebar, below the Databricks app status bar */
#tool-activity {
    position: fixed;
    top: 3.2rem;
    right: 12px;
    width: 280px;
    max-height: calc(100vh - 4rem);
    overflow-y: auto;
    z-index: 90;
}
@media (max-width: 1100px) {
    #tool-activity { display: none; }
}
.tool-panel-header {
    background: #1e293b;
    border-radius: 10px 10px 0 0;
    padding: 10px 14px;
    color: #f1f5f9;
    font-weight: 600;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    gap: 6px;
}
.tool-panel-body {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-top: none;
    border-radius: 0 0 10px 10px;
    padding: 8px;
    min-height: 50px;
}
.tool-panel-empty {
    color: #94a3b8;
    font-size: 0.82rem;
    text-align: center;
    padding: 16px 8px;
}

/* Tool cards */
.tool-card {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 10px;
    background: #fafbfc;
    margin-bottom: 6px;
    font-size: 0.82rem;
}
.tool-card code {
    background: #eef2ff;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
    color: #4338ca;
}
.tool-card .tool-name {
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 5px;
}
.tool-card .tool-args {
    color: #64748b;
    font-size: 0.78rem;
    margin-top: 3px;
    word-break: break-word;
}
.tool-card .tool-status {
    font-size: 0.75rem;
    margin-top: 4px;
    font-weight: 500;
}
.status-complete { color: #16a34a; }
.status-working { color: #d97706; }
.status-genie { color: #7c3aed; }

/* Processing indicator */
.processing-card { border-color: #fbbf24; background: #fffbeb; }
.processing-dots {
    display: inline-flex;
    gap: 3px;
    margin-left: 6px;
}
.processing-dots span {
    width: 5px; height: 5px;
    background: #d97706;
    border-radius: 50%;
    animation: pulse 1.4s ease-in-out infinite;
}
.processing-dots span:nth-child(2) { animation-delay: 0.2s; }
.processing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes pulse {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1.1); }
}

/* Genie card */
.genie-card { border-color: #c4b5fd; background: #faf5ff; }
.genie-card code { background: #ede9fe; color: #6d28d9; }

/* Skeleton loader */
.skeleton-container {
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    background: #fafbfc;
    min-height: 200px;
}
.skeleton-line {
    border-radius: 6px;
    margin-bottom: 10px;
    animation: shimmer 2s ease-in-out infinite;
}
@keyframes shimmer {
    0% { opacity: 0.5; }
    50% { opacity: 1; }
    100% { opacity: 0.5; }
}
</style>
"""


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()


def convert_messages_for_serving(messages):
    converted = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role not in ("user", "assistant", "system"):
            role = "user"
        if not isinstance(content, str):
            try:
                content = json.dumps(content)
            except Exception:
                content = str(content)
        converted.append({"role": role, "content": content})
    return converted


def extract_assistant_text(response_dict):
    output = response_dict.get("output")
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        if isinstance(output.get("content"), str):
            return output["content"]
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message", {})
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"]
                if isinstance(first.get("text"), str):
                    return first["text"]
    if isinstance(output, list) and output:
        for item in reversed(output):
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message" and item.get("role") in ("assistant", "ASSISTANT"):
                content = item.get("content")
                if isinstance(content, list):
                    text_parts = [c.get("text") for c in content if isinstance(c, dict) and isinstance(c.get("text"), str)]
                    if text_parts:
                        return "".join(text_parts)
                if isinstance(content, str):
                    return content
    messages = response_dict.get("messages")
    if isinstance(messages, list) and messages:
        for item in reversed(messages):
            role = item.get("role")
            content = item.get("content")
            if role in ("assistant", "ASSISTANT") and isinstance(content, str):
                return content
    choices = response_dict.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message", {})
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    predictions = response_dict.get("predictions")
    if isinstance(predictions, list) and predictions:
        first = predictions[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("prediction", "text", "content", "output"):
                val = first.get(key)
                if isinstance(val, str):
                    return val
    return json.dumps(response_dict, indent=2)


def _clean_assistant_markdown(text: str) -> str:
    try:
        if not isinstance(text, str):
            return text
        pattern = r"(?im)(^|\b)tool\s*call:?\s*"
        return re.sub(pattern, "", text)
    except Exception:
        return text


def extract_tool_events(response_dict):
    events = []
    if not isinstance(response_dict, dict):
        return events

    def add_event(label, payload):
        events.append({"label": label, "payload": payload})

    out = response_dict.get("output")
    if isinstance(out, list):
        for item in out:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "function_call":
                add_event("function_call", {
                    "name": item.get("name"),
                    "call_id": item.get("call_id"),
                    "arguments": item.get("arguments"),
                })
            elif item_type == "function_call_output":
                add_event("function_call_output", {
                    "call_id": item.get("call_id"),
                    "output": item.get("output"),
                })
            elif item_type == "message" and item.get("role") in ("assistant", "system"):
                add_event("message", item.get("content"))
    if isinstance(out, dict):
        if isinstance(out.get("tool_calls"), list):
            add_event("tool_calls", out["tool_calls"])

    choices = response_dict.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict):
                msg = choice.get("message", {})
                if isinstance(msg, dict) and isinstance(msg.get("tool_calls"), list):
                    add_event("tool_calls", msg["tool_calls"])

    msgs = response_dict.get("messages")
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") in ("tool", "TOOL", "function"):
                add_event("tool_message", m)

    if isinstance(response_dict.get("events"), list):
        for ev in response_dict["events"]:
            add_event("event", ev)

    return events


def _format_args_for_display(args_value, max_value_len: int = 80) -> str:
    try:
        obj = None
        if isinstance(args_value, str):
            try:
                obj = json.loads(args_value)
            except Exception:
                return args_value
        elif isinstance(args_value, dict):
            obj = args_value
        else:
            return str(args_value)
        parts = []
        for k, v in obj.items():
            val = json.dumps(v)
            if len(val) > max_value_len:
                val = val[: max_value_len - 3] + "..."
            parts.append(f"{k}={val}")
        return ", ".join(parts)
    except Exception:
        return str(args_value)


def _shorten_function_name(full_name: str) -> str:
    try:
        if not isinstance(full_name, str):
            return str(full_name)
        parts = full_name.split("__")
        return parts[-1] if parts else full_name
    except Exception:
        return str(full_name)


def _normalize_host(host: str) -> str:
    h = host.strip().rstrip("/")
    if not (h.startswith("https://") or h.startswith("http://")):
        h = f"https://{h}"
    return h


def _resolve_host(workspace_client: WorkspaceClient) -> str:
    host_env = os.getenv("DATABRICKS_HOST")
    if host_env:
        return _normalize_host(host_env)
    cfg_host = getattr(getattr(workspace_client, "config", None), "host", None)
    if isinstance(cfg_host, str) and cfg_host:
        return _normalize_host(cfg_host)
    raise RuntimeError("Unable to resolve Databricks host; set DATABRICKS_HOST or configure SDK host")


def _get_access_token(host: str) -> str:
    token = os.getenv("DATABRICKS_TOKEN")
    if token:
        return token
    client_id = os.getenv("DATABRICKS_CLIENT_ID")
    client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")
    if client_id and client_secret:
        token_url = f"{host}/oidc/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "all-apis",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        resp = requests.post(token_url, data=data, headers=headers, timeout=30)
        content_type = resp.headers.get("Content-Type", "")
        status = resp.status_code
        try:
            resp.raise_for_status()
        except Exception as http_err:
            snippet = (resp.text or "")[:300]
            raise RuntimeError(
                f"OAuth token request failed: HTTP {status}; Content-Type={content_type}; Body~{snippet}"
            ) from http_err
        try:
            body = resp.json()
        except Exception:
            parsed = _parse_json_safely_from_response(resp)
            if isinstance(parsed, dict) and "raw_text" in parsed and "parse_error" in parsed:
                raise RuntimeError(
                    f"OAuth token response was not valid JSON: HTTP {status}; Content-Type={content_type}; "
                    f"ParseError={parsed.get('parse_error')}; Raw~{parsed.get('raw_text', '')}"
                )
            body = parsed
        access_token = None
        if isinstance(body, dict):
            access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            keys = list(body.keys()) if isinstance(body, dict) else type(body).__name__
            raise RuntimeError(
                f"OAuth token response missing access_token; HTTP {status}; Content-Type={content_type}; Keys={keys}"
            )
        return access_token
    raise RuntimeError("Set DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID/DATABRICKS_CLIENT_SECRET for REST auth")


def _get_bearer_token(workspace_client: WorkspaceClient, host: str) -> str:
    sdk_token = getattr(getattr(workspace_client, "config", None), "token", None)
    if isinstance(sdk_token, str) and sdk_token:
        return sdk_token
    return _get_access_token(host)


def _parse_json_safely_from_response(resp):
    try:
        return resp.json()
    except Exception as je:
        text = resp.text or ""
        first_obj_idx = -1
        brace_idx = text.find("{")
        bracket_idx = text.find("[")
        candidates = [i for i in (brace_idx, bracket_idx) if i != -1]
        if candidates:
            first_obj_idx = min(candidates)
        if first_obj_idx != -1:
            end_brace = text.rfind("}")
            end_bracket = text.rfind("]")
            end_candidates = [i for i in (end_brace, end_bracket) if i != -1]
            if end_candidates:
                end_idx = max(end_candidates) + 1
                snippet = text[first_obj_idx:end_idx]
                try:
                    return json.loads(snippet)
                except Exception:
                    pass
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("{") or s.startswith("["):
                try:
                    return json.loads(s)
                except Exception:
                    continue
        return {"raw_text": text[:2000], "parse_error": str(je)}


def query_via_mlflow(input_messages, workspace_client: WorkspaceClient):
    client = get_deploy_client("databricks")
    payload = {"input": input_messages}

    def _predict(inputs_payload):
        return client.predict(endpoint=SERVING_ENDPOINT_NAME, inputs=inputs_payload)

    def _last_user_message(msgs):
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
                return {"role": "user", "content": m["content"]}
        last = msgs[-1] if msgs else {"role": "user", "content": ""}
        return {"role": "user", "content": last.get("content", "") if isinstance(last, dict) else str(last)}

    try:
        resp = _predict(payload)
    except Exception as e:
        emsg = str(e)
        if "Extra data" in emsg or "BAD_REQUEST" in emsg:
            simple_payload = {"input": [_last_user_message(input_messages)]}
            resp = _predict(simple_payload)
        else:
            raise
    if isinstance(resp, dict):
        body = resp
    else:
        to_dict_fn = getattr(resp, "as_dict", None) or getattr(resp, "to_dict", None)
        body = to_dict_fn() if callable(to_dict_fn) else {"raw": str(resp)}
    if isinstance(body, dict) and body.get("error_code") and isinstance(body.get("message"), str):
        if "Extra data" in body["message"]:
            simple_payload = {"input": [_last_user_message(input_messages)]}
            body = _predict(simple_payload)
            if not isinstance(body, dict):
                to_dict_fn = getattr(body, "as_dict", None) or getattr(body, "to_dict", None)
                body = to_dict_fn() if callable(to_dict_fn) else {"raw": str(body)}
    if isinstance(body, list):
        body = {"output": body}
    elif isinstance(body, dict) and isinstance(body.get("predictions"), list):
        preds = body["predictions"]
        if preds and isinstance(preds[0], dict) and "type" in preds[0]:
            body = {"output": preds}
    return body


def _build_tool_card(call_id, raw_name, args, card_type="standard"):
    name = _shorten_function_name(raw_name)
    if card_type == "genie":
        return f"""
<div class='tool-card genie-card' id='tool-{call_id}'>
  <div class='tool-name'><span>&#127760;</span> <code>Genie Space</code></div>
  <div class='tool-args'><strong>Query</strong>: {args if args else '---'}</div>
  <div class='tool-status status-genie'>Complete</div>
</div>"""
    elif card_type == "skill":
        return f"""
<div class='tool-card' id='tool-{call_id}' style='border-color:#3b82f6; background:#f0f9ff;'>
  <div class='tool-name'><span>&#128218;</span> <code>load_skill</code></div>
  <div class='tool-args'>{args if args else '---'}</div>
  <div class='tool-status' style='color:#2563eb;'>Loaded</div>
</div>"""
    else:
        return f"""
<div class='tool-card' id='tool-{call_id}'>
  <div class='tool-name'><span>&#9881;&#65039;</span> <code>{name}</code></div>
  <div class='tool-args'><strong>Inputs</strong>: {args if args else '---'}</div>
  <div class='tool-status status-complete'>Complete</div>
</div>"""


def _build_processing_card():
    return """
<div class='tool-card processing-card' id='processing-card'>
  <div class='tool-name' style='color:#d97706;'>
    <span>&#9889;</span> Processing
    <div class='processing-dots'><span></span><span></span><span></span></div>
  </div>
  <div class='tool-args' style='color:#92400e;'>Analyzing query and calling tools</div>
</div>"""


def _render_tool_panel_html(cards_html: str, empty: bool = False):
    body_content = cards_html if cards_html and not empty else "<div class='tool-panel-empty'>Tool calls will appear here</div>"
    return f"""
<div id='tool-activity'>
  <div class='tool-panel-header'>
    <span>&#128202;</span> Agent Activity
  </div>
  <div class='tool-panel-body'>
    {body_content}
  </div>
</div>"""


def main():
    st.set_page_config(page_title="At-Bat Assistant", layout="wide", page_icon="\u26be")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Hero header
    st.markdown("""
<div class='hero-header'>
  <div class='hero-title'>&#9918; At-Bat Assistant</div>
  <p class='hero-subtitle'>Baseball hitting intelligence &middot; Powered by Databricks Agent Framework</p>
</div>
""", unsafe_allow_html=True)

    if "last_tool_events" not in st.session_state:
        st.session_state.last_tool_events = []
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "placeholder_hint" not in st.session_state:
        st.session_state.placeholder_hint = random.choice(PLACEHOLDER_EXAMPLES)

    # Tool panel placeholder
    tool_panel = st.empty()

    def _render_tool_panel(cards_html: str, empty: bool = False):
        tool_panel.markdown(_render_tool_panel_html(cards_html, empty), unsafe_allow_html=True)

    _render_tool_panel("", empty=True)

    # Starter prompt chips (only show when no messages)
    if not st.session_state.messages:
        st.markdown("<div class='starter-label'>Try one of these to get started:</div>", unsafe_allow_html=True)
        # Use 2-3 chips per row for readability
        row1 = st.columns(3)
        row2 = st.columns(3)
        rows = [row1, row2]
        for i, sp in enumerate(STARTER_PROMPTS):
            r = i // 3
            c = i % 3
            if r < len(rows):
                with rows[r][c]:
                    if st.button(sp["prompt"], key=f"chip_{i}", use_container_width=True):
                        st.session_state.messages.append({"role": "user", "content": sp["prompt"]})
                        st.rerun()

    # Clear conversation button
    if st.session_state.messages:
        if st.button("Clear conversation", key="clear_btn"):
            st.session_state.messages = []
            st.session_state.last_tool_events = []
            st.session_state.placeholder_hint = random.choice(PLACEHOLDER_EXAMPLES)
            st.rerun()

    # Chat input
    user_input = st.chat_input(placeholder=st.session_state.placeholder_hint, key="chat_input")

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Handle new input (either from chat_input or chip click)
    needs_response = False
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        needs_response = True
    elif st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        # Check if the last message needs a response (from chip click)
        if len(st.session_state.messages) == 1 or (len(st.session_state.messages) >= 2 and st.session_state.messages[-2]["role"] != "user"):
            needs_response = True

    if needs_response:
        # Show the user message if just typed
        if user_input:
            with st.chat_message("user"):
                st.markdown(user_input)

        # Skeleton loader
        skeleton = st.empty()
        skeleton.markdown("""
<div class='skeleton-container'>
  <div class='skeleton-line' style='height:22px; width:55%; background:#e2e8f0;'></div>
  <div class='skeleton-line' style='height:14px; width:90%; background:#f1f5f9;'></div>
  <div class='skeleton-line' style='height:14px; width:85%; background:#f1f5f9;'></div>
  <div class='skeleton-line' style='height:14px; width:88%; background:#f1f5f9;'></div>
  <div style='height:160px; background:#f8fafc; border-radius:10px; border:1px dashed #e2e8f0; margin-top:16px;'></div>
</div>
""", unsafe_allow_html=True)

        with st.chat_message("assistant"):
            with st.spinner(random.choice(BASEBALL_SPINNERS)):
                try:
                    w = get_workspace_client()
                    input_messages = convert_messages_for_serving(st.session_state.messages)
                    client = get_deploy_client("databricks")
                    payload = {"input": input_messages}

                    text_placeholder = st.empty()
                    st.session_state.last_tool_events = []
                    _render_tool_panel(_build_processing_card())

                    assistant_text_parts = []
                    last_message_text = ""
                    streamed_any = False
                    tool_cards_html_parts = []

                    import time as time_module
                    start_time = time_module.time()

                    for chunk in client.predict_stream(endpoint=SERVING_ENDPOINT_NAME, inputs=payload):
                        streamed_any = True
                        ev = chunk if isinstance(chunk, dict) else (getattr(chunk, "to_dict", None) or getattr(chunk, "as_dict", None) or (lambda: {"raw": str(chunk)}))()

                        ev_type = ev.get("type")
                        item = ev.get("item", {}) if isinstance(ev, dict) else {}

                        if ev_type == "response.output_text.delta":
                            delta_text = ev.get("delta", "")
                            if delta_text:
                                assistant_text_parts.append(delta_text)
                                current_text = "".join(assistant_text_parts)
                                text_placeholder.markdown(_clean_assistant_markdown(current_text))

                        elif ev_type == "response.output_item.done" and isinstance(item, dict):
                            item_type = item.get("type")

                            if item_type == "function_call":
                                call_id = item.get("call_id", item.get("id", str(uuid.uuid4())))
                                raw_name = item.get("name", "unknown")
                                args = _format_args_for_display(item.get("arguments", ""))

                                # Remove processing card
                                tool_cards_html_parts = [c for c in tool_cards_html_parts if "id='processing-card'" not in c]

                                if raw_name == "load_skill":
                                    card_type = "skill"
                                elif "genie" in raw_name.lower():
                                    card_type = "genie"
                                else:
                                    card_type = "standard"

                                tool_cards_html_parts.append(_build_tool_card(call_id, raw_name, args, card_type))
                                _render_tool_panel("\n".join(tool_cards_html_parts))
                                st.session_state.last_tool_events.append({
                                    "label": "function_call",
                                    "payload": {"name": raw_name, "call_id": call_id, "arguments": item.get("arguments")}
                                })

                            elif item_type == "function_call_output":
                                pass

                            elif item_type == "message" and item.get("role") in ("assistant", "ASSISTANT"):
                                content = item.get("content")
                                msg_text = ""
                                if isinstance(content, list):
                                    parts = [c.get("text") for c in content if isinstance(c, dict) and isinstance(c.get("text"), str)]
                                    if parts:
                                        msg_text = "".join(parts)
                                elif isinstance(content, str):
                                    msg_text = content
                                if msg_text:
                                    last_message_text = msg_text

                    if assistant_text_parts:
                        assistant_text = "".join(assistant_text_parts)
                    elif last_message_text:
                        assistant_text = last_message_text
                    else:
                        assistant_text = ""

                    assistant_text = _clean_assistant_markdown(assistant_text)
                    if assistant_text:
                        text_placeholder.markdown(assistant_text)

                    if tool_cards_html_parts:
                        tool_cards_html_parts = [c for c in tool_cards_html_parts if "id='processing-card'" not in c]
                        if tool_cards_html_parts:
                            _render_tool_panel("\n".join(tool_cards_html_parts))
                        else:
                            _render_tool_panel("", empty=True)
                    else:
                        _render_tool_panel("", empty=True)

                except Exception as e:
                    try:
                        resp_dict = query_via_mlflow(input_messages, w)
                        tool_events = extract_tool_events(resp_dict)
                        st.session_state.last_tool_events = tool_events
                        assistant_text = _clean_assistant_markdown(extract_assistant_text(resp_dict))
                    except Exception as ee:
                        assistant_text = f"Error querying serving endpoint: {ee}"

                skeleton.empty()
                if not ("streamed_any" in locals() and streamed_any):
                    st.markdown(assistant_text)

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})


if __name__ == "__main__":
    main()
