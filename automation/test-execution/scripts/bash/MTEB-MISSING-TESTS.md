# Run Missing MTEB Tests

Quick script to complete the MTEB model sweep by running only the tests that failed or weren't completed.

## Tests Included

1. **RedHatAI/embeddinggemma-300m** - reranking (~15-20 min)
2. **RedHatAI/nomic-embed-text-v1.5** - reranking (~15-20 min) *requires trust_remote_code*
3. **RedHatAI/nomic-embed-text-v1.5** - pair_classification (~10-15 min) *requires trust_remote_code*
4. **RedHatAI/Qwen3-Embedding-8B** - reranking (~80-90 min)
5. **RedHatAI/Qwen3-Embedding-8B** - pair_classification (~45-60 min)

**Total estimated time: ~2.5-3 hours**

**Note:** The script automatically handles `trust_remote_code=true` for models that require custom code execution (nomic-embed-text-v1.5).

## Usage

### Test Run (Dry-run mode)
```bash
cd automation/test-execution/scripts/bash
DRY_RUN=true ./run-mteb-missing-tests.sh
```

### Actual Run
```bash
cd automation/test-execution/scripts/bash
./run-mteb-missing-tests.sh
```

### Custom Core Count
```bash
CORES=8 ./run-mteb-missing-tests.sh
```

## What Happens

1. Runs each test sequentially
2. Tracks pass/fail status
3. Waits 10 seconds between tests
4. Shows progress with timing
5. Provides final summary with results location

## Results

Results are saved to: `results/mteb/`

Directory structure:
```
results/mteb/
├── RedHatAI__embeddinggemma-300m/
│   └── TIMESTAMP/
│       ├── AskUbuntuDupQuestions/test.json
│       ├── MindSmallReranking/test.json
│       └── StackOverflowDupQuestions/test.json
├── RedHatAI__nomic-embed-text-v1.5/
│   └── TIMESTAMP/
│       └── ...
└── RedHatAI__Qwen3-Embedding-8B/
    └── TIMESTAMP/
        └── ...
```

## AWS Tips

To prevent SSH disconnects during long tests:

1. **Use tmux/screen** (recommended):
   ```bash
   tmux new -s mteb-tests
   ./run-mteb-missing-tests.sh
   # Ctrl+B, then D to detach
   # tmux attach -t mteb-tests to reattach
   ```

2. **Use nohup**:
   ```bash
   nohup ./run-mteb-missing-tests.sh > mteb-tests.log 2>&1 &
   tail -f mteb-tests.log
   ```

3. **Configure SSH keepalive** in `~/.ssh/config`:
   ```
   Host *
     ServerAliveInterval 60
     ServerAliveCountMax 10
   ```

## Checking Progress

While tests run, check results:
```bash
# On guidellm-client machine
ls -lR /tmp/mteb-results/

# Locally (after fetch)
ls -lR results/mteb/
```

## After Completion

Once all tests pass, view results in dashboard:
```bash
cd automation/test-execution/dashboard-examples/vllm_dashboard
streamlit run Home.py
# Navigate to: 📊 Embedding Metrics → 🎯 MTEB Quality
```
