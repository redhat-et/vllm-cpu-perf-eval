# AWX Test Execution for vLLM Performance Testing

Complete guide for setting up and running vLLM performance tests using AWX (Ansible AWX).

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Initial Setup](#initial-setup)
4. [Execution Environment](#execution-environment)
5. [Running Tests](#running-tests)
6. [Working with Credentials](#working-with-credentials)
7. [Customizing Tests](#customizing-tests)
8. [Viewing Results](#viewing-results)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Topics](#advanced-topics)

---

## Overview

This directory contains everything needed to run vLLM performance tests through AWX:

- **AWX Deployment**: KIND cluster setup with AWX operator
- **Custom Execution Environment**: Container image with required Ansible collections
- **Job Templates**: Pre-configured test workflows
- **Automation**: Single-command configuration and deployment

### What is AWX?

AWX is the open-source version of Ansible Automation Platform. It provides:
- Web UI for launching Ansible playbooks
- Job scheduling and tracking
- Credential management
- Result history and logging

### Architecture

```
┌─────────────────────────────────────────┐
│  AWX Web UI (localhost:30080)           │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  AWX Operator (in KIND cluster)         │
│  - Manages AWX deployment                │
│  - Handles upgrades                      │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  AWX Pods                                │
│  ├─ awx-web                             │
│  ├─ awx-task (runs jobs here)           │
│  └─ awx-postgres                        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Job Execution (vllm-awx-ee container)  │
│  ├─ Run Ansible playbook                │
│  ├─ SSH to DUT and loadgen hosts        │
│  ├─ Start vLLM container on DUT         │
│  ├─ Run GuideLLM benchmark on loadgen   │
│  └─ Collect and fetch results           │
└─────────────────────────────────────────┘
```

---

## Quick Start

### Local KIND Cluster (Recommended for Testing)

```bash
# From automation/test-execution/awx directory
cd automation/test-execution/awx

# Deploy everything
make kind-quickstart
```

This will:
1. Create a local KIND cluster
2. Deploy AWX operator
3. Build custom execution environment
4. Deploy AWX with pre-configured job templates
5. Configure inventories and credentials

**Access AWX:** <http://localhost:30080>

- Username: `admin`
- Password: `password` <!-- pragma: allowlist secret -->

### Configure for Your Infrastructure

```bash
# Set environment variables
export CONTROLLER_HOST=http://localhost:30080
export CONTROLLER_USERNAME=admin
export CONTROLLER_PASSWORD=password

# Your infrastructure
export DUT_HOSTNAME=ec2-3-144-81-209.us-east-2.compute.amazonaws.com
export LOADGEN_HOSTNAME=ec2-13-59-250-172.us-east-2.compute.amazonaws.com
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_SSH_KEY=~/mtahhan.pem
export HF_TOKEN=$(cat ~/hf_token)

# Optional: Container images (defaults provided)
export VLLM_IMAGE=public.ecr.aws/q9t5s3a7/vllm-cpu-release-repo:v0.15.0
export GUIDELLM_IMAGE=ghcr.io/vllm-project/guidellm:v0.5.3

# Optional: Test defaults
export TEST_MODEL=meta-llama/Llama-3.2-1B-Instruct
export BASE_WORKLOAD=chat
export REQUESTED_CORES=16

# Configure AWX
ansible-playbook configure-awx.yml
```

---

## Initial Setup

### Prerequisites

- **Docker** or **Podman**
- **kubectl**
- **KIND** (Kubernetes in Docker)
- **ansible-builder** (for custom execution environment)
- **Python 3.9+** with `ansible` and `awx.awx` collection

### Install Dependencies

```bash
# macOS
brew install kind kubectl

# Install Ansible and AWX collection
pip3 install ansible
ansible-galaxy collection install awx.awx

# Install ansible-builder (for custom EE)
pip3 install ansible-builder
```

### File Structure

```
automation/test-execution/awx/
├── README.md                   # This file
├── configure-awx.yml          # AWX setup playbook
├── execution-environment.yml  # Custom EE definition
├── requirements.yml           # Ansible collections for EE
├── Makefile                   # Build/deploy commands
├── awx-instance.yaml          # AWX deployment spec
└── kind-cluster.yaml          # KIND cluster configuration
```

### Verify Setup

1. Open AWX: <http://localhost:30080>
2. Login: admin / password <!-- pragma: allowlist secret -->
3. Check:
   - **Resources → Inventories → vLLM Test Infrastructure**
   - **Resources → Templates → LLM Concurrent Load Test**
   - **Administration → Execution Environments → vLLM AWX EE**

---

## Execution Environment

### What is an Execution Environment?

An **Execution Environment (EE)** is a containerized image that AWX uses to run Ansible playbooks. It contains:
- Ansible core
- Python dependencies
- Ansible collections
- System packages

**Benefits:**
- ✅ **Isolation**: Different jobs can use different Ansible versions
- ✅ **Reproducibility**: Same environment every time
- ✅ **Portability**: Works on any AWX instance
- ✅ **Security**: Jobs are sandboxed

### Our Custom EE: `vllm-awx-ee`

The default AWX EE doesn't include collections we need, so we build a custom one:

```yaml
# execution-environment.yml
base_image: quay.io/ansible/awx-ee:latest

dependencies:
  galaxy: requirements.yml  # Contains:
    - containers.podman     # For managing vLLM containers
    - ansible.posix         # For rsync/synchronize module
```

### Building the Execution Environment

#### Local Build (for KIND)

```bash
# Build EE image locally
make kind-build-ee

# Load into KIND cluster
make kind-load-ee

# Or do both at once
make kind-quickstart
```

#### Production Build (quay.io)

The execution environment is automatically built via GitHub Actions:

- **Registry**: `quay.io/octo-et/vllm-cpu-perf-eval`
- **Trigger**: Push to `main` branch
- **Workflow**: `.github/workflows/build-execution-environment.yml`

To use in production:

```yaml
# awx-deployment.yml
spec:
  ee_images:
    - name: vllm-awx-ee
      image: quay.io/octo-et/vllm-cpu-perf-eval:latest
```

### Customizing the EE

#### Adding Ansible Collections

1. Edit `requirements.yml`:
   ```yaml
   collections:
     - name: community.general
       version: ">=8.0.0"
   ```

2. Rebuild:
   ```bash
   make kind-build-ee && make kind-load-ee
   ```

#### Adding Python Packages

1. Create `requirements.txt`:
   ```
   pandas>=2.0.0
   numpy>=1.24.0
   ```

2. Update `execution-environment.yml`:
   ```yaml
   dependencies:
     galaxy: requirements.yml
     python: requirements.txt
   ```

3. Rebuild

#### Adding System Packages

```yaml
additional_build_steps:
  prepend_final:
    - RUN dnf install -y git vim
```

---

## Running Tests

### Step-by-Step Test Launch

#### 1. Navigate to Job Template

- Go to **Resources → Templates**
- Find **"LLM Concurrent Load Test"**
- Click the **rocket icon** (🚀)

#### 2. CRITICAL: Attach Credentials

**For Gated Models (meta-llama/*):**

You MUST attach BOTH credentials:

1. In the launch dialog, find **"Credentials"** section
2. Click the **search icon** 🔍
3. Select both:
   - **DUT SSH Key** (should already be there)
   - **HuggingFace Token** (click search again to add)
4. Verify BOTH are listed

**For Public Models (TinyLlama/*):**
- Only **DUT SSH Key** is required

#### 3. Review/Modify Variables (Optional)

Click **"Variables"** to see configuration:

```yaml
test_model: "meta-llama/Llama-3.2-1B-Instruct"
base_workload: "chat"
requested_cores: 16
skip_phase_2: true
skip_phase_3: true
guidellm_max_seconds: 300
guidellm_rate: [1]
```

Modify as needed.

#### 4. Launch

Click **"Next"** → **"Launch"**

### Monitoring Job Progress

1. **Resources → Jobs** → Click on your running job
2. **Output** tab shows live Ansible output
3. Watch for:
   - vLLM server startup
   - Health check success
   - GuideLLM benchmark progress

---

## Working with Credentials

### SSH Credentials

**Automatically configured** by `configure-awx.yml`:

- **Name**: DUT SSH Key
- **Type**: Machine
- **Username**: From `ANSIBLE_SSH_USER`
- **SSH Private Key**: From `ANSIBLE_SSH_KEY` file

**To update:**
1. **Resources → Credentials → DUT SSH Key → Edit**
2. Update username or paste new SSH key
3. **Save**

### HuggingFace Token Credential

**Required for gated models** (meta-llama/*, mistralai/*)

#### First Time Setup

1. **Resources → Credentials → Add**
2. **Name**: `HuggingFace Token`
3. **Credential Type**: **"HuggingFace Token"**
4. **HuggingFace API Token**: Paste your token (starts with `hf_`)
5. **Save**

#### Get Your HF Token

```bash
# If in a file:
cat ~/hf_token

# Or from HuggingFace:
# Visit: https://huggingface.co/settings/tokens
```

### Common Credential Issues

**Problem**: "401 Unauthorized" when downloading model

**Solution**: Attach HuggingFace Token credential when launching job

**Problem**: SSH connection fails

**Solutions**:
- Check DUT_HOSTNAME is correct in inventory
- Verify SSH key permissions: `chmod 600 ~/mtahhan.pem`
- Test manual SSH: `ssh -i ~/mtahhan.pem ec2-user@your-dut-host`

---

## Customizing Tests

### Available Workloads

| Workload | Description | ISL | OSL |
|----------|-------------|-----|-----|
| `chat` | Chat/conversation | 512 | 128 |
| `rag` | Retrieval-augmented generation | 4096 | 256 |
| `code` | Code generation | 2048 | 512 |
| `summarization` | Text summarization | 1024 | 256 |

### Model Selection

**Gated Models** (require HuggingFace Token):
- `meta-llama/Llama-3.2-1B-Instruct`
- `meta-llama/Llama-3.2-3B-Instruct`
- `mistralai/Mistral-7B-v0.1`

**Public Models** (no token required):
- `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- `Qwen/Qwen2.5-0.5B-Instruct`

### Test Phases

#### Phase 1: Baseline (Fixed Tokens, No Caching)
- Fixed input/output lengths
- No prefix caching
- Establishes performance baseline

#### Phase 2: Realistic (Variable Tokens, No Caching)
- Variable length inputs/outputs (±20%)
- No prefix caching
- Simulates real-world variability

#### Phase 3: Production (Variable Tokens, With Caching)
- Variable length inputs/outputs
- Prefix caching enabled
- Shows production performance with optimizations

**Control via variables:**
```yaml
skip_phase_1: false  # Run Phase 1
skip_phase_2: true   # Skip Phase 2
skip_phase_3: true   # Skip Phase 3
```

### Method 1: Environment Variables

Set defaults when configuring AWX:

```bash
export TEST_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0
export BASE_WORKLOAD=rag
export REQUESTED_CORES=32
export GUIDELLM_MAX_SECONDS=600
export GUIDELLM_RATE=[1,2,4]

ansible-playbook configure-awx.yml
```

### Method 2: Override at Launch

Modify variables when launching:

```yaml
test_model: "meta-llama/Llama-3.2-3B-Instruct"
base_workload: "rag"
requested_cores: 64
skip_phase_2: false  # Enable all phases
skip_phase_3: false
guidellm_rate: [1, 2, 4, 8, 16]
guidellm_max_seconds: 600
```

---

## Viewing Results

### During Execution

1. **Resources → Jobs** → Click running job
2. **Output** tab shows live progress
3. Watch for benchmark completion

### After Completion

#### AWX Job Results

**In AWX UI:**

1. **Resources → Jobs** → Click on your completed job
2. **Details** tab shows:
   - Job status (Success/Failed)
   - Runtime duration
   - Job ID and timestamps
3. **Output** tab shows full Ansible logs
4. Scroll to bottom for result file listings

**Look for this in the output:**
```
TASK [Display result files]
ok: [loadgen-host] => {
    "msg": "Generated 2 result files: ['benchmark_results.json', 'benchmark_results.csv']"
}
```

#### Results Storage Locations

**On Loadgen Host** (Primary Storage):
```bash
~/benchmark-results/<model>/<workload>-<run-id>/<core-config>/
```

For test run ID `20260312-114810`:
```bash
ssh ec2-user@your-loadgen-host
cd ~/benchmark-results/meta-llama__Llama-3.2-1B-Instruct/chat-20260312-114810/16cores-numa0-tp1/
ls -lah
```

**AWX Artifacts Directory** (Temporary):

AWX stores job artifacts temporarily in:
```bash
# On the AWX pod
/runner/artifacts/<job-id>/
```

However, these are **ephemeral** - they're deleted when the job pod terminates. Always retrieve results from the loadgen host.

#### Result Files

- `*.json` - GuideLLM benchmark results (metrics, throughput, latency)
- `*.csv` - CSV format results (easy for spreadsheet analysis)
- `*.html` - HTML report (if generated, visual dashboard)
- `guidellm.log` - Full GuideLLM execution logs (detailed output)
- `test-metadata.json` - Test configuration (model, cores, workload, etc.)

#### Retrieving Results

**Method 1: SSH and Download**
```bash
# SSH to loadgen
ssh ec2-user@your-loadgen-host

# Find your results
cd ~/benchmark-results
ls -lR

# Download from your laptop
scp -r ec2-user@your-loadgen-host:~/benchmark-results ./local-results/
```

**Method 2: AWX File Transfer (Future Enhancement)**

AWX doesn't currently support built-in result download. Consider:
- Setting up an artifact server (S3, HTTP server)
- Modifying playbook to upload results automatically
- Using `ansible.builtin.fetch` to AWX control node (limited by AWX storage)

**Method 3: Automated Collection**

Add to playbook:
```yaml
- name: Upload results to S3
  amazon.aws.s3_sync:
    bucket: my-vllm-results
    file_root: "{{ results_path }}"
    key_prefix: "{{ test_run_id }}/"
```

---

## Troubleshooting

### Health Check Keeps Retrying

**Symptoms:**
```
FAILED - RETRYING: Wait for vLLM health endpoint (60 retries left)
```

**Common Causes:**

#### 1. Missing HuggingFace Token (Most Common!)

**Check:** Job output shows:
```
"msg": "HuggingFace Token: Not provided"
```

**Fix:** Cancel and relaunch with HuggingFace Token credential

#### 2. Model Still Downloading

**Check:** SSH to DUT:
```bash
ssh ec2-user@your-dut-host
sudo podman logs vllm-server --tail 50
```

Look for "Downloading model files..."

**Fix:** Wait for download to complete (5-10 min for large models)

#### 3. vLLM Container Crashed

**Check:**
```bash
sudo podman ps | grep vllm-server  # Should show "Up"
sudo podman logs vllm-server --tail 100
```

**Fixes:**
- Out of memory? Reduce `requested_cores` or model size
- Permission error? Use Podman with `--security-opt label=disable` or apply correct SELinux labels with `restorecon -Rv <path>` (see [Podman SELinux docs](https://docs.podman.io/en/latest/markdown/podman-run.1.html#security-opt-option))

#### 4. Network/Firewall Issue

**Check:** Can you reach the DUT?
```bash
curl http://your-dut-host:8000/health
```

**Fix:** Update AWS security group to allow port 8000

### GuideLLM Container Fails

**Symptoms:** Exit code 126, cpuset controller error

**Cause:** Rootless podman can't access cpuset controller

**Fix:** In AWX job template settings:
- **Privilege Escalation**: ✓ Enabled
- **Privilege Escalation Method**: sudo
- **Privilege Escalation Username**: (leave empty or remove override)

See [GUIDELLM-DEBUG-GUIDE.md](GUIDELLM-DEBUG-GUIDE.md) for detailed troubleshooting.

### ImagePullBackOff Error

**Symptom**: AWX pods fail to start

**Cause**: KIND cluster can't find EE image

**Fix**:
```bash
make kind-load-ee
```

### DNS Resolution Failures in KIND (Linux with firewalld)

**Symptoms**:
- AWX operator pods show `ImagePullBackOff`
- Container image pulls timeout or fail
- Error logs show DNS resolution failures

**Cause**: On Linux systems with firewalld, the docker/podman firewall zone may block outbound DNS queries (UDP port 53) from containers, preventing KIND cluster pods from resolving external hostnames.

**Check if this is your issue**:
```bash
# Check if firewalld is running
sudo firewall-cmd --state

# Try pulling an image from within a KIND node (should timeout if DNS is blocked)
kubectl run dns-test --image=busybox:1.28 --restart=Never --rm -it -- nslookup google.com
```

**Fix** (Linux with firewalld only):
```bash
# Add DNS service to docker zone (allows UDP port 53 outbound)
sudo firewall-cmd --zone=docker --add-service=dns
sudo firewall-cmd --zone=docker --add-port=53/udp

# Make permanent
sudo firewall-cmd --zone=docker --add-service=dns --permanent
sudo firewall-cmd --zone=docker --add-port=53/udp --permanent

# Verify
sudo firewall-cmd --zone=docker --list-all
```

After applying the fix, delete and recreate any failing pods:
```bash
kubectl delete pod -n awx --field-selector=status.phase=Failed
kubectl delete pod -n awx-operator-system --all
```

**Note**: This is only needed on Linux systems with firewalld. macOS and other firewall solutions don't require this.

### Collections Not Found

**Symptom**: "Collection not found" in job output

**Fix**:
1. Add collection to `requirements.yml`
2. Rebuild EE: `make kind-build-ee && make kind-load-ee`

### Diagnostic Commands

```bash
# On DUT - Check vLLM
ssh ec2-user@your-dut-host
sudo podman ps
sudo podman logs vllm-server --tail 50
curl http://localhost:8000/health
curl http://localhost:8000/v1/models

# On Load Generator - Check GuideLLM
ssh ec2-user@your-loadgen-host
sudo podman ps | grep guidellm
sudo podman logs <guidellm-container> --tail 50

# On AWX host - Check cluster
kubectl get pods -n awx
kubectl logs -n awx <awx-task-pod>
```

---

## Advanced Topics

### Available Make Targets

```bash
make help                # Show all targets
make kind-quickstart     # Complete setup
make kind-build-ee       # Build execution environment
make kind-load-ee        # Load EE into cluster
make kind-status         # Show cluster status
make kind-logs           # Show AWX logs
make kind-configure      # Reconfigure AWX
make kind-stop           # Stop cluster
make kind-restart        # Restart cluster
make clean-all           # Remove everything
```

### Production Deployment

#### Using quay.io Image

```yaml
# awx-deployment.yml
spec:
  ee_images:
    - name: vllm-awx-ee
      image: quay.io/octo-et/vllm-cpu-perf-eval:v1.0.0  # Pin version
```

#### Image Pull Credentials

For private registry:

```bash
kubectl create secret docker-registry quay-creds \
  --docker-server=quay.io \
  --docker-username=<username> \
  --docker-password=<password> \
  -n awx
```

Reference in AWX spec:
```yaml
spec:
  ee_pull_credentials_secret: quay-creds
```

### Reconfiguration Workflow

When infrastructure changes:

```bash
# Update environment variables
export DUT_HOSTNAME=new-dut-hostname
export LOADGEN_HOSTNAME=new-loadgen-hostname
export ANSIBLE_SSH_KEY=~/new-key.pem

# Reconfigure AWX
ansible-playbook configure-awx.yml

# Verify in AWX UI
# Resources → Inventories → vLLM Test Infrastructure → Hosts
```

Changes take effect immediately!

---

## Best Practices

1. **Always attach HuggingFace Token** for gated models
2. **Start small** - Test with TinyLlama first
3. **Monitor first run** - Watch job output
4. **Check disk space** - Models can be 10GB+
5. **Use descriptive job names** - Add notes for complex tests
6. **Save results regularly** - Download from loadgen periodically

---

## Quick Reference

### Common Launch Scenarios

#### Quick Test (Public Model)
```yaml
Credentials: [DUT SSH Key]
Variables:
  test_model: "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
  requested_cores: 16
  guidellm_max_seconds: 300
```

#### Full 3-Phase (Gated Model)
```yaml
Credentials: [DUT SSH Key, HuggingFace Token]
Variables:
  test_model: "meta-llama/Llama-3.2-3B-Instruct"
  requested_cores: 32
  skip_phase_2: false
  skip_phase_3: false
```

#### Performance Sweep
```yaml
Credentials: [DUT SSH Key, HuggingFace Token]
Variables:
  guidellm_rate: [1, 2, 4, 8, 16]
  guidellm_max_seconds: 600
```

---

## Resources

- [Ansible Builder Documentation](https://ansible-builder.readthedocs.io/)
- [AWX Operator Documentation](https://ansible.readthedocs.io/projects/awx-operator/)
- [AWX User Guide](https://docs.ansible.com/automation-controller/latest/html/userguide/index.html)
- [Execution Environment Guide](https://docs.ansible.com/automation-controller/latest/html/userguide/execution_environments.html)
- [KIND Documentation](https://kind.sigs.k8s.io/)
- [HuggingFace Tokens](https://huggingface.co/docs/hub/security-tokens)

---

## Support

For issues:
1. Check logs: `make kind-logs`
2. Check status: `make kind-status`
3. Review [troubleshooting section](#troubleshooting)
4. Check [GUIDELLM-DEBUG-GUIDE.md](GUIDELLM-DEBUG-GUIDE.md)
5. Open an issue on GitHub
