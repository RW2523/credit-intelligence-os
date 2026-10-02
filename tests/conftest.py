"""Test set-up: a throwaway database, and the local model switched off unless CIOS_EVAL_LLM=1, so the
deterministic suite is fast and repeatable. The live assistant evaluation runs separately:

    CIOS_EVAL_LLM=1 .venv/bin/python -m pytest tests/test_assistant_eval.py -s
"""
import os, sys, tempfile

_tmp = tempfile.mkdtemp(prefix="kt-test-")
os.environ.setdefault("CIOS_DB", os.path.join(_tmp, "test.db"))
os.environ.setdefault("CIOS_PRERUN_COUNCIL", "0")
if os.environ.get("CIOS_EVAL_LLM") != "1":
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"          # nothing listens here: deterministic paths only
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
