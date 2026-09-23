from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from matchdebate.paths import REPO_ROOT

load_dotenv(REPO_ROOT / ".env")

READ_PACKET_TOOL = {
    "name": "read_packet",
    "description": (
        "Return the bound Match Packet for this run. Takes no arguments. "
        "This is the only world you may use."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


def read_prompt(name: str) -> str:
    return files("matchdebate.prompts").joinpath(name).read_text(encoding="utf-8")


def api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing. Set it in .env.")
    return key


def model_name() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")


def run_advocate(role: str, packet: dict) -> str:
    if role not in {"home", "away"}:
        raise ValueError(f"role must be home or away, got {role!r}")

    system = read_prompt("shared.md") + "\n\n" + read_prompt(f"{role}.md")
    packet_json = json.dumps(packet)
    client = anthropic.Anthropic(api_key=api_key())
    model = model_name()

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Write the Advocate Brief for your club. "
                "Call read_packet, then argue only from that packet."
            ),
        }
    ]

    for _ in range(6):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            tools=[READ_PACKET_TOOL],
            messages=messages,
        )
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        text_blocks = [block.text for block in response.content if block.type == "text"]

        if response.stop_reason == "tool_use" and tool_uses:
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in tool_uses:
                if block.name != "read_packet":
                    result = json.dumps({"error": "The only tool is read_packet."})
                else:
                    result = packet_json
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            continue

        brief = "\n\n".join(text.strip() for text in text_blocks if text.strip())
        if brief:
            return brief
        raise RuntimeError(f"Advocate {role} returned no brief text.")

    raise RuntimeError(f"Advocate {role} exceeded tool-use rounds.")


def write_brief(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
