"""Thin Ollama client. Local models only — nothing leaves the machine.

CIOS_MODEL        the main model for every assistant and the Council (default qwen3:30b, which resolves to
                  the installed qwen3:30b-a3b-instruct-2507 tag — a mixture-of-experts model with ~3B
                  active parameters, so it is quick on the DGX Spark)
CIOS_FAST_MODEL   fallback if the main model is not served (default llama3.2:3b)
CIOS_COUNCIL_MODEL optional override for the six Council calls
"""
from __future__ import annotations
import json, os, re, httpx, asyncio

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("CIOS_MODEL", "qwen3:30b")
FAST_MODEL = os.environ.get("CIOS_FAST_MODEL", "llama3.2:3b")
COUNCIL_MODEL = os.environ.get("CIOS_COUNCIL_MODEL", "")
KEEP_ALIVE = os.environ.get("CIOS_KEEP_ALIVE", "4h")       # avoid a cold 18 GB reload mid-demo
NUM_CTX = int(os.environ.get("CIOS_NUM_CTX", "8192"))

_state = {"available": None, "model": MODEL, "models": []}


def _resolve(want: str, tags: list[str]) -> str | None:
    """Pick the served tag for `want`: exact first, then any tag sharing its base name and size."""
    if want in tags:
        return want
    base, _, size = want.partition(":")
    for t in tags:
        tb, _, ts = t.partition(":")
        if tb == base and (not size or ts == size or ts.startswith(size + "-") or ts == "latest"):
            return t
    for t in tags:
        if t.split(":")[0] == base:
            return t
    return None


async def probe() -> dict:
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{OLLAMA}/api/tags")
            tags = [m["name"] for m in r.json().get("models", [])]
        _state["models"] = tags
        # Resolve the configured model to a tag Ollama actually serves; calling the configured string
        # when only a sibling tag is installed makes every request 404 while probe reports available.
        _state["model"] = _resolve(MODEL, tags) or _resolve(FAST_MODEL, tags)
        _state["council_model"] = _resolve(COUNCIL_MODEL, tags) if COUNCIL_MODEL else _state["model"]
        _state["available"] = _state["model"] is not None
        if not _state["available"] and tags:
            _state["model"] = tags[0]
            _state["available"] = True
    except Exception as e:                                     # noqa: BLE001
        _state["available"] = False
        _state["error"] = str(e)
    return _state


def status() -> dict:
    return dict(_state, host=OLLAMA, configured=MODEL)


async def warm():
    """Load the model into memory in the background so the first question is not a cold start."""
    if not _state.get("available"):
        return
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            await c.post(f"{OLLAMA}/api/generate", json={"model": _state["model"], "prompt": "", "keep_alive": KEEP_ALIVE,
                                                       "options": {"num_ctx": NUM_CTX}})   # same context size, or Ollama reloads
    except Exception:                                          # noqa: BLE001
        pass


_THINK = re.compile(r"<think>.*?</think>", re.S)


def clean(text: str) -> str:
    return _THINK.sub("", text or "").strip()


def _opts(temperature, num_predict, top_p=0.9):
    return {"temperature": temperature, "num_predict": num_predict, "top_p": top_p, "num_ctx": NUM_CTX}


async def generate(system: str, prompt: str, *, json_mode=True, temperature=0.2,
                   num_predict=400, model: str | None = None) -> str:
    body = {"model": model or _state["model"], "prompt": prompt, "system": system, "stream": False,
            "keep_alive": KEEP_ALIVE, "options": _opts(temperature, num_predict)}
    if json_mode:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(f"{OLLAMA}/api/generate", json=body)
        r.raise_for_status()
        return clean(r.json().get("response", ""))


async def stream(system: str, prompt: str, *, temperature=0.3, num_predict=500):
    body = {"model": _state["model"], "prompt": prompt, "system": system, "stream": True,
            "keep_alive": KEEP_ALIVE, "options": _opts(temperature, num_predict)}
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


async def chat(messages: list[dict], *, tools: list | None = None, temperature=0.2, num_predict=700):
    """Streaming chat. Yields ("token", text) and ("tool_calls", [...]) events."""
    body = {"model": _state["model"], "messages": messages, "stream": True, "keep_alive": KEEP_ALIVE,
            "options": _opts(temperature, num_predict)}
    if tools:
        body["tools"] = tools
    in_think = False
    async with httpx.AsyncClient(timeout=240) as c:
        async with c.stream("POST", f"{OLLAMA}/api/chat", json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message") or {}
                if msg.get("tool_calls"):
                    yield "tool_calls", msg["tool_calls"]
                text = msg.get("content") or ""
                if "<think>" in text:
                    in_think = True
                if text and not in_think:
                    yield "token", text
                if "</think>" in text:
                    in_think = False
                if chunk.get("done"):
                    return


async def json_call(system: str, prompt: str, fallback: dict, model: str | None = None, **kw) -> dict:
    """Generate JSON with a guaranteed shape. Never raises — the demo must not stall."""
    if _state["available"] is False:
        return dict(fallback, _source="deterministic")
    try:
        raw = await asyncio.wait_for(generate(system, prompt, model=model, **kw), timeout=120)
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
