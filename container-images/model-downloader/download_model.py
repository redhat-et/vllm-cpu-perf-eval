#!/usr/bin/env python3
"""
Download a full Hugging Face model (weights + tokenizer + configs)
to a local directory for offline or vLLM use.

Usage:
    # Command line argument
    python download_model.py meta-llama/Llama-3.1-8B-Instruct
    python download_model.py meta-llama/Llama-3.1-8B-Instruct --local-dir /custom/path

    # Environment variable (useful in containers)
    MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 python download_model.py
    MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 LOCAL_DIR=/models python download_model.py

Container usage:
    # Using command line argument
    podman run --rm -v hf-cache:/root/.cache/huggingface \\
      quay.io/octo-et/vllm-cpu-perf-eval:model-downloader \\
      /usr/local/bin/download_model.py TinyLlama/TinyLlama-1.1B-Chat-v1.0

    # Using environment variable
    podman run --rm \\
      -v /path/to/models:/models \\
      -e MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \\
      -e LOCAL_DIR=/models \\
      quay.io/octo-et/vllm-cpu-perf-eval:model-downloader
"""

import os
import sys
import platform
import argparse
from huggingface_hub import snapshot_download

# Ensure Python version is 3.8+
if tuple(map(int, platform.python_version_tuple())) < (3, 8):
    print("❌ Python 3.8 or higher is required.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Download a Hugging Face model to a local directory",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "repo_id",
        nargs="?",  # Make optional to allow env var
        help="Hugging Face model repository ID (e.g., meta-llama/Llama-3.1-8B-Instruct). Can also use MODEL_NAME env var."
    )
    parser.add_argument(
        "--local-dir",
        help="Local directory to save the model (default: HuggingFace cache). Can also use LOCAL_DIR env var.",
        default=None
    )

    args = parser.parse_args()

    # Get model ID from args or environment
    model_id = args.repo_id or os.getenv("MODEL_NAME")
    if not model_id:
        print("❌ Error: No model specified.")
        print("   Provide model via command line argument or MODEL_NAME environment variable.")
        print("\nExamples:")
        print("  python download_model.py TinyLlama/TinyLlama-1.1B-Chat-v1.0")
        print("  MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 python download_model.py")
        sys.exit(1)

    model_id = model_id.strip()

    # Get local directory from args or environment
    local_dir = args.local_dir or os.getenv("LOCAL_DIR")

    # Optional: read token from environment (if gated/private)
    hf_token = os.getenv("HF_TOKEN", None)

    print(f"📦 Downloading model: {model_id}")
    if local_dir:
        print(f"📂 Target directory: {local_dir}")
        os.makedirs(local_dir, exist_ok=True)
    else:
        print(f"📂 Using HuggingFace cache: {os.getenv('HF_HOME', '~/.cache/huggingface')}")

    try:
        snapshot_download(
            repo_id=model_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False if local_dir else True,
            resume_download=True,
            token=hf_token,
        )

        if local_dir:
            print(f"✅ Download complete! Files saved in: {local_dir}")
        else:
            print(f"✅ Download complete! Model cached and ready to use.")

    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        print("Ensure your HF_TOKEN is valid (if gated model) and the model ID is correct.")
        sys.exit(1)

    print(f"\nYou can now use this model with vLLM:")
    if local_dir:
        print(f"  --model {local_dir}")
    else:
        print(f"  --model {model_id}")

if __name__ == "__main__":
    main()
