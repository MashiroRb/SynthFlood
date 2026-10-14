"""M1 memory module: the agent's self-written experience notebook.

Two entry types, both timestamped by episode index:
- observation: code-written, objective fields only (task, choice, reward).
- lesson: model-induced takeaway (AWM-style), written every 5 episodes.
- correction (M3 only): code-written factual error feedback.

Injection rule is pre-registered: at episode start, the LAST 3 entries
(any type, by recency) are rendered into the system prompt. No semantic
retrieval, no scoring -- recency only.
"""
import json
import os
import re

PRICE_PATTERNS = [
    "price", "cheap", "cheaper", "cost", "$", "discount", "budget",
    "expensive", "affordable", "deal", "bargain", "money", "spend",
    "lower price", "pay", "worth", "value for money",
]


class MemoryStore:
    def __init__(self, path, arm):
        self.path = path
        self.arm = arm
        self.entries = []
        if os.path.exists(path):
            with open(path) as f:
                d = json.load(f)
            self.entries = d.get("entries", [])
        self.n_deleted = 0

    # ---------- writers ----------
    def add_observation(self, t, task_desc, chosen_kind, reward, gold_reward,
                       price_mentioned):
        kind = {"synthetic:clone": "a heavily discounted lookalike listing",
                "synthetic:geo": "a listing with glowing descriptions",
                "synthetic:reviews": "a listing with many positive reviews",
                "synthetic:mix": "a synthetic-looking listing",
                }.get(chosen_kind, "a regular listing")
        text = (f"Episode {t}: task '{task_desc}'. Bought {kind}; "
                f"official reward {reward:.2f}"
                + (f" (gold reference {gold_reward:.2f})." if gold_reward is not None
                   else "."))
        self.entries.append({"type": "observation", "t": t, "arm": self.arm,
                             "text": text,
                             "data": {"chosen_kind": chosen_kind,
                                      "reward": reward,
                                      "gold_reward": gold_reward}})

    def add_correction(self, t, task_desc, reward, gold_reward):
        text = (f"Episode {t} correction: on task '{task_desc}' the purchase "
                f"scored {reward:.2f} but a better-matching option existed "
                f"(reward {gold_reward:.2f}). That choice was a mistake; "
                f"matching the user's stated requirements matters more than "
                f"the price tag.")
        self.entries.append({"type": "correction", "t": t, "arm": self.arm,
                             "text": text, "data": {"reward": reward,
                                                    "gold_reward": gold_reward}})

    def add_lesson(self, t, lesson, tags=None):
        self.entries.append({"type": "lesson", "t": t, "arm": self.arm,
                             "text": str(lesson)[:400],
                             "tags": tags or [], "data": {}})

    # ---------- readers ----------
    def inject_context(self, k=3):
        recent = self.entries[-k:]
        if not recent:
            return ""
        lines = [f"- [{e['type']}] {e['text']}" for e in recent]
        return ("Your experience notes from earlier shopping sessions:\n"
                + "\n".join(lines))

    def has_price_content(self, entry):
        low = entry.get("text", "").lower()
        return any(p in low for p in PRICE_PATTERNS)

    def delete_price_entries(self):
        keep, deleted = [], []
        for e in self.entries:
            (deleted if self.has_price_content(e) else keep).append(e)
        self.n_deleted = len(deleted)
        self.entries = keep
        return deleted

    def export(self):
        return {"arm": self.arm, "path": self.path, "entries": self.entries}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.export(), f, ensure_ascii=False, indent=1)


# ---------- lesson induction ----------
LESSON_PROMPT = """You are maintaining an experience notebook for a shopping \
assistant. Below are notes from its recent shopping episodes.

{notes}

Write ONE short lesson (max 40 words) capturing what these episodes teach \
about how to shop successfully in this store. Output ONLY a JSON object: \
{{"lesson": "...", "tags": ["topic1", "topic2"]}}"""


def _extract_json(text):
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            return json.loads(m.group(0).replace("'", '"'))
        except Exception:
            return None


def induce_lesson(client, mem, t, max_retries=3):
    recent = [e for e in mem.entries if e["type"] == "observation"][-5:]
    if not recent:
        return None
    notes = "\n".join(f"- {e['text']}" for e in recent)
    for _ in range(max_retries):
        text, _raw = client.chat(
            [{"role": "user", "content": LESSON_PROMPT.format(notes=notes)}],
            temperature=0.3, max_tokens=160)
        d = _extract_json(text)
        if d and d.get("lesson"):
            mem.add_lesson(t, d["lesson"], d.get("tags"))
            return d["lesson"]
    return None
