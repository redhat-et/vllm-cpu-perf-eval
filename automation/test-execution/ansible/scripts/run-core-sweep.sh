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

# Global variables
MODEL=""
WORKLOAD=""
CORES=""
EXTRA_VARS=()
ANSIBLE_VERBOSITY=""

#
# Display usage information
#
show_usage() {
  cat <<EOF
Usage (positional):
  $0 MODEL WORKLOAD CORES [EXTRA_ARGS...] [-v|-vv|-vvv]

Usage (named):
  $0 --model MODEL --workload WORKLOAD --cores CORES [-v|-vv|-vvv]

Arguments:
  MODEL         Model identifier (e.g., "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
  WORKLOAD      Workload type (e.g., "chat", "code", "rag")
  CORES         Comma-separated list of core counts (e.g., "2,4,8,16")

Options:
  --extra-vars  Additional Ansible extra vars (named mode only)
  -v, -vv, -vvv Ansible verbosity level (optional)

Examples:
  $0 TinyLlama/TinyLlama-1.1B-Chat-v1.0 chat "2,4,8,16"
  $0 TinyLlama/TinyLlama-1.1B-Chat-v1.0 chat "2,4,8,16" -vv
  $0 --model meta-llama/Llama-3.2-1B-Instruct --workload rag --cores "8,16,32"
EOF
}

#
# Parse positional arguments
# Args: MODEL WORKLOAD CORES [EXTRA_ARGS...]
#
parse_positional_args() {
  MODEL="$1"
  WORKLOAD="$2"
  CORES="$3"
  shift 3

  # Separate verbosity flags from extra vars
  # Verbosity flags like -v, -vv, -vvv go to ANSIBLE_VERBOSITY
  # All other arguments are treated as extra vars
  for arg in "$@"; do
    if [[ "$arg" =~ ^-v+$ ]]; then
      ANSIBLE_VERBOSITY="$arg"
    else
      EXTRA_VARS+=("$arg")
    fi
  done
}

#
# Parse named arguments
# Args: --model MODEL --workload WORKLOAD --cores CORES [OPTIONS...]
#
parse_named_args() {
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
        EXTRA_VARS+=("$2")
        shift 2
        ;;
      -v|-vv|-vvv|-vvvv)
        ANSIBLE_VERBOSITY="$1"
        shift
        ;;
      -h|--help)
        show_usage
        exit 0
        ;;
      *)
        echo "Error: Unknown option: $1" >&2
        echo "" >&2
        show_usage >&2
        exit 1
        ;;
    esac
  done
}

#
# Validate that all required arguments are provided
#
validate_required_args() {
  local missing=()

  [[ -z "$MODEL" ]] && missing+=("MODEL")
  [[ -z "$WORKLOAD" ]] && missing+=("WORKLOAD")
  [[ -z "$CORES" ]] && missing+=("CORES")

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Error: Missing required arguments: ${missing[*]}" >&2
    echo "" >&2
    show_usage >&2
    exit 1
  fi
}

#
# Parse command line arguments (auto-detect positional vs named)
#
parse_arguments() {
  if [[ $# -eq 0 ]]; then
    show_usage
    exit 1
  fi

  # Check if using positional or named arguments
  # Positional: First arg doesn't start with --
  # Named: First arg starts with --
  if [[ $# -ge 3 ]] && [[ ! "$1" =~ ^-- ]]; then
    parse_positional_args "$@"
  else
    parse_named_args "$@"
  fi

  validate_required_args
}

# Parse command line arguments
parse_arguments "$@"

#
# Generate unique test run identifier
# Format: YYYYMMDD-HHMMSS (e.g., 20260304-143022)
#
TEST_RUN_ID=$(date +%Y%m%d-%H%M%S)

#
# Convert comma-separated cores to array for iteration
# Example: "2,4,8,16" -> ("2" "4" "8" "16")
#
IFS=',' read -ra CORE_ARRAY <<< "$CORES"

#
# Display test configuration
#
print_header() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$1"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

print_header "Core Sweep Test"
echo "Test Run ID: $TEST_RUN_ID"
echo "Model: $MODEL"
echo "Workload: $WORKLOAD"
echo "Core Counts: ${CORE_ARRAY[*]}"
[[ -n "$ANSIBLE_VERBOSITY" ]] && echo "Ansible Verbosity: $ANSIBLE_VERBOSITY"
[[ ${#EXTRA_VARS[@]} -gt 0 ]] && echo "Extra Vars: ${EXTRA_VARS[*]}"
print_header ""
echo

#
# Run benchmark for each core count
# Each iteration runs the full benchmark workflow with a different core allocation
# The test_run_id is shared across all iterations for result aggregation
#
TOTAL=${#CORE_ARRAY[@]}
CURRENT=0

for cores in "${CORE_ARRAY[@]}"; do
  CURRENT=$((CURRENT + 1))
  echo
  print_header "[$CURRENT/$TOTAL] Testing with $cores cores"

  # shellcheck disable=SC2086
  # Note: ANSIBLE_VERBOSITY must be unquoted for proper expansion
  ansible-playbook llm-benchmark-auto.yml \
    -e "test_model=$MODEL" \
    -e "workload_type=$WORKLOAD" \
    -e "requested_cores=$cores" \
    -e "test_run_id=$TEST_RUN_ID" \
    -e "is_core_sweep=true" \
    $ANSIBLE_VERBOSITY \
    "${EXTRA_VARS[@]}"

  echo "✓ Completed $cores cores"
done

#
# Collect and consolidate results from all core count iterations
#
echo
print_header "Collecting Results"

# shellcheck disable=SC2086
ansible-playbook collect-sweep-results.yml \
  -e "test_model=$MODEL" \
  -e "workload_type=$WORKLOAD" \
  -e "test_run_id=$TEST_RUN_ID" \
  $ANSIBLE_VERBOSITY

#
# Display completion summary
#
echo
print_header "✓ Core Sweep Complete!"
echo "Results: results/llm/${MODEL//\//__}/$WORKLOAD-$TEST_RUN_ID/"
echo "Core Counts Tested: ${CORE_ARRAY[*]}"
echo "Total Configurations: ${#CORE_ARRAY[@]}"
print_header ""
