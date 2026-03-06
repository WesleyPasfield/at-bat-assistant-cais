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


# Example prompts used to randomize the chat placeholder hint
PLACEHOLDER_EXAMPLES = [
    "How might Aaron Nola pitch to Mookie Betts?",
    "What pitches are similar to Paul Skenes Fastball?",
    "What batters are similar to Kyle Schwarber?",
    "How does Max Fried pitch to lefties in 0-2 counts?",
    "How does Max Scherzer pitch to righties with a runner on 2nd?",
]

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
        # Ensure content is a string to avoid JSON serialization surprises
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
        # ResponsesAgent style: list of OutputItem dicts
        # Prefer the last assistant message's text content
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
    """Remove incidental 'tool call' leakage from model outputs.
    We keep it conservative: strip standalone occurrences like 'tool call', 'tool call:'
    at boundaries or line starts; case-insensitive.
    """
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
    # ResponsesAgent style OutputItem list
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


def is_minimal_sdk_response(resp_dict):
    # No longer used in MLflow-only path; preserved for compatibility
    return False


def _format_args_for_display(args_value, max_value_len: int = 80) -> str:
    """Format tool arguments compactly for UI display."""
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
    """Return the last segment of a fully qualified UC function name (catalog__schema__func)."""
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
            # Include small body snippet for diagnostics
            snippet = (resp.text or "")[:300]
            raise RuntimeError(
                f"OAuth token request failed: HTTP {status}; Content-Type={content_type}; Body~{snippet}"
            ) from http_err

        try:
            body = resp.json()
        except Exception:
            parsed = _parse_json_safely_from_response(resp)
            # If parsing still failed, surface helpful diagnostics
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
            # Provide body keys to aid debugging without dumping secrets
            keys = list(body.keys()) if isinstance(body, dict) else type(body).__name__
            raise RuntimeError(
                f"OAuth token response missing access_token; HTTP {status}; Content-Type={content_type}; Keys={keys}"
            )
        return access_token
    raise RuntimeError("Set DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID/DATABRICKS_CLIENT_SECRET for REST auth")


def _get_bearer_token(workspace_client: WorkspaceClient, host: str) -> str:
    """Resolve a bearer token preferring SDK-configured token, then env, then client credentials."""
    # Prefer token already resolved by the SDK (works with Databricks CLI/UC auth, PATs, etc.)
    sdk_token = getattr(getattr(workspace_client, "config", None), "token", None)
    if isinstance(sdk_token, str) and sdk_token:
        return sdk_token
    # Fallback to env/client credentials path
    return _get_access_token(host)


def _parse_json_safely_from_response(resp):
    try:
        return resp.json()
    except Exception as je:
        text = resp.text or ""
        # Try to extract the JSON portion if there is leading/trailing noise
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
        # Try NDJSON lines
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("{") or s.startswith("["):
                try:
                    return json.loads(s)
                except Exception:
                    continue
        # Fallback to raw text payload for diagnostics
        return {"raw_text": text[:2000], "parse_error": str(je)}


def query_via_rest(input_messages, workspace_client: WorkspaceClient):
    # Removed in simplified flow; keeping stub for safety if referenced
    return {"output": []}


def query_via_sdk_data_plane(input_messages, workspace_client: WorkspaceClient):
    return {"output": []}

def query_via_responses_api(input_messages, workspace_client: WorkspaceClient):
    return {"output": []}

def query_via_mlflow(input_messages, workspace_client: WorkspaceClient):
    """Query the ResponsesAgent endpoint using MLflow deployments client.
    Requests return_trace and normalizes the response for the UI.
    """
    # MLflow deployments: use the 'databricks' target
    client = get_deploy_client("databricks")
    # Use ResponsesAgent schema: inputs expects top-level "input"
    payload = {"input": input_messages}
    def _predict(inputs_payload):
        return client.predict(endpoint=SERVING_ENDPOINT_NAME, inputs=inputs_payload)

    def _last_user_message(msgs):
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
                return {"role": "user", "content": m["content"]}
        # Fallback: just take the final message as a plain user turn
        last = msgs[-1] if msgs else {"role": "user", "content": ""}
        return {"role": "user", "content": last.get("content", "") if isinstance(last, dict) else str(last)}

    try:
        resp = _predict(payload)
    except Exception as e:
        emsg = str(e)
        if "Extra data" in emsg or "BAD_REQUEST" in emsg:
            # Retry with a simplified single-turn user input to avoid JSON parsing issues server-side
            simple_payload = {"input": [_last_user_message(input_messages)]}
            resp = _predict(simple_payload)
        else:
            raise
    # Convert response to a plain dict (support both mlflow client and SDK-like objects)
    if isinstance(resp, dict):
        body = resp
    else:
        to_dict_fn = getattr(resp, "as_dict", None) or getattr(resp, "to_dict", None)
        body = to_dict_fn() if callable(to_dict_fn) else {"raw": str(resp)}
    # Normalize response shapes if needed; handle error objects and auto-retry
    if isinstance(body, dict) and body.get("error_code") and isinstance(body.get("message"), str):
        if "Extra data" in body["message"]:
            simple_payload = {"input": [_last_user_message(input_messages)]}
            body = _predict(simple_payload)
            if not isinstance(body, dict):
                to_dict_fn = getattr(body, "as_dict", None) or getattr(body, "to_dict", None)
                body = to_dict_fn() if callable(to_dict_fn) else {"raw": str(body)}
    # Normalize response shapes
    if isinstance(body, list):
        body = {"output": body}
    elif isinstance(body, dict) and isinstance(body.get("predictions"), list):
        preds = body["predictions"]
        if preds and isinstance(preds[0], dict) and "type" in preds[0]:
            body = {"output": preds}
    return body

# OpenAI client fallback removed per user request

def main():
    st.set_page_config(page_title="At-Bat Assistant", layout="wide")
    st.title("At-Bat Assistant")
    # Lightweight CSS for sleeker UI
    st.markdown(
        """
        <style>
        /* Increase top padding to avoid clipping in embedded environments */
        .block-container { padding-top: 2.4rem; padding-bottom: 2rem; }
        /* Reserve space for a fixed right-side panel */
        @media (min-width: 1100px) {
          .block-container { padding-right: 23%; }
        }
        h1 { margin-bottom: 0.3rem; }
        .app-caption { color:#6b7280; }
        /* Button styling (applies to Streamlit buttons) */
        .stButton>button {
          border: 1px solid #e5e7eb; background: #fff; color: #111827;
          border-radius: 9999px; padding: 0.45rem 0.9rem; font-weight: 500;
          box-shadow: 0 1px 2px rgba(0,0,0,.04);
        }
        .stButton>button:hover { border-color:#cbd5e1; background:#f8fafc; }
        /* Tool cards */
        .tool-card { border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; background:#fafafa; margin-bottom:8px; }
        .tool-card code { background:#eef6ff; padding:2px 6px; border-radius:6px; }
        .small { font-size: 0.9rem; }
        /* Pin agent activity to the viewport on the right */
        #tool-activity { position: fixed; top: 6.5rem; right: 1.2rem; width: 22%; max-height: calc(100vh - 7rem); overflow-y: auto; padding-bottom: 8px; z-index: 100; }
        #tool-activity .tool-card { margin-bottom: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Chat with your baseball hitting assistant powered by an Agent Built on Databricks.")

    if "last_tool_events" not in st.session_state:
        st.session_state.last_tool_events = []

    left_col, right_col = st.columns([2, 1])

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Ask me about specific pitcher-batter matchups, pitcher tendencies, or similar pitches to a given pitch (ex. Paul Skenes Fastball)."}]

    # Initialize randomized placeholder once per session
    if "placeholder_hint" not in st.session_state:
        st.session_state.placeholder_hint = random.choice(PLACEHOLDER_EXAMPLES)
    # Bottom-pinned chat input (with placeholder guidance)
    user_input = st.chat_input(placeholder=st.session_state.placeholder_hint, key="chat_input")

    # Clear conversation button just under caption
    if st.button("Clear conversation", use_container_width=False):
        st.session_state.messages = []
        st.session_state.last_tool_events = []
        st.session_state.placeholder_hint = random.choice(PLACEHOLDER_EXAMPLES)

    # Main layout: left content and right agent activity panel
    left_col, right_col = st.columns([2, 1])

    # Fixed Agent activity panel anchored to body (not inside scrolling columns)
    tool_panel = st.empty()
    def _render_tool_panel(cards_html: str):
        tool_panel.markdown(
            f"""
<div id='tool-activity'>
  <div class='tool-card small' style='font-weight:600; margin-bottom:6px;'>Agent activity</div>
  {cards_html}
</div>
""",
            unsafe_allow_html=True,
        )
    _render_tool_panel("")

    with left_col:
        # Render oldest to newest so new messages appear at the bottom
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # Pre-allocate space with a lightweight skeleton so the page doesn't look empty
            skeleton = st.empty()
            skeleton.markdown(
                """
<div style='border:1px solid #e5e7eb; border-radius:10px; padding:16px; background:#fafafa; min-height:420px'>
  <div style='height:22px; width:60%; background:#e5e7eb; border-radius:6px; margin-bottom:14px;'></div>
  <div style='height:14px; width:95%; background:#f1f5f9; border-radius:6px; margin-bottom:8px;'></div>
  <div style='height:14px; width:92%; background:#f1f5f9; border-radius:6px; margin-bottom:8px;'></div>
  <div style='height:14px; width:90%; background:#f1f5f9; border-radius:6px; margin-bottom:14px;'></div>
  <div style='height:180px; background:#f8fafc; border-radius:8px; border:1px dashed #e5e7eb;'></div>
</div>
""",
                unsafe_allow_html=True,
            )

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        w = get_workspace_client()
                        input_messages = convert_messages_for_serving(st.session_state.messages)
                        client = get_deploy_client("databricks")
                        payload = {"input": input_messages}

                        # Prepare live UI areas
                        text_placeholder = st.empty()
                        st.session_state.last_tool_events = []
                        # Prepare right panel content holder
                        _render_tool_panel("<div class='small' style='opacity:.85'>Working…</div>")

                        assistant_text_parts = []  # accumulates text deltas
                        last_message_text = ""     # tracks the last complete message event
                        streamed_any = False
                        tool_cards_html_parts = []
                        genie_shown = False
                        
                        # Track processing time
                        import time as time_module
                        start_time = time_module.time()
                        shown_processing = False
                        
                        for chunk in client.predict_stream(endpoint=SERVING_ENDPOINT_NAME, inputs=payload):
                            # Show processing indicator if no tool cards yet
                            current_time = time_module.time()
                            elapsed = current_time - start_time
                            
                            if elapsed > 0.5 and not shown_processing and not tool_cards_html_parts:
                                shown_processing = True
                                _render_tool_panel(f"""
<div class='tool-card small' style='border-color:#fbbf24; background:#fffbeb;' id='processing-card'>
  <div style='font-weight:600; color:#d97706;'>Processing...</div>
  <div style='opacity:0.9; font-size:0.85em;'>Analyzing query and calling tools</div>
</div>
""")
                            streamed_any = True
                            ev = chunk if isinstance(chunk, dict) else (getattr(chunk, "to_dict", None) or getattr(chunk, "as_dict", None) or (lambda: {"raw": str(chunk)}))()
                            
                            ev_type = ev.get("type")
                            item = ev.get("item", {}) if isinstance(ev, dict) else {}
                            
                            # Handle text delta events (streaming text)
                            if ev_type == "response.output_text.delta":
                                delta_text = ev.get("delta", "")
                                if delta_text:
                                    assistant_text_parts.append(delta_text)
                                    current_text = "".join(assistant_text_parts)
                                    text_placeholder.markdown(_clean_assistant_markdown(current_text))
                            
                            # Handle structured events (function calls, messages)
                            elif ev_type == "response.output_item.done" and isinstance(item, dict):
                                item_type = item.get("type")
                                
                                # Function call - show in tool panel
                                if item_type == "function_call":
                                    call_id = item.get("call_id", item.get("id", str(uuid.uuid4())))
                                    raw_name = item.get("name", "unknown")
                                    name = _shorten_function_name(raw_name)
                                    args = _format_args_for_display(item.get("arguments", ""))
                                    # Remove processing card and add tool card
                                    tool_cards_html_parts = [c for c in tool_cards_html_parts if "id='processing-card'" not in c]
                                    
                                    # Skip deferred tool placeholders (load_skill deferral)
                                    # These aren't real tool executions
                                    if raw_name == "load_skill":
                                        # Show skill loading with distinct style
                                        tool_cards_html_parts.append(
                                            f"""
<div class='tool-card small' id='tool-{call_id}' style='border-color:#3b82f6; background:#eff6ff;'>
  <div style='font-weight:600; color:#2563eb; margin-bottom:4px;'>&#128218; <code>load_skill</code></div>
  <div style='opacity:0.9; margin-top:4px;'><span style='font-weight:600'>Skill</span>: {args if args else '---'}</div>
  <div class='tool-status' style='color:#2563eb; font-size:0.85em; margin-top:4px;'>Loaded</div>
</div>
"""
                                        )
                                    elif "genie" in raw_name.lower():
                                        # Style Genie calls differently (purple theme)
                                        tool_cards_html_parts.append(
                                            f"""
<div class='tool-card small' id='tool-{call_id}' style='border-color:#8b5cf6; background:#f5f3ff;'>
  <div style='font-weight:600; color:#7c3aed; margin-bottom:4px;'>&#128302; <code>Genie Space Query</code></div>
  <div style='opacity:0.9; margin-top:4px;'><span style='font-weight:600'>Query</span>: {args if args else '---'}</div>
  <div class='tool-status' style='color:#7c3aed; font-size:0.85em; margin-top:4px;'>Complete</div>
</div>
"""
                                        )
                                    else:
                                        # Standard UC tool (green theme)
                                        tool_cards_html_parts.append(
                                            f"""
<div class='tool-card small' id='tool-{call_id}'>
  <div style='font-weight:600; color:#444; margin-bottom:4px;'>&#128295; <code>{name}</code></div>
  <div style='opacity:0.9; margin-top:4px;'><span style='font-weight:600'>Inputs</span>: {args if args else '---'}</div>
  <div class='tool-status' style='color:#22c55e; font-size:0.85em; margin-top:4px;'>Complete</div>
</div>
"""
                                        )
                                    _render_tool_panel("\n".join(tool_cards_html_parts))
                                    st.session_state.last_tool_events.append({
                                        "label": "function_call",
                                        "payload": {"name": raw_name, "call_id": call_id, "arguments": item.get("arguments")}
                                    })
                                
                                # Function call output - no special handling needed
                                elif item_type == "function_call_output":
                                    pass
                                
                                # Message event - track the LAST one as fallback
                                # Don't overwrite streamed text deltas; only use this
                                # if no text deltas were received.
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
                            
                        

                        # Resolve final text: prefer streamed deltas, fall back to
                        # the last complete message event from the stream.
                        if assistant_text_parts:
                            assistant_text = "".join(assistant_text_parts)
                        elif last_message_text:
                            assistant_text = last_message_text
                        else:
                            assistant_text = ""

                        assistant_text = _clean_assistant_markdown(assistant_text)
                        if assistant_text:
                            text_placeholder.markdown(assistant_text)
                        
                        # Finalize tool panel - keep tool cards visible (remove processing card if present)
                        if tool_cards_html_parts:
                            # Remove any lingering processing card
                            tool_cards_html_parts = [c for c in tool_cards_html_parts if "id='processing-card'" not in c]
                            if tool_cards_html_parts:
                                _render_tool_panel("\n".join(tool_cards_html_parts))
                            else:
                                _render_tool_panel("")  # Clear panel if no tool cards
                        else:
                            _render_tool_panel("")  # Clear the "Working..." message
                    except Exception as e:
                        # Fallback to non-streaming path on error
                        try:
                            resp_dict = query_via_mlflow(input_messages, w)
                            tool_events = extract_tool_events(resp_dict)
                            st.session_state.last_tool_events = tool_events
                            assistant_text = _clean_assistant_markdown(extract_assistant_text(resp_dict))
                        except Exception as ee:
                            assistant_text = f"Error querying serving endpoint: {ee}"

                    # Replace skeleton with the final assistant content
                    skeleton.empty()
                    # Only print the final markdown if we did not already stream content
                    if not ("streamed_any" in locals() and streamed_any):
                        st.markdown(assistant_text)
            st.session_state.messages.append({"role": "assistant", "content": assistant_text})




if __name__ == "__main__":
    main()
