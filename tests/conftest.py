from __future__ import annotations

import copy
import inspect
import json
from types import SimpleNamespace

import anthropic
from anthropic.resources.messages import Messages
import pytest


@pytest.fixture
def prediction():
    return {
        "probabilities": {"home": 0.6, "draw": 0.25, "away": 0.15},
        "scoreline": {"home": 2, "away": 1},
        "reasoning": [{"claim": "Home venue record supports the home case.",
                       "packet_fields": ["home.home_record.played"]}],
        "outside_knowledge_used": False,
    }


@pytest.fixture
def packet():
    return {
        "fixture": {"id": "synthetic", "home": "Home", "away": "Away"},
        "home": {"home_record": {"played": 4, "won": 3, "drawn": 1}},
        "away": {"away_record": {"played": 4, "won": 1, "drawn": 2}},
        "h2h": [],
    }


@pytest.fixture
def provider(monkeypatch, prediction):
    """Stub the external model boundary; run all lab/validation/scoring code."""
    gateway = SimpleNamespace(calls=[], replies=[], error=None)
    create_signature = inspect.signature(Messages.create)

    def create(**request):
        create_signature.bind(None, **request)
        gateway.calls.append(copy.deepcopy(request))
        if gateway.error is not None:
            raise gateway.error
        stop_reason = "end_turn"
        if request.get("tools"):
            results = [
                block for message in request["messages"] if isinstance(message["content"], list)
                for block in message["content"]
                if isinstance(block, dict) and block.get("type") == "tool_result"
            ]
            if not results:
                content = [{"type": "tool_use", "id": "read-1", "name": "read_packet", "input": {}}]
                stop_reason = "tool_use"
            else:
                bound = json.loads(results[-1]["content"])
                side = "home" if "You are Agent 1" in request["system"] else "away"
                content = [{"type": "text", "text": f"{bound['fixture'][side]} wins, citing {side}.shooting."}]
        else:
            reply = gateway.replies.pop(0) if gateway.replies else prediction
            if isinstance(reply, tuple):
                reply, stop_reason = reply
            content = [{"type": "text", "text": reply if isinstance(reply, str) else json.dumps(reply)}]
        return anthropic.types.Message.model_validate({
            "id": f"test-{len(gateway.calls)}", "type": "message", "role": "assistant",
            "model": request["model"], "content": content, "stop_reason": stop_reason,
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: SimpleNamespace(
        messages=SimpleNamespace(create=create)))
    return gateway
