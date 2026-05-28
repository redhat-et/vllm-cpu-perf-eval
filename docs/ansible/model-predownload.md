# Model Pre-Download Documentation

## Overview

Models are automatically pre-downloaded to the persistent cache **before** vLLM starts, eliminating download delays during container initialization.

## Container Image Pinning

The model-downloader image is pinned to a specific SHA digest (`@sha256:...`) rather than a version tag for maximum immutability and reproducibility:

- **SHA digests are immutable** - Once published, they can never change
- **Prevents supply chain attacks** - Tags like `:latest` can be overwritten; digests cannot
- **Exact reproducibility** - Same digest always pulls identical image bits
- **Production best practice** - Recommended by Kubernetes and security guidelines

To update to a newer image, query the registry and update the SHA:
```bash
curl -sL "https://quay.io/api/v1/repository/vllm-cpu-perf-eval/model-downloader/tag/?onlyActiveTags=true" | \
  python3 -m json.tool | grep -A2 '"name": "latest"' | grep manifest_digest
```

## Why Use the Container Instead of CLI?

The model pre-download uses the `quay.io/vllm-cpu-perf-eval/model-downloader` container rather than installing `huggingface-cli` directly on the DUT for several important reasons:

### 1. **Restricted DUT Environments**
- DUT systems may have restricted package installation capabilities
- Cannot assume pip/Python package management is available
- Production systems often prohibit direct package installation for security/compliance

### 2. **Consistent Tooling**
- Container provides versioned, immutable tooling
- Same download behavior across all DUT environments
- No dependency conflicts with host system packages

### 3. **Infrastructure Alignment**
- All other components (vLLM, benchmarks) already run in containers
- Maintains architectural consistency
- Leverages existing container runtime infrastructure

### 4. **Isolation**
- Download dependencies isolated from host system
- No risk of polluting DUT system packages
- Clean separation of concerns

## When Model Pre-Download Runs

The model pre-download task (`download-model.yml`) runs when:

- ✅ `use_persistent_cache: true` is set
- ✅ vLLM is running locally on DUT (not external mode)
- ✅ Model is not already cached or `force_model_download: true`

The task is **automatically skipped** when:

- ❌ `use_persistent_cache: false` (no caching)
- ❌ `vllm_mode: external` (vLLM running elsewhere - handled by playbook-level `end_play`)
- ❌ Model already exists in cache (unless `force_model_download: true`)

## Configuration Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `test_model` | HuggingFace model ID | `meta-llama/Llama-3.1-8B-Instruct` |
| `model_cache_dir` | Persistent cache directory | `/mnt/storage/hf-cache` |
| `use_persistent_cache` | Enable persistent caching | `true` |
| `hf_token` | HuggingFace token (for gated models) | `hf_xxx...` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `model_downloader_image` | `quay.io/vllm-cpu-perf-eval/model-downloader@sha256:ef8bf007...` | Container image for downloads (pinned to SHA digest for immutability) |
| `force_model_download` | `false` | Force re-download even if cached |
| `model_download_min_space_gb` | `50` | Minimum free disk space (GB) required before download |
| `model_download_retries` | `3` | Number of retry attempts for failed downloads |
| `model_download_retry_delay` | `30` | Delay in seconds between retry attempts |

## How It Works

### 1. Cache Check
```yaml
- Check if model exists: {{ model_cache_dir }}/hub/models--{{ test_model | replace('/', '--') }}
- Display cache status
- Skip download if cached (unless force_model_download: true)
```

### 2. Disk Space Check
```yaml
- Check available disk space in {{ model_cache_dir }}
- Fail if available space < {{ model_download_min_space_gb }}GB (default: 50GB)
- Prevents partial downloads due to disk exhaustion
```

### 3. Download Execution
```yaml
- Pull model-downloader container image (pinned to SHA digest for immutability)
- Run container with:
  - Volume: {{ model_cache_dir }}:/cache:z (SELinux compatible)
  - Env: MODEL_NAME={{ test_model }}
  - Env: HF_TOKEN={{ hf_token }}
  - Env: HF_HOME=/cache
  - Command: /usr/local/bin/download_model.py {{ test_model }}
- Retry logic: Up to 3 attempts with 30s delay between retries
```

### 4. Verification
```yaml
- Verify model cache exists after download
- Fail with helpful error message if download unsuccessful
```

## Cache Directory Structure

HuggingFace uses the following cache structure:

```
{{ model_cache_dir }}/
└── hub/
    ├── models--meta-llama--Llama-3.1-8B-Instruct/
    │   ├── snapshots/
    │   │   └── <commit-hash>/
    │   │       ├── config.json
    │   │       ├── tokenizer.json
    │   │       ├── model-*.safetensors
    │   │       └── ...
    │   └── refs/
    ├── models--ibm-granite--granite-embedding-278m-multilingual/
    │   └── ...
    └── ...
```

## Benefits

- ✅ **Faster test execution** - No download wait time on repeated runs
- ✅ **More reliable tests** - Network issues won't interrupt running tests
- ✅ **Bandwidth savings** - Download once, use many times
- ✅ **Better CI/CD integration** - Pre-download in setup phase
- ✅ **Support for offline testing** - Models cached before network disconnection
- ✅ **Automatic retry logic** - Transient network failures are automatically retried
- ✅ **Disk space protection** - Pre-flight checks prevent partial downloads

## Troubleshooting

### Download Fails

**Check:**
1. `HF_TOKEN` is valid (required for gated models like Llama)
2. Model ID is correct: `{{ test_model }}`
3. Network connectivity to `huggingface.co`
4. Available disk space in `{{ model_cache_dir }}`

**View download logs:**
```bash
journalctl -u podman -f | grep model-downloader
```

### Model Not Found After Download

**Verify cache structure:**
```bash
ls -la {{ model_cache_dir }}/hub/models--{{ test_model | replace('/', '--') }}
```

**Force re-download:**
```bash
ansible-playbook ... -e force_model_download=true
```

### Disk Space Issues

**Check available space:**
```bash
df -h {{ model_cache_dir }}
```

**Adjust minimum space requirement:**
```bash
ansible-playbook ... -e model_download_min_space_gb=100
```

### Permission Issues

**Ensure cache directory has correct permissions:**
```bash
chmod 755 {{ model_cache_dir }}
```

## Example Playbook Usage

```yaml
- name: Run vLLM benchmarks with pre-downloaded models
  hosts: dut
  vars:
    use_persistent_cache: true
    model_cache_dir: /mnt/nvme/hf-cache
    test_model: meta-llama/Llama-3.1-8B-Instruct
    hf_token: "{{ lookup('env', 'HF_TOKEN') }}"
  roles:
    - vllm_server
```

## Integration Points

The model pre-download is integrated into:

- [`start-llm.yml`](../../automation/test-execution/ansible/roles/vllm_server/tasks/start-llm.yml) - LLM generative model workflows
- [`start-embedding.yml`](../../automation/test-execution/ansible/roles/vllm_server/tasks/start-embedding.yml) - Embedding model workflows

Both include the download task after directory creation and before vLLM container startup.

## Related Files

- [`download-model.yml`](../../automation/test-execution/ansible/roles/vllm_server/tasks/download-model.yml) - Main download task
- [`/container-images/model-downloader/`](/container-images/model-downloader/) - Container source code
- [`/container-images/model-downloader/download_model.py`](/container-images/model-downloader/download_model.py) - Download script
