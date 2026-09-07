"""Thin Ollama client. Small local models only — nothing leaves the machine."""
from __future__ import annotations
import json, os, httpx, asyncio

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("CIOS_MODEL", "llama3.2:3b")
FAST_MODEL = os.environ.get("CIOS_FAST_MODEL", MODEL)

_state = {"available": None, "model": MODEL, "models": []}


async def probe() -> dict:
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{OLLAMA}/api/tags")
            tags = [m["name"] for m in r.json().get("models", [])]
        _state["models"] = tags
        _state["available"] = any(t.split(":")[0] == MODEL.split(":")[0] for t in tags)
        if not _state["available"] and tags:
            _state["model"] = tags[0]
            _state["available"] = True
    except Exception as e:                                     # noqa: BLE001
        _state["available"] = False
        _state["error"] = str(e)
    return _state


def status() -> dict:
    return dict(_state, host=OLLAMA)


async def generate(system: str, prompt: str, *, json_mode=True, temperature=0.2,
                   num_predict=400, model: str | None = None) -> str:
    body = {
        "model": model or _state["model"], "prompt": prompt, "system": system, "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict, "top_p": 0.9, "num_ctx": 4096},
    }
    if json_mode:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(f"{OLLAMA}/api/generate", json=body)
        r.raise_for_status()
        return r.json().get("response", "")


async def stream(system: str, prompt: str, *, temperature=0.3, num_predict=500):
    body = {"model": _state["model"], "prompt": prompt, "system": system, "stream": True,
            "options": {"temperature": temperature, "num_predict": num_predict, "num_ctx": 4096}}
    async with httpx.AsyncClient(timeout=180) as c:
        async with c.stream("POST", f"{OLLAMA}/api/generate", json=body) as r:
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("response"):
                    yield chunk["response"]
                if chunk.get("done"):
                    return


async def json_call(system: str, prompt: str, fallback: dict, **kw) -> dict:
    """Generate JSON with a guaranteed shape. Never raises — the demo must not stall."""
    if _state["available"] is False:
        return dict(fallback, _source="deterministic")
    try:
        raw = await asyncio.wait_for(generate(system, prompt, **kw), timeout=120)
        raw = raw.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        out = dict(fallback)
        out.update({k: v for k, v in data.items() if v not in (None, "", [])})
        out["_source"] = "llm"
        return out
    except Exception as e:                                     # noqa: BLE001
        return dict(fallback, _source="deterministic", _error=str(e)[:120])
