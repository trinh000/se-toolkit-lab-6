import os, sys, json, httpx, time
from openai import OpenAI
from dotenv import load_dotenv

def get_abs_path(path):
    root = os.path.abspath(os.getcwd())
    abs_p = os.path.abspath(os.path.join(root, path))
    if not abs_p.startswith(root):
        raise PermissionError("Path outside root")
    return abs_p

def list_files(path):
    try:
        p = get_abs_path(path)
        if not os.path.exists(p): return f"Error: {path} not found"
        return "\n".join(os.listdir(p)) if os.path.isdir(p) else f"Error: {path} not dir"
    except Exception as e: return str(e)

def read_file(path):
    try:
        p = get_abs_path(path)
        if not os.path.isfile(p): return f"Error: {path} not found"
        with open(p, 'r', encoding='utf-8') as f:
            c = f.read()
            return (c[:15000] + "\n[Content truncated for brevity]") if len(c) > 15000 else c
    except Exception as e: return str(e)

def query_api(method, path, body=None):
    base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    key = os.getenv("LMS_API_KEY")
    if not key: return "Error: LMS_API_KEY not set"
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    u = f"{base.rstrip('/')}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=15.0) as cl:
            if method.upper() == "GET": r = cl.get(u, headers=h)
            else: r = cl.post(u, headers=h, content=body)
            return json.dumps({"status_code": r.status_code, "body": r.text})
    except Exception as e: return f"API Error: {e}"

tools = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in a directory to explore the project structure.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path, e.g., 'wiki' or 'backend/app'."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file content to find information in documentation or code.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path, e.g., 'wiki/docker.md' or 'backend/app/main.py'."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "query_api", "description": "Query the backend API for real-time system data or analytics.", "parameters": {"type": "object", "properties": {"method": {"type": "string", "enum": ["GET", "POST"]}, "path": {"type": "string", "description": "API endpoint, e.g., '/items/' or '/analytics/completion-rate'."}, "body": {"type": "string", "description": "Optional JSON body."}}, "required": ["method", "path"]}}},
    {"type": "function", "function": {"name": "submit_answer", "description": "Submit your final answer once you have verified facts with tools.", "parameters": {"type": "object", "properties": {"answer": {"type": "string", "description": "The concise answer to the user's question."}, "source": {"type": "string", "description": "The source file and section (e.g. 'wiki/docker.md#clean-up-docker'). Use 'unknown' if no file applies."}}, "required": ["answer"]}}}
]

SYSTEM_PROMPT = """You are a System Agent. Answer questions using the project's documentation, code, and live API.

GUIDELINES:
1. NEVER guess facts. Always use 'read_file' on documentation or code to verify.
2. For wiki questions, search 'wiki/' directory. For code questions, search 'backend/app/' directory.
3. For system data (counts, scores), use 'query_api'.
4. To finish, you MUST call 'submit_answer' with your final answer and source.

IMPORTANT: Your final output must be valid JSON matching the schema: {"answer": "...", "source": "...", "tool_calls": [...]}."""

def main():
    load_dotenv(".env.agent.secret")
    load_dotenv(".env.docker.secret")
    client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_API_BASE"))
    model = os.getenv("LLM_MODEL", "qwen3-coder-plus")
    question = sys.argv[1] if len(sys.argv) > 1 else "Hi"
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
    history = []
    final_output = None
    
    for _ in range(15):
        try:
            resp = client.chat.completions.create(model=model, messages=messages, tools=tools, tool_choice="auto")
            msg = resp.choices[0].message
            
            if not msg.tool_calls:
                # Fallback: parse text as answer
                if msg.content:
                    final_output = {"answer": msg.content, "source": "unknown", "tool_calls": history}
                    break
                continue
            
            messages.append(msg)
            for tc in msg.tool_calls:
                fn, arg_str = tc.function.name, tc.function.arguments
                try: args = json.loads(arg_str)
                except: args = {}
                
                if fn == "submit_answer":
                    final_output = {"answer": args.get("answer"), "source": args.get("source", "unknown"), "tool_calls": history}
                    break
                
                if fn == "list_files": res = list_files(args.get("path", "."))
                elif fn == "read_file": res = read_file(args.get("path", ""))
                elif fn == "query_api": res = query_api(args.get("method", "GET"), args.get("path", "/"), args.get("body"))
                else: res = f"Error: Tool {fn} not found"
                
                history.append({"tool": fn, "args": args, "result": str(res)})
                messages.append({"tool_call_id": tc.id, "role": "tool", "name": fn, "content": str(res)})
            
            if final_output: break
        except Exception as e:
            # Handle transient connection issues
            if "Connection reset" in str(e) or "500" in str(e):
                time.sleep(2)
                continue
            final_output = {"answer": f"Loop error: {e}", "source": "unknown", "tool_calls": history}
            break
            
    if not final_output:
        final_output = {"answer": "Max iterations reached.", "source": "unknown", "tool_calls": history}
    
    # Ensure answer is string
    if not isinstance(final_output["answer"], str):
        final_output["answer"] = str(final_output["answer"])
        
    print(json.dumps(final_output))

if __name__ == "__main__": main()
