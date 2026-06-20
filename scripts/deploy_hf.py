#!/usr/bin/env python3
"""Deploy the MenuMind backend to a Hugging Face Space (Docker SDK).

Prerequisites:
    1. `huggingface-cli login`  (or `hf auth login`) — stores a WRITE token
       locally so this script can authenticate. The token is never printed.
    2. A populated .env (the script reads API secrets from it and pushes them
       to the Space as repository secrets).

Usage:
    python scripts/deploy_hf.py --space menumind-api
    python scripts/deploy_hf.py --space menumind-api --private --no-wait
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from huggingface_hub import HfApi

from config import get_settings

# env-var name on the Space  ->  Settings field to read the value from
SECRET_KEYS = {
    "GOOGLE_API_KEY": "google_api_key",
    "GROQ_API_KEY": "groq_api_key",
    "QDRANT_URL": "qdrant_url",
    "QDRANT_API_KEY": "qdrant_api_key",
    "QDRANT_COLLECTION_NAME": "qdrant_collection_name",
}

# Only the files the backend image needs (keeps the Space repo lean).
ALLOW_PATTERNS = [
    "Dockerfile",
    ".dockerignore",
    "README.md",
    "api/**",
    "rag.py",
    "embedder.py",
    "ingestor.py",
    "chunker.py",
    "config.py",
    "utils.py",
]


def space_host(owner: str, space: str) -> str:
    """The direct API hostname HF assigns to a Space."""
    sub = re.sub(r"[^a-z0-9-]+", "-", f"{owner}-{space}".lower()).strip("-")
    return f"https://{sub}.hf.space"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", default="menumind-api", help="Space name (repo)")
    ap.add_argument("--private", action="store_true", help="Make the Space private")
    ap.add_argument("--no-wait", action="store_true", help="Don't poll for build to finish")
    args = ap.parse_args()

    api = HfApi()
    try:
        me = api.whoami()
    except Exception:
        print("Not logged in. Run `huggingface-cli login` first.")
        sys.exit(1)

    owner = me["name"]
    repo_id = f"{owner}/{args.space}"
    print(f"Deploying to Space: {repo_id}  (user: {owner})")

    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="docker",
        private=args.private,
        exist_ok=True,
    )
    print("  repo ready")

    settings = get_settings()
    for env_key, field in SECRET_KEYS.items():
        value = getattr(settings, field)
        if not value:
            print(f"  WARNING: {env_key} is empty in .env — skipping")
            continue
        api.add_space_secret(repo_id=repo_id, key=env_key, value=value)
        print(f"  secret set: {env_key}")

    root = Path(__file__).resolve().parent.parent
    print("Uploading backend files ...")
    api.upload_folder(
        folder_path=str(root),
        repo_id=repo_id,
        repo_type="space",
        allow_patterns=ALLOW_PATTERNS,
        commit_message="Deploy MenuMind backend",
    )
    print("  upload complete — build triggered")

    host = space_host(owner, args.space)
    print(f"\nSpace page: https://huggingface.co/spaces/{repo_id}")
    print(f"API URL:    {host}")

    if args.no_wait:
        return

    print("\nWaiting for the Space to build & start (up to ~5 min) ...")
    deadline = time.time() + 360
    while time.time() < deadline:
        try:
            stage = api.get_space_runtime(repo_id).stage
        except Exception as exc:
            stage = f"unknown ({exc})"
        print(f"  stage: {stage}")
        if stage == "RUNNING":
            print(f"\n✅ Live: {host}/menus")
            return
        if stage in {"RUNTIME_ERROR", "BUILD_ERROR"}:
            print(f"\n❌ Build failed ({stage}). Check logs at the Space page.")
            sys.exit(1)
        time.sleep(15)
    print("\nStill building — check the Space page for progress.")


if __name__ == "__main__":
    main()
