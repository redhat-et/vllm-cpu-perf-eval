#!/bin/bash
#
# Test all parameter combinations for concurrent load playbook
# Runs syntax checks and lists tasks without executing anything
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$SCRIPT_DIR/../automation/test-execution/ansible"
cd "$ANSIBLE_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Create temporary inventory
TMP_INVENTORY=$(mktemp -d)
trap "rm -rf $TMP_INVENTORY" EXIT

cat > "$TMP_INVENTORY/hosts.yml" <<EOF
all:
  children:
    dut:
      hosts:
        test-dut:
          ansible_host: 192.168.1.100
          ansible_user: test
          ansible_ssh_private_key_file: /dev/null
    load_generator:
      hosts:
        test-loadgen:
          ansible_host: 192.168.1.101
          ansible_user: test
          ansible_ssh_private_key_file: /dev/null
EOF

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    shift
    local extra_vars=("$@")

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Test $TOTAL_TESTS: $test_name${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Build command
    local cmd="ansible-playbook llm-benchmark-concurrent-load.yml -i $TMP_INVENTORY/hosts.yml"
    for var in "${extra_vars[@]}"; do
        cmd="$cmd -e \"$var\""
    done

    echo "Parameters:"
    for var in "${extra_vars[@]}"; do
        echo "  - $var"
    done
    echo ""

    # Run syntax check
    echo -e "${YELLOW}Running syntax check...${NC}"
    if eval "$cmd --syntax-check" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Syntax check passed${NC}"
    else
        echo -e "${RED}✗ Syntax check failed${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi

    # List tasks
    echo -e "${YELLOW}Listing tasks...${NC}"
    if eval "$cmd --list-tasks" 2>&1 | head -20; then
        echo -e "${GREEN}✓ Task listing successful${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ Task listing failed${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}Concurrent Load Playbook - Parameter Combination Tests${NC}"
echo -e "${GREEN}======================================================${NC}"

# Single core configurations
run_test "Single Core - Chat - All Phases" \
    "test_model=test/model" \
    "base_workload=chat" \
    "requested_cores=16"

run_test "Single Core - Chat - Phase 1 Only" \
    "test_model=test/model" \
    "base_workload=chat" \
    "requested_cores=16" \
    "skip_phase_2=true" \
    "skip_phase_3=true"

run_test "Single Core - Code - All Phases" \
    "test_model=test/model" \
    "base_workload=code" \
    "requested_cores=32"

run_test "Single Core - RAG" \
    "test_model=test/model" \
    "base_workload=rag" \
    "requested_cores=16"

# Core sweep configurations
run_test "Core Sweep - Chat - All Phases" \
    "test_model=test/model" \
    "base_workload=chat" \
    "core_sweep_counts=[16,32,64]"

run_test "Core Sweep - Chat - Phase 1 Only" \
    "test_model=test/model" \
    "base_workload=chat" \
    "core_sweep_counts=[16,32]" \
    "skip_phase_2=true" \
    "skip_phase_3=true"

run_test "Core Sweep - Code - Phase 1+2" \
    "test_model=test/model" \
    "base_workload=code" \
    "core_sweep_counts=[16,32,64]" \
    "skip_phase_3=true"

# With custom rate configurations
run_test "Single Core - Custom Rates" \
    "test_model=test/model" \
    "base_workload=chat" \
    "requested_cores=16" \
    "guidellm_rate=[1,2,4,8]" \
    "skip_phase_2=true" \
    "skip_phase_3=true"

run_test "Core Sweep - Custom Duration" \
    "test_model=test/model" \
    "base_workload=chat" \
    "core_sweep_counts=[16,32]" \
    "guidellm_max_seconds=300" \
    "skip_phase_2=true" \
    "skip_phase_3=true"

# Variable workloads
run_test "Single Core - All Phases with Variable Workload" \
    "test_model=test/model" \
    "base_workload=chat" \
    "requested_cores=16" \
    "skip_phase_1=true"

run_test "Core Sweep - Production Only (Phase 3)" \
    "test_model=test/model" \
    "base_workload=code" \
    "core_sweep_counts=[32,64]" \
    "skip_phase_1=true" \
    "skip_phase_2=true"

# Summary
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Test Summary${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Total tests:  $TOTAL_TESTS"
echo -e "${GREEN}Passed:       $PASSED_TESTS${NC}"
if [ $FAILED_TESTS -gt 0 ]; then
    echo -e "${RED}Failed:       $FAILED_TESTS${NC}"
    exit 1
else
    echo -e "${GREEN}Failed:       $FAILED_TESTS${NC}"
    echo ""
    echo -e "${GREEN}✓ All parameter combination tests passed!${NC}"
    exit 0
fi
