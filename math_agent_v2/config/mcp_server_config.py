import os
from pathlib import Path

# Get the root directory of the project
ROOT_DIR = Path(__file__).parent.parent

# MCP Server configurations
MCP_SERVER_CONFIG = {
    "math_server": {
        "command": "python",
        "script_path": str(ROOT_DIR / "mcp_server" / "math_mcp_server" / "math_mcp_server.py")
    },
    "gmail_server": {
        "command": "python",
        "script_path": str(ROOT_DIR /  "mcp_server" / "gmail_mcp_server" / "src" / "gmail" / "gmail_mcp_server.py"),
        "creds_file_path": str(ROOT_DIR / ".google" / "client_creds.json"),
        "token_path": str(ROOT_DIR / ".google" / "app_tokens.json")
    }
}