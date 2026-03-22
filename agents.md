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

- **Single Responsibility**: Each module and class has one reason to change. MCP server registration is separate from API client logic. UI components are separate from data fetching.
- **Open/Closed**: Use abstractions (protocols, base classes) where extension is expected. New MCP servers should be addable without modifying existing agent code.
- **Liskov Substitution**: Subtypes must be substitutable for their base types without altering correctness.
- **Interface Segregation**: Keep interfaces small and focused. Clients should not depend on methods they do not use.
- **Dependency Inversion**: High-level modules (agent, UI) depend on abstractions (config, typed models), not on concrete implementations (specific API clients).

## Project Conventions

- Single `pyproject.toml` at project root. Managed with `uv`.
- All configuration in `src/agent/config.py` as module-level constants.
- API keys loaded from `.env` via `python-dotenv`. Never hardcoded.
- Pydantic models define all data contracts between layers.
