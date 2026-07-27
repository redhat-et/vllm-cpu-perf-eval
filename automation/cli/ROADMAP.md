# cpueval Roadmap

Product vision: **Thin friction-free launcher** for bare-metal CPU benchmarking. Analytics and trending belong in Streamlit/PSAP/FORGE, not the CLI.

---

## Next Release (v0.2.0)

### 1. Config File Support ✨ **Highest UX Win**

**Problem:** Setting env vars every time is the #1 friction point.

**Solution:** Load `~/.config/cpueval/config.yaml` or `./.cpueval.yaml`

```yaml
# ~/.config/cpueval/config.yaml or .cpueval.yaml (project-level)
dut_hostname: ec2-52-16-102-83.eu-west-1.compute.amazonaws.com
loadgen_hostname: same  # Special value → copy dut_hostname
hf_token: hf_xxxxx
ansible_ssh_key: ~/eu-mtahhan.pem

defaults:
  cores: 16
  workload: chat

presets:
  aws-prod:
    dut_hostname: prod-dut
    vllm_container_image: custom:latest
```

**Behavior:**
- Load order: default config → project `.cpueval.yaml` → env vars (env wins)
- `--preset NAME` loads `presets.NAME` section
- Doctor checks for config file and suggests creating one

**Estimate:** ~4 hours

---

### 2. Shell Completion ✨ **Daily Quality of Life**

**Implementation:** Typer built-in

```bash
# Add to README
cpueval --install-completion  # One-time setup

# Then enjoy:
cpueval run --suite <TAB>           # concurrent-load, chat-smoke, audio...
cpueval run --suite audio --scenario <TAB>  # transcription-throughput, quick-test...
cpueval run --profile <TAB>         # dual-socket-split, ...
```

**Estimate:** ~1 hour (Typer does the work)

---

### 3. Pre-Run Validation (Extend Doctor) ✅ **Fail Fast**

**Do validate:**
- Required suite params present (model, cores, scenario)
- `cores > 0` and `cores` is reasonable (< system max)
- Playbook file exists
- Inventory/env configured (already in doctor)

**Skip (or make optional `--check-hf`):**
- ❌ HF "model exists" check — needs network, false-negatives on private/RHAIIS models
- ❌ Runtime estimation — too guessy without suite-specific logic

**Estimate:** ~2 hours

---

### 4. Wire RHAIIS Sweep Suite 🔄 **Native Batch Support**

**Current:** `run-rhaiis-concurrent-load.sh` sweeps models/cores/workloads in bash.

**Solution:** Make it accessible via cpueval

**Option A - Script wrapper (quick):**
```bash
# automation/cli/suites/rhaiis-sweep.yaml
name: rhaiis-sweep
runner: script
target: automation/test-execution/scripts/bash/run-rhaiis-concurrent-load.sh
```

**Option B - Thin Python loop (cleaner):**
```bash
./cpueval run --suite concurrent-load \
  --model "RedHatAI/Llama-3.1-8B-w4a16,RedHatAI/Qwen3-8B-w4a16" \
  --cores "8,16,32" \
  --workload "chat,rag"

# Loops: for model in models; for cores in cores; ansible-playbook ...
```

**Estimate:** ~3 hours

---

### 5. Results Comparison (Simple) 📊 **Side-by-Side Diff**

```bash
./cpueval results diff <run-id-1> <run-id-2>

# Output:
┏━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┓
┃ Concurrency ┃ Run 1     ┃ Run 2     ┃ Δ%      ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━┩
│ Tok/s (8)   │ 283.42    │ 310.15    │ +9.4%   │
│ TTFT (8)    │ 12262 ms  │ 11450 ms  │ -6.6%   │
└─────────────┴───────────┴───────────┴─────────┘
```

Keep simple — just concurrency table diff. No trend analysis.

**Estimate:** ~3 hours

---

## Later / Nice-to-Have

### Export Formats (JSON/CSV)

**Need:** Scripting automation over results.

```bash
./cpueval results --last --format json > results.json
```

**Why later:** You have `convert_batch.py` + Streamlit for CSV export. Only add if automation needs raw CLI JSON.

---

### Progress Indicators

**Problem:** Long runs feel silent.

**Why later:**
- Ansible/GuideLLM already stream detailed logs
- A spinner that hides TASK output hurts debugging
- Only add if playbooks emit clear phase markers we can parse

---

### ❌ Skip These (Covered Elsewhere)

| Feature | Why Skip |
|---------|----------|
| Test templates | Already have: suite defaults + `--profile` + `--extra-vars-file`. That IS templates. |
| Historical trending | Belongs in Streamlit / MLflow / PSAP / FORGE Caliper, not CLI |
| HF model validation | Network call, false-negatives on RHAIIS/private models |
| Runtime estimation | Too guessy without per-suite calibration |

---

## Summary Priority

**v0.2.0 (Next):**
1. Config file (~4h) ✨
2. Shell completion (~1h) ✨
3. Extended validation (~2h) ✅
4. RHAIIS sweep suite (~3h) 🔄
5. Simple diff (~3h) 📊

**Total:** ~13 hours for high-impact UX improvements.

**Later:** Export formats (if needed for automation).

**Skip:** Templates (redundant), trending (dashboard's job), HF validation (false-negatives).
