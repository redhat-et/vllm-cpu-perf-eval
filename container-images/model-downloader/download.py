#!/usr/bin/env python3
"""
Download HuggingFace models and datasets for vLLM benchmarking.

Usage:
    # Models
    python download.py model meta-llama/Llama-3.1-8B-Instruct
    python download.py model meta-llama/Llama-3.1-8B-Instruct --local-dir /models

    # Datasets
    python download.py dataset sonnet
    python download.py dataset --url https://example.com/data.txt --output /datasets/data.txt
    python download.py dataset --hf-dataset cnn_dailymail --hf-config 3.0.0 --hf-split test[:1000]

    # Environment variables
    MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 python download.py model
    DATASET_NAME=sonnet OUTPUT_PATH=/datasets/sonnet.txt python download.py dataset

Container usage:
    # Download model
    podman run --rm -v $(pwd)/models:/models \\
      -e MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \\
      -e LOCAL_DIR=/models \\
      quay.io/vllm-cpu-perf-eval/model-downloader:latest \\
      /usr/local/bin/download.py model

    # Download dataset
    podman run --rm -v $(pwd)/datasets:/datasets \\
      -e DATASET_NAME=sonnet \\
      -e OUTPUT_PATH=/datasets/sonnet.txt \\
      quay.io/vllm-cpu-perf-eval/model-downloader:latest \\
      /usr/local/bin/download.py dataset
"""

import os
import sys
import platform
import argparse
import urllib.request

# Ensure Python version is 3.8+
if tuple(map(int, platform.python_version_tuple())) < (3, 8):
    print("❌ Python 3.8 or higher is required.")
    sys.exit(1)

# Standard dataset URLs
STANDARD_DATASETS = {
    "sonnet": "https://raw.githubusercontent.com/vllm-project/vllm/main/benchmarks/sonnet.txt"
}

#
# Model download
#
def download_model(repo_id: str, local_dir: str = None):
    """Download a HuggingFace model."""
    from huggingface_hub import snapshot_download

    hf_token = os.getenv("HF_TOKEN", None)

    print(f"📦 Downloading model: {repo_id}")
    if local_dir:
        print(f"📂 Target directory: {local_dir}")
        os.makedirs(local_dir, exist_ok=True)
    else:
        print(f"📂 Using HuggingFace cache: {os.getenv('HF_HOME', '~/.cache/huggingface')}")

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False if local_dir else True,
            resume_download=True,
            token=hf_token,
        )

        if local_dir:
            print(f"✅ Download complete! Files saved in: {local_dir}")
        else:
            print(f"✅ Download complete! Model cached and ready to use.")

        print(f"\nYou can now use this model with vLLM:")
        if local_dir:
            print(f"  --model {local_dir}")
        else:
            print(f"  --model {repo_id}")

    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        print("Ensure your HF_TOKEN is valid (if gated model) and the model ID is correct.")
        sys.exit(1)

#
# Dataset download
#
def download_file(url: str, output_path: str):
    """Download a file from URL to local path."""
    print(f"📥 Downloading from: {url}")
    print(f"📂 Output path: {output_path}")

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    try:
        urllib.request.urlretrieve(url, output_path)
        file_size = os.path.getsize(output_path)
        print(f"✅ Download complete! File size: {file_size:,} bytes")
        return output_path
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        sys.exit(1)

def download_hf_dataset(dataset_id: str, split: str, output_path: str):
    """Download a HuggingFace dataset and save to JSON."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("❌ Error: 'datasets' library not installed.")
        print("   Install with: pip install datasets")
        sys.exit(1)

    print(f"📦 Loading HuggingFace dataset: {dataset_id}")
    print(f"📊 Split: {split}")
    print(f"📂 Output path: {output_path}")

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    try:
        hf_token = os.getenv("HF_TOKEN", None)
        dataset = load_dataset(dataset_id, split=split, token=hf_token)
        dataset.to_json(output_path)

        file_size = os.path.getsize(output_path)
        num_rows = len(dataset)
        print(f"✅ Download complete!")
        print(f"   Rows: {num_rows:,}")
        print(f"   File size: {file_size:,} bytes")
        return output_path

    except Exception as e:
        print(f"❌ Error loading HuggingFace dataset: {e}")
        print("   Ensure the dataset ID is correct and HF_TOKEN is set if gated.")
        sys.exit(1)

def download_dataset(name: str = None, url: str = None, hf_dataset: str = None,
                    hf_config: str = None, hf_split: str = "train", output: str = None):
    """Download a dataset (standard, URL, or HuggingFace)."""

    # Determine what to download
    if name:
        # Standard dataset
        if name not in STANDARD_DATASETS:
            print(f"❌ Error: Unknown standard dataset '{name}'")
            print(f"   Available: {', '.join(STANDARD_DATASETS.keys())}")
            sys.exit(1)

        url = STANDARD_DATASETS[name]
        if not output:
            output = f"/datasets/{name}.txt"

        download_file(url, output)

    elif url:
        # Direct URL download
        if not output:
            output = f"/datasets/{url.split('/')[-1]}"

        download_file(url, output)

    elif hf_dataset:
        # HuggingFace dataset
        if not output:
            dataset_slug = hf_dataset.replace("/", "-")
            output = f"/datasets/{dataset_slug}.json"

        # Build full dataset identifier
        dataset_id = hf_dataset
        if hf_config:
            dataset_id = f"{hf_dataset}/{hf_config}"

        download_hf_dataset(dataset_id, hf_split, output)

    else:
        print("❌ Error: No dataset specified.")
        print("   Provide via: standard name, --url, or --hf-dataset")
        print("\nExamples:")
        print("  python download.py dataset sonnet")
        print("  python download.py dataset --url https://example.com/data.txt --output /datasets/data.txt")
        print("  python download.py dataset --hf-dataset cnn_dailymail --hf-config 3.0.0 --hf-split test[:1000]")
        sys.exit(1)

    print(f"\n✅ Dataset ready: {output}")
    print(f"\nYou can now use this dataset with vLLM:")
    print(f"  --dataset-path {output}")

#
# CLI
#
def main():
    parser = argparse.ArgumentParser(
        description="Download HuggingFace models and datasets for vLLM benchmarking",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.required = True

    # Model subcommand
    model_parser = subparsers.add_parser(
        "model",
        help="Download a HuggingFace model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Command line
  python download.py model meta-llama/Llama-3.1-8B-Instruct
  python download.py model meta-llama/Llama-3.1-8B-Instruct --local-dir /models

  # Environment variables
  MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 python download.py model
  MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 LOCAL_DIR=/models python download.py model
        """
    )
    model_parser.add_argument(
        "repo_id",
        nargs="?",
        help="HuggingFace model repository ID. Can also use MODEL_NAME env var."
    )
    model_parser.add_argument(
        "--local-dir",
        help="Local directory to save the model (default: HuggingFace cache). Can also use LOCAL_DIR env var."
    )

    # Dataset subcommand
    dataset_parser = subparsers.add_parser(
        "dataset",
        help="Download a dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Standard Datasets:
  sonnet          vLLM standard sonnet benchmark dataset

Examples:
  # Standard dataset
  python download.py dataset sonnet --output /datasets/sonnet.txt

  # From URL
  python download.py dataset --url https://example.com/data.txt --output /datasets/data.txt

  # HuggingFace dataset
  python download.py dataset --hf-dataset cnn_dailymail --hf-config 3.0.0 --hf-split test[:1000] --output /datasets/cnn-1k.json

  # Environment variables
  DATASET_NAME=sonnet OUTPUT_PATH=/datasets/sonnet.txt python download.py dataset
        """
    )
    dataset_parser.add_argument(
        "name",
        nargs="?",
        help="Standard dataset name (sonnet). Can also use DATASET_NAME env var."
    )
    dataset_parser.add_argument(
        "--url",
        help="Direct URL to download. Can also use DATASET_URL env var."
    )
    dataset_parser.add_argument(
        "--hf-dataset",
        help="HuggingFace dataset ID. Can also use HF_DATASET env var."
    )
    dataset_parser.add_argument(
        "--hf-config",
        help="HuggingFace dataset config name. Can also use HF_DATASET_CONFIG env var."
    )
    dataset_parser.add_argument(
        "--hf-split",
        default="train",
        help="HuggingFace dataset split (default: train). Can also use HF_SPLIT env var."
    )
    dataset_parser.add_argument(
        "--output",
        "-o",
        help="Output file path. Can also use OUTPUT_PATH env var."
    )

    args = parser.parse_args()

    if args.command == "model":
        # Get model parameters from args or environment
        repo_id = args.repo_id or os.getenv("MODEL_NAME")
        local_dir = args.local_dir or os.getenv("LOCAL_DIR")

        if not repo_id:
            print("❌ Error: No model specified.")
            print("   Provide model via command line argument or MODEL_NAME environment variable.")
            print("\nExamples:")
            print("  python download.py model TinyLlama/TinyLlama-1.1B-Chat-v1.0")
            print("  MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 python download.py model")
            sys.exit(1)

        download_model(repo_id.strip(), local_dir)

    elif args.command == "dataset":
        # Get dataset parameters from args or environment
        name = args.name or os.getenv("DATASET_NAME")
        url = args.url or os.getenv("DATASET_URL")
        hf_dataset = args.hf_dataset or os.getenv("HF_DATASET")
        hf_config = args.hf_config or os.getenv("HF_DATASET_CONFIG")
        hf_split = args.hf_split or os.getenv("HF_SPLIT", "train")
        output = args.output or os.getenv("OUTPUT_PATH")

        download_dataset(name, url, hf_dataset, hf_config, hf_split, output)

if __name__ == "__main__":
    # Backwards compatibility: detect if called via symlink and auto-inject subcommand
    import os
    script_name = os.path.basename(sys.argv[0])

    if script_name == "download_model.py" and (len(sys.argv) == 1 or sys.argv[1] not in ["model", "dataset"]):
        # Called as download_model.py - inject "model" subcommand
        sys.argv.insert(1, "model")
    elif script_name == "download_dataset.py" and (len(sys.argv) == 1 or sys.argv[1] not in ["model", "dataset"]):
        # Called as download_dataset.py - inject "dataset" subcommand
        sys.argv.insert(1, "dataset")

    main()
