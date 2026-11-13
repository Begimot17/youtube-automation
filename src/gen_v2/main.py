import base64
import json
import logging
import os
import random
import time

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — from environment
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("RUNPOD_API_KEY")
ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")

_HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_FILE = os.path.join(_HERE, "workflow_api.json")
AVATAR_PATH = os.path.join(_HERE, "my_avatar_reference.png")

# Node IDs in the ComfyUI workflow JSON (open the file and find these IDs)
PROMPT_NODE_ID = "6"       # CLIP Text Encode node
IP_ADAPTER_NODE_ID = "15"  # Load Image node for IP-Adapter
SEED_NODE_ID = "3"         # KSampler node

MAX_POLL_SECONDS = 600  # 10 minutes
POLL_INTERVAL = 5
FAILED_STATUSES = ("FAILED", "CANCELLED", "TIMED_OUT")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def load_workflow_template() -> dict:
    if not os.path.exists(WORKFLOW_FILE):
        raise FileNotFoundError(f"Workflow file not found: {WORKFLOW_FILE}")
    with open(WORKFLOW_FILE, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_scene(action_prompt: str, output_filename: str) -> str:
    """
    Submits a ComfyUI workflow to RunPod, polls until COMPLETED,
    saves the output to output_filename, and returns the path.
    Raises RuntimeError / TimeoutError on failure.
    """
    if not API_KEY or not ENDPOINT_ID:
        raise EnvironmentError(
            "RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID must be set in .env"
        )

    logger.info(f"gen_v2: generating scene — '{action_prompt}'")

    workflow = load_workflow_template()

    # Inject text prompt into CLIP Text Encode node
    if PROMPT_NODE_ID not in workflow:
        raise KeyError(f"Prompt node ID '{PROMPT_NODE_ID}' not found in workflow JSON.")
    workflow[PROMPT_NODE_ID]["inputs"]["text"] = (
        f"masterpiece, best quality, (({action_prompt})), character consistent"
    )

    # Randomise seed in KSampler node
    if SEED_NODE_ID in workflow:
        workflow[SEED_NODE_ID]["inputs"]["seed"] = random.randint(1, 1_000_000_000)

    # Set the avatar image filename that the Load Image node expects
    if IP_ADAPTER_NODE_ID in workflow:
        workflow[IP_ADAPTER_NODE_ID]["inputs"]["image"] = "avatar_input.png"

    if not os.path.exists(AVATAR_PATH):
        raise FileNotFoundError(f"Avatar image not found: {AVATAR_PATH}")
    avatar_b64 = encode_image_to_base64(AVATAR_PATH)

    payload = {
        "input": {
            "workflow": workflow,
            "images": [{"name": "avatar_input.png", "image": avatar_b64}],
        }
    }

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    run_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/run"

    response = requests.post(run_url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    if "id" not in data:
        raise RuntimeError(f"RunPod did not return a job ID: {data}")

    job_id = data["id"]
    logger.info(f"gen_v2: job submitted (ID: {job_id}). Polling...")

    status_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{job_id}"
    output = poll_job(job_id, status_url, headers)
    _save_output(output, output_filename)
    logger.info(f"gen_v2: saved → {output_filename}")
    return output_filename


def poll_job(job_id, status_url, headers):
    """
    Polls RunPod until the job finishes and returns its `output` dict.
    Raises RuntimeError on FAILED/CANCELLED/TIMED_OUT and TimeoutError past MAX_POLL_SECONDS.
    """
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > MAX_POLL_SECONDS:
            raise TimeoutError(
                f"RunPod job {job_id} did not complete within {MAX_POLL_SECONDS}s"
            )

        time.sleep(POLL_INTERVAL)
        status_response = requests.get(status_url, headers=headers, timeout=30)
        status_response.raise_for_status()
        status_data = status_response.json()
        status = status_data.get("status")

        if status == "COMPLETED":
            logger.info(f"gen_v2: job {job_id} COMPLETED ({int(elapsed)}s elapsed)")
            return status_data.get("output") or {}

        if status in FAILED_STATUSES:
            error_detail = status_data.get("error", "no detail")
            raise RuntimeError(f"RunPod job {job_id} {status}: {error_detail}")

        if status in ("IN_QUEUE", "IN_PROGRESS"):
            logger.debug(f"gen_v2: [{int(elapsed)}s] status={status}")
        else:
            logger.warning(f"gen_v2: unknown status '{status}' for job {job_id}")


def _save_output(output: dict, output_filename: str) -> None:
    if not isinstance(output, dict):
        raise ValueError(f"Could not parse output from RunPod response: {output!r}")
    saved = False

    # Format 1: {"images": [{"filename": "x.png", "data": "<base64>"}]}
    images_list = output.get("images", [])
    if images_list and isinstance(images_list, list):
        for img_obj in images_list:
            if not isinstance(img_obj, dict):
                continue
            img_data = img_obj.get("data") or img_obj.get("image")
            if img_data:
                with open(output_filename, "wb") as f:
                    f.write(base64.b64decode(img_data))
                saved = True
                break

    # Format 2: {"message": "https://..."} or {"url": "https://..."}
    if not saved:
        url = output.get("message") or output.get("url")
        if url and isinstance(url, str) and url.startswith("http"):
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            with open(output_filename, "wb") as f:
                f.write(resp.content)
            saved = True

    if not saved:
        raise ValueError(f"Could not parse output from RunPod response: {output}")


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------
daily_scenes = [
    "character walking in the rain, cyberpunk city",
    "character drinking coffee in a cafe, sunny morning",
    "character fighting with a lightsaber, space station",
]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for i, prompt in enumerate(daily_scenes):
        generate_scene(prompt, f"scene_{i + 1}.mp4")
