#!/usr/bin/env bash
#
# Core Sweep Runner
# Orchestrates multiple test runs across different core counts
#
# Usage (positional):
#   ./scripts/run-core-sweep.sh MODEL WORKLOAD CORES [EXTRA_ARGS...]
#   ./scripts/run-core-sweep.sh "TinyLlama/TinyLlama-1.1B-Chat-v1.0" "chat" "8,16,32,64"
#
# Usage (named):
#   ./scripts/run-core-sweep.sh --model MODEL --workload WORKLOAD --cores CORES
#

set -euo pipefail

# Default values
MODEL=""
WORKLOAD=""
CORES=""
EXTRA_VARS=""
ANSIBLE_VERBOSITY=""

# Check if first argument is a flag or positional
if [[ $# -ge 3 ]] && [[ ! "$1" =~ ^-- ]]; then
  # Positional arguments
  MODEL="$1"
  WORKLOAD="$2"
  CORES="$3"
  shift 3
  # Extract verbosity flag if present, keep rest as extra vars
  for arg in "$@"; do
    if [[ "$arg" =~ ^-v+$ ]]; then
      ANSIBLE_VERBOSITY="$arg"
    else
      EXTRA_VARS="$EXTRA_VARS $arg"
    fi
  done
else
  # Named arguments
  while [[ $# -gt 0 ]]; do
    case $1 in
      --model)
        MODEL="$2"
        shift 2
        ;;
      --workload)
        WORKLOAD="$2"
        shift 2
        ;;
      --cores)
        CORES="$2"
        shift 2
        ;;
      --extra-vars)
        EXTRA_VARS="$2"
        shift 2
        ;;
      -v|-vv|-vvv|-vvvv)
        ANSIBLE_VERBOSITY="$1"
        shift
        ;;
      *)
        echo "Unknown option: $1"
        exit 1
        ;;
    esac
  done
fi

# Validate required arguments
if [[ -z "$MODEL" ]] || [[ -z "$WORKLOAD" ]] || [[ -z "$CORES" ]]; then
  echo "Error: Missing required arguments"
  echo ""
  echo "Usage (positional):"
  echo "  $0 MODEL WORKLOAD CORES [EXTRA_ARGS...] [-v|-vv|-vvv]"
  echo ""
  echo "Usage (named):"
  echo "  $0 --model MODEL --workload WORKLOAD --cores CORES [-v|-vv|-vvv]"
  echo ""
  echo "Options:"
  echo "  -v, -vv, -vvv    Ansible verbosity level (optional)"
  echo ""
  echo "Example:"
  echo "  $0 TinyLlama/TinyLlama-1.1B-Chat-v1.0 chat \"2,4,8,16\""
  echo "  $0 TinyLlama/TinyLlama-1.1B-Chat-v1.0 chat \"2,4,8,16\" -vv"
  exit 1
fi

# Generate test run ID
TEST_RUN_ID=$(date +%Y%m%d-%H%M%S)

# Convert comma-separated cores to array
IFS=',' read -ra CORE_ARRAY <<< "$CORES"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Core Sweep Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Run ID: $TEST_RUN_ID"
echo "Model: $MODEL"
echo "Workload: $WORKLOAD"
echo "Core Counts: ${CORE_ARRAY[*]}"
[[ -n "$ANSIBLE_VERBOSITY" ]] && echo "Ansible Verbosity: $ANSIBLE_VERBOSITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Run test for each core count
# Note: NUMA detection happens within each iteration playbook
TOTAL=${#CORE_ARRAY[@]}
CURRENT=0

for cores in "${CORE_ARRAY[@]}"; do
  CURRENT=$((CURRENT + 1))
  echo
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "[$CURRENT/$TOTAL] Testing with $cores cores"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  ansible-playbook llm-benchmark-auto.yml \
    -e "test_model=$MODEL" \
    -e "workload_type=$WORKLOAD" \
    -e "requested_cores=$cores" \
    -e "test_run_id=$TEST_RUN_ID" \
    $ANSIBLE_VERBOSITY \
    $EXTRA_VARS

  echo "✓ Completed $cores cores"
done

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Collecting Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Collect all results
ansible-playbook collect-sweep-results.yml \
  -e "test_model=$MODEL" \
  -e "workload_type=$WORKLOAD" \
  -e "test_run_id=$TEST_RUN_ID" \
  $ANSIBLE_VERBOSITY

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Core Sweep Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: results/llm/${MODEL//\//__}/$WORKLOAD-$TEST_RUN_ID/"
echo "Core Counts Tested: ${CORE_ARRAY[*]}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
