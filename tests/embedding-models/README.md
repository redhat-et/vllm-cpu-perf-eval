# Embedding Models Performance Testing

This directory contains performance evaluation tests for vLLM embedding
models running on CPU platforms.

## Overview

These tests evaluate embedding model performance using `vllm bench serve`
to establish:

- Baseline performance for CPU-based vLLM inference of embedding models
- Which embedding models work on CPU and their suitability for
  enterprise use cases based on RPS/Latency
- Performance characteristics under various load conditions

## Test Structure

```text
embedding-models/
├── README.md                  # This file
├── model-matrix.yaml          # Model to test scenario mapping
├── test-scenarios/            # Test scenario definitions
│   ├── baseline-sweep.yaml    # Baseline throughput tests
│   └── latency-concurrent.yaml # Concurrent latency tests
└── scripts/                   # Automation scripts
    ├── run-baseline.sh        # Run baseline performance tests
    ├── run-latency.sh         # Run latency tests
    └── run-all.sh             # Run all embedding tests
```

## Models Under Test

The test suite focuses on representative models from different
architecture families:

| Architecture Family | Representative Model | Application Focus |
|-------------------|---------------------|-------------------|
| MiniLM/BERT (English Dense) | granite-embedding-english-r2 | Encoder-Only (Fastest Baseline) |
| XLM-RoBERTa (Multilingual Dense) | granite-embedding-278m-multilingual | Encoder-Only (Multilingual) |

See [models/embedding/](../../models/embedding/) for complete model
definitions.

## Test Cases

### Test Case 1.1: Baseline Performance and Scalability (English Model)

**Objective**: Establish maximum Request Throughput (RPS) and analyze
performance scaling.

- **Test Type**: vllm bench serve (sweep)
- **Model**: slate-125m-english-rtrvr-v2
- **Workload**: Embedding (512:1)
- **KV Cache**: 1GiB
- **Quantization**: OFF
- **Primary Metric**: Enterprise English Embedding Throughput (RPS)

**Test Steps**:

1. Find max throughput with `--request-rate inf`
2. Run at 25%, 50%, 75% of max throughput
3. Measure latency curves at each rate

**Expected Outputs**:

- Maximum sustained RPS
- Latency vs throughput curves
- Saturation point identification

### Test Case 1.2: Baseline Performance and Scalability (Multilingual Model)

**Objective**: Establish maximum Request Throughput (RPS) for
multilingual model.

- **Test Type**: vllm bench serve (sweep)
- **Model**: granite-embedding-278m-multilingual
- **Workload**: Embedding (512:1)
- **KV Cache**: 1GiB
- **Quantization**: OFF
- **Primary Metric**: Multilingual Embedding Throughput (RPS)

**Test Steps**: Same as Test Case 1.1

### Test Case 2.1: Latency and Stability Under Load

**Objective**: Measure latency scaling under increasing concurrent
requests.

- **Test Type**: vllm bench serve (concurrent)
- **Model**: granite-embedding-278m-multilingual
- **Workload**: Embedding (512:1)
- **Concurrency Levels**: {16, 32, 64, 128, 196}
- **Primary Metric**: P99 Latency Scaling

**Test Steps**:

1. Run at each concurrency level
2. Measure P95/P99 latency at each level
3. Identify optimal concurrency (throughput plateau, acceptable P99)

**Expected Outputs**:

- Mean/P95/P99 latency at each concurrency
- Throughput at each concurrency
- Sweet spot identification

## Test Parameters

### Common Parameters

| Variable | Description | Test Setting |
|----------|-------------|--------------|
| **Workload** | Input/Output token counts (ISL:OSL) | Embedding (512:1) |
| **Input Sequence Length** | Fixed input token count | 512 |
| **Output Sequence Length** | Fixed output token count | 1 |
| **Affinity** | Core allocation strategy | Handled by vLLM automatically |
| **Cores** | Number of cores for test | VENDOR-DEFINED OPTIMAL CONFIGURATION |
| **NUMA nodes** | Number of NUMA nodes used | VENDOR-DEFINED OPTIMAL CONFIGURATION |
| **Dtype** | Data type for model weights | bfloat16 |
| **KV Cache** | KV Cache size | VLLM_CPU_KVCACHE_SPACE=1GiB |


## Performance Metrics

### Primary Metrics

| Metric | Description |
|--------|-------------|
| **Request throughput (req/s)** | Total requests successfully processed per second |
| **Total Token throughput (tok/s)** | Combined rate of all input tokens processed per second |
| **Mean E2EL (ms)** | Average end-to-end latency from request to response |
| **P95 E2EL (ms)** | 95th percentile end-to-end latency |
| **P99 E2EL (ms)** | 99th percentile end-to-end latency (primary metric) |

### System Level Metrics

| Metric | Description |
|--------|-------------|
| **vLLM Process CPU Utilization (%)** | CPU time spent on non-idle threads |
| **Memory Utilization/Consumption (GB)** | Total RAM used by vLLM process |


## Running Tests

### Prerequisites

```bash
# Ensure vLLM >= v0.11.0 (for embedding benchmarking support)
pip install "vllm>=0.11.0"

# Set environment variables
export VLLM_CPU_KVCACHE_SPACE=1GiB
```

### Run Individual Test Cases

```bash
# Baseline test for English model
./scripts/run-baseline.sh slate-125m-english-rtrvr-v2

# Baseline test for Multilingual model
./scripts/run-baseline.sh granite-embedding-278m-multilingual

# Latency test
./scripts/run-latency.sh granite-embedding-278m-multilingual
```

### Run All Embedding Tests

```bash
# Run complete test suite
./scripts/run-all.sh

# Run with custom configuration
MODEL=granite-embedding-english-r2 ./scripts/run-baseline.sh
```

### Using Ansible

```bash
# Run all embedding tests
cd ../../automation/test-execution/ansible
ansible-playbook playbooks/run-embedding-tests.yml

# Run specific test case
ansible-playbook playbooks/run-embedding-tests.yml \
  -e "test_case=baseline" \
  -e "model=granite-embedding-278m-multilingual"
```

## Test Methodology

### Baseline Performance Tests

These tests use `vllm bench serve` to simulate sweep-rate behavior:

1. **Find Maximum Throughput**:
   ```bash
   vllm bench serve --backend openai-embeddings \
     --model <model> \
     --dataset-name random \
     --random-input-len 512 \
     --num-prompts 1000 \
     --request-rate inf \
     --endpoint /v1/embeddings \
     --save-result \
     --result-filename "<model>-sweep-inf.json"
   ```

2. **Measure at Load Levels**:
   - Extract max RPS from step 1 output (e.g., 42.35 req/s)
   - Test at 25% (10.6 req/s), 50% (21.2 req/s), 75% (31.8 req/s)
   - Measure latency curves at each rate

### Latency and Concurrent Load Tests

These tests measure latency scaling with concurrency:

```bash
for concurrency in 16 32 64 128 196; do
  vllm bench serve \
    --backend openai-embeddings \
    --model <model> \
    --dataset-name random \
    --random-input-len 512 \
    --num-prompts 1000 \
    --endpoint /v1/embeddings \
    --request-rate inf \
    --max-concurrency $concurrency \
    --save-result \
    --result-filename "<model>-concurrent-${concurrency}.json"
done
```

**Key Metrics to Monitor**:
- Mean E2EL (ms) - Average end-to-end latency
- P95 E2EL (ms) - 95th percentile latency
- P99 E2EL (ms) - 99th percentile latency (primary metric)
- Request throughput (req/s) - Actual requests completed per second

**What to Look For**:

- **Sweet spot**: Concurrency level where throughput plateaus but
  P99 latency remains acceptable
- **Degradation point**: When P99 latency increases significantly
  while throughput gains diminish
- **Comparison**: How P99 scales from low (16) to high (196) concurrency

## Results Format

### Test Settings

Each test result should include:

| Information | Description |
|------------|-------------|
| **vLLM serving command** | Complete command with all CLI args |
| **vLLM bench serve testing command** | Complete benchmarking command |
| **Optimal Core Count Used** | Number of physical cores (e.g., 32, 64) |
| **vLLM Environment Variables** | All non-default VLLM_ and OMP_ variables |
| **Container build params** | Build variables if built from source |
| **Container image** | Image URL if using containers |


### Baseline Performance Results

Example results table:

| Request Rate | Actual RPS | Mean (ms) | P95 (ms) | P99 (ms) | Calculated Avg. Concurrency |
|-------------|-----------|-----------|----------|----------|---------------------------|
| inf (100%) | 46.97 | 11066.20 | ~19000 | 21143.23 | 519.78 |
| 12 (25%) | 11.99 | 50.91 | ~100 | 137.83 | 0.61 |
| 23 (50%) | 22.98 | 79.27 | ~180 | 224.39 | 1.82 |
| 35 (75%) | 34.89 | 161.10 | ~380 | 451.55 | 5.62 |

**Note**: Calculated Avg. Concurrency uses Little's Law (L = RPS ×
Mean Latency in Seconds)

### Latency and Stability Results

Example results table:

| Concurrency | RPS | Mean (ms) | P95 (ms) | P99 (ms) |
|------------|-----|-----------|----------|----------|
| 16 | 44.87 | 353.26 | ~365 | 370.72 |
| 32 | 47.66 | 663.30 | ~705 | 731.10 |
| 64 | 48.20 | 1305.45 | ~1450 | 1502.30 |
| 128 | 48.85 | 2589.12 | ~2850 | 2945.67 |
| 196 | 49.01 | 3942.78 | ~4200 | 4356.21 |


## Results Location

Test results are stored in:

```text
results/embedding-models/
├── <model-name>/
│   ├── baseline/
│   │   ├── sweep-inf.json
│   │   ├── sweep-25pct.json
│   │   ├── sweep-50pct.json
│   │   └── sweep-75pct.json
│   └── latency/
│       ├── concurrent-16.json
│       ├── concurrent-32.json
│       ├── concurrent-64.json
│       ├── concurrent-128.json
│       └── concurrent-196.json
```

## Analysis and Reporting

### Generate Graphs

```bash
cd ../../automation/analysis
python generate-embedding-report.py \
  --input ../../results/embedding-models/ \
  --format html \
  --output ../../results/reports/embedding-models.html
```

### Expected Visualizations

1. **Throughput Saturation Curve**: Achieved throughput vs
   requested rate
2. **Latency vs Request Rate**: Mean and P99 latency scaling
3. **Throughput vs Concurrency**: Request throughput at each
   concurrency level
4. **Latency vs Concurrency**: Mean and P99 latency scaling with
   concurrency

## Configuration Details Required

### Hardware & BIOS Information

- Baseboard Model/Vendor
- Architecture/MicroArchitecture (e.g., Intel Sapphire Rapids)
- Sockets & Cores per Socket
- Instruction Set Architecture (ISA) - AVX512, AMX, VNNI, AVX512_BF16
- L3 Cache Size (MB)
- Hyperthreading Status
- Base/All-Core Max Frequency (GHz)
- NUMA nodes count
- Sub-NUMA Clustering (SNC) status
- Installed Memory Size/Speed/Channels
- Hugepage size and status
- BIOS version
- TDP (W)

### OS & Software Settings

- RHEL Version & Kernel Version
- OS Tuning Parameters (tuned profile, etc.)
- Automatic NUMA Balancing status
- Power and performance policy
- Frequency Governor & Driver
- vLLM version

## Test ID Naming Convention

Embedding test cases follow the hierarchical naming scheme:

**Format**: `EMB-{TYPE}-{model}-{workload}`

**Components**:
- **Prefix**: `EMB` (Embedding)
- **Type**: `BASELINE` (Baseline Performance), `LATENCY` (Concurrent Latency)
- **Model**: Short abbreviation (e.g., `GRANITE-EN`, `GRANITE-ML`)
- **Workload**: `EMB512` (512-token embedding)

**Examples**:

- `EMB-BASELINE-GRANITE-EN-EMB512`: Baseline test, Granite English
  model
- `EMB-LATENCY-GRANITE-ML-EMB512`: Latency test, Granite
  Multilingual model

## References

- [vLLM Benchmarking Documentation](https://docs.vllm.ai/en/latest/serving/benchmarking.html)
- [vLLM Embedding Models Guide](https://docs.vllm.ai/en/latest/models/embedding_models.html)
- [Performance Evaluation Guide PDF](../../docs/vllm-embedding-perf-eval-guide.pdf)
