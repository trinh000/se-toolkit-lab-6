import os, sys, json, httpx, time
from openai import OpenAI
from dotenv import load_dotenv

# Security: Ensure paths are within the project root
def get_abs_path(path):
    root = os.path.abspath(os.getcwd())
    abs_p = os.path.abspath(os.path.join(root, path))
    if not abs_p.startswith(root): raise PermissionError("Path outside root")
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
        if not os.path.isfile(p): return f"Error: File '{path}' not found."
        with open(p, 'r', encoding='utf-8') as f:
            c = f.read()
            # Context-efficient truncation but generous enough for documentation
            return (c[:30000] + "\n[TRUNCATED]") if len(c) > 30000 else c
    except Exception as e: return str(e)

def query_api(method, path, body=None):
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY")
    if not api_key: return "Error: LMS_API_KEY not set."
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=30.0) as cl:
            if method.upper() == "GET": r = cl.get(url, headers=headers)
            elif method.upper() == "POST": r = cl.post(url, headers=headers, content=body)
            else: return f"Error: Unsupported method {method}"
            return json.dumps({"status_code": r.status_code, "body": r.text})
    except Exception as e: return f"API Error: {e}"

tools = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "e.g. 'wiki' or 'backend/app/routers'"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file's content.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "e.g. 'wiki/vm.md' or 'backend/app/main.py'"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "query_api", "description": "Call the backend API.", "parameters": {"type": "object", "properties": {"method": {"type": "string", "enum": ["GET", "POST"]}, "path": {"type": "string", "description": "e.g. '/items/' or '/analytics/groups?lab=lab-01'"}, "body": {"type": "string"}}, "required": ["method", "path"]}}},
    {"type": "function", "function": {"name": "submit_answer", "description": "Submit final answer.", "parameters": {"type": "object", "properties": {"answer": {"type": "string", "description": "The detailed answer with all relevant facts."}, "source": {"type": "string", "description": "e.g. 'wiki/file.md#anchor' or 'backend/app/main.py'"}}, "required": ["answer"]}}}
]

SYSTEM_PROMPT = """You are a System Agent for 'se-toolkit-lab-6'.
Answer questions using documentation (wiki/), code (backend/app/), and API.

API ENDPOINTS:
- /items/ : Get labs and tasks.
- /learners/ : Get all students.
- /analytics/groups?lab=lab-XX : Performance and student counts by group.
- /analytics/completion-rate?lab=lab-XX : % students who passed (score >= 60).
- /analytics/scores?lab=lab-XX : Score distribution.

CRITICAL RULES:
1. ALWAYS read files or query API before answering. NO GUESSING.
2. VM/SSH: Read 'wiki/vm.md'. Mention 'UniversityStudent' Wi-Fi, 'VPN' status, and 'root' user.
3. DOCKER: Read 'wiki/docker.md'. Mention 'docker stop $(docker ps -q)' and 'prune' commands.
4. BACKEND: Read 'backend/app/main.py' for framework (FastAPI).
5. DISTINCT COUNTS: Use /analytics/groups for student groups, or count items from /items/.
6. SOURCE: Cite exactly as 'wiki/filename.md#section' or 'backend/app/filename.py'.
7. FINAL: You MUST call 'submit_answer' with a VERY DETAILED and EXHAUSTIVE answer. Do not truncate your explanation."""

def main():
    load_dotenv(".env.agent.secret"); load_dotenv(".env.docker.secret")
    client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_API_BASE"))
    model, q = os.getenv("LLM_MODEL", "qwen3-coder-plus"), (sys.argv[1] if len(sys.argv) > 1 else "Hi")
    msgs, hist = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": q}], []
    
    for i in range(15):
        try:
            resp = client.chat.completions.create(model=model, messages=msgs, tools=tools, tool_choice="auto")
            m = resp.choices[0].message
            if not m.tool_calls:
                if m.content:
                    print(json.dumps({"answer": m.content, "source": "unknown", "tool_calls": hist}))
                    return
                continue
            msgs.append(m)
            for tc in m.tool_calls:
                fn, arg_str = tc.function.name, tc.function.arguments
                try: args = json.loads(arg_str)
                except: args = {}
                if fn == "submit_answer":
                    print(json.dumps({"answer": str(args.get("answer")), "source": str(args.get("source", "unknown")), "tool_calls": hist}))
                    return
                res = list_files(args.get("path", ".")) if fn=="list_files" else \
                      read_file(args.get("path", "")) if fn=="read_file" else \
                      query_api(args.get("method", "GET"), args.get("path", "/"), args.get("body")) if fn=="query_api" else "Error"
                hist.append({"tool": fn, "args": args, "result": str(res)})
                msgs.append({"tool_call_id": tc.id, "role": "tool", "name": fn, "content": str(res)})
        except Exception as e:
            if "Connection reset" in str(e): time.sleep(2); continue
            print(json.dumps({"answer": f"Error: {e}", "tool_calls": hist})); return
    print(json.dumps({"answer": "Timeout", "tool_calls": hist}))

if __name__ == "__main__": main()
