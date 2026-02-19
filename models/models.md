# Models Directory

This directory contains centralized model definitions used across all test phases.

## Structure

```text
models/
├── llm/                    # Large Language Models
│   ├── llama-3.2-1b.yaml
│   ├── llama-3.2-3b.yaml
│   ├── tinyllama-1.1b.yaml
│   ├── opt-125m.yaml
│   ├── opt-1.3b.yaml
│   ├── granite-3.0-2b.yaml
│   ├── qwen2.5-0.5b.yaml
│   └── qwen2.5-3b.yaml
└── embedding/              # Embedding Models
    ├── bge-base-en-v1.5.yaml
    └── bge-large-en-v1.5.yaml
```text

## Model Configuration Format

Each model is defined in a YAML file with the following structure:

```yaml
model:
  name: "model-name"
  full_name: "org/model-name"
  type: "llm" | "embedding"

  source:
    type: "huggingface"
    repo_id: "org/model-name"
    revision: "main"

  local_path: "/models/model-name"

  vllm:
    # vLLM server configuration
    tensor_parallel_size: 1
    max_model_len: 8192

  metadata:
    size: "1.2B parameters"
    tags: ["chat", "instruct"]
```text

## Usage

Models defined here are referenced by test scenarios in the `tests/` directory.
Each test phase uses a model matrix file to specify which models to test.

## Adding a New Model

1. Create a new YAML file in `llm/` or `embedding/`
2. Define the model configuration
3. Add the model to relevant test phase matrix files
4. Validate the configuration:
   ```bash
   automation/utilities/validate-model-config.sh models/llm/your-model.yaml
   ```

See `docs/getting-started/adding-models.md` for detailed instructions.
