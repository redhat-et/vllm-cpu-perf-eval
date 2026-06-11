# Standard Offline Batch Test Suite

This document defines the standard test suite for offline batch benchmarking with vLLM CPU.

## Overview

The standard test suite provides reproducible benchmarks across different models, datasets, and configurations to establish baseline performance for offline batch processing.

## Standard Datasets

### 1. Sonnet Dataset (Default)

**Source**: [vLLM benchmarks/sonnet.txt](https://raw.githubusercontent.com/vllm-project/vllm/main/benchmarks/sonnet.txt)

**Characteristics**:
- Classic poetry text
- Consistent format
- Good for reproducible testing
- ~50 prompts, varied lengths (200-800 tokens)

**Use for**: Baseline throughput measurements

**Run**:
```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=<model>" \
  -e "dataset_name=sonnet" \
  -e "num_prompts=50" \
  -e "requested_cores=32"
```

### 2. Random Synthetic Dataset

**Characteristics**:
- Generates random text tokens
- Fully controlled input/output lengths
- No external dependencies
- Deterministic with seed

**Use for**: Controlled experiments, batch size scaling, I/O length variation

**Run**:
```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=<model>" \
  -e "dataset_name=random" \
  -e "num_prompts=1000" \
  -e "input_len=512" \
  -e "output_len=256" \
  -e "requested_cores=32"
```

### 3. ShareGPT Conversations

**Source**: ShareGPT conversation dataset

**Characteristics**:
- Real-world conversation patterns
- Variable length prompts (100-2000 tokens)
- Realistic chat/assistant use case
- Available via HuggingFace

**Use for**: Chat/conversational workload testing

**Download**:
```bash
# Download subset
wget https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/resolve/main/ShareGPT_V3_unfiltered_cleaned_split.json

# Use first 1000 conversations
head -1000 ShareGPT_V3_unfiltered_cleaned_split.json > ~/datasets/sharegpt-1k.json
```

**Run**:
```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=<model>" \
  -e "dataset_name=sharegpt" \
  -e "dataset_path=~/datasets/sharegpt-1k.json" \
  -e "num_prompts=1000" \
  -e "requested_cores=32"
```

### 4. CNN/DailyMail (Summarization)

**Source**: HuggingFace `cnn_dailymail` dataset

**Characteristics**:
- News articles for summarization
- Long documents (400-1500 tokens)
- Real-world summarization task
- Ground truth summaries available

**Use for**: Document summarization benchmarking, quality evaluation

**Access via HF datasets**:
```python
from datasets import load_dataset
dataset = load_dataset("cnn_dailymail", "3.0.0", split="test[:1000]")
# Save to jsonl for vLLM bench
```

## Standard Test Matrix

### Test 1: Baseline Throughput (All Models)

**Purpose**: Establish baseline throughput for each model

**Configuration**:
- Dataset: sonnet
- Num prompts: 100
- Cores: 32
- Models: All target models

**Command**:
```bash
for model in \
  "meta-llama/Llama-3.2-1B-Instruct" \
  "meta-llama/Llama-3.1-8B-Instruct" \
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8" \
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16" \
  "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
do
  ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
    -e "test_model=$model" \
    -e "dataset_name=sonnet" \
    -e "num_prompts=100" \
    -e "requested_cores=32"
done
```

### Test 2: Batch Size Scaling

**Purpose**: Find optimal batch size for throughput

**Configuration**:
- Dataset: random
- Input: 512 tokens
- Output: 256 tokens
- Batch sizes: 10, 50, 100, 250, 500, 1000
- Cores: 32

**Command**:
```bash
for batch_size in 10 50 100 250 500 1000
do
  ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
    -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
    -e "dataset_name=random" \
    -e "num_prompts=$batch_size" \
    -e "input_len=512" \
    -e "output_len=256" \
    -e "requested_cores=32"
done
```

### Test 3: Input Length Variation

**Purpose**: Understand prefill scaling

**Configuration**:
- Dataset: random
- Batch size: 100
- Input lengths: 128, 256, 512, 1024, 2048
- Output: 256 tokens (fixed)
- Cores: 32

**Command**:
```bash
for input_len in 128 256 512 1024 2048
do
  ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
    -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
    -e "dataset_name=random" \
    -e "num_prompts=100" \
    -e "input_len=$input_len" \
    -e "output_len=256" \
    -e "requested_cores=32"
done
```

### Test 4: Output Length Variation

**Purpose**: Understand decode scaling

**Configuration**:
- Dataset: random
- Batch size: 100
- Input: 512 tokens (fixed)
- Output lengths: 64, 128, 256, 512, 1024
- Cores: 32

**Command**:
```bash
for output_len in 64 128 256 512 1024
do
  ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
    -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
    -e "dataset_name=random" \
    -e "num_prompts=100" \
    -e "input_len=512" \
    -e "output_len=$output_len" \
    -e "requested_cores=32"
done
```

### Test 5: Core Scaling

**Purpose**: Understand CPU scaling efficiency

**Configuration**:
- Dataset: sonnet
- Batch size: 100
- Core counts: 8, 16, 32, 64
- Model: Llama-3.2-1B

**Command**:
```bash
for cores in 8 16 32 64
do
  ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
    -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
    -e "dataset_name=sonnet" \
    -e "num_prompts=100" \
    -e "requested_cores=$cores"
done
```

### Test 6: Quantization Comparison

**Purpose**: Compare quantization impact on throughput

**Configuration**:
- Dataset: sonnet
- Batch size: 100
- Cores: 32
- Models: Same model, different quantizations

**Command**:
```bash
for model in \
  "meta-llama/Llama-3.1-8B-Instruct" \
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8" \
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16"
do
  ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
    -e "test_model=$model" \
    -e "dataset_name=sonnet" \
    -e "num_prompts=100" \
    -e "requested_cores=32"
done
```

## Recommended Test Workflow

### Phase 1: Quick Validation (5-10 minutes)

Run single baseline test to verify setup:

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "dataset_name=random" \
  -e "num_prompts=50" \
  -e "input_len=512" \
  -e "output_len=256" \
  -e "requested_cores=16"
```

### Phase 2: Baseline Sweep (30-60 minutes)

Run Test 1 (Baseline Throughput) across all target models.

### Phase 3: Optimization Tests (1-2 hours)

Run Tests 2-5 for your primary model to find optimal configuration.

### Phase 4: Production Validation (2-4 hours)

Run Test 6 (Quantization Comparison) with production-size batches (1000+ prompts).

## Expected Results

### Baseline (Llama-3.2-1B, 32 cores, 100 prompts)

| Metric | Expected Range |
|--------|----------------|
| Throughput | 2-4 requests/sec |
| Token throughput | 1000-2000 tokens/sec |
| Avg time/request | 0.25-0.5 sec |

### Quantization Impact (Llama-3.1-8B, 32 cores)

| Quantization | Throughput Multiplier | Memory Reduction |
|--------------|----------------------|------------------|
| fp16 (baseline) | 1.0x | - |
| bf16 | 1.0-1.05x | ~0% |
| w8a8 | 1.2-1.5x | ~50% |
| w4a16 | 1.4-1.8x | ~60% |

### Batch Size Impact (Llama-3.2-1B, 32 cores)

| Batch Size | Efficiency (tokens/sec per core) |
|------------|----------------------------------|
| 10 | 30-40 |
| 100 | 60-80 |
| 500 | 75-95 |
| 1000 | 80-100 |

## Dataset Recommendations by Use Case

| Use Case | Recommended Dataset | Why |
|----------|-------------------|-----|
| **Baseline benchmarking** | sonnet | Consistent, reproducible |
| **Batch size optimization** | random | Controlled I/O lengths |
| **Document summarization** | CNN/DailyMail | Real-world documents |
| **Chat/conversational** | ShareGPT | Realistic conversations |
| **I/O scaling tests** | random | Full control over lengths |
| **Production simulation** | Custom dataset | Your actual workload |

## Creating Custom Datasets

### Format for vLLM bench

**Random dataset** - Use built-in random generation:
```bash
# Just specify lengths
-e "dataset_name=random" \
-e "input_len=512" \
-e "output_len=256"
```

**Text file dataset** - Create simple text file:
```bash
# One prompt per line
cat > ~/datasets/my-prompts.txt << 'EOF'
Summarize this document: [text...]
Translate the following to French: [text...]
...
EOF

# Use in benchmark
-e "dataset_name=sonnet" \
-e "dataset_path=~/datasets/my-prompts.txt"
```

**HuggingFace dataset** - Use any HF dataset:
```bash
# Requires HF datasets library in container
-e "dataset_name=hf" \
-e "dataset_name_hf=cnn_dailymail" \
-e "dataset_config_hf=3.0.0"
```

## Automated Test Suite Runner

For convenience, create a test runner script:

```bash
#!/bin/bash
# run-standard-test-suite.sh

MODEL="${1:-meta-llama/Llama-3.2-1B-Instruct}"
CORES="${2:-32}"

echo "Running standard offline batch test suite"
echo "Model: $MODEL"
echo "Cores: $CORES"

cd automation/test-execution/ansible

# Test 1: Baseline
echo "Test 1: Baseline throughput..."
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=$MODEL" \
  -e "dataset_name=sonnet" \
  -e "num_prompts=100" \
  -e "requested_cores=$CORES"

# Test 2: Batch sizes
echo "Test 2: Batch size scaling..."
for size in 50 100 500; do
  ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
    -e "test_model=$MODEL" \
    -e "dataset_name=random" \
    -e "num_prompts=$size" \
    -e "input_len=512" \
    -e "output_len=256" \
    -e "requested_cores=$CORES"
done

echo "Test suite complete!"
echo "Results in: ../../../results/llm/$(echo $MODEL | tr '/' '__')/offline-batch/"
```

## Next Steps

1. Run Phase 1 validation test
2. Select datasets based on your use case
3. Run standard test matrix
4. Analyze results to find optimal configuration
5. Run production validation with large batch sizes
