# Results Directory

This directory stores test execution results. It is gitignored except for this
README.

## Structure

Results are organized in multiple ways to facilitate different analysis
patterns:

```text
results/
├── by-phase/              # Organized by test phase
│   ├── phase-1-concurrent/
│   │   ├── llama-3.2-1b/
│   │   │   ├── concurrent-8.json
│   │   │   ├── concurrent-16.json
│   │   │   └── ...
│   │   ├── llama-3.2-3b/
│   │   └── ...
│   └── phase-2-scalability/
│
├── by-model/             # Organized by model
│   ├── llama-3.2-1b/
│   │   ├── phase-1/
│   │   │   ├── concurrent-8.json
│   │   │   └── ...
│   │   ├── phase-2/
│   │   └── phase-3/
│   └── llama-3.2-3b/
│
├── by-host/              # Organized by test host (distributed testing)
│   ├── test-node-01/
│   │   ├── phase-1/
│   │   └── phase-2/
│   └── test-node-02/
│
├── reports/              # Generated reports
│   ├── html/
│   ├── markdown/
│   └── json/
│
├── archives/             # Timestamped archives
│   ├── 2024-02-13_10-30-00/
│   └── 2024-02-14_14-15-00/
│
└── metrics/              # Exported metrics
    └── prometheus/
```text

## Result File Format

Test results are stored in JSON format following GuideLLM's output schema:

```json
{
  "test_info": {
    "model": "llama-3.2-1b",
    "scenario": "concurrent-8",
    "phase": "phase-1-concurrent",
    "timestamp": "2024-02-13T10:30:00Z"
  },
  "metrics": {
    "throughput": 45.3,
    "p50_ttft_ms": 234.5,
    "p95_ttft_ms": 456.7,
    "p99_ttft_ms": 678.9
  },
  "requests": [...]
}
```text

## Viewing Results

### Generate HTML Report

```bash
cd automation/analysis
python generate-report.py \
  --input ../../results/by-phase/phase-1-concurrent \
  --format html \
  --output ../../results/reports/html/phase-1.html
```text

### Compare Results

```bash
python compare-results.py \
  --baseline ../../results/archives/2024-02-13/phase-1 \
  --current ../../results/by-phase/phase-1-concurrent
```text

### GuideLLM CLI

```bash
guidellm report generate \
  --input results/by-phase/phase-1-concurrent/llama-3.2-1b/concurrent-8.json
```text

## Archiving Results

Results can be archived with timestamps for long-term storage:

```bash
# Manual archive
./automation/utilities/archive-results.sh phase-1-concurrent

# Automated archiving (run after test completion)
cd automation/test-execution/ansible
ansible-playbook playbooks/archive-results.yml
```text

## Cleanup

To remove old results and free disk space:

```bash
# Clean results older than 30 days
./automation/utilities/cleanup-results.sh --days 30

# Clean specific phase
./automation/utilities/cleanup-results.sh --phase phase-1-concurrent
```text

## Result Collection (Distributed Testing)

When running distributed tests across multiple nodes, results are
automatically collected:

```bash
cd automation/test-execution/ansible
ansible-playbook playbooks/collect-results.yml
```text

This fetches results from all test nodes to the control node.

## .gitignore

The following patterns are gitignored:

```gitignore
# Ignore all result files
*.json
*.csv
*.html

# But keep README and directory structure
!README.md
!.gitkeep
```text
