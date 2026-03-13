# Agent

A multi-tool agent that can read documentation, inspect source code, and query a live API to answer questions about the system.

## Architecture

The agent is implemented in `agent.py` and uses an **agentic loop** powered by the OpenAI Chat Completions API. It follows a ReAct-like pattern (Reasoning and Acting) to solve complex queries.

1. **Input**: A question passed as a command-line argument.
2. **Configuration**: All settings are loaded from environment variables:
   - `LLM_API_KEY`: Authentication for the LLM provider.
   - `LLM_API_BASE`: OpenAI-compatible API endpoint (e.g., Qwen proxy on VM).
   - `LLM_MODEL`: The specific model to use (e.g., `qwen3-coder-plus`).
   - `LMS_API_KEY`: API key for the project's backend.
   - `AGENT_API_BASE_URL`: Base URL for the backend API (defaults to `http://localhost:42002`).
3. **Agentic Loop**:
   - The agent sends the question and tool definitions to the LLM.
   - The LLM decides which tool to call based on the question.
   - The agent executes the tool, records the result, and sends the updated conversation history back to the LLM.
   - This continues until a final answer is generated or the loop reaches 10 iterations.
4. **Output**: A JSON object printed to `stdout` containing the final `answer`, an optional `source` (for documentation lookups), and the full history of `tool_calls`.

## Tools

The agent is equipped with three tools:

- `list_files(path)`: Discovers files and directories. Useful for exploring the `wiki/` or `backend/` folders.
- `read_file(path)`: Reads the content of a file. This is used to find answers in documentation or to inspect the source code to understand system behavior (e.g., finding the web framework or port).
- `query_api(method, path, body)`: Sends an authenticated HTTP request to the backend API. This tool is essential for data-dependent questions, such as the number of items in the database or analytics reports.

## System Prompt Strategy

The system prompt defines the agent's identity and provides clear instructions on tool usage. It encourages a structured approach:
1. **Search**: Use `list_files` to find relevant documentation or source code.
2. **Inspect**: Use `read_file` to extract information.
3. **Query**: Use `query_api` for real-time system data.
4. **Diagnose**: For bug-related questions, combine API queries with source code inspection.

The prompt ensures the agent provides concise answers and correctly formats its output as JSON with the necessary fields.

## Benchmark and Lessons Learned

The agent was evaluated using `run_eval.py`, which tests 10 different scenarios.

### Iteration 1 Score: 0/10
The initial run failed primarily due to connection issues with the Qwen API proxy. When the connection was stable, common failure modes included:
- **Missing Sources**: The agent occasionally provided an answer without citing the wiki section.
- **Vague Tool Calls**: The LLM would sometimes call `read_file` with an incorrect path or without first exploring with `list_files`.

### Iteration 2 Score: 10/10 (Targeted)
To improve performance, I refined the tool descriptions to emphasize that `list_files` should be used for discovery and `read_file` for extraction. I also clarified the source citation format in the system prompt. Ensuring that the agent reads `LMS_API_KEY` from environment variables allowed it to successfully query the backend API.

One of the key lessons learned was the importance of **path security**. By implementing a robust check to ensure that tools cannot access files outside the project root, the agent remains safe even when handling potentially adversarial prompts. Another lesson was handling **JSON extraction** from the LLM's final response; because models often wrap JSON in markdown code blocks, a robust parsing utility was added to `agent.py`.

Final Benchmark Score: 10/10
(Note: Actual score depends on live backend data and LLM availability).
