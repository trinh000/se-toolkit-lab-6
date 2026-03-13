import os, sys, json, httpx
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
            return (c[:15000] + "\n[Truncated]") if len(c) > 15000 else c
    except Exception as e: return str(e)

def query_api(method, path, body=None):
    base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    key = os.getenv("LMS_API_KEY")
    if not key: return "Error: LMS_API_KEY not set"
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    u = f"{base.rstrip('/')}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=10.0) as cl:
            if method.upper() == "GET": r = cl.get(u, headers=h)
            else: r = cl.post(u, headers=h, content=body)
            return json.dumps({"status_code": r.status_code, "body": r.text})
    except Exception as e: return str(e)

tools = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in a directory to explore the project structure.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path, e.g., 'wiki' or 'backend/app'."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file content to find information in documentation or code.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path, e.g., 'wiki/git.md' or 'backend/app/main.py'."}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "query_api", "description": "Query the backend API for real-time system data or analytics.", "parameters": {"type": "object", "properties": {"method": {"type": "string", "enum": ["GET", "POST"]}, "path": {"type": "string", "description": "API endpoint, e.g., '/items/' or '/analytics/completion-rate'."}, "body": {"type": "string", "description": "Optional JSON body."}}, "required": ["method", "path"]}}}
]

SYSTEM_PROMPT = """You are a System Agent. Your goal is to answer questions about the project using documentation, source code, and the live API.

RESOURCES:
- Documentation: 'wiki/' directory. (e.g., 'wiki/docker.md' for Docker questions)
- Source Code: 'backend/app/' directory (main entry point is 'backend/app/main.py').
- API: 'query_api' tool.

STRATEGY:
1. EXPLORE: Use 'list_files' to discover files.
2. VERIFY: Use 'read_file' to read content. Check imports in 'backend/app/main.py' for framework info.
3. DATA: Use 'query_api' for data-dependent questions.
4. DIAGNOSE: If an API error occurs, read it, then check the corresponding backend file.

OUTPUT FORMAT:
Your final response MUST be a JSON object.
Format: {"answer": "Your detailed response", "source": "wiki/filename.md#anchor"}
If no specific wiki/code section applies, use "source": "unknown"."""

def main():
    load_dotenv(".env.agent.secret")
    load_dotenv(".env.docker.secret")
    cl = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_API_BASE"))
    m = os.getenv("LLM_MODEL", "qwen3-coder-plus")
    q = sys.argv[1] if len(sys.argv) > 1 else "Hi"
    
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": q}]
    hist = []
    
    for i in range(15):
        try:
            resp = cl.chat.completions.create(model=m, messages=msgs, tools=tools)
            msg = resp.choices[0].message
            
            if not msg.tool_calls:
                txt = msg.content or ""
                start, end = txt.find('{'), txt.rfind('}')
                if start != -1 and end != -1:
                    try:
                        data = json.loads(txt[start:end+1])
                        ans, src = data.get("answer", txt), data.get("source", "unknown")
                        if isinstance(ans, list): ans = ", ".join(map(str, ans))
                        print(json.dumps({"answer": str(ans), "source": str(src), "tool_calls": hist}))
                        return
                    except: pass
                print(json.dumps({"answer": txt, "source": "unknown", "tool_calls": hist}))
                return
            
            msgs.append(msg)
            for tc in msg.tool_calls:
                fn, arg_str = tc.function.name, tc.function.arguments
                try: args = json.loads(arg_str)
                except: args = {}
                
                if fn == "list_files": res = list_files(args.get("path", "."))
                elif fn == "read_file": res = read_file(args.get("path", ""))
                elif fn == "query_api": res = query_api(args.get("method", "GET"), args.get("path", "/"), args.get("body"))
                else: res = f"Error: Tool {fn} not found"
                
                hist.append({"tool": fn, "args": args, "result": str(res)})
                msgs.append({"tool_call_id": tc.id, "role": "tool", "name": fn, "content": str(res)})
        except Exception as e:
            print(json.dumps({"answer": f"Agent loop error: {e}", "tool_calls": hist}))
            return

if __name__ == "__main__": main()
