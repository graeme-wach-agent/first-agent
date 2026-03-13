from dotenv import load_dotenv
import json
import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PROJECT_ROOT = Path.cwd()


def get_current_time():
    return datetime.now().isoformat()


def safe_path(relative_path: str) -> Path:
    if not relative_path:
        raise ValueError("Path cannot be empty.")

    path = (PROJECT_ROOT / relative_path).resolve()

    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Access denied: path escapes project directory.") from exc

    return path


def list_files(path: str = "."):
    target = safe_path(path)

    if not target.exists():
        return f"Error: path does not exist: {path}"

    if not target.is_dir():
        return f"Error: path is not a directory: {path}"

    items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not items:
        return "Directory is empty."

    lines = []
    for item in items:
        prefix = "dir " if item.is_dir() else "file"
        rel = item.relative_to(PROJECT_ROOT)
        lines.append(f"{prefix}: {rel}")

    return "\n".join(lines)


def read_file(path: str):
    target = safe_path(path)

    if not target.exists():
        return f"Error: file does not exist: {path}"

    if not target.is_file():
        return f"Error: path is not a file: {path}"

    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "Error: file is not valid UTF-8 text."


def write_file(path: str, content: str):
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    rel = target.relative_to(PROJECT_ROOT)
    return f"Successfully wrote file: {rel}"


ALLOWED_COMMANDS = {
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "wc",
    "find",
    "echo",
    "python",
    "python3",
    "pytest",
    "git",
}

BLOCKED_COMMANDS = {
    "rm",
    "sudo",
    "mv",
    "shutdown",
    "reboot",
    "kill",
    "killall",
    "dd",
    "mkfs",
}


def run_shell_command(command: str):
    if not command.strip():
        return "Error: command cannot be empty."

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return f"Error parsing command: {exc}"

    if not parts:
        return "Error: command cannot be empty."

    base_cmd = parts[0]

    if base_cmd in BLOCKED_COMMANDS:
        return f"Error: command not allowed: {base_cmd}"

    if base_cmd not in ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(ALLOWED_COMMANDS))
        return f"Error: command not allowed: {base_cmd}. Allowed commands: {allowed}"

    try:
        result = subprocess.run(
            parts,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 15 seconds."
    except Exception as exc:
        return f"Error running command: {exc}"

    output = [f"Exit code: {result.returncode}"]

    if result.stdout.strip():
        output.append(f"STDOUT:\n{result.stdout.strip()}")

    if result.stderr.strip():
        output.append(f"STDERR:\n{result.stderr.strip()}")

    return "\n\n".join(output)


TOOLS = [
    {
        "type": "function",
        "name": "get_current_time",
        "description": "Get the current local time on the computer.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_files",
        "description": "List files and directories inside the project directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path inside the project. Defaults to '.'",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a UTF-8 text file from inside the project directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the project directory.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Create or overwrite a UTF-8 text file inside the project directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the project directory.",
                },
                "content": {
                    "type": "string",
                    "description": "The full text content to write to the file.",
                },
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "run_shell_command",
        "description": "Run a safe shell command inside the project directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "A shell command to run.",
                }
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
{
    "type": "function",
    "name": "replace_in_file",
    "description": "Replace exact text in a UTF-8 text file inside the project directory.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path inside the project directory."
            },
            "old_text": {
                "type": "string",
                "description": "Exact text to replace."
            },
            "new_text": {
                "type": "string",
                "description": "Replacement text."
            }
        },
        "required": ["path", "old_text", "new_text"],
	"additionalProperties": False
    }
},
]


def call_tool(name, args):
    if name == "get_current_time":
        return get_current_time()
    if name == "list_files":
        return list_files(args.get("path", "."))
    if name == "read_file":
        return read_file(args["path"])
    if name == "write_file":
        return write_file(args["path"], args["content"])
    if name == "run_shell_command":
        return run_shell_command(args["command"])
    if name == "replace_in_file":
        return replace_in_file(args["path"], args["old_text"], args["new_text"])

    return f"Error: unknown tool '{name}'"


SYSTEM_PROMPT = """
You are a local CLI coding assistant.

You have tools for:
- getting local time
- listing files
- reading files
- writing files
- running safe shell commands

Rules:
- Use tools whenever helpful.
- Never pretend to inspect files or run commands.
- Prefer reading relevant files before editing them.
- Keep work constrained to the current project directory.
- Explain clearly what you changed.
"""


def run_agent():
    print("Agent ready. Type 'exit' to quit.")

    conversation = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        conversation.append({"role": "user", "content": user_input})

        response = client.responses.create(
            model="gpt-5",
            input=conversation,
            tools=TOOLS,
        )

        while True:
            tool_calls = [item for item in response.output if item.type == "function_call"]

            if not tool_calls:
                final_text = response.output_text
                print(f"\nAgent:\n{final_text}")
                conversation.append({"role": "assistant", "content": final_text})
                break

            new_items = []

            for call in tool_calls:
                args = json.loads(call.arguments) if call.arguments else {}
                result = call_tool(call.name, args)

                new_items.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result,
                })

            response = client.responses.create(
                model="gpt-5",
                previous_response_id=response.id,
                input=new_items,
                tools=TOOLS,
            )


if __name__ == "__main__":
    run_agent()