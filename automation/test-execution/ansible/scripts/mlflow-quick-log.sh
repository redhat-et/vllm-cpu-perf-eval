#!/bin/bash
# Quick MLflow logging helper script
# Usage: ./mlflow-quick-log.sh [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAYBOOK_DIR="${SCRIPT_DIR}/.."
RESULTS_BASE="${PLAYBOOK_DIR}/../../../results/llm"
MLFLOW_DIR="${PLAYBOOK_DIR}/../mlflow"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
MLFLOW_URI="${MLFLOW_TRACKING_URI:-http://localhost:5000}"
MODE="latest"

# Help text
show_help() {
    cat << EOF
MLflow Quick Logging Helper

Usage: $(basename "$0") [OPTIONS]

OPTIONS:
    -l, --latest              Log the most recent test result (default)
    -a, --all                 Batch import all results
    -t, --today               Log all results from today
    -m, --model MODEL         Filter by model name (for batch import)
    -w, --workload WORKLOAD   Filter by workload type (for batch import)
    -f, --file BENCH_FILE     Log specific benchmarks.json file
    -u, --uri URI             MLflow tracking URI (default: $MLFLOW_URI)
    -h, --help                Show this help message

EXAMPLES:
    # Log the latest test
    $(basename "$0") --latest

    # Batch import all results
    $(basename "$0") --all

    # Import all Llama results
    $(basename "$0") --all --model Llama-3.1

    # Import all chat workloads
    $(basename "$0") --all --workload chat

    # Log a specific result
    $(basename "$0") --file results/llm/model/workload/128c/benchmarks.json

    # Use remote MLflow server
    $(basename "$0") --latest --uri http://mlflow-server:5000

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -l|--latest)
            MODE="latest"
            shift
            ;;
        -a|--all)
            MODE="all"
            shift
            ;;
        -t|--today)
            MODE="today"
            shift
            ;;
        -m|--model)
            MODEL_FILTER="$2"
            shift 2
            ;;
        -w|--workload)
            WORKLOAD_FILTER="$2"
            shift 2
            ;;
        -f|--file)
            BENCH_FILE="$2"
            MODE="file"
            shift 2
            ;;
        -u|--uri)
            MLFLOW_URI="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            ;;
    esac
done

# Export MLflow URI
export MLFLOW_TRACKING_URI="$MLFLOW_URI"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}MLflow Quick Logging${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Tracking URI: ${YELLOW}${MLFLOW_URI}${NC}"
echo -e "Mode: ${YELLOW}${MODE}${NC}"

# Activate MLflow venv if it exists
if [ -f "${MLFLOW_DIR}/venv/bin/activate" ]; then
    source "${MLFLOW_DIR}/venv/bin/activate"
    echo -e "Python: ${YELLOW}MLflow venv${NC}"
else
    echo -e "${YELLOW}Note: MLflow venv not found. Using system Python.${NC}"
    echo -e "Run: cd ${MLFLOW_DIR} && ./launch-mlflow.sh"
fi

# Check if MLflow is accessible
if [[ "$MLFLOW_URI" == http* ]]; then
    echo -n "Checking MLflow server... "
    if curl -s -f "${MLFLOW_URI}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Connected${NC}"
    else
        echo -e "${RED}✗ Not accessible${NC}"
        echo -e "${YELLOW}Warning: MLflow server may not be running${NC}"
        echo "Start it with: cd automation/test-execution/mlflow && docker-compose up -d"
        exit 1
    fi
fi

cd "$PLAYBOOK_DIR"

case $MODE in
    latest)
        echo -e "\n${YELLOW}Finding latest test result...${NC}"
        LATEST_BENCH=$(find "$RESULTS_BASE" -name "benchmarks.json" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2)

        if [ -z "$LATEST_BENCH" ]; then
            echo -e "${RED}No benchmark results found in $RESULTS_BASE${NC}"
            exit 1
        fi

        LATEST_META="${LATEST_BENCH%/*}/test-metadata.json"

        echo -e "Found: ${GREEN}${LATEST_BENCH}${NC}"

        ansible-playbook log-to-mlflow.yml \
            -e "benchmarks_file=${LATEST_BENCH}" \
            -e "metadata_file=${LATEST_META}" \
            -e "mlflow_tracking_uri=${MLFLOW_URI}"
        ;;

    all)
        echo -e "\n${YELLOW}Batch importing all results...${NC}"
        EXTRA_ARGS=""

        if [ -n "$MODEL_FILTER" ]; then
            echo -e "Model filter: ${GREEN}${MODEL_FILTER}${NC}"
            EXTRA_ARGS="${EXTRA_ARGS} -e model_filter=${MODEL_FILTER}"
        fi

        if [ -n "$WORKLOAD_FILTER" ]; then
            echo -e "Workload filter: ${GREEN}${WORKLOAD_FILTER}${NC}"
            EXTRA_ARGS="${EXTRA_ARGS} -e workload_filter=${WORKLOAD_FILTER}"
        fi

        ansible-playbook log-to-mlflow.yml \
            -e "batch_import=true" \
            -e "mlflow_tracking_uri=${MLFLOW_URI}" \
            ${EXTRA_ARGS}
        ;;

    today)
        echo -e "\n${YELLOW}Importing results from today...${NC}"
        COUNT=0

        while IFS= read -r bench; do
            meta="${bench%/*}/test-metadata.json"
            if [ -f "$meta" ]; then
                echo -e "Logging: ${GREEN}$(basename $(dirname "$bench"))${NC}"
                ansible-playbook log-to-mlflow.yml \
                    -e "benchmarks_file=${bench}" \
                    -e "metadata_file=${meta}" \
                    -e "mlflow_tracking_uri=${MLFLOW_URI}" \
                    --quiet
                ((COUNT++))
            fi
        done < <(find "$RESULTS_BASE" -name "benchmarks.json" -type f -mtime -1)

        echo -e "\n${GREEN}✓ Logged ${COUNT} test(s) from today${NC}"
        ;;

    file)
        if [ ! -f "$BENCH_FILE" ]; then
            echo -e "${RED}File not found: $BENCH_FILE${NC}"
            exit 1
        fi

        META_FILE="${BENCH_FILE%/*}/test-metadata.json"

        if [ ! -f "$META_FILE" ]; then
            echo -e "${RED}Metadata file not found: $META_FILE${NC}"
            exit 1
        fi

        echo -e "Logging: ${GREEN}${BENCH_FILE}${NC}"

        ansible-playbook log-to-mlflow.yml \
            -e "benchmarks_file=${BENCH_FILE}" \
            -e "metadata_file=${META_FILE}" \
            -e "mlflow_tracking_uri=${MLFLOW_URI}"
        ;;
esac

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ MLflow logging complete${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "View results at: ${YELLOW}${MLFLOW_URI}${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
