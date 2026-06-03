"""vLLM CPU Wrapper for MTEB.

This wrapper extends MTEB's vLLM support to work with CPU backends,
specifically targeting vLLM CPU and Red Hat AI Inference Server (RHAIIS).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests

from mteb.models.abs_encoder import AbsEncoder
from mteb.types import PromptType

if TYPE_CHECKING:
    from collections.abc import Callable

    from torch.utils.data import DataLoader

    from mteb.abstasks.task_metadata import TaskMetadata
    from mteb.types import Array, BatchedInput

logger = logging.getLogger(__name__)


class VllmCPUEncoderWrapper(AbsEncoder):
    """vLLM CPU wrapper for MTEB embedding benchmarks.

    This wrapper uses the OpenAI-compatible HTTP API to communicate with
    a vLLM server (CPU backend) or RHAIIS instance.

    Args:
        endpoint_url: URL of the vLLM server (e.g., "http://localhost:8000")
        model_name: Name of the model loaded in vLLM
        api_key: Optional API key for authentication
        revision: The revision of the model to use
        prompt_dict: A dictionary mapping task names to prompt strings
        use_instructions: Whether to use instructions from the prompt_dict
        instruction_template: A template or callable to format instructions
        apply_instruction_to_documents: Whether to apply instructions
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries for failed requests
        batch_size: Batch size for processing embeddings
        verify_ssl: Whether to verify SSL certificates (default: True)
    """

    def __init__(
        self,
        endpoint_url: str,
        model_name: str,
        api_key: str | None = None,
        revision: str | None = None,
        *,
        prompt_dict: dict[str, str] | None = None,
        use_instructions: bool = False,
        instruction_template: (
            str | Callable[[str, PromptType | None], str] | None
        ) = None,
        apply_instruction_to_documents: bool = True,
        timeout: int = 300,
        max_retries: int = 3,
        batch_size: int = 32,
        verify_ssl: bool = True,
    ):
        """Initialize the vLLM CPU wrapper."""
        self.endpoint_url = endpoint_url.rstrip("/")
        self.api_key = api_key
        self.prompts_dict = prompt_dict
        self.use_instructions = use_instructions
        self.instruction_template = instruction_template
        self.apply_instruction_to_passages = apply_instruction_to_documents
        self.timeout = timeout
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.verify_ssl = verify_ssl

        # MTEB looks for these attributes directly for result organization
        self.model_name = model_name
        self.revision = revision if revision else "main"

        # Set MTEB model metadata for proper result organization
        # MTEB will construct mteb_model_meta from model_name and revision if not set
        self.mteb_model_meta = None

        if use_instructions and instruction_template is None:
            raise ValueError(
                "To use instructions, an instruction_template must be provided. "
                "For example, `Instruction: {instruction}`"
            )

        if (
            isinstance(instruction_template, str)
            and "{instruction}" not in instruction_template
        ):
            raise ValueError(
                "Instruction template must contain the string '{instruction}'."
            )

        # Verify server is reachable
        self._verify_server()

    def _verify_server(self) -> None:
        """Verify that the vLLM server is reachable."""
        try:
            response = requests.get(
                f"{self.endpoint_url}/v1/models",
                timeout=10,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            models = response.json()

            # Check if our model is available
            available_models = [m["id"] for m in models.get("data", [])]
            if self.model_name not in available_models:
                logger.warning(
                    f"Model '{self.model_name}' not found in server. "
                    f"Available models: {available_models}"
                )
                # Still allow initialization - model name might be alias
            else:
                logger.info(
                    f"Successfully connected to vLLM server. "
                    f"Model: {self.model_name}"
                )

        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to vLLM server at "
                f"{self.endpoint_url}: {e}"
            ) from e

    def _get_embeddings(self, texts: list[str]) -> Array:
        """Get embeddings from the vLLM server via HTTP API.

        Args:
            texts: List of texts to embed

        Returns:
            Array of embeddings
        """
        import numpy as np

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "input": texts,
            "encoding_format": "float",
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.endpoint_url}/v1/embeddings",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                response.raise_for_status()

                result = response.json()

                # Extract embeddings in correct order
                embeddings = [None] * len(texts)
                for item in result["data"]:
                    embeddings[item["index"]] = item["embedding"]

                # Convert to numpy array
                return np.array(embeddings, dtype=np.float32)

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Request timeout "
                        f"(attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying..."
                    )
                    continue
                raise
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Request failed "
                        f"(attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying..."
                    )
                    continue
                raise RuntimeError(
                    f"Failed to get embeddings from vLLM server: {e}"
                ) from e

    def encode(
        self,
        inputs: DataLoader[BatchedInput],
        *,
        task_metadata: TaskMetadata,
        hf_split: str,
        hf_subset: str,
        prompt_type: PromptType | None = None,
        **kwargs: Any,
    ) -> Array:
        """Encode the given sentences using the vLLM server.

        Args:
            inputs: The sentences to encode
            task_metadata: The metadata of the task
            prompt_type: The type of prompt (query or passage)
            hf_split: Split of current task
            hf_subset: Subset of current task
            **kwargs: Additional arguments

        Returns:
            The encoded sentences as embeddings
        """
        import numpy as np

        # Determine prompt to use
        prompt = ""
        if self.use_instructions and self.prompts_dict is not None:
            prompt = self.get_task_instruction(task_metadata, prompt_type)
        elif self.prompts_dict is not None:
            prompt_name = self.get_prompt_name(task_metadata, prompt_type)
            if prompt_name is not None:
                prompt = self.prompts_dict.get(prompt_name, "")

        # Skip instruction for documents if configured
        if (
            self.use_instructions
            and self.apply_instruction_to_passages is False
            and prompt_type == PromptType.document
        ):
            logger.info(
                f"No instruction used, because prompt type = {prompt_type.document}"
            )
            prompt = ""
        else:
            if prompt:
                logger.info(
                    f"Using instruction: '{prompt}' for task: '{task_metadata.name}' "
                    f"prompt type: '{prompt_type}'"
                )

        # Collect all texts from batches
        texts = [prompt + text for batch in inputs for text in batch["text"]]

        # Process in batches to avoid overwhelming the server
        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            logger.debug(
                f"Processing batch {i // self.batch_size + 1} "
                f"({len(batch_texts)} texts)"
            )
            batch_embeddings = self._get_embeddings(batch_texts)
            all_embeddings.append(batch_embeddings)

        # Concatenate all batches
        embeddings = np.vstack(all_embeddings)
        return embeddings


class VllmCPULocalWrapper(AbsEncoder):
    """vLLM CPU wrapper using local vLLM instance (no HTTP server).

    This wrapper runs vLLM directly in the same process, suitable for
    development/testing or when you want to avoid the HTTP overhead.

    Note: This requires vLLM to be installed with CPU support.

    Args:
        model: Model name or path
        revision: Model revision
        trust_remote_code: Whether to trust remote code
        dtype: Data type for weights (bfloat16, float16, float32)
        max_model_len: Maximum sequence length
        prompt_dict: Task-specific prompts
        use_instructions: Whether to use instruction templates
        instruction_template: Template for formatting instructions
        apply_instruction_to_documents: Apply instructions to documents
    """

    mteb_model_meta = None

    def __init__(
        self,
        model: str,
        revision: str | None = None,
        *,
        trust_remote_code: bool = True,
        dtype: str = "bfloat16",
        max_model_len: int | None = None,
        prompt_dict: dict[str, str] | None = None,
        use_instructions: bool = False,
        instruction_template: (
            str | Callable[[str, PromptType | None], str] | None
        ) = None,
        apply_instruction_to_documents: bool = True,
        **kwargs: Any,
    ):
        """Initialize local vLLM CPU wrapper."""
        try:
            from vllm import LLM
        except ImportError as e:
            raise ImportError(
                "vLLM is required for VllmCPULocalWrapper. "
                "Please ensure vLLM is installed with CPU support."
            ) from e

        self.model_name = model
        self.revision = revision
        self.prompts_dict = prompt_dict
        self.use_instructions = use_instructions
        self.instruction_template = instruction_template
        self.apply_instruction_to_passages = apply_instruction_to_documents

        if use_instructions and instruction_template is None:
            raise ValueError(
                "To use instructions, an instruction_template must be provided."
            )

        # Initialize vLLM with CPU-specific settings
        logger.info(f"Initializing vLLM CPU with model: {model}")

        # Force CPU device
        import os
        os.environ["VLLM_USE_CPU"] = "1"

        self.llm = LLM(
            model=model,
            revision=revision,
            trust_remote_code=trust_remote_code,
            dtype=dtype,
            max_model_len=max_model_len,
            enforce_eager=True,  # Disable CUDA graphs for CPU
            **kwargs,
        )

        logger.info("vLLM CPU initialized successfully")

    def encode(
        self,
        inputs: DataLoader[BatchedInput],
        *,
        task_metadata: TaskMetadata,
        hf_split: str,
        hf_subset: str,
        prompt_type: PromptType | None = None,
        **kwargs: Any,
    ) -> Array:
        """Encode sentences using local vLLM instance.

        Args:
            inputs: Sentences to encode
            task_metadata: Task metadata
            prompt_type: Query or passage
            hf_split: Dataset split
            hf_subset: Dataset subset
            **kwargs: Additional arguments

        Returns:
            Embeddings array
        """
        import torch

        # Determine prompt
        prompt = ""
        if self.use_instructions and self.prompts_dict is not None:
            prompt = self.get_task_instruction(task_metadata, prompt_type)
        elif self.prompts_dict is not None:
            prompt_name = self.get_prompt_name(task_metadata, prompt_type)
            if prompt_name is not None:
                prompt = self.prompts_dict.get(prompt_name, "")

        if (
            self.use_instructions
            and self.apply_instruction_to_passages is False
            and prompt_type == PromptType.document
        ):
            logger.info(f"No instruction for documents (prompt type = {prompt_type})")
            prompt = ""
        else:
            if prompt:
                logger.info(
                    f"Using instruction: '{prompt}' for task: '{task_metadata.name}' "
                    f"prompt type: '{prompt_type}'"
                )

        # Collect texts
        prompts = [prompt + text for batch in inputs for text in batch["text"]]

        # Get embeddings from vLLM
        # Note: This assumes vLLM has embedding support via encode() method
        outputs = self.llm.encode(prompts)
        embeddings = torch.stack([output.outputs.data for output in outputs])

        return embeddings.cpu().numpy()
