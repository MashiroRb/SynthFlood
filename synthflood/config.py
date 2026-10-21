"""Central configuration for SynthFlood experiments."""
import os
from dataclasses import dataclass, field

LAB_ROOT = os.environ.get("SYNTHFLOOD_ROOT", os.path.expanduser("~/synthflood"))
DATA_DIR = os.environ.get("SYNTHFLOOD_DATA_DIR", os.path.join(LAB_ROOT, "data"))
MODEL_DIR = os.path.join(LAB_ROOT, "models")
LOG_DIR = os.path.join(LAB_ROOT, "logs")
RESULT_DIR = os.path.join(LAB_ROOT, "results")
FIG_DIR = os.path.join(RESULT_DIR, "figs")
GEN_DIR = os.path.join(DATA_DIR, "contamination")

EPS_GRID = [0.0, 0.10, 0.25, 0.50, 0.75]
PILOT_EPS_GRID = [0.0, 0.25, 0.75]

MAIN_MODEL = "Qwen/Qwen2.5-7B-Instruct"
SECOND_MODEL = "NousResearch/Meta-Llama-3.1-8B-Instruct"
SMALL_MODELS = ["Qwen/Qwen2.5-3B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct"]
JUDGE_MODEL = "Qwen/Qwen2.5-7B-Instruct"

N_CANDIDATES = 10
AGENT_TEMP = 0.0
AGENT_MAX_STEPS = 10
GEN_TEMP = 0.9
GEN_SEED = 2027

VLLM_PORT_MODEL0 = 8000
VLLM_PORT_MODEL1 = 8001


def vllm_url(port: int) -> str:
    return os.environ.get("SYNTHFLOOD_API_BASE", f"http://127.0.0.1:{port}/v1")


@dataclass
class RunSpec:
    """One agent run: task + contamination setting."""
    task_id: str
    eps: float
    contamination_family: str  # 'none' | 'geo' | 'reviews' | 'clone' | 'mix'
    contamination_seed: int
    defense: str = "none"      # 'none' | 'prompt' | 'detector_text' | 'detector_struct' | 'random' | 'provenance' | 'oracle'
    model: str = MAIN_MODEL
    port: int = VLLM_PORT_MODEL0

    def tag(self) -> str:
        return (
            f"{self.model.split('/')[-1]}__eps{self.eps:.2f}__{self.contamination_family}"
            f"__s{self.contamination_seed}__{self.defense}"
        )
