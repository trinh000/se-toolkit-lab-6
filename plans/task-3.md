# Plan: Task 3 - The System Agent

## Objective
Add a `query_api` tool to the agent, enabling it to interact with the deployed backend API. This allows the agent to answer questions about the actual state of the system (e.g., database counts, analytics) in addition to documentation.

## Strategy
- **`query_api(method, path, body)` Tool**:
  - Use `requests` or `httpx` to call the backend.
  - Authentication: Use `Authorization: Bearer <LMS_API_KEY>`.
  - Base URL: Read `AGENT_API_BASE_URL` from environment, default to `http://localhost:42002`.
- **Environment Variables**:
  - The agent must read `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from environment.
  - `LMS_API_KEY` will be read from environment.
- **System Prompt Updates**:
  - Instruct the LLM on when to use `query_api` (for data/analytics questions), `read_file` (for code/facts), and `list_files` (for documentation).
- **Agentic Loop Improvements**:
  - Ensure the loop handles the `query_api` response (status code and body).
  - Handle potential JSON decoding errors in the API response gracefully.

## Components
1. **`agent.py`**:
   - Add `query_api` implementation and tool schema.
   - Update `main()` to read all configuration from environment variables.
   - Improve the system prompt to guide tool selection.
2. **`AGENT.md`**: Update documentation with details on the system agent and benchmark results.
3. **Tests**: Add `tests/test_agent_system.py` with tests for:
   - Backend framework lookup via `read_file`.
   - Item count via `query_api`.

## Benchmark Strategy
1. Run `uv run run_eval.py` once the tools are implemented.
2. Analyze failures and iterate on the system prompt or tool descriptions.
3. Record the final benchmark score in `AGENT.md`.
