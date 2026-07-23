# Python Scripts Organization

This directory contains Python scripts for benchmark processing, result conversion, and automation tasks.

## Directory Structure

```
scripts/
├── ansible/              # Scripts invoked by Ansible playbooks
│   ├── extract_benchmark_timings.py   # Extract per-benchmark timing data
│   ├── log_to_mlflow.py               # Log results to MLflow tracking
│   ├── audio_enterprise_report.py     # Audio enterprise metrics report (CLI)
│   └── evaluate_audio_quality.py      # Audio transcription WER/CER evaluator
└── conversion/           # Result conversion utilities
    ├── view_results.py                # Terminal results viewer (LLM + embedding)
    ├── convert_embedding_results.py   # Convert embedding JSON to CSV
    ├── convert_batch.py               # Batch convert LLM results
    └── convert_single.py              # Convert single LLM result file
```

## Ansible Scripts

### extract_benchmark_timings.py

Extracts per-benchmark timing information from `benchmarks.json` and adds it to `test-metadata.json`.

**Usage:**
```bash
python3 extract_benchmark_timings.py <benchmarks.json> <test-metadata.json>
```

**Used by:**
- `automation/test-execution/ansible/llm-benchmark.yml`
- `automation/test-execution/ansible/llm-benchmark-auto.yml`
- `automation/test-execution/ansible/scripts/extract-all-timings.sh`

### log_to_mlflow.py

Logs benchmark results and server metrics to MLflow for experiment tracking.

**Usage:**
```bash
python3 log_to_mlflow.py <benchmarks.json> <metadata.json> \
  [-e EXPERIMENT_NAME] [-r RUN_NAME] [-u TRACKING_URI] \
  [--log-per-load-point]
```

**Used by:**
- `automation/test-execution/ansible/log-to-mlflow.yml`

### audio_enterprise_report.py

Prints a plain-text enterprise summary of audio benchmark results (capacity,
sizing, efficiency, warmup, quality).

**Usage:**
```bash
python3 audio_enterprise_report.py RESULTS_DIR [--p95-target 2.0] [--json]
python3 audio_enterprise_report.py RESULTS_DIR --eta-files 100000 --eta-audio-hours 500
```

**Used by:**
- `automation/test-execution/ansible/audio-benchmark.yml` (Play 5 — prints automatically)
- Operators directly (standalone CLI)

### evaluate_audio_quality.py

Sends audio clips to a vLLM `/v1/audio/transcriptions` endpoint, computes
WER/CER against ground truth using [jiwer](https://github.com/jitsi/jiwer),
and writes `quality-results.json`.

**Prerequisites:** `pip install jiwer datasets soundfile requests`

**Usage:**
```bash
python3 evaluate_audio_quality.py \
  --endpoint http://dut:8000 \
  --output-dir results/audio-models/openai__whisper-small/transcription-quality-run/ \
  --model openai/whisper-small \
  --num-clips 50
```

**Used by:**
- Operators after running `transcription-quality` scenario
- Dashboard Quality tab (reads `quality-results.json`)

## Conversion Scripts

### view_results.py

Displays benchmark results as a formatted table in the terminal.
Auto-detects LLM (GuideLLM) vs embedding (vllm bench serve) format.

**Usage:**
```bash
# LLM results
python3 view_results.py <path/to/benchmarks.json>
python3 view_results.py <path/to/results-directory/>

# Embedding results
python3 view_results.py <path/to/embedding-test-run-dir/>

# Suppress metadata header
python3 view_results.py --no-header <path>
```

**Used by:**
- `automation/test-execution/ansible/llm-benchmark.yml`
- `automation/test-execution/ansible/llm-benchmark-auto.yml`
- `automation/test-execution/ansible/embedding-benchmark.yml`

See [Terminal Results Viewer](../../../docs/terminal-results-viewer.md)
for full documentation.

### convert_embedding_results.py

Converts embedding benchmark JSON results to CSV format for analysis.

**Usage:**
```bash
python3 convert_embedding_results.py <results_directory> -o <output.csv>
```

### convert_batch.py

Batch processes all CPU benchmark results from the `results/llm/` directory.

**Usage:**
```bash
python3 convert_batch.py
```

Creates `managed_cpu_benchmarks.csv` and `external_cpu_benchmarks.csv`.

### convert_single.py

Converts individual GuideLLM 0.5.x+ benchmark JSON to CSV (CPU-specific).

**Usage:**
```bash
python3 convert_single.py <benchmark.json> -m <metadata.json> -o <output.csv>
```

**Used by:**
- `convert_batch.py` (via subprocess)

## Shared Libraries

Common utilities are available in `automation/test-execution/shared/`:

- **io_utils.py**: JSON loading (`load_json_file`), saving (`save_json_file`), time formatting (`format_duration`)
- **vllm_metrics.py**: vLLM Prometheus metrics parsing helpers

**Importing shared utilities:**

Due to the hyphen in `test-execution`, standard dotted imports don't work. Scripts use sys.path manipulation:

```python
import sys
from pathlib import Path

# Add shared library to path
_script_dir = Path(__file__).parent
_shared_dir = _script_dir.parent.parent / "shared"
sys.path.insert(0, str(_shared_dir))

from io_utils import load_json_file, save_json_file, format_duration  # noqa: E402
```

**For pytest tests:** The root `conftest.py` adds the project root to sys.path automatically, enabling imports to work without manual path manipulation.

## Development

All Python scripts should be run from the project root directory to ensure proper module imports:

```bash
cd /path/to/mt-perf-eval
python3 automation/test-execution/scripts/ansible/extract_benchmark_timings.py ...
```

The root `conftest.py` adds the project root to `PYTHONPATH` for pytest, enabling absolute imports in tests.
