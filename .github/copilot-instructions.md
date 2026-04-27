# Copilot instructions for `t.ai`

## Build, test, and lint commands

- Install runtime dependencies: `pip install -r requirements.txt`
- Launch the TUI app: `python main.py`
- Launch the legacy CLI loop (reference mode): `python legacy_main.py`
- Run all unit tests: `python -m unittest discover -s tests -p "test_*.py"`
- Run a single test module: `python -m unittest tests.test_app_commands -v`
- Run a single test case: `python -m unittest tests.test_app_commands.TestAppCommands.test_regen_commands_propagate_in_tui_mode -v`
- Run a single pipeline-focused test case: `python -m unittest tests.test_responses_pipeline.TestResponsesPipeline.test_pipeline_candidates_path -v`

This repository does not define a dedicated lint command or build pipeline in project config.

## High-level architecture

- **Startup and app shell**
  - `main.py` is the primary launcher: validates environment/dependencies, ensures runtime directories, then starts `TaiMenu` from `menu.py`.
  - `legacy_main.py` is the older CLI loop kept for reference; active UX work is centered in the Textual TUI (`menu.py`).

- **TUI orchestration**
  - `menu.py` owns profile/session bootstrapping, chat rendering, command handling, streamed assistant updates, recap flow, and TTS queue workers.
  - User input flow is: `menu.py` → `engines.chat_controller.handle_command_input` (for `//...`) or `menu.py` → `engines.response_orchestrator.iterate_response_events` (for normal chat).
  - Streaming workers (`@work(thread=True)`) emit events and marshal UI changes back to the main thread.

- **LLM response pipeline**
  - `engines.response_orchestrator.iterate_response_events` wraps `engines.responses.get_respond_stream` and turns chunks into event types (`chunk`, `tts`, `complete`) consumed by `menu.py`.
  - `engines.responses.get_respond_stream` assembles full prompt context from profile data, recent history, memory core, lorebook activation, mood/rule mode, and optional narrative pipeline state.
  - Generation can run locally (Ollama) or remotely (`remote_llm_url`), and can optionally use candidate ranking + critic rewrite via `engines.narrative_pipeline`.
  - Prompt composition boundaries are explicit: `engines.prompts` (persona/rules), `engines.lorebook` (keyword-triggered lore injection), and `response_rule/*.md` + `mood_intensity.json` (behavior tuning data).

- **Persistence and memory model**
  - `engines.memory_v2.HistoryManager` persists per-character history in `history/{sanitized_profile}_history.json` as `{ metadata, history }`.
  - Metadata carries recap/memory and pipeline state (`memory_core`, `last_summarized_index`, `narrative_state`, `last_turn_metrics`) in addition to interaction/mood fields.
  - `engines.recap_service` + `menu.py` drive recap and rolling summarization, updating memory core incrementally without deleting full chat history.
  - Regeneration stores assistant alternatives on the same message (`alternatives`, `selected_index`) and UI navigation (`Alt+Left` / `Alt+Right`) swaps selected variants.

- **Audio/TTS path**
  - `menu.py` queues TTS payloads while response text is still streaming; synthesis and playback are decoupled from UI updates.
  - `engines.tts_module` handles voice cleanup/routing and supports Edge TTS plus XTTS local/remote fallback with cache integration via `engines.audio_cache`.
  - `engines.response_orchestrator` decides narration-vs-dialogue voice segments from streamed text boundaries before enqueueing TTS events.

## Key conventions in this codebase

- **TUI command dispatch contract**
  - In TUI mode, command handling goes through `engines.chat_controller.handle_command_input(...)`, which internally calls `app_commands(..., suppress_output=True)`.
  - Control-flow commands are exception-driven (`RestartRequested`, `RegenerateRequested`, `RewindRequested`) and must be propagated/handled by the TUI layer.

- **Threading and Textual DOM safety**
  - Background workers (`@work(thread=True)`) should not query/mutate the widget tree directly.
  - Resolve widget references on the main thread before worker start, and use `self.app.call_from_thread(...)` for UI updates from workers.

- **Profile/history naming convention**
  - `history_profile_name` is derived from the character profile filename (basename without `.json`), and that key is used consistently for memory reads/writes.
  - Do not use display names as storage identifiers when a profile basename is available; history files are keyed by sanitized basename.

- **Settings access pattern**
  - Use `engines.config.get_setting` / `update_setting` instead of ad-hoc file access.
  - `get_setting` gives environment variables precedence over `settings.json` (uppercase key mapping).

- **Prompt/rule composition**
  - Keep RP/Casual behavior logic in `response_rule/rp_rule.md` and `response_rule/casual_rule.md`.
  - Relationship-state behavior should flow through `engines.prompts.get_mood_rule` / `mood_intensity.json`, not hardcoded mood thresholds in UI logic.

- **Regeneration and alternatives**
  - Regeneration should produce a new assistant alternative for the last user turn, not overwrite prior answer content.
  - When regenerating, preserve and update `alternatives` + `selected_index` so response pagination in UI remains coherent.

- **Rolling summary trigger**
  - Use `engines.recap_service.rolling_summary_target_index(...)` to decide when to summarize.
  - Current behavior summarizes only when unsummarized backlog exceeds `memory_limit + 5`, and persists via `memory_manager.update_memory_core(...)`.

## MCP servers

- Configure the **GitHub MCP server** for PR/issue and repository operations:

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server:v0.27.0"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

- Ensure `GITHUB_TOKEN` (or a PAT mapped to `GITHUB_PERSONAL_ACCESS_TOKEN`) is available in the environment before starting Copilot sessions that need GitHub MCP tools.
