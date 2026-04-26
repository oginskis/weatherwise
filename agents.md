# Coding Standards & Conventions

## Python Version & Typing

- Python 3.10+. Use PEP 604 union types: `str | None`, `list[str]`, not `Optional[str]` or `List[str]`.
- Type all function signatures (parameters and return types).
- Use `from __future__ import annotations` only if needed for forward references.

## Naming & Style

- Expressive names that convey intent. Avoid abbreviations unless universally understood (`url`, `http`, `mcp`).
- Small, focused functions — each does one thing. If a function needs a comment explaining what a block does, extract that block into a named function.
- Module-level constants for magic values (ports, URLs, timeouts, defaults). No literals buried in logic.

## Imports

- Standard import order: stdlib, third-party, local. Separated by blank lines.
- No unused imports. No wildcard imports (`from x import *`).
- Prefer explicit imports over module-level imports when only one or two names are used.

## Error Handling

- Never bare `except:` — always catch specific exception types.
- Always log context with exceptions: what was being attempted, relevant parameters.
- Use `raise ... from err` to preserve exception chains.
- Validate HTTP status codes before parsing response bodies.

## HTTP

- Reuse a single `httpx.AsyncClient` instance per service. Do not create a new client per request.
- Configure timeouts explicitly on the client.
- Validate `response.status_code` before calling `response.json()`.
- Use `response.raise_for_status()` where appropriate, wrapped in specific exception handling.

## File Paths

- Use `pathlib.Path` for all file path operations. No string concatenation for paths.

## None Handling

- Filter None values with `is not None`, not truthiness checks (which incorrectly filter `0`, `""`, `False`).

## Architecture (SOLID)

- **Single Responsibility**: Each module and class has one reason to change. MCP server registration is separate from API client logic. UI components are separate from data fetching. The disasters MCP server, for example, splits into `server.py` (FastMCP tool registration), `repository.py` (pandas query layer), `loader.py` (CSV ingestion), `models.py` (Pydantic contracts).
- **Open/Closed**: Use abstractions (protocols, base classes) where extension is expected. New MCP servers should be addable without modifying existing agent code.
- **Liskov Substitution**: Subtypes must be substitutable for their base types without altering correctness.
- **Interface Segregation**: Keep interfaces small and focused. Clients should not depend on methods they do not use.
- **Dependency Inversion**: High-level modules (agent, UI) depend on abstractions (config, typed models), not on concrete implementations (specific API clients).

## LLM Discipline

- **Don't put the LLM in a data-construction loop.** When tool calls already produce the data the UI needs, build structured fields deterministically from the tool returns (e.g. `src/agent/disaster_card.py` reads `result.new_messages()`). Only let the LLM author free-text fields. This eliminates structured-data hallucination by construction.
- **Retry transient model errors** with exponential backoff before surfacing failures to the user. Defaults live in `src/agent/config.py`: `AGENT_MAX_RETRIES`, `AGENT_RETRY_BASE_DELAY_SECONDS`, `AGENT_RETRYABLE_STATUS_CODES`.
- **System-prompt changes need a top-to-bottom re-read.** Section-level diffs can each look correct in isolation and still produce a Frankensteined prompt when concatenated. Re-read the full prompt for tone, ordering, terminology, and contradictions after every edit.

## Test Layout

- **Two buckets:** `tests/unit/` (offline, no LLM, no live MCP — runs on every commit) and `tests/eval/` (live agent + MCP servers, opt-in via the `eval` pytest marker).
- **Default `pytest tests/` skips evals** via `addopts = "-m 'not eval'"` in `pyproject.toml`. Eval runs require the launcher to be running locally.
- Each bucket has its own `conftest.py` next to its tests — keeps fixture scoping local and avoids importing heavy eval scaffolding when running unit tests.
- **Pure functions get unit tests**, even when only consumed by other tests (e.g. `is_subsequence`, `args_subset_match` in `tests/eval/validators.py` are covered by `tests/unit/test_eval_validators.py`).
- **Assertions should be exact, not loose.** Prefer `len(rows) == 3` over `len(rows) > 0`; prefer `values == sorted(values, reverse=True)` over `values[0] >= values[-1]`. Loose bounds turn into tautologies when the underlying data shifts.

## Project Conventions

- Single `pyproject.toml` at project root. Managed with `uv`.
- All configuration in `src/agent/config.py` as module-level constants.
- `src/agent/config.py` calls `load_dotenv(override=True)` so `.env` is authoritative over stale shell exports.
- API keys loaded from `.env` via `python-dotenv`. Never hardcoded.
- Pydantic models define all data contracts between layers.
- The default LLM in `.env.example` is `google-gla:gemini-2.5-pro` (verified reliable on the multi-tool disaster chain). `gemini-3-flash-preview` is unreliable on free tier and should not be the default.
