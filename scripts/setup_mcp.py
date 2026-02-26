#!/usr/bin/env python3
"""Cross-platform setup for Chrome DevTools MCP server.

Generates the correct .mcp.json for the current OS:
- Windows: wraps npx with `cmd /c` (npx is a .cmd shim on Windows)
- macOS/Linux: calls npx directly

Usage:
    python scripts/setup_mcp.py              # default setup
    python scripts/setup_mcp.py --headless   # headless Chrome
    python scripts/setup_mcp.py --slim       # fewer tools, lighter
"""

import json
import platform
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_CONFIG_PATH = PROJECT_ROOT / ".mcp.json"
PACKAGE = "chrome-devtools-mcp@latest"


def build_config(extra_args: list[str] | None = None) -> dict:
    system = platform.system()
    args = extra_args or []

    if system == "Windows":
        # Windows: npx is a .cmd batch script, must invoke via cmd /c
        # See: https://github.com/anthropics/claude-code/issues/9594
        command = "cmd"
        cmd_args = ["/c", "npx", "-y", PACKAGE] + args
    else:
        # macOS / Linux: npx works directly
        command = "npx"
        cmd_args = ["-y", PACKAGE] + args

    return {
        "mcpServers": {
            "chrome-devtools": {
                "command": command,
                "args": cmd_args,
            }
        }
    }


def main() -> None:
    extra_args = [a for a in sys.argv[1:] if a.startswith("--")]
    config = build_config(extra_args)

    # Merge with existing .mcp.json if it exists
    if MCP_CONFIG_PATH.exists():
        existing = json.loads(MCP_CONFIG_PATH.read_text())
        existing.setdefault("mcpServers", {})
        existing["mcpServers"]["chrome-devtools"] = config["mcpServers"]["chrome-devtools"]
        config = existing

    MCP_CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")

    system = platform.system()
    server_cfg = config["mcpServers"]["chrome-devtools"]

    print(f"Platform:  {system}")
    print(f"Command:   {server_cfg['command']} {' '.join(server_cfg['args'])}")
    print(f"Written:   {MCP_CONFIG_PATH}")
    print()
    print("Chrome DevTools MCP server configured.")
    print("Restart Claude Code to pick up the new MCP server.")


if __name__ == "__main__":
    main()
