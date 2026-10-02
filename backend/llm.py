"""Thin Ollama client. Local models only — nothing leaves the machine.

CIOS_MODEL        the main model for every assistant and the Council (default qwen3:30b, which resolves to the
                  installed qwen3:30b-a3b-instruct-2507 tag). The Ollama on this machine is shared with another
                  application that uses the same model; KT shares that one loaded instance rather than loading a
                  second copy (two do not fit in memory alongside the vision model).
CIOS_NUM_CTX      context size to request. Default: none — use the server's default, so every app sharing the
                  model asks for the same thing. Requesting a different size makes Ollama reload the whole
                  model (20–40 s), and under memory pressure that reload can land on the CPU.
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
NUM_CTX = int(os.environ.get("CIOS_NUM_CTX") or 0)                # 0 = share the server's default

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


async def placement() -> dict:
    """Where Ollama holds the model right now: on the GPU, partly, on the CPU, or not loaded."""
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            ps = (await c.get(f"{OLLAMA}/api/ps")).json().get("models", [])
        m = next((x for x in ps if x["name"] == _state.get("model")), None)
        if not m:
            where = "not loaded"
        else:
            frac = (m.get("size_vram") or 0) / max(1, m.get("size") or 1)
            where = "gpu" if frac > 0.95 else "cpu" if frac < 0.05 else "partial"
    except Exception:                                          # noqa: BLE001
        where = "unknown"
    _state["placement"] = where
    return _state


async def watchdog():
    """Keep the model loaded between questions, and notice if it has fallen back to the CPU (when the Ollama
    container loses GPU access every answer slows ~30x; the fix is restarting that container)."""
    while True:
        try:
            await placement()
            if _state.get("available") and _state["placement"] == "not loaded":
                await warm()
                await placement()
        except Exception:                                      # noqa: BLE001
            pass
        await asyncio.sleep(120)


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
                                                       "options": _ctx()})   # same context as every request, or Ollama reloads
    except Exception:                                          # noqa: BLE001
        pass


_THINK = re.compile(r"<think>.*?</think>", re.S)
# models occasionally emit a Cyrillic letter inside a Latin word ("DSР" for DSR); Malay and English never need
# them. Р/р is mapped by sound (it is the Cyrillic R, which is what the model meant); the rest by shape.
_HOMOGLYPH = str.maketrans("АВЕКМНОРСТХаеорсухі", "ABEKMHORCTXaeorcyxi")


def clean(text: str) -> str:
    return _THINK.sub("", text or "").translate(_HOMOGLYPH).strip()


def _ctx() -> dict:
    return {"num_ctx": NUM_CTX} if NUM_CTX else {}


def _opts(temperature, num_predict, top_p=0.9):
    return {"temperature": temperature, "num_predict": num_predict, "top_p": top_p, **_ctx()}


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
                text = (msg.get("content") or "").translate(_HOMOGLYPH)
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
