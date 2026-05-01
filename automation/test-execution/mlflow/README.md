# MLflow Experiment Tracking

MLflow provides experiment tracking and comparison for LLM performance benchmarks.

## Quick Start

```bash
# Launch MLflow server
./launch-mlflow.sh

# Import benchmark results
cd ../ansible/scripts
./mlflow-quick-log.sh --all

# View at http://localhost:5000
```

## Full Documentation

See the complete MLflow guide on GitHub Pages:

**📖 [MLflow Documentation](https://redhat-et.github.io/vllm-cpu-perf-eval/docs/mlflow)**

The documentation covers:
- Quick start guide
- Client-side and server-side metrics tracked
- Using the MLflow UI for comparison and visualization
- Command reference
- Python API usage
- Troubleshooting
- Advanced features

## Files

- `launch-mlflow.sh` - One-command setup and launch
- `stop-mlflow.sh` - Stop MLflow server
- `docker-compose.yml` - MLflow server configuration
- `requirements.txt` - Python dependencies
- `venv/` - Python virtual environment (auto-created)
- `artifacts/` - Experiment artifacts (auto-created)

## Common Commands

```bash
# Management
./launch-mlflow.sh          # Start MLflow
./stop-mlflow.sh            # Stop MLflow

# Import results
cd ../ansible/scripts
./mlflow-quick-log.sh --all     # Import all
./mlflow-quick-log.sh --latest  # Import latest
./mlflow-quick-log.sh --today   # Import today's
```

## Quick Links

- MLflow UI: http://localhost:5000
- Documentation: https://redhat-et.github.io/vllm-cpu-perf-eval/docs/mlflow
- MLflow Official Docs: https://mlflow.org/docs/latest/
