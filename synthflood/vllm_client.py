"""Minimal OpenAI-compatible client for a local vLLM server, with retries,
token accounting and (near-)deterministic decoding."""
import json
import time
import urllib.request
import urllib.error

from .config import vllm_url


class LLMClient:
    def __init__(self, port: int, model: str, timeout: int = 600):
        self.url = vllm_url(port).rstrip("/") + "/chat/completions"
        self.model = model
        self.timeout = timeout
        self.tokens_in = 0
        self.tokens_out = 0
        self.calls = 0

    def chat(self, messages, temperature=0.0, max_tokens=512, seed=0,
             stop=None, retries=5):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "seed": seed,
        }
        if stop:
            payload["stop"] = stop
        body = json.dumps(payload).encode()
        last_err = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    self.url, data=body,
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    out = json.loads(resp.read().decode())
                self.calls += 1
                u = out.get("usage", {})
                self.tokens_in += u.get("prompt_tokens", 0)
                self.tokens_out += u.get("completion_tokens", 0)
                return out["choices"][0]["message"]["content"], out
            except (urllib.error.URLError, urllib.error.HTTPError,
                    TimeoutError, KeyError) as e:
                last_err = e
                time.sleep(min(2 ** attempt * 2, 30))
        raise RuntimeError(f"LLM call failed after {retries} retries: {last_err}")

    def usage(self):
        return {"calls": self.calls, "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out}

    def perplexity(self, text: str, max_chars: int = 3000):
        """Mean token NLL of `text` under the served model, via the
        completions endpoint with echo=True and logprobs."""
        url = self.url.replace("/chat/completions", "/completions")
        payload = {
            "model": self.model,
            "prompt": text[:max_chars],
            "max_tokens": 1,
            "temperature": 0.0,
            "echo": True,
            "logprobs": 0,
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            out = json.loads(resp.read().decode())
        ch = out["choices"][0]
        lps = ch.get("logprobs") or {}
        toks = lps.get("token_logprobs") or []
        # drop the first token (no logprob) and any None entries
        vals = [x for x in toks[1:] if x is not None]
        n = max(1, len(vals))
        ppl = float(np_exp(-sum(vals) / n))
        return ppl, len(vals)


def np_exp(x):
    import math
    return math.exp(x)