#!/usr/bin/env python3
"""Run MTEB benchmarks against a vLLM CPU or RHAIIS endpoint.

This script evaluates embedding models using the MTEB framework,
targeting vLLM CPU backends or Red Hat AI Inference Server instances
via MTEB's upstream OpenAI-compatible API wrapper.
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import mteb
from mteb.models import OpenAIAPIEncodeWrapper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Default task configurations
TASK_PRESETS = {
    "quick": [
        "Banking77Classification",  # Classification task
        "EmotionClassification",  # Multi-class classification
    ],
    "retrieval": [
        "ArguAna",  # Argument retrieval
        "NFCorpus",  # Medical information retrieval
        "SCIDOCS",  # Scientific document retrieval
    ],
    "classification": [
        "Banking77Classification",
        "EmotionClassification",
        "ToxicConversationsClassification",
    ],
    "sts": [  # Semantic Textual Similarity
        "STS12",
        "STS15",
        "STS16",
    ],
    # Note: Clustering tasks disabled due to segmentation faults
    # "clustering": [
    #     "ArxivClusteringP2P",
    #     "TwentyNewsgroupsClustering",
    # ],
    "reranking": [
        "AskUbuntuDupQuestions",
        "MindSmallReranking",
        "StackOverflowDupQuestions",
    ],
    "pair_classification": [
        "SprintDuplicateQuestions",
        "TwitterSemEval2015",
    ],
    "comprehensive": [
        # Mix of different task types for comprehensive evaluation
        # Note: Clustering tasks (ArxivClusteringP2P) removed due to segfaults
        "Banking77Classification",  # Classification
        "ArguAna",                  # Retrieval
        "STS12",                    # STS
        "EmotionClassification",    # Classification
        "NFCorpus",                 # Retrieval
    ],
    "full": [
        # Maximum coverage across task categories (takes longer)
        # Classification
        "Banking77Classification",
        "EmotionClassification",
        "ToxicConversationsClassification",
        # Retrieval
        "ArguAna",
        "NFCorpus",
        "SCIDOCS",
        # STS
        "STS12",
        "STS15",
        "STS16",
        # Reranking
        "AskUbuntuDupQuestions",
        "MindSmallReranking",
        # Pair Classification
        "SprintDuplicateQuestions",
        "TwitterSemEval2015",
    ],
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run MTEB benchmarks on vLLM CPU/RHAIIS endpoints"
    )

    parser.add_argument(
        "--endpoint-url",
        type=str,
        required=True,
        help="vLLM server endpoint URL (e.g., http://localhost:8000)",
    )

    parser.add_argument(
        "--model-name",
        type=str,
        required=True,
        help="Model name as reported by vLLM server",
    )

    parser.add_argument(
        "--tasks",
        type=str,
        nargs="+",
        help="Specific MTEB tasks to run (overrides --task-preset)",
    )

    parser.add_argument(
        "--task-preset",
        type=str,
        choices=list(TASK_PRESETS.keys()),
        default="quick",
        help="Preset group of tasks to run (default: quick)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/results"),
        help="Output directory for results (default: /results)",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for authentication (if required)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for encoding (default: 32)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds (default: 300)",
    )

    parser.add_argument(
        "--languages",
        type=str,
        nargs="+",
        default=["eng"],
        help="Languages to filter tasks by (ISO 639-3 codes, default: eng for English)",
    )

    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection to vLLM server and exit",
    )

    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        default=True,
        help="Verify SSL certificates (default: True)",
    )

    parser.add_argument(
        "--no-verify-ssl",
        dest="verify_ssl",
        action="store_false",
        help="Disable SSL certificate verification",
    )

    parser.add_argument(
        "--max-length",
        type=int,
        default=None,
        help="Maximum sequence length for truncation (default: use model's max)",
    )

    parser.add_argument(
        "--use-chat-template",
        action="store_true",
        default=False,
        help=(
            "Send text batches via the Chat Embeddings API (messages field). "
            "Required for multimodal/VLM models; leave disabled for standard "
            "text embedding models served by vLLM."
        ),
    )

    parser.add_argument(
        "--platform",
        type=str,
        default="unknown",
        help="CPU platform identifier recorded in run_summary.json (e.g. Intel_R__Xeon_R__Gold_6238)",
    )

    return parser.parse_args()


def create_encoder(args) -> OpenAIAPIEncodeWrapper:
    """Create the upstream MTEB OpenAI-compatible encoder wrapper."""
    return OpenAIAPIEncodeWrapper(
        endpoint_url=args.endpoint_url,
        model_name=args.model_name,
        api_key=args.api_key,
        timeout=args.timeout,
        verify_ssl=args.verify_ssl,
        max_length=args.max_length,
        modalities=["text"],
        use_chat_template=args.use_chat_template,
    )


def reorganize_mteb_results(output_path: Path) -> int:
    """Flatten nested MTEB result files into TaskName/test.json structure."""
    metadata_files = {"model_meta.json", "run_settings.jsonl"}
    moved = 0

    for json_file in list(output_path.rglob("*.json")):
        relative = json_file.relative_to(output_path)
        if len(relative.parts) <= 1:
            continue
        if json_file.name in metadata_files:
            continue
        if json_file.stem in {"model_meta", "run_summary"}:
            continue

        task_name = json_file.stem
        dest = output_path / task_name / "test.json"
        if dest.exists():
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        if "test" not in data and "scores" in data:
            test_scores = data["scores"].get("test", [])
            if isinstance(test_scores, list) and test_scores:
                data = {"test": test_scores[0]}
            elif isinstance(test_scores, dict):
                data = {"test": test_scores}

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        moved += 1

    for item in list(output_path.iterdir()):
        if item.is_dir() and not (item / "test.json").exists():
            shutil.rmtree(item, ignore_errors=True)

    return moved


def test_connection(
    endpoint_url: str,
    model_name: str,
    verify_ssl: bool = True,
    api_key: str | None = None,
    *,
    use_chat_template: bool = False,
) -> bool:
    """Test connection to vLLM server."""
    try:
        logger.info(f"Testing connection to {endpoint_url}...")

        wrapper = OpenAIAPIEncodeWrapper(
            endpoint_url=endpoint_url,
            model_name=model_name,
            api_key=api_key,
            verify_ssl=verify_ssl,
            modalities=["text"],
            use_chat_template=use_chat_template,
        )

        test_texts = ["Hello, world!"]
        logger.info("Sending test embedding request...")

        from torch.utils.data import DataLoader

        class SimpleDataset:
            def __init__(self, texts):
                self.texts = texts

            def __iter__(self):
                for text in self.texts:
                    yield {"text": [text]}

        dataset = SimpleDataset(test_texts)
        dataloader = DataLoader(dataset, batch_size=1)

        class MockMetadata:
            name = "test"
            type = "test"

        embeddings = wrapper.encode(
            dataloader,
            task_metadata=MockMetadata(),
            hf_split="test",
            hf_subset="test",
            batch_size=1,
            show_progress_bar=False,
        )

        logger.info(f"✓ Connection successful! Embedding shape: {embeddings.shape}")
        return True

    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        return False


def run_benchmark(args):
    """Run MTEB benchmark with specified configuration."""
    if args.tasks:
        task_names = args.tasks
        logger.info(f"Running custom task list: {task_names}")
    else:
        task_names = TASK_PRESETS[args.task_preset]
        logger.info(f"Running task preset '{args.task_preset}': {task_names}")

    logger.info(f"Initializing OpenAI API wrapper for endpoint: {args.endpoint_url}")
    logger.info(f"Model: {args.model_name}")

    model = create_encoder(args)

    logger.info("Loading MTEB tasks...")
    tasks = mteb.get_tasks(
        tasks=task_names,
        languages=args.languages,
    )

    logger.info(f"Loaded {len(tasks)} tasks: {[task.metadata.name for task in tasks]}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    model_safe_name = args.model_name.replace("/", "__")
    output_path = args.output_dir / model_safe_name / timestamp
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Results will be saved to: {output_path}")

    logger.info("Starting MTEB evaluation...")
    logger.info("=" * 80)

    try:
        evaluation = mteb.MTEB(tasks=tasks)
        evaluation.run(
            model,
            output_folder=str(output_path),
            eval_splits=["test"],
            verbosity=2,
            encode_kwargs={"batch_size": args.batch_size},
        )

        reorganized = reorganize_mteb_results(output_path)
        if reorganized:
            logger.info(f"Reorganized {reorganized} task result files")

        logger.info("=" * 80)
        logger.info("✓ Evaluation complete!")

        summary = {
            "model": args.model_name,
            "endpoint_url": args.endpoint_url,
            "timestamp": timestamp,
            "task_preset": args.task_preset if not args.tasks else "custom",
            "tasks_run": task_names,
            "num_tasks": len(tasks),
            "languages": args.languages,
            "mteb_version": mteb.__version__,
            "wrapper": "OpenAIAPIEncodeWrapper",
            "results_path": str(output_path),
            "platform": args.platform,
        }

        summary_file = output_path / "run_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Summary saved to: {summary_file}")
        logger.info("\nResults Summary:")
        logger.info(f"  Tasks completed: {len(tasks)}")
        logger.info(f"  Output directory: {output_path}")

        return 0

    except Exception as e:
        logger.error(f"✗ Evaluation failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point."""
    args = parse_args()

    if args.test_connection:
        success = test_connection(
            args.endpoint_url,
            args.model_name,
            args.verify_ssl,
            args.api_key,
            use_chat_template=args.use_chat_template,
        )
        return 0 if success else 1

    return run_benchmark(args)


if __name__ == "__main__":
    sys.exit(main())
