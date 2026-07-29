#!/bin/bash
# Comprehensive vLLM Offline Batch Benchmark Suite
#
# Supports both use-case-oriented and technical benchmark modes
# Uses Ansible playbook: llm-benchmark-offline-batch.yml
#
# Usage:
#   ./run-offline-batch-suite.sh <mode> [args...]
#
# Modes:
#   use-cases [runs]                 - Run all 11 real-world use cases (default: 5 runs each)
#   baseline [cores] [prompts]       - Baseline throughput across 5 models
#   batch-scaling <model> [cores]    - Batch size scaling (6 sizes)
#   input-scaling <model> [cores]    - Input length variation (5 lengths)
#   output-scaling <model> [cores]   - Output length variation (5 lengths)
#   core-scaling <model>             - Core scaling (4 configurations)
#   quantization [cores] [prompts]   - Quantization comparison (3 variants)
#   kv-capacity <model> [cores]      - KV-cache capacity sweep (6 batch sizes)
#   context-scaling <model> [cores]  - Context length scaling (4 input lengths)
#   all <model> [cores]              - Run all 8 technical tests
#
# Examples:
#   ./run-offline-batch-suite.sh use-cases 3
#   ./run-offline-batch-suite.sh baseline 32 100
#   ./run-offline-batch-suite.sh batch-scaling TinyLlama/TinyLlama-1.1B-Chat-v1.0 16
#   ./run-offline-batch-suite.sh all meta-llama/Llama-3.2-1B-Instruct 32

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

# Ensure we're in the repo root
cd "${REPO_ROOT}"

if [ ! -f "automation/test-execution/ansible/llm-benchmark-offline-batch.yml" ]; then
    echo "ERROR: Not in repository root or structure has changed"
    echo "Expected file: automation/test-execution/ansible/llm-benchmark-offline-batch.yml"
    exit 1
fi

PLAYBOOK="automation/test-execution/ansible/llm-benchmark-offline-batch.yml"
INVENTORY="automation/test-execution/ansible/inventory/hosts.yml"

# Models (RedHatAI Intel Xeon Compatible Collection)
MODEL_TINY_PRUNED="RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4"
MODEL_LLAMA_W8A8="RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
MODEL_LLAMA_W4A16="RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16"
MODEL_QWEN_W4A16="RedHatAI/Qwen3-8B-quantized.w4a16"

# Comma-separated list of all 4 models for use-cases testing
ALL_MODELS="$MODEL_TINY_PRUNED,$MODEL_LLAMA_W8A8,$MODEL_LLAMA_W4A16,$MODEL_QWEN_W4A16"

# Legacy aliases for backward compatibility
MODEL_TINY="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
MODEL_LLAMA_1B="meta-llama/Llama-3.2-1B-Instruct"
MODEL_LLAMA_8B="meta-llama/Llama-3.1-8B-Instruct"
MODEL_QUANTIZED_W8A8="$MODEL_LLAMA_W8A8"
MODEL_QUANTIZED_W4A16="$MODEL_LLAMA_W4A16"

# Container image (can be overridden via environment variable)
DEFAULT_VLLM_CONTAINER_IMAGE="docker.io/vllm/vllm-openai-cpu:v0.25.1"
VLLM_CONTAINER_IMAGE="${VLLM_CONTAINER_IMAGE:-$DEFAULT_VLLM_CONTAINER_IMAGE}"

# Timeout configuration (can be overridden via environment variable)
# Base timeout in seconds + per-prompt overhead
DEFAULT_BASE_TIMEOUT=600  # 10 minutes base
DEFAULT_TIMEOUT_PER_PROMPT=2  # 2 seconds per prompt
BASE_TIMEOUT="${OFFLINE_BATCH_BASE_TIMEOUT:-$DEFAULT_BASE_TIMEOUT}"
TIMEOUT_PER_PROMPT="${OFFLINE_BATCH_TIMEOUT_PER_PROMPT:-$DEFAULT_TIMEOUT_PER_PROMPT}"

# Retry configuration
MAX_RETRIES="${OFFLINE_BATCH_MAX_RETRIES:-1}"  # Retry once on timeout/failure
RETRY_DELAY=30  # Seconds to wait between retries

# Detect timeout command (GNU timeout on Linux, gtimeout from coreutils on macOS)
TIMEOUT_CMD=""
if command -v timeout &> /dev/null; then
    TIMEOUT_CMD="timeout"
elif command -v gtimeout &> /dev/null; then
    TIMEOUT_CMD="gtimeout"
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Print usage
usage() {
    cat << 'EOF'
vLLM Offline Batch Benchmark Suite

USAGE:
  ./run-offline-batch-suite.sh <mode> [args...]

MODES:

  Use Case Oriented (Real-world scenarios):
    use-cases [runs] [models]        Run all 11 use cases (default: 5 runs each, TinyLlama pruned)
      - Document summarization
      - Classification/tagging
      - Translation
      - Entity extraction
      - Dataset generation
      - ETL pipelines (core scaling)
      - Code generation
      - Long-document summarization (2k-8k input)
      - Batch RAG / grounded Q&A
      - Shared-prefix / template batch
      - Ultra-short labeling (output 16 tokens)

      Models: Single model or comma-separated list. Use 'all' for all 4 RedHatAI models.

    use-case-sweep <use-case> [models] [cores] [runs]
      Run a specific use case with core sweep
      Use cases: summarization, classification, translation, entity-extraction,
                 dataset-generation, code-generation, etl, long-summarization,
                 rag, shared-prefix, short-labeling
      Models: 'all' or comma-separated list (default: all)
      Cores: comma-separated list (default: 8,16,24,32)
      Runs: number of iterations (default: 3)

  Technical Benchmarks (Performance analysis):
    baseline [cores] [prompts]       Baseline throughput across 4 RedHatAI models
    batch-scaling <model> [cores]    Batch size scaling (10, 50, 100, 250, 500, 1000)
    input-scaling <model> [cores]    Input length variation (128-2048 tokens)
    output-scaling <model> [cores]   Output length variation (64-1024 tokens)
    core-scaling <model>             Core scaling (8, 16, 24, 32 cores)
    quantization [cores] [prompts]   Quantization comparison (Llama w8a8, w4a16, Qwen w4a16)
    kv-capacity <model> [cores]      KV-cache capacity sweep (100-5000 prompts)
    context-scaling <model> [cores]  Context length scaling (1024-8192 input tokens)
    all <model> [cores]              Run all 8 technical tests

EXAMPLES:

  # Use cases (practical scenarios)
  ./run-offline-batch-suite.sh use-cases 3                    # 3 runs, TinyLlama pruned only
  ./run-offline-batch-suite.sh use-cases 5 all                # 5 runs, all 4 RedHatAI models
  ./run-offline-batch-suite.sh use-cases 1 "$MODEL_LLAMA_W8A8,$MODEL_QWEN_W4A16"  # Specific models

  # Focused use case testing
  ./run-offline-batch-suite.sh use-case-sweep summarization all 8,16,24,32 3
  ./run-offline-batch-suite.sh use-case-sweep classification all
  ./run-offline-batch-suite.sh use-case-sweep translation "$MODEL_LLAMA_W8A8" 16,32 5
  ./run-offline-batch-suite.sh use-case-sweep long-summarization all 16,32 3
  ./run-offline-batch-suite.sh use-case-sweep rag all
  ./run-offline-batch-suite.sh use-case-sweep short-labeling all 8,16,24,32

  # Technical benchmarks
  ./run-offline-batch-suite.sh baseline 32 100
  ./run-offline-batch-suite.sh batch-scaling TinyLlama/TinyLlama-1.1B-Chat-v1.0 16
  ./run-offline-batch-suite.sh all meta-llama/Llama-3.2-1B-Instruct 32

ENVIRONMENT VARIABLES:
  VLLM_CONTAINER_IMAGE    Override vLLM container image
                          Default: docker.io/vllm/vllm-openai-cpu:v0.25.1
                          RHAIIS: export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

REDHATAI MODELS (Intel Xeon Compatible):
  RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4
  RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8
  RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16
  RedHatAI/Qwen3-8B-quantized.w4a16

OTHER MODELS:
  TinyLlama/TinyLlama-1.1B-Chat-v1.0
  meta-llama/Llama-3.2-1B-Instruct
  meta-llama/Llama-3.1-8B-Instruct

RESULTS:
  All results saved to: results/llm/
  View in dashboard: cd automation/test-execution/dashboard-examples/vllm_dashboard && streamlit run Home.py

EOF
    exit 1
}

# Calculate timeout based on batch size
calculate_timeout() {
    local num_prompts=$1
    local timeout=$((BASE_TIMEOUT + (num_prompts * TIMEOUT_PER_PROMPT)))
    echo $timeout
}

# Run Ansible playbook with timeout and retry
run_ansible_with_timeout() {
    local timeout_seconds=$1
    local model=$2
    local dataset=$3
    local num_prompts=$4
    local cores=$5
    shift 5

    local attempt=1
    local max_attempts=$((MAX_RETRIES + 1))

    # Parallel instance overrides — set env vars to run multiple instances
    # simultaneously on the same host (each with its own container, port, NUMA nodes):
    #   VLLM_CONTAINER_NAME=vllm-0 VLLM_PORT=8000 VLLM_NUMA_NODES="0,1" ./run-offline-batch-suite.sh use-cases
    local parallel_args=()
    if [[ -n "${VLLM_CONTAINER_NAME:-}" ]]; then
        parallel_args+=(-e "vllm_container_name=${VLLM_CONTAINER_NAME}")
    fi
    if [[ -n "${VLLM_PORT:-}" ]]; then
        parallel_args+=(-e "vllm_port=${VLLM_PORT}")
    fi
    if [[ -n "${VLLM_NUMA_NODES:-}" ]]; then
        parallel_args+=(-e "vllm_numa_nodes=${VLLM_NUMA_NODES}")
    fi

    while [ $attempt -le $max_attempts ]; do
        if [ -n "$TIMEOUT_CMD" ]; then
            echo -e "${BLUE}Attempt $attempt/$max_attempts (timeout: ${timeout_seconds}s)${NC}"
        else
            echo -e "${BLUE}Attempt $attempt/$max_attempts (no timeout - install coreutils for timeout support)${NC}"
        fi

        # Run with timeout if available, otherwise run directly
        local exit_code=0
        if [ -n "$TIMEOUT_CMD" ]; then
            "$TIMEOUT_CMD" "${timeout_seconds}s" ansible-playbook -i "$INVENTORY" "$PLAYBOOK" \
                -e "test_model=$model" \
                -e "dataset_name=$dataset" \
                -e "num_prompts=$num_prompts" \
                -e "requested_cores=$cores" \
                -e "vllm_container_image=$VLLM_CONTAINER_IMAGE" \
                "${parallel_args[@]}" \
                "$@" || exit_code=$?
        else
            ansible-playbook -i "$INVENTORY" "$PLAYBOOK" \
                -e "test_model=$model" \
                -e "dataset_name=$dataset" \
                -e "num_prompts=$num_prompts" \
                -e "requested_cores=$cores" \
                -e "vllm_container_image=$VLLM_CONTAINER_IMAGE" \
                "${parallel_args[@]}" \
                "$@" || exit_code=$?
        fi

        if [ $exit_code -eq 0 ]; then
            return 0  # Success
        fi

        if [ $exit_code -eq 124 ]; then
            echo -e "${RED}✗ TIMEOUT after ${timeout_seconds}s${NC}"
        else
            echo -e "${RED}✗ FAILED with exit code $exit_code${NC}"
        fi

        # Cleanup any hung containers on DUT
        echo -e "${YELLOW}Cleaning up any hung containers...${NC}"
        ansible dut -i "$INVENTORY" -m shell -a "podman ps -q --filter 'name=vllm-batch-*' | xargs -r podman stop" -b || true
        ansible dut -i "$INVENTORY" -m shell -a "podman ps -aq --filter 'name=vllm-batch-*' | xargs -r podman rm" -b || true

        if [ $attempt -lt $max_attempts ]; then
            echo -e "${YELLOW}Retrying in ${RETRY_DELAY}s...${NC}"
            sleep $RETRY_DELAY
            ((attempt++))
        else
            echo -e "${RED}✗ All $max_attempts attempts failed${NC}"
            return 1
        fi
    done
}

# Run Ansible playbook
run_test() {
    local model_list=$1
    local dataset=$2
    local num_prompts=$3
    local cores=$4
    shift 4

    # Handle "all" keyword for all models
    if [[ "$model_list" == "all" ]]; then
        model_list="$ALL_MODELS"
    fi

    # Calculate timeout based on batch size
    local timeout_seconds=$(calculate_timeout $num_prompts)

    # Check if comma-separated list (multiple models)
    if [[ "$model_list" == *","* ]]; then
        IFS=',' read -ra MODELS <<< "$model_list"
        local failed=0
        for model in "${MODELS[@]}"; do
            echo -e "${YELLOW}Testing model: $model${NC}"
            if ! run_ansible_with_timeout "$timeout_seconds" "$model" "$dataset" "$num_prompts" "$cores" "$@"; then
                echo -e "${RED}✗ Failed: $model${NC}"
                failed=$((failed + 1))
            else
                echo -e "${GREEN}✓ Complete: $model${NC}"
            fi
        done
        return $failed
    fi

    # Single model
    run_ansible_with_timeout "$timeout_seconds" "$model_list" "$dataset" "$num_prompts" "$cores" "$@"
}

# ==============================================================================
# USE CASE ORIENTED TESTS
# ==============================================================================

use_cases_suite() {
    local runs="${1:-5}"
    local model_list="${2:-$MODEL_TINY_PRUNED}"

    # Handle "all" keyword for all models
    if [[ "$model_list" == "all" ]]; then
        model_list="$ALL_MODELS"
    fi

    # Parse comma-separated model list
    IFS=',' read -ra MODELS <<< "$model_list"

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Offline Batch Use Case Suite${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Running $runs iterations per configuration"
    echo -e "Testing ${#MODELS[@]} model(s):"
    for model in "${MODELS[@]}"; do
        echo -e "  - $model"
    done
    echo -e "${BLUE}========================================${NC}"
    echo

    local failed_tests=()

    # 1. BULK DOCUMENT PROCESSING
    echo -e "${GREEN}📄 [1/11] Bulk Document Processing (Summarization)${NC}"
    echo "Use case: Summarize 10,000 support tickets overnight"
    echo "Parameters: 1000 prompts, sharegpt dataset (conversations), 16 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "sharegpt" 1000 16 -e "use_case=summarization"; then
                failed_tests+=("Document Processing - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 2. CLASSIFICATION / TAGGING
    echo -e "${GREEN}🏷️ [2/11] Classification/Tagging${NC}"
    echo "Use case: Classify 50,000 articles for tagging"
    echo "Parameters: 1000 prompts, sharegpt dataset (real conversations), 16 cores, output=64 tokens"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "sharegpt" 1000 16 -e "output_len=64" -e "use_case=classification"; then
                failed_tests+=("Classification - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 3. TRANSLATION
    echo -e "${GREEN}🌐 [3/11] Translation${NC}"
    echo "Use case: Translate documentation corpus"
    echo "Parameters: 500 prompts, sharegpt dataset (real text), output=1024 tokens"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "sharegpt" 500 16 -e "output_len=1024" -e "use_case=translation"; then
                failed_tests+=("Translation - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 4. ENTITY EXTRACTION
    echo -e "${GREEN}🧬 [4/11] Entity Extraction${NC}"
    echo "Use case: Extract entities from document batches"
    echo "Parameters: 1000 prompts, sharegpt dataset (conversations with real entities), output=128 tokens"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "sharegpt" 1000 16 -e "output_len=128" -e "use_case=entity_extraction"; then
                failed_tests+=("Entity Extraction - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 5. DATASET GENERATION
    echo -e "${GREEN}🎲 [5/11] Dataset Generation${NC}"
    echo "Use case: Generate 100k synthetic training examples"
    echo "Parameters: 5000 prompts, 256→256 tokens, 32 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "random" 5000 32 -e "input_len=256" -e "output_len=256" -e "use_case=dataset_generation"; then
                failed_tests+=("Dataset Generation - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 6. ETL PIPELINES (Core Scaling)
    echo -e "${GREEN}🔄 [6/11] ETL Pipelines (Core Scaling)${NC}"
    echo "Use case: Batch inference in data workflows"
    echo "Parameters: 500 prompts, sonnet, 8/16/24/32 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for cores in 8 16 24 32; do
            echo "    Testing with $cores cores..."
            for run in $(seq 1 $runs); do
                echo "      Run $run/$runs..."
                if ! run_test "$model" "sonnet" 500 $cores -e "use_case=etl"; then
                    failed_tests+=("ETL ($cores cores) - $model - Run $run")
                fi
            done
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 7. CODE GENERATION
    echo -e "${GREEN}💻 [7/11] Code Generation${NC}"
    echo "Use case: Generate tests for 1,000 functions"
    echo "Parameters: 500 prompts, 512→512 tokens, 16 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "random" 500 16 -e "input_len=512" -e "output_len=512" -e "use_case=code_generation"; then
                failed_tests+=("Code Generation - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 8. LONG-DOCUMENT SUMMARIZATION
    echo -e "${GREEN}📜 [8/11] Long-Document Summarization${NC}"
    echo "Use case: Summarize long documents (reports, articles, legal docs)"
    echo "Parameters: 500 prompts, random 4096→256 tokens, 16 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "random" 500 16 -e "input_len=4096" -e "output_len=256" -e "use_case=long_summarization"; then
                failed_tests+=("Long-Document Summarization - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 9. BATCH RAG / GROUNDED Q&A
    echo -e "${GREEN}🔍 [9/11] Batch RAG / Grounded Q&A${NC}"
    echo "Use case: Process RAG queries with retrieved context + short answers"
    echo "Parameters: 500 prompts, random 2048→128 tokens, 16 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "random" 500 16 -e "input_len=2048" -e "output_len=128" -e "use_case=rag_batch"; then
                failed_tests+=("RAG Batch - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 10. SHARED-PREFIX / TEMPLATE BATCH
    echo -e "${GREEN}📋 [10/11] Shared-Prefix / Template Batch${NC}"
    echo "Use case: Short-output template-shaped throughput (1024→64 tokens)"
    echo "Parameters: 1000 prompts, random 1024→64 tokens, 16 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "random" 1000 16 -e "input_len=1024" -e "output_len=64" -e "use_case=shared_prefix"; then
                failed_tests+=("Shared-Prefix - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # 11. ULTRA-SHORT LABELING
    echo -e "${GREEN}⚡ [11/11] Ultra-Short Labeling${NC}"
    echo "Use case: Sentiment/moderation/yes-no labeling at high volume"
    echo "Parameters: 2000 prompts, sharegpt, output=16 tokens, 16 cores"
    echo
    for model in "${MODELS[@]}"; do
        echo "  Model: $model"
        for run in $(seq 1 $runs); do
            echo "    Run $run/$runs..."
            if ! run_test "$model" "sharegpt" 2000 16 -e "output_len=16" -e "use_case=short_labeling"; then
                failed_tests+=("Ultra-Short Labeling - $model - Run $run")
            fi
        done
    done
    echo -e "${GREEN}✓ Complete${NC}"
    echo

    # Summary
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Use Case Suite Complete${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo

    if [ ${#failed_tests[@]} -eq 0 ]; then
        echo -e "${GREEN}✓✓✓ All use cases completed successfully! ✓✓✓${NC}"
        return 0
    else
        echo -e "${RED}✗ ${#failed_tests[@]} test(s) failed:${NC}"
        for test in "${failed_tests[@]}"; do
            echo -e "${RED}  - $test${NC}"
        done
        return 1
    fi
}

# ==============================================================================
# TECHNICAL BENCHMARK TESTS
# ==============================================================================

test_baseline() {
    local cores="${1:-32}"
    local prompts="${2:-100}"

    local models=(
        "$MODEL_TINY_PRUNED"
        "$MODEL_LLAMA_W8A8"
        "$MODEL_LLAMA_W4A16"
        "$MODEL_QWEN_W4A16"
    )

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: Baseline Throughput${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Dataset: sonnet"
    echo "Prompts: $prompts"
    echo "Cores: $cores"
    echo "Models: ${#models[@]} RedHatAI models"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for model in "${models[@]}"; do
        echo -e "${YELLOW}Testing: $model${NC}"
        if run_test "$model" "sonnet" "$prompts" "$cores" -e "use_case=baseline"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$model")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

test_batch_scaling() {
    local model="$1"
    local cores="${2:-32}"
    local sizes=(10 50 100 250 500 1000)

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: Batch Size Scaling${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Model: $model"
    echo "Dataset: random (512 → 256 tokens)"
    echo "Cores: $cores"
    echo "Batch sizes: ${sizes[*]}"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for size in "${sizes[@]}"; do
        echo -e "${YELLOW}Batch size: $size${NC}"
        if run_test "$model" "random" "$size" "$cores" -e "input_len=512" -e "output_len=256" -e "use_case=batch_scaling"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$size")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

test_input_scaling() {
    local model="$1"
    local cores="${2:-32}"
    local lengths=(128 256 512 1024 2048)

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: Input Length Variation${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Model: $model"
    echo "Batch size: 100"
    echo "Output: 256 tokens (fixed)"
    echo "Cores: $cores"
    echo "Input lengths: ${lengths[*]}"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for len in "${lengths[@]}"; do
        echo -e "${YELLOW}Input length: $len tokens${NC}"
        if run_test "$model" "random" 100 "$cores" -e "input_len=$len" -e "output_len=256" -e "use_case=input_scaling"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$len")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

test_output_scaling() {
    local model="$1"
    local cores="${2:-32}"
    local lengths=(64 128 256 512 1024)

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: Output Length Variation${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Model: $model"
    echo "Batch size: 100"
    echo "Input: 512 tokens (fixed)"
    echo "Cores: $cores"
    echo "Output lengths: ${lengths[*]}"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for len in "${lengths[@]}"; do
        echo -e "${YELLOW}Output length: $len tokens${NC}"
        if run_test "$model" "random" 100 "$cores" -e "input_len=512" -e "output_len=$len" -e "use_case=output_scaling"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$len")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

test_core_scaling() {
    local model="$1"
    local cores_list=(8 16 24 32)

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: Core Scaling${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Model: $model"
    echo "Dataset: sonnet"
    echo "Batch size: 100"
    echo "Core counts: ${cores_list[*]}"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for cores in "${cores_list[@]}"; do
        echo -e "${YELLOW}Cores: $cores${NC}"
        if run_test "$model" "sonnet" 100 "$cores" -e "use_case=core_scaling"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$cores")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

test_quantization() {
    local cores="${1:-32}"
    local prompts="${2:-100}"

    local models=(
        "$MODEL_LLAMA_W8A8"
        "$MODEL_LLAMA_W4A16"
        "$MODEL_QWEN_W4A16"
    )

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: Quantization Comparison${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "RedHatAI Quantized Models"
    echo "Dataset: sonnet"
    echo "Prompts: $prompts"
    echo "Cores: $cores"
    echo "Models: Llama w8a8, Llama w4a16, Qwen w4a16"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for model in "${models[@]}"; do
        local model_short=$(basename "$model")

        echo -e "${YELLOW}Testing: $model_short${NC}"
        if run_test "$model" "sonnet" "$prompts" "$cores" -e "use_case=quantization_comparison"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$model_short")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

test_kv_capacity() {
    local model="$1"
    local cores="${2:-32}"
    local sizes=(100 250 500 1000 2000 5000)

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: KV-Cache Capacity Sweep${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Model: $model"
    echo "Dataset: random (512 → 256 tokens)"
    echo "Cores: $cores"
    echo "Batch sizes: ${sizes[*]}"
    echo "Question: How large a batch fits before KV cache saturates?"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for size in "${sizes[@]}"; do
        echo -e "${YELLOW}Batch size: $size${NC}"
        if run_test "$model" "random" "$size" "$cores" -e "input_len=512" -e "output_len=256" -e "use_case=kv_capacity"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$size")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

test_context_scaling() {
    local model="$1"
    local cores="${2:-32}"
    local lengths=(1024 2048 4096 8192)

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test: Context Length Scaling${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Model: $model"
    echo "Batch size: 100"
    echo "Output: 128 tokens (fixed)"
    echo "Cores: $cores"
    echo "Input lengths: ${lengths[*]}"
    echo "Question: How does throughput degrade as context grows?"
    echo -e "${GREEN}========================================${NC}"
    echo

    local failed=()
    for len in "${lengths[@]}"; do
        echo -e "${YELLOW}Context length: $len tokens${NC}"
        if run_test "$model" "random" 100 "$cores" -e "input_len=$len" -e "output_len=128" -e "use_case=context_scaling"; then
            echo -e "${GREEN}✓ Completed${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            failed+=("$len")
        fi
        echo
    done

    [ ${#failed[@]} -eq 0 ]
}

# Run a specific use case with core sweep
use_case_sweep() {
    local use_case="$1"
    local model_list="${2:-all}"
    local cores_list="${3:-8,16,24,32}"
    local runs="${4:-3}"

    # Handle "all" keyword for models
    if [[ "$model_list" == "all" ]]; then
        model_list="$ALL_MODELS"
    fi

    # Parse comma-separated lists
    IFS=',' read -ra MODELS <<< "$model_list"
    IFS=',' read -ra CORES <<< "$cores_list"

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Use Case: $use_case (Core Sweep)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Models: ${#MODELS[@]}"
    for model in "${MODELS[@]}"; do
        echo -e "  - $model"
    done
    echo -e "Core counts: ${CORES[*]}"
    echo -e "Runs per config: $runs"
    echo -e "${BLUE}========================================${NC}"
    echo

    local failed_tests=()

    # Define use case parameters
    local dataset num_prompts extra_args use_case_name
    case "$use_case" in
        summarization|summary|sum)
            use_case_name="📝 Summarization"
            dataset="sharegpt"
            num_prompts=1000
            extra_args="-e use_case=summarization"
            echo "Use case: Summarize 10,000 support tickets overnight"
            echo "Dataset: sharegpt (conversations)"
            ;;
        classification|class|tag)
            use_case_name="🏷️ Classification/Tagging"
            dataset="sharegpt"
            num_prompts=1000
            extra_args="-e output_len=64 -e use_case=classification"
            echo "Use case: Classify 50,000 articles for tagging"
            echo "Dataset: sharegpt (real conversations)"
            ;;
        translation|trans)
            use_case_name="🌐 Translation"
            dataset="sharegpt"
            num_prompts=500
            extra_args="-e output_len=1024 -e use_case=translation"
            echo "Use case: Translate documentation corpus"
            echo "Dataset: sharegpt (real text)"
            ;;
        entity-extraction|entity|extract)
            use_case_name="🧬 Entity Extraction"
            dataset="sharegpt"
            num_prompts=1000
            extra_args="-e output_len=128 -e use_case=entity_extraction"
            echo "Use case: Extract entities from document batches"
            echo "Dataset: sharegpt (conversations with real entities)"
            ;;
        dataset-generation|dataset|datagen)
            use_case_name="🎲 Dataset Generation"
            dataset="random"
            num_prompts=5000
            extra_args="-e input_len=256 -e output_len=256 -e use_case=dataset_generation"
            echo "Use case: Generate 100k synthetic training examples"
            echo "Dataset: random (synthetic data)"
            ;;
        code-generation|code|codegen)
            use_case_name="💻 Code Generation"
            dataset="random"
            num_prompts=500
            extra_args="-e input_len=512 -e output_len=512 -e use_case=code_generation"
            echo "Use case: Generate tests for 1,000 functions"
            echo "Dataset: random (no code-specific dataset available)"
            ;;
        etl|pipeline)
            use_case_name="🔄 ETL Pipelines"
            dataset="sonnet"
            num_prompts=500
            extra_args="-e use_case=etl"
            echo "Use case: Batch inference in data workflows"
            echo "Dataset: sonnet (baseline)"
            ;;
        long-summarization|long-summary|longsum)
            use_case_name="📜 Long-Document Summarization"
            dataset="random"
            num_prompts=500
            extra_args="-e input_len=4096 -e output_len=256 -e use_case=long_summarization"
            echo "Use case: Summarize long documents (reports, articles, legal)"
            echo "Dataset: random (controlled long input)"
            ;;
        rag|rag-batch|grounded-qa)
            use_case_name="🔍 Batch RAG / Grounded Q&A"
            dataset="random"
            num_prompts=500
            extra_args="-e input_len=2048 -e output_len=128 -e use_case=rag_batch"
            echo "Use case: RAG queries with retrieved context + short answers"
            echo "Dataset: random (simulating retrieved chunks)"
            ;;
        shared-prefix|prefix|template)
            use_case_name="📋 Shared-Prefix / Template Batch"
            dataset="random"
            num_prompts=1000
            extra_args="-e input_len=1024 -e output_len=64 -e use_case=shared_prefix"
            echo "Use case: Short-output template-shaped throughput (1024→64 tokens)"
            echo "Dataset: random (controlled I/O shape)"
            ;;
        short-labeling|short-label|labeling|sentiment)
            use_case_name="⚡ Ultra-Short Labeling"
            dataset="sharegpt"
            num_prompts=2000
            extra_args="-e output_len=16 -e use_case=short_labeling"
            echo "Use case: Sentiment/moderation/yes-no labeling at high volume"
            echo "Dataset: sharegpt (real text, ultra-short output)"
            ;;
        *)
            echo -e "${RED}Error: Unknown use case: $use_case${NC}"
            echo "Valid use cases: summarization, classification, translation,"
            echo "                 entity-extraction, dataset-generation, code-generation, etl,"
            echo "                 long-summarization, rag, shared-prefix, short-labeling"
            return 1
            ;;
    esac
    echo "Parameters: $num_prompts prompts"
    echo

    # Run tests for each model and core count
    for model in "${MODELS[@]}"; do
        echo -e "${GREEN}Model: $model${NC}"
        for cores in "${CORES[@]}"; do
            echo "  Cores: $cores"
            for run in $(seq 1 $runs); do
                echo "    Run $run/$runs..."
                if ! run_test "$model" "$dataset" "$num_prompts" "$cores" $extra_args; then
                    failed_tests+=("$use_case_name - $model - $cores cores - Run $run")
                fi
            done
        done
        echo
    done

    # Summary
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Use Case Sweep Complete${NC}"
    echo -e "${BLUE}========================================${NC}"

    if [ ${#failed_tests[@]} -eq 0 ]; then
        echo -e "${GREEN}✓✓✓ All tests completed successfully! ✓✓✓${NC}"
        return 0
    else
        echo -e "${RED}✗ ${#failed_tests[@]} test(s) failed:${NC}"
        for test in "${failed_tests[@]}"; do
            echo -e "${RED}  - $test${NC}"
        done
        return 1
    fi
}

test_all() {
    local model="$1"
    local cores="${2:-32}"

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}FULL TECHNICAL BENCHMARK SUITE${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "Model: $model"
    echo "Cores: $cores"
    echo -e "${BLUE}========================================${NC}"
    echo
    echo "This will run all 8 technical tests:"
    echo "  1. Baseline throughput (4 models)"
    echo "  2. Batch size scaling (6 sizes)"
    echo "  3. Input length variation (5 lengths)"
    echo "  4. Output length variation (5 lengths)"
    echo "  5. Core scaling (4 configurations)"
    echo "  6. Quantization comparison (3 variants)"
    echo "  7. KV-cache capacity sweep (6 sizes)"
    echo "  8. Context length scaling (4 lengths)"
    echo
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        return 1
    fi
    echo

    local failed_tests=()

    test_baseline "$cores" 100 || failed_tests+=("Baseline")
    echo
    test_batch_scaling "$model" "$cores" || failed_tests+=("Batch Scaling")
    echo
    test_input_scaling "$model" "$cores" || failed_tests+=("Input Scaling")
    echo
    test_output_scaling "$model" "$cores" || failed_tests+=("Output Scaling")
    echo
    test_core_scaling "$model" || failed_tests+=("Core Scaling")
    echo
    test_quantization "$cores" 100 || failed_tests+=("Quantization")
    echo
    test_kv_capacity "$model" "$cores" || failed_tests+=("KV Capacity")
    echo
    test_context_scaling "$model" "$cores" || failed_tests+=("Context Scaling")
    echo

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}TECHNICAL SUITE COMPLETE${NC}"
    echo -e "${BLUE}========================================${NC}"

    if [ ${#failed_tests[@]} -eq 0 ]; then
        echo -e "${GREEN}✓✓✓ All 8 tests completed successfully! ✓✓✓${NC}"
        return 0
    else
        echo -e "${RED}✗ ${#failed_tests[@]} test(s) failed:${NC}"
        for test in "${failed_tests[@]}"; do
            echo -e "${RED}  - $test${NC}"
        done
        return 1
    fi
}

# ==============================================================================
# MAIN
# ==============================================================================

main() {
    if [ $# -lt 1 ]; then
        usage
    fi

    local mode=$1
    shift

    case "$mode" in
        run-test|run_test)
            if [ $# -lt 4 ]; then
                echo "Error: run-test requires <model> <dataset> <num-prompts> <cores> [extra-args]"
                exit 1
            fi
            run_test "$@"
            ;;
        use-cases)
            use_cases_suite "$@"
            ;;
        use-case-sweep)
            if [ $# -lt 1 ]; then
                echo "Error: use-case-sweep requires <use-case> [model-list] [cores-list] [runs]"
                exit 1
            fi
            use_case_sweep "$@"
            ;;
        baseline)
            test_baseline "$@"
            ;;
        batch-scaling)
            if [ $# -lt 1 ]; then
                echo "Error: batch-scaling requires <model> argument"
                exit 1
            fi
            test_batch_scaling "$@"
            ;;
        input-scaling)
            if [ $# -lt 1 ]; then
                echo "Error: input-scaling requires <model> argument"
                exit 1
            fi
            test_input_scaling "$@"
            ;;
        output-scaling)
            if [ $# -lt 1 ]; then
                echo "Error: output-scaling requires <model> argument"
                exit 1
            fi
            test_output_scaling "$@"
            ;;
        core-scaling)
            if [ $# -lt 1 ]; then
                echo "Error: core-scaling requires <model> argument"
                exit 1
            fi
            test_core_scaling "$@"
            ;;
        quantization)
            test_quantization "$@"
            ;;
        kv-capacity)
            if [ $# -lt 1 ]; then
                echo "Error: kv-capacity requires <model> argument"
                exit 1
            fi
            test_kv_capacity "$@"
            ;;
        context-scaling)
            if [ $# -lt 1 ]; then
                echo "Error: context-scaling requires <model> argument"
                exit 1
            fi
            test_context_scaling "$@"
            ;;
        all)
            if [ $# -lt 1 ]; then
                echo "Error: all requires <model> argument"
                exit 1
            fi
            test_all "$@"
            ;;
        *)
            echo "Error: Unknown mode: $mode"
            echo
            usage
            ;;
    esac

    local exit_code=$?

    echo
    echo -e "${GREEN}Results saved to: results/llm/${NC}"
    echo
    echo "View in dashboard:"
    echo "  cd automation/test-execution/dashboard-examples/vllm_dashboard"
    echo "  streamlit run Home.py"
    echo

    return $exit_code
}

main "$@"
