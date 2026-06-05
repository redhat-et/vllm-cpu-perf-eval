#!/bin/bash
# Run only the missing MTEB tests to complete the model sweep
# Use this script to finish incomplete test runs

set -e

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
ANSIBLE_DIR="$REPO_ROOT/automation/test-execution/ansible"

# Default configuration
CORES="${CORES:-4}"
DRY_RUN="${DRY_RUN:-false}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "MTEB Missing Tests Runner"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Repo: $REPO_ROOT"
echo "Cores: $CORES"
echo "Dry run: $DRY_RUN"
echo ""

# Test configurations: model|preset|estimated_time|trust_remote_code
TESTS=(
    "RedHatAI/embeddinggemma-300m|reranking|15-20 min|false"
    "RedHatAI/nomic-embed-text-v1.5|reranking|15-20 min|true"
    "RedHatAI/nomic-embed-text-v1.5|pair_classification|10-15 min|true"
    "RedHatAI/Qwen3-Embedding-8B|reranking|80-90 min|false"
    "RedHatAI/Qwen3-Embedding-8B|pair_classification|45-60 min|false"
)

total_tests=${#TESTS[@]}
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Tests to run: $total_tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for test in "${TESTS[@]}"; do
    IFS='|' read -r model preset time trust_code <<< "$test"
    if [ "$trust_code" = "true" ]; then
        echo "  - $(basename $model): $preset (~$time) [trust-remote-code]"
    else
        echo "  - $(basename $model): $preset (~$time)"
    fi
done
echo ""
echo "Estimated total time: ~2.5-3 hours"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$DRY_RUN" = "true" ]; then
    echo "DRY RUN: Commands that would be executed:"
    echo ""
fi

# Track progress
passed=0
failed=0
failed_tests=()

# Run each test
for i in "${!TESTS[@]}"; do
    IFS='|' read -r model preset time trust_code <<< "${TESTS[$i]}"
    test_num=$((i + 1))

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Test $test_num/$total_tests: $(basename $model) - $preset"
    echo "Estimated time: ~$time"
    if [ "$trust_code" = "true" ]; then
        echo "Trust remote code: enabled"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if [ "$DRY_RUN" = "true" ]; then
        echo "Would run:"
        echo "  cd $ANSIBLE_DIR"
        echo "  ansible-playbook -i inventory/hosts.yml mteb-benchmark.yml \\"
        echo "    -e test_model=$model \\"
        echo "    -e mteb_task_preset=$preset \\"
        echo "    -e requested_cores=$CORES \\"
        echo "    -e trust_remote_code=$trust_code"
        echo ""
        continue
    fi

    # Run the test
    start_time=$(date +%s)

    if (cd "$ANSIBLE_DIR" && \
        ansible-playbook -i inventory/hosts.yml mteb-benchmark.yml \
            -e "test_model=$model" \
            -e "mteb_task_preset=$preset" \
            -e "requested_cores=$CORES" \
            -e "trust_remote_code=$trust_code"); then

        end_time=$(date +%s)
        duration=$((end_time - start_time))
        duration_min=$((duration / 60))

        echo ""
        echo "✅ PASSED: $(basename $model) - $preset (${duration_min}m)"
        ((passed++))
    else
        echo ""
        echo "❌ FAILED: $(basename $model) - $preset"
        ((failed++))
        failed_tests+=("$(basename $model) - $preset")
    fi

    # Don't sleep after last test
    if [ $test_num -lt $total_tests ]; then
        echo ""
        echo "Waiting 10 seconds before next test..."
        sleep 10
    fi
done

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Run Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Total: $total_tests tests"
echo "Passed: $passed"
echo "Failed: $failed"

if [ $failed -gt 0 ]; then
    echo ""
    echo "Failed tests:"
    for test in "${failed_tests[@]}"; do
        echo "  ❌ $test"
    done
    echo ""
    echo "Results: $REPO_ROOT/results/mteb/"
    exit 1
else
    echo ""
    echo "🎉 All tests passed!"
    echo "Results: $REPO_ROOT/results/mteb/"
    exit 0
fi
