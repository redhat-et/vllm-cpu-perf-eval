#!/usr/bin/env python3
"""Run MTEB benchmarks against a vLLM CPU or RHAIIS endpoint.

This script evaluates embedding models using the MTEB framework,
targeting vLLM CPU backends or Red Hat AI Inference Server instances.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import mteb

# Add custom wrapper to path
sys.path.insert(0, "/opt/mteb")
from vllm_cpu_wrapper import VllmCPUEncoderWrapper

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

    return parser.parse_args()


def test_connection(
    endpoint_url: str, model_name: str, verify_ssl: bool = True
) -> bool:
    """Test connection to vLLM server.

    Args:
        endpoint_url: vLLM server URL
        model_name: Model name to check

    Returns:
        True if connection successful
    """
    try:
        logger.info(f"Testing connection to {endpoint_url}...")

        wrapper = VllmCPUEncoderWrapper(
            endpoint_url=endpoint_url,
            model_name=model_name,
            verify_ssl=verify_ssl,
        )

        # Try a simple embedding request
        test_texts = ["Hello, world!"]
        logger.info("Sending test embedding request...")

        import numpy as np
        from torch.utils.data import DataLoader

        # Create a simple batch for testing
        class SimpleDataset:
            def __init__(self, texts):
                self.texts = texts

            def __iter__(self):
                for text in self.texts:
                    yield {"text": [text]}

        dataset = SimpleDataset(test_texts)
        dataloader = DataLoader(dataset, batch_size=1)

        # Mock task metadata
        class MockMetadata:
            name = "test"
            type = "test"

        embeddings = wrapper.encode(
            dataloader,
            task_metadata=MockMetadata(),
            hf_split="test",
            hf_subset="test",
        )

        logger.info(f"✓ Connection successful! Embedding shape: {embeddings.shape}")
        return True

    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        return False


def run_benchmark(args):
    """Run MTEB benchmark with specified configuration.

    Args:
        args: Parsed command line arguments
    """
    # Determine which tasks to run
    if args.tasks:
        task_names = args.tasks
        logger.info(f"Running custom task list: {task_names}")
    else:
        task_names = TASK_PRESETS[args.task_preset]
        logger.info(f"Running task preset '{args.task_preset}': {task_names}")

    # Initialize the wrapper
    logger.info(f"Initializing vLLM CPU wrapper for endpoint: {args.endpoint_url}")
    logger.info(f"Model: {args.model_name}")

    model = VllmCPUEncoderWrapper(
        endpoint_url=args.endpoint_url,
        model_name=args.model_name,
        api_key=args.api_key,
        timeout=args.timeout,
        batch_size=args.batch_size,
        verify_ssl=args.verify_ssl,
        max_length=args.max_length,
    )

    # Get tasks
    logger.info("Loading MTEB tasks...")
    tasks = mteb.get_tasks(
        tasks=task_names,
        languages=args.languages,
    )

    logger.info(f"Loaded {len(tasks)} tasks: {[task.metadata.name for task in tasks]}")

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    model_safe_name = args.model_name.replace("/", "__")
    output_path = args.output_dir / model_safe_name / timestamp
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Results will be saved to: {output_path}")

    # Run evaluation
    logger.info("Starting MTEB evaluation...")
    logger.info("=" * 80)

    try:
        evaluation = mteb.MTEB(tasks=tasks)
        results = evaluation.run(
            model,
            output_folder=str(output_path),
            eval_splits=["test"],  # Use test split by default
            verbosity=2,
        )

        logger.info("=" * 80)
        logger.info("✓ Evaluation complete!")

        # Save summary metadata
        summary = {
            "model": args.model_name,
            "endpoint_url": args.endpoint_url,
            "timestamp": timestamp,
            "task_preset": args.task_preset if not args.tasks else "custom",
            "tasks_run": task_names,
            "num_tasks": len(tasks),
            "languages": args.languages,
            "results_path": str(output_path),
        }

        summary_file = output_path / "run_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Summary saved to: {summary_file}")

        # Print quick summary
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

    # Test connection if requested
    if args.test_connection:
        success = test_connection(
            args.endpoint_url, args.model_name, args.verify_ssl
        )
        return 0 if success else 1

    # Run benchmark
    return run_benchmark(args)


if __name__ == "__main__":
    sys.exit(main())
