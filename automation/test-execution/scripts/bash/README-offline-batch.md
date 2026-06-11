# Offline Batch Benchmarking

Single comprehensive script for running vLLM offline batch benchmarks.

## Quick Start

```bash
cd automation/test-execution/ansible

# Run all real-world use cases (3 iterations each)
./run-offline-batch-suite.sh use-cases 3

# Run technical benchmark suite
./run-offline-batch-suite.sh all TinyLlama/TinyLlama-1.1B-Chat-v1.0 16

# Run specific test
./run-offline-batch-suite.sh batch-scaling meta-llama/Llama-3.2-1B-Instruct 32
```

## Modes

### Use Case Oriented (Real-World Scenarios)

**`use-cases [runs]`** - Run all 7 real-world use cases

Covers practical scenarios:
- 📄 Document summarization (support tickets, articles)
- 🏷️ Classification/tagging (article categorization)
- 🌐 Translation (documentation corpus)
- 🧬 Entity extraction (document batches)
- 🎲 Dataset generation (synthetic examples)
- 🔄 ETL pipelines (data workflows with core scaling)
- 💻 Code generation (test generation)

**Example:**
```bash
# Run use cases with 5 iterations each (default)
./run-offline-batch-suite.sh use-cases

# Run with 3 iterations (faster)
./run-offline-batch-suite.sh use-cases 3
```

### Technical Benchmarks (Performance Analysis)

Individual benchmark types:

**`baseline [cores] [prompts]`** - Baseline throughput across 5 models
```bash
./run-offline-batch-suite.sh baseline 32 100
```

**`batch-scaling <model> [cores]`** - Batch size scaling (6 sizes: 10, 50, 100, 250, 500, 1000)
```bash
./run-offline-batch-suite.sh batch-scaling TinyLlama/TinyLlama-1.1B-Chat-v1.0 16
```

**`input-scaling <model> [cores]`** - Input length variation (128-2048 tokens)
```bash
./run-offline-batch-suite.sh input-scaling meta-llama/Llama-3.2-1B-Instruct 32
```

**`output-scaling <model> [cores]`** - Output length variation (64-1024 tokens)
```bash
./run-offline-batch-suite.sh output-scaling meta-llama/Llama-3.2-1B-Instruct 32
```

**`core-scaling <model>`** - Core scaling (8, 16, 32, 64 cores)
```bash
./run-offline-batch-suite.sh core-scaling meta-llama/Llama-3.2-1B-Instruct
```

**`quantization [cores] [prompts]`** - Quantization comparison (fp16, w8a8, w4a16)
```bash
./run-offline-batch-suite.sh quantization 32 100
```

**`all <model> [cores]`** - Run all 6 technical tests
```bash
./run-offline-batch-suite.sh all meta-llama/Llama-3.2-1B-Instruct 32
```

## Models

Supported models:
- `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- `meta-llama/Llama-3.2-1B-Instruct`
- `meta-llama/Llama-3.1-8B-Instruct`
- `RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8`
- `RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16`

## Results

All results saved to: `results/llm/<model>/offline-batch-<timestamp>/<config>/`

### View Results

```bash
cd automation/test-execution/dashboard-examples/vllm_dashboard
streamlit run Home.py
```

Navigate to "📦 Offline Batch" page.

## Directory Structure

```
results/llm/
└── TinyLlama__TinyLlama-1.1B-Chat-v1.0/
    └── offline-batch-20260611-143022/
        └── 16cores-sonnet-500prompts/
            ├── test-metadata.json       # Test configuration
            ├── results.json              # Enhanced metrics (includes prefill/decode/cache)
            └── benchmark.log             # Raw vLLM output
```

## Enhanced Metrics

The new results format includes:

**Throughput:**
- `throughput_requests_per_sec` - Documents/sec
- `throughput_total_tokens_per_sec` - Total tokens/sec
- `throughput_output_tokens_per_sec` - Output tokens/sec
- `prefill_throughput_tokens_per_sec` - **NEW:** Input processing speed
- `decode_throughput_tokens_per_sec` - **NEW:** Generation speed

**System Efficiency:**
- `max_kv_cache_usage_percent` - **NEW:** Memory usage
- `avg_prefix_cache_hit_rate_percent` - **NEW:** Cache effectiveness

## Single Test Examples

Run individual tests with custom parameters:

```bash
# Document summarization: 500 prompts, sonnet dataset, 16 cores
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "dataset_name=sonnet" \
  -e "num_prompts=500" \
  -e "requested_cores=16"

# Classification: short outputs (64 tokens), 1000 prompts
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "dataset_name=random" \
  -e "num_prompts=1000" \
  -e "input_len=512" \
  -e "output_len=64" \
  -e "requested_cores=16"
```

## Migration Notes

**Old scripts removed:**
- ~~`automation/test-execution/scripts/bash/run-offline-batch-benchmark.sh`~~ → Use `run-offline-batch-suite.sh`
- ~~`automation/test-execution/scripts/bash/run-offline-batch-tests.sh`~~ → Use `run-offline-batch-suite.sh`
- ~~`automation/test-execution/scripts/python/offline_batch_benchmark.py`~~ → Not needed (Ansible playbook handles everything)

**Everything consolidated into:**
- `automation/test-execution/ansible/run-offline-batch-suite.sh` ✅
