Here’s a full build spec that uses **JARB as the tool factory**, **LangGraph as the brain**, **Jan as the LLM engine**, and **Macuse + APIs + computer-use MCPs as the effectors**.

I’ll treat sections 3 (ontology), 6 (observability), 10 (deployment), and 11 (voice/VR) as **planned modules**: designed in outline but not fully wired into the core loops yet.

---

## 1. Product overview

**Goal:**
A personal “Jarvis” on macOS that can:

* Chat with you about tasks/goals.
* Read & act on your **email/calendar** (Apple & Google).
* Summarize **PDFs, local docs, and YouTube videos**.
* Control local apps and UI via **Macuse/computer-use**.
* Create new Python tools via **JARB** when an integration doesn’t exist yet.

**Target environment:**

* Primary: single **macOS** machine (Apple Silicon preferred).
* Hybrid: can offload heavy model work to cloud if configured.
* LLM backends: **Jan** (local OpenAI-compatible server) + optional OpenAI/Anthropic.

---

## 2. Core user-facing capabilities

MVP features this spec must support:

1. **Chat + Tasking**

   * User: “Summarize this PDF and create a calendar reminder.”
   * System: pulls file, summarizes, drafts reminder, asks to confirm.

2. **Email & Calendar**

   * Read and summarize threads.
   * Draft replies.
   * Propose times and create events (Google Calendar + Apple Calendar).
   * Confirm before actually sending or saving.

3. **Document & YouTube summarization**

   * PDF: drag/drop into app or “summarize file X”.
   * YouTube: paste URL → transcript → summary, timeline.

4. **Mac automation**

   * Open apps, locate windows, type, click (where no API exists).
   * Use higher-level tools (Macuse) where possible instead of raw UI scripting.

5. **Dynamic tool creation**

   * When existing tools can’t do a task, ask JARB to **generate a new Python script** and register it as a tool (after tests pass).

6. **Autonomy modes (per action type)**

   * Manual: always prompt.
   * Scoped auto: user approves certain flows (“morning brief”, “auto-file summarization”).

---

## 3. High-level architecture

### 3.1 Components

1. **Frontend / UI**

   * Electron or Tauri app (or a simple local web UI) running on macOS.
   * Provides:

     * Chat interface.
     * File drop and YouTube URL input.
     * Action confirmation modals.
     * “Tools & Runs” views (for inspection).

2. **Orchestrator**

   * Python service using **LangGraph**.
   * Hosts:

     * Conversation state.
     * Agent planning logic.
     * Calls to LLM and tools.
     * JARB subgraph for tool generation.

3. **LLM Runtime**

   * Primary: **Jan** local server (`http://localhost:1337/v1`) as an OpenAI-compatible endpoint.
   * Optional: remote OpenAI/Anthropic endpoints (configured in `config.yml`).

4. **Tool Layer**

   * **Static tools:** hand-written Python wrappers for:

     * Gmail, Google Calendar, PDFs, YouTube, file system, etc.
   * **JARB tools:** auto-generated Python modules in `tools/` that become new callable tools.
   * **MCP tools:** Macuse, browser-use, computer-use/remote-macos MCP servers loaded and exposed as tools.

5. **Data Layer**

   * Configuration store (YAML + Keychain).
   * Tool registry (SQLite).
   * Minimal document index (for summarization & basic RAG).
   * **(Ontology, memory, observability, deployment will be structured but added later.)**

---

## 4. LLM backend design

### 4.1 Jan integration

* Jan runs as a local process exposing:

  * `POST /v1/chat/completions`
  * `POST /v1/completions`
* Assistant uses `ChatOpenAI` (or equivalent) configured as:

```python
llm = ChatOpenAI(
    base_url="http://localhost:1337/v1",
    api_key="jan",  # dummy
    model="local/llama3"  # or any Jan-exposed model
)
```

* For more demanding tasks, user can configure:

```yaml
models:
  primary:
    type: jan
    model: local/llama3
  heavy:
    type: openai
    model: gpt-4o
    api_key_env: OPENAI_API_KEY
```

* LangGraph uses `primary` by default and can switch to `heavy` for long-code-gen or very long-document summarization.

### 4.2 Model usage patterns

* **Planner**: uses `heavy` (if configured) for complex multi-step tasks.
* **Summarizer**: can use `primary` (local) if document is chunked.
* **JARB codegen**: ideally uses `heavy` or a code-specialized model for reliability, but falls back to local if offline.

---

## 5. Orchestrator: LangGraph graph design

### 5.1 State

Define a `ConversationState` object (Pydantic or dataclass), e.g.:

```python
class ConversationState(BaseModel):
    user_input: str
    messages: List[BaseMessage] = []
    plan: Optional[str] = None
    pending_tool_call: Optional[ToolCall] = None
    tool_results: Dict[str, Any] = {}
    jarb_task: Optional[JarbTaskState] = None
    autonomy_profile: AutonomyProfile  # from config
```

`JarbTaskState` holds intermediate artifacts during tool generation (spec, code, test output).

### 5.2 Nodes

Core nodes for MVP:

1. `user_entry`

   * Initializes state with `user_input` and appends user message.

2. `planner`

   * LLM node with tools bound:

     * Static tools (email, calendar, pdf, etc.).
     * JARB meta-tool: `create_new_tool`.
     * Macuse/computer-use tools.
   * Uses function calling to either:

     * Call an existing tool, or
     * Call `create_new_tool` with a tool spec description.

3. `tool_node`

   * LangGraph `ToolNode` wrapping:

     * a `ToolExecutor` for static + MCP + JARB tools.
   * Executes the selected tool and updates `tool_results`.

4. `jarb_create_tool` (subgraph entry)

   * Activated when planner calls function `create_new_tool(spec: ToolSpec)`.

5. `respond`

   * Synthesizes a final answer to the user using:

     * `messages`, `tool_results`.

### 5.3 Edges

* `user_entry → planner`
* `planner → tool_node` if a known tool was called.
* `planner → jarb_create_tool` if `create_new_tool` was invoked.
* `tool_node → planner` if more steps needed, else `tool_node → respond`.
* `jarb_create_tool → planner` once tool is registered, then planner will likely call it.

LangGraph config uses a checkpointer (e.g. `MemorySaver`) to persist state across tool calls.

---

## 6. JARB integration: tool factory

### 6.1 JARB responsibilities

JARB is responsible for:

1. Turn a natural language **ToolSpec** into a Python script in `tools/`.
2. Generate unit tests for that script.
3. Run tests and automatically repair code on failures.
4. Once tests pass, log the tool and expose it as a callable function.

### 6.2 ToolSpec schema

In LangGraph, define Pydantic:

```python
class ToolArg(BaseModel):
    name: str
    type: str  # "str", "int", "float", "bool", "List[str]" etc.
    description: str

class ToolSpec(BaseModel):
    name: str                     # snake_case
    description: str
    args: List[ToolArg]
    return_type: str              # e.g. "str", "Dict[str, Any]"
    side_effects: List[str]       # e.g. ["email_send", "calendar_write"]
    examples: List[str]           # example calls in natural language
```

The planner calls `create_new_tool(spec: ToolSpec)`.

### 6.3 JARB subgraph

Separate subgraph inside LangGraph:

1. `jarb_spec_to_code`

   * Uses LLM to generate Python module stub according to `ToolSpec`.
   * Writes to `tools/{spec.name}_v{n}.py`.

2. `jarb_generate_tests`

   * Generates `tests/test_{spec.name}_v{n}.py` with unit tests.
   * Uses example calls and simple invariants.

3. `jarb_run_tests`

   * Spawns subprocess:

     * Activates sandboxed venv.
     * Runs `pytest tests/test_{name}_v{n}.py -q`.
   * Captures stdout/stderr and exit code.

4. `jarb_repair`

   * On failure, passes code + test error back into LLM to patch the module.
   * Writes updated file and re-runs tests.
   * Bounded retries (`max_retries = 3`).

5. `jarb_register`

   * On success:

     * Computes SHA256 of module source.
     * Inserts row into `tool_registry.sqlite`:

       * `name`, `version`, `path`, `hash`, `schema_json`, `side_effects`.
     * Dynamically imports the module, wraps main entrypoint as a `StructuredTool` with proper Pydantic args and return type.
     * Adds this new tool to the **ToolExecutor** used by `tool_node`.

Flow:

* `jarb_create_tool` ≡ entry node that orchestrates `spec_to_code → generate_tests → run_tests → repair? → register`.

### 6.4 Sandbox details (execution)

Sandbox subprocess for tests and runtime:

* Run with:

  * Limited environment variables.
  * No network (unset `HTTP_PROXY`, etc.; optional firewall rules).
  * CWD is `sandbox/` directory.
* Disallow dangerous imports by code review pattern and test:

  * JARB prompt disallows `os.remove`, `subprocess.Popen`, etc., unless explicitly requested for a specialized tool (then require stronger confirmation).
* Timeouts:

  * Each test run: max 10 seconds CPU, enforced via subprocess timeout.

---

## 7. Tool layer

### 7.1 Static integration tools

We implement a set of core tools by hand in `integrations/`:

1. **Gmail tools**

   * `gmail_search(query: str, max_results: int = 20) -> List[EmailSummary]`
   * `gmail_get_thread(thread_id: str) -> EmailThread`
   * `gmail_draft_reply(thread_id: str, body_md: str) -> DraftId`
   * `gmail_send_draft(draft_id: str, confirm: bool = True) -> str`

2. **Google Calendar tools**

   * `gcal_list_events(time_min: str, time_max: str) -> List[Event]`
   * `gcal_create_event(event: EventCreate, confirm: bool = True) -> EventId`

3. **Apple Mail/Calendar/Notes via Macuse**

   * Macuse exposed via MCP; we load Macuse tools and wrap them:

     * `apple_mail_list_threads`, `apple_mail_draft_reply`, `apple_mail_send`.
     * `apple_calendar_create_event`.
     * `apple_notes_create_note`, `apple_notes_update_note`, etc.
   * Each wrapper is a Python `StructuredTool` that calls Macuse-tool via MCP client.

4. **PDF tools**

   * `pdf_extract_text(path: str) -> str`
   * `pdf_summarize(path: str, style: str = "concise") -> str`
   * `pdf_qa(path: str, question: str) -> str`

5. **YouTube tools**

   * `yt_get_transcript(url: str) -> str`
   * `yt_summarize(url: str, style: str = "key_points") -> str`

6. **File system tools**

   * `fs_list_dir(path: str) -> List[str]`
   * `fs_read_text(path: str) -> str`
   * `fs_write_text(path: str, content: str, confirm: bool = True) -> None`

### 7.2 MCP / computer-use tools

We load external MCP servers:

* **Macuse MCP**
* **Browser-use MCP**
* Optional: **automation/remote-macos MCP**

Each MCP tool is discovered via config and registered as a `StructuredTool`. For example:

```python
macuse_tools = load_mcp_server("macuse", config_path="mcp/macuse.toml")
browser_tools = load_mcp_server("browser-use", config_path="mcp/browser.toml")
```

We then add these to the `ToolExecutor` alongside static and JARB tools.

The planner is told:

* “Prefer API/static tools for Gmail/GCal/etc.”
* “Use Macuse for Apple-native actions.”
* “Use browser-use/computer-use only when no simpler tool can do the job.”

---

## 8. Config & secrets

### 8.1 Config file

`config/config.yml` (user-editable):

```yaml
profiles:
  default:
    gmail:
      enabled: true
      account_email: "you@gmail.com"
      token_path: "~/.jarvis/google_tokens.json"
    gcal:
      enabled: true
    apple:
      mail_enabled: true
      calendar_enabled: true
    jan:
      base_url: "http://localhost:1337/v1"
      model: "local/llama3"
    openai:
      enabled: false
    autonomy:
      email_send: "confirm"
      calendar_create: "confirm"
      pdf_summarize: "auto"
      youtube_summarize: "auto"
      ui_automation: "confirm"
```

### 8.2 Secrets

* OAuth tokens stored in:

  * `~/.jarvis/credentials/` (file), but actual secrets kept in macOS Keychain where possible.
* API keys:

  * environment variables (`OPENAI_API_KEY`, etc.) or Keychain entries.

---

## 9. Autonomy modes & policy (base version)

We don’t fully wire in a complex policy engine yet but define a simple mechanism:

* Each tool has a `side_effects` list (from its `ToolSpec` or static metadata).
* Autonomy config defines per-effect behavior: `"auto" | "confirm" | "deny"`.

On each tool invocation:

1. Orchestrator inspects `side_effects`.
2. Looks up autonomy settings in `config.yml`.
3. If `"confirm"`, planner produces a natural-language summary of intended action and sends to UI for user confirmation.
4. UI responds with allow/deny, then orchestrator proceeds or aborts.

---

## 10. Directory layout

Proposed repo structure:

```text
jarvis/
  app/                     # frontend (Electron/Tauri/web)
    src/
    package.json
  orchestrator/
    graph.py               # LangGraph graph definition
    state.py               # ConversationState, ToolSpec models
    planner.py             # LLM planner node
    tool_node.py           # ToolNode wrapper
    jarb_subgraph.py       # JARB integration as LangGraph nodes
    config.py              # load config.yml
    mcp_loader.py          # load Macuse/browser-use MCP tools
  jarb_core/               # your existing JARB code (as a package)
    __init__.py
    generator.py
    tests_generator.py
    runner.py
    registry.py
  tools/                   # JARB-generated tools
    __init__.py
    ...
  integrations/            # static tools
    gmail_tools.py
    gcal_tools.py
    pdf_tools.py
    yt_tools.py
    fs_tools.py
    apple_tools.py         # wrappers around Macuse MCP calls
  mcp/
    macuse.toml            # Macuse server config
    browser-use.toml
  config/
    config.yml
  data/
    tool_registry.sqlite
    docs_index.sqlite      # minimal index for documents
  tests/
    test_static_tools.py
    ...
```

---

## 11. Key flows (how pieces interact)

### 11.1 Summarize PDF & add reminder

1. User drops a PDF into UI and types:
   “Summarize this and remind me tomorrow at 9am.”

2. UI sends:

   * `user_input` + file path to `orchestrator`.

3. `planner` sees attached file and goal:

   * Calls `pdf_summarize(path, style="key_points")`.
   * Then calls `apple_reminder_create` or `gcal_create_event` with extracted date/time.

4. Each tool call goes through:

   * `tool_node` → Python tool → maybe Macuse MCP (for Apple Reminders).
   * If `calendar_create` autonomy = `"confirm"`, a summary is sent to UI for approval.

5. On approval, reminder/event is created.
   `respond` returns:

   * Summary text.
   * Confirmation that reminder is set.

### 11.2 “Build me a new integration” (JARB)

User:
“Whenever I star an email from Alice, create a todo in my Todoist inbox.”

1. Planner checks: no existing `todoist_create_task` tool.

2. Planner calls `create_new_tool` with a `ToolSpec` like:

   * `name="todoist_create_task"`
   * `args=[content: str, due: Optional[str]]`
   * `side_effects=["task_write"]`.

3. `jarb_create_tool` subgraph:

   * `spec_to_code`: JARB writes Python wrapper using Todoist API.
   * `generate_tests`: simple tests calling stub API.
   * `run_tests`: passes.
   * `register`: tool added to registry and ToolExecutor.

4. Planner then builds a small routine:

   * Search Gmail for starred emails from Alice.
   * For each, call `todoist_create_task(subject + snippet)`.

5. Autonomy:

   * `task_write` may be `"confirm"` → UI shows preview list of tasks → user approves.

From then on, `todoist_create_task` is a regular tool for future flows.

### 11.3 UI automation as fallback

User:
“In that weird desktop app X, export all current records to CSV.”

1. Planner sees no API tools for App X.

2. Planner chooses Macuse/computer-use tools:

   * `open_application("X")`
   * `find_button("Export")`
   * `click_button("Export")`
   * `wait_for_file_download(...)`

3. All those are MCP tools wrapped as Python tools.

4. Because `ui_automation` autonomy = `"confirm"`, planner must ask the user:

   * “I’ll control app X: click Export and save a CSV. Is that ok?”

5. On yes, orchestrator executes sequence via Macuse.

---

## 12. Future modules (considered but not wired fully)

You’ve said 3, 6, 10, 11 are important but not to fully wire yet. So we define them as **modules with stubs**:

1. **Ontology / knowledge graph (3)**

   * Stub: `data/ontology.py` with entity classes and DB schema.
   * Initially only used to store minimal metadata for docs/events; full linking & cross-queries added later.

2. **Observability & tracing (6)**

   * Stub: `orchestrator/telemetry.py` that currently logs to stdout/file.
   * Later: integrate with LangSmith or custom trace viewer.

3. **Process management & deployment (10)**

   * Stub: `scripts/start_all.sh` / `Makefile` to start Jan, Macuse, orchestrator.
   * Later: proper `launchd` plist, auto-start at login, and simple health checks.

4. **Voice I/O & VR hooks (11)**

   * Stub: `app/voice.ts` or `orchestrator/voice_server.py` with no-op; define interface for:

     * `transcribe(audio) -> text`
     * `speak(text)`.
   * VR: no code yet, but keep UI API clean so future frontends (VR/AR) can talk to the same orchestrator.

---

If you’d like, next step we can take this spec and:

* Turn it into a **scaffold repo layout** (with minimal code stubs).
* Or zoom in on one path (e.g. JARB subgraph or Macuse wiring) and write actual code skeletons for it.
