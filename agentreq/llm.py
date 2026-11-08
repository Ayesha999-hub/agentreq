"""One small client for any OpenAI-compatible chat API (OpenAI, Groq, Gemini, Ollama...).

Settings come from environment variables (see .env.example):
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL      -> the model that rewrites / detects
  JUDGE_BASE_URL, JUDGE_API_KEY, JUDGE_MODEL -> optional, a different model that scores
                                                (any JUDGE_* left unset falls back to LLM_*)
  LLM_REASONING_EFFORT=low                   -> optional, cuts token use on Groq gpt-oss models
  LLM_NO_CACHE=1                             -> do not reuse earlier answers (see below)
  LLM_PROVIDER=mock                          -> offline stub, ONLY for testing the pipeline

Every answer is saved to .llm_cache.jsonl. If a run stops half way (daily token limit, lost
internet), running the same command again reuses all saved answers, so no tokens are spent twice.
"""
import hashlib
import json
import os
import re
import time

import requests


class LLMError(RuntimeError):
    pass


def _env(prefix: str, name: str, default=None):
    return os.getenv(f"{prefix}_{name}") or os.getenv(f"LLM_{name}") or default


def extract_json(text: str):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE)
    decoder = json.JSONDecoder()
    for m in re.finditer(r"[\{\[]", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
            return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("no JSON found in model reply")


_CACHE = {}
_CACHE_LOADED = set()


def _load_cache(path: str):
    if path in _CACHE_LOADED:
        return
    _CACHE_LOADED.add(path)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                rec = json.loads(line)
                _CACHE[rec["k"]] = rec["v"]
            except (json.JSONDecodeError, KeyError):
                continue


class LLMClient:
    def __init__(self, prefix: str = "LLM"):
        self.prefix = prefix
        self.provider = _env(prefix, "PROVIDER", "openai_compat").lower()
        self.calls = 0          # logical calls (what the experiment would cost)
        self.cache_hits = 0     # how many of them were answered from the saved file
        self.temperature = float(_env(prefix, "TEMPERATURE", "0"))
        if self.provider == "mock":
            self.model = "mock"
            return
        self.base_url = (_env(prefix, "BASE_URL") or "").rstrip("/")
        self.api_key = _env(prefix, "API_KEY", "")
        self.model = _env(prefix, "MODEL")
        self.effort = _env(prefix, "REASONING_EFFORT")
        self.use_cache = not os.getenv("LLM_NO_CACHE")
        self.cache_path = os.getenv("LLM_CACHE_FILE", ".llm_cache.jsonl")
        if not self.base_url or not self.model:
            raise LLMError(
                f"Set {prefix}_BASE_URL and {prefix}_MODEL (or LLM_BASE_URL / LLM_MODEL). "
                "See .env.example."
            )
        if self.use_cache:
            _load_cache(self.cache_path)

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    def _key(self, system: str, user: str) -> str:
        raw = json.dumps([self.base_url, self.model, self.temperature, self.effort, system, user])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def chat(self, system: str, user: str, task: str = None, payload: dict = None) -> str:
        """`task` and `payload` are only used by the offline mock; real models ignore them."""
        self.calls += 1
        if self.is_mock:
            from .mock import mock_reply
            return mock_reply(task, payload or {})
        key = self._key(system, user)
        if self.use_cache and key in _CACHE:
            self.cache_hits += 1
            return _CACHE[key]
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.effort:
            body["reasoning_effort"] = self.effort
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last = None
        for attempt in range(6):
            try:
                r = requests.post(f"{self.base_url}/chat/completions", headers=headers,
                                  json=body, timeout=180)
                if r.status_code == 429 and re.search(r"per day|\bTPD\b|\bRPD\b|daily", r.text, re.I):
                    raise LLMError(
                        "Daily limit reached for this model, so waiting a few seconds will not help.\n"
                        f"Server said: {r.text[:500]}\n"
                        "Everything answered so far is saved: run the same command again later "
                        "(or after switching model) and it continues without repeating those calls."
                    )
                if r.status_code in (429, 500, 502, 503, 504):
                    last = f"HTTP {r.status_code}: {r.text[:200]}"
                    time.sleep(min(60, 3 * (attempt + 1) ** 2))
                    continue
                if 400 <= r.status_code < 500:  # a client error will not fix itself, show why now
                    raise LLMError(f"HTTP {r.status_code} from {self.base_url}: {r.text[:600]}")
                r.raise_for_status()
                out = r.json()["choices"][0]["message"]["content"] or ""
                if self.use_cache and out:
                    _CACHE[key] = out
                    with open(self.cache_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"k": key, "v": out}) + "\n")
                return out
            except requests.RequestException as e:
                last = str(e)
                time.sleep(2 * (attempt + 1))
        raise LLMError(f"LLM call failed after retries: {last}")

    def chat_json(self, system: str, user: str, task: str = None, payload: dict = None):
        reply = self.chat(system, user, task, payload)
        try:
            return extract_json(reply)
        except ValueError:
            retry = self.chat(system, user + "\n\nReply with valid JSON only, nothing else.",
                              task, payload)
            return extract_json(retry)