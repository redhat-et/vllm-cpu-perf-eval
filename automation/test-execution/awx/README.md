# AWX Integration for vLLM CPU Performance Testing

AWX provides a web UI for running vLLM performance tests without editing configuration files. Users fill out web forms to configure tests, select models, and launch test suites.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [AWX Setup](#awx-setup)
- [Running Tests](#running-tests)
- [Workflows](#workflows)
- [Troubleshooting](#troubleshooting)

## Overview

### What is AWX?

AWX is the open-source web UI for Ansible. It provides:
- **Web Interface**: Run tests from a browser instead of command line
- **No File Editing**: All configuration via web forms
- **Credential Management**: Securely store SSH keys and API tokens
- **Job Scheduling**: Schedule tests to run at specific times
- **RBAC**: Control who can run which tests
- **Audit Logs**: Track all test executions

### Architecture

```
┌─────────────┐
│  User       │
│  (Browser)  │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────────────┐
│  AWX Web UI                             │
│  - Job Templates (test configurations)  │
│  - Surveys (collect user input)         │
│  - Credentials (SSH keys, HF_TOKEN)     │
│  - Inventory (DUT + Load Gen hosts)     │
└──────┬──────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────┐
│  Ansible Playbooks (our existing code)  │
│  - playbooks/llm/run-guidellm-test.yml  │
│  - playbooks/embedding/run-tests.yml    │
└──────┬──────────────────────────────────┘
       │
       ↓
┌──────────────────┐      ┌──────────────────┐
│  DUT             │      │  Load Generator  │
│  (vLLM Server)   │◄─────┤  (GuideLLM)      │
└──────────────────┘      └──────────────────┘
```

## Quick Start

### Prerequisites

- Docker or Podman (for running AWX)
- Access to DUT and load generator machines
- SSH keys for DUT access
- (Optional) HuggingFace token for gated models

### 1. Install AWX

**Option A: Docker Compose (Recommended for testing)**

```bash
git clone https://github.com/ansible/awx.git
cd awx
make docker-compose

# Wait for AWX to start (may take a few minutes)
# Default URL: http://localhost:8052
# Default credentials: admin / password
```

**Option B: Kubernetes (Production)**

```bash
# Install AWX Operator
kubectl apply -f https://raw.githubusercontent.com/ansible/awx-operator/devel/deploy/awx-operator.yaml

# Create AWX instance
cat <<EOF | kubectl apply -f -
apiVersion: awx.ansible.com/v1beta1
kind: AWX
metadata:
  name: awx
spec:
  service_type: LoadBalancer
EOF

# Get admin password
kubectl get secret awx-admin-password -o jsonpath="{.data.password}" | base64 --decode
```

**Option C: RPM/DEB (RHEL/Ubuntu)**

See: https://github.com/ansible/awx/blob/devel/INSTALL.md

### 2. Configure AWX

#### Step 1: Create Organization

1. Navigate to **Access** → **Organizations**
2. Click **Add**
3. Enter:
   - **Name**: vLLM Performance Testing
   - **Description**: LLM and embedding model performance evaluation

#### Step 2: Create Project (Git Repository)

1. Navigate to **Resources** → **Projects**
2. Click **Add**
3. Configure:
   - **Name**: vLLM CPU Perf Eval
   - **Organization**: vLLM Performance Testing
   - **Source Control Type**: Git
   - **Source Control URL**: `https://github.com/your-org/vllm-cpu-perf-eval.git`
   - **Source Control Branch/Tag/Commit**: `main` or `feature/inventory-split`
   - **Update Revision on Launch**: ✓ (recommended)
4. Click **Save**
5. Click **Sync** to download the repository

#### Step 3: Create Custom Credential Type (HuggingFace Token)

1. Navigate to **Administration** → **Credential Types**
2. Click **Add**
3. Copy/paste from [`credentials/huggingface-token.yml`](credentials/huggingface-token.yml)
   - **Name**: `HuggingFace Token`
   - **Description**: `HuggingFace API token for gated models`
   - **Input Configuration**:
     ```yaml
     fields:
       - id: hf_token
         type: string
         label: HuggingFace Token
         secret: true
     required:
       - hf_token
     ```
   - **Injector Configuration**:
     ```yaml
     env:
       HF_TOKEN: "{{ hf_token }}"
     extra_vars:
       hf_token: "{{ hf_token }}"
     ```
4. Click **Save**

#### Step 4: Create Credentials

**A. DUT SSH Credential**

1. Navigate to **Resources** → **Credentials**
2. Click **Add**
3. Configure:
   - **Name**: DUT SSH Key (AWS EC2)
   - **Organization**: vLLM Performance Testing
   - **Credential Type**: Machine
   - **Username**: `ec2-user` (or your SSH user)
   - **SSH Private Key**: Paste your private key (e.g., `~/.ssh/your-key.pem`)
4. Click **Save**

**B. HuggingFace Token (Optional, for gated models)**

1. Navigate to **Resources** → **Credentials**
2. Click **Add**
3. Configure:
   - **Name**: HuggingFace API Token
   - **Organization**: vLLM Performance Testing
   - **Credential Type**: HuggingFace Token (the one you just created)
   - **HuggingFace Token**: `hf_xxxxxxxxxxxxx` (from https://huggingface.co/settings/tokens)
4. Click **Save**

#### Step 5: Create Inventory

**Option A: Static Inventory (Simple)**

1. Navigate to **Resources** → **Inventories**
2. Click **Add** → **Add inventory**
3. Configure:
   - **Name**: vLLM Test Infrastructure
   - **Organization**: vLLM Performance Testing
4. Click **Save**
5. Click **Hosts** → **Add**
6. Add DUT:
   - **Name**: `my-dut`
   - **Variables** (YAML):
     ```yaml
     ansible_host: ec2-3-144-144-132.us-east-2.compute.amazonaws.com
     ansible_user: ec2-user
     ```
7. Add Load Generator:
   - **Name**: `my-loadgen`
   - **Variables**:
     ```yaml
     ansible_host: localhost
     ansible_connection: local
     ansible_python_interpreter: auto_silent
     ansible_become: false
     bench_config:
       vllm_host: ec2-3-144-144-132.us-east-2.compute.amazonaws.com
       vllm_port: 8000
       results_dir: /tmp/benchmark-results
     ```
8. Click **Groups** → **Add**
9. Create groups:
   - Group **dut**: Add host `my-dut`
   - Group **load_generator**: Add host `my-loadgen`

**Option B: Dynamic Inventory (Advanced)**

1. Create inventory as above
2. Click **Sources** → **Add**
3. Configure:
   - **Name**: Dynamic vLLM Inventory
   - **Source**: Custom Script
   - **Custom Inventory Script**: Paste [`inventory/awx-dynamic-inventory.py`](inventory/awx-dynamic-inventory.py)
4. Click **Save**
5. Click **Sync** to populate inventory

#### Step 6: Create Job Template

1. Navigate to **Resources** → **Templates**
2. Click **Add** → **Add job template**
3. Configure using [`job-templates/llm-guidellm-test.yml`](job-templates/llm-guidellm-test.yml):
   - **Name**: LLM GuideLLM Performance Test
   - **Job Type**: Run
   - **Inventory**: vLLM Test Infrastructure
   - **Project**: vLLM CPU Perf Eval
   - **Playbook**: `automation/test-execution/ansible/playbooks/llm/run-guidellm-test.yml`
   - **Credentials**:
     - Select: DUT SSH Key (AWS EC2)
   - **Options**:
     - ✓ **Prompt on launch** (for Credentials) - allows attaching HF_TOKEN
     - ✓ **Enable Concurrent Jobs** (if you want parallel tests)
4. Click **Save**

#### Step 7: Add Survey to Job Template

1. Click on the job template you just created
2. Click **Survey** tab
3. Click **Add**
4. Add questions from [`surveys/llm-guidellm-test.yml`](surveys/llm-guidellm-test.yml):

   **Example Questions:**

   | Name | Question | Type | Variable | Choices/Default |
   |------|----------|------|----------|-----------------|
   | DUT Hostname | Hostname or IP of DUT | Text | `dut_host` | (empty) |
   | vLLM Image | vLLM container image | Text | `vllm_image` | `quay.io/mtahhan/vllm:0.13.0-amx` |
   | Model | Model to test | Multiple Choice | `test_model` | Qwen/Qwen3-0.6B, meta-llama/Llama-3.2-1B-Instruct, ... |
   | Workload | Workload type | Multiple Choice | `workload_type` | chat, summarization, code, rag |
   | Core Config | CPU allocation | Multiple Choice | `core_config_name` | 8cores-single-socket, 16cores-single-socket, ... |

5. Click **Save** for each question
6. Enable the survey with the toggle switch

## Running Tests

### Single Test via Job Template

1. Navigate to **Resources** → **Templates**
2. Click **Launch** (rocket icon) next to "LLM GuideLLM Performance Test"
3. Fill out the survey:
   - **DUT Hostname**: `ec2-3-144-144-132.us-east-2.compute.amazonaws.com`
   - **vLLM Image**: `quay.io/mtahhan/vllm:0.13.0-amx`
   - **Model**: `Qwen/Qwen3-0.6B`
   - **Workload**: `chat`
   - **Core Config**: `16cores-single-socket`
   - **Results Directory**: `/tmp/benchmark-results`
4. (Optional) Select **HuggingFace API Token** credential if testing gated models
5. Click **Next** → **Launch**
6. Monitor job execution in real-time
7. View results in **Jobs** list

### Test Suite via Workflow

1. Navigate to **Resources** → **Templates**
2. Click **Launch** next to "LLM Model Test Suite" workflow
3. Fill out the survey:
   - **Model**: `Qwen/Qwen3-0.6B`
   - **Workloads**: `chat,summarization,rag`
   - **Core Configs**: `8cores-single-socket,16cores-single-socket`
   - **Execution Mode**: `sequential` or `parallel`
4. Click **Launch**
5. View workflow progress visualization
6. Results collected automatically at the end

### Scheduling Tests

1. Create a job template as above
2. Click **Schedules** tab
3. Click **Add**
4. Configure:
   - **Name**: Nightly Performance Test
   - **Start Date/Time**: Select date and time
   - **Frequency**: Daily, Weekly, etc.
   - **Time Zone**: Your timezone
5. Click **Save**

Tests will run automatically on schedule.

## Workflows

Workflows orchestrate multiple jobs in sequence or parallel.

### Creating a Workflow Template

1. Navigate to **Resources** → **Templates**
2. Click **Add** → **Add workflow template**
3. Configure using [`workflows/llm-model-test-suite.yml`](workflows/llm-model-test-suite.yml):
   - **Name**: LLM Model Test Suite
   - **Organization**: vLLM Performance Testing
   - **Inventory**: vLLM Test Infrastructure
4. Click **Save**
5. Click **Visualizer** to design the workflow:

   ```
   START
     ↓
   Setup Environment
     ↓
   Test Matrix (parallel)
     ├─ Test: chat + 8c
     ├─ Test: chat + 16c
     ├─ Test: summarization + 8c
     └─ Test: summarization + 16c
     ↓
   Collect Results
     ↓
   Generate Report
     ↓
   Cleanup
   ```

6. Add nodes by clicking **+** between steps
7. Connect nodes with success/failure/always paths
8. Save workflow

### Pre-Built Workflows

See [`workflows/`](workflows/) directory for examples:
- `llm-model-test-suite.yml` - Test one model across multiple workloads
- `embedding-model-suite.yml` - Embedding model performance suite
- `core-sweep-suite.yml` - Test all core configurations

## Viewing Results

### Job Output

1. Navigate to **Views** → **Jobs**
2. Click on a completed job
3. View:
   - **Details**: Start time, duration, who launched it
   - **Output**: Full Ansible playbook output
   - **Results**: Structured output (if configured)

### Downloading Results

Results are stored in the configured `results_dir` on the load generator.

To fetch results to AWX server:

1. Create a "Fetch Results" job template:
   - Playbook: `playbooks/common/collect-logs.yml`
   - Runs on: load_generator
   - Fetches: `{{ results_dir }}` to AWX project directory

2. Add as final step in workflow

### Results Structure

```
{{ results_dir }}/
├── <model-name>/
│   ├── <workload-type>/
│   │   ├── <core-config>/
│   │   │   ├── benchmarks.json
│   │   │   ├── benchmarks.csv
│   │   │   └── benchmarks.html
│   │   └── ...
│   └── ...
└── ...
```

## Troubleshooting

### Job Fails Immediately

**Check:**
- Credentials are attached to job template
- Inventory has correct host variables
- Playbook path is correct in project
- Project sync succeeded

**View:**
- Job output for Ansible errors
- AWX logs: `docker logs awx_task` (if using Docker Compose)

### SSH Connection Failures

**Check:**
- SSH credential has correct username and private key
- DUT is reachable from AWX server: `ssh -i key.pem user@dut_host`
- Security groups/firewall allow SSH (port 22)

**Test:**
- Run a simple ad-hoc command: Templates → Ad Hoc → Module: `ping`

### Slow Job Execution

**Check:**
- AWX server has enough resources (CPU, memory)
- Network latency between AWX and DUT
- DUT has enough resources for vLLM

**Optimize:**
- Use local execution environment (reduce overhead)
- Run AWX closer to DUT (same VPC/region)
- Increase AWX container resources

### HuggingFace Token Not Working

**Check:**
- Custom credential type is created correctly
- Credential is attached to job template launch
- Token is valid: `curl -H "Authorization: Bearer $HF_TOKEN" https://huggingface.co/api/whoami`

**Debug:**
- Check job output for HF_TOKEN environment variable
- Verify injector configuration in credential type

### Results Not Collected

**Check:**
- `results_dir` exists and is writable on load generator
- Sufficient disk space
- Log collection playbook runs successfully

**Manual Collection:**
```bash
# On load generator
ls -lh {{ results_dir }}/

# Fetch to local machine
scp -r user@loadgen:{{ results_dir }} ./local-results/
```

## Advanced Configuration

### Custom Execution Environments

Build a custom execution environment with all dependencies:

```dockerfile
FROM quay.io/ansible/awx-ee:latest

RUN pip install guidellm ansible

USER 1000
```

Upload to AWX:
1. Administration → Execution Environments → Add
2. Name: vLLM Testing EE
3. Image: `your-registry/vllm-testing-ee:latest`

Use in job templates:
- Job Template → Execution Environment → vLLM Testing EE

### RBAC Setup

**Create Teams:**
1. Access → Teams → Add
   - **Name**: Performance Testers
   - **Organization**: vLLM Performance Testing

**Assign Permissions:**
1. Click on team
2. Permissions → Add
   - **Resource**: Job Template: LLM GuideLLM Performance Test
   - **Role**: Execute

Now team members can run tests but not modify configurations.

### Notifications

**Slack Notifications:**
1. Administration → Notification Templates → Add
2. Configure:
   - **Name**: Slack Performance Test Alerts
   - **Type**: Slack
   - **Destination Channels**: `#performance-testing`
   - **Token**: Your Slack webhook URL

**Attach to Job Template:**
1. Job Template → Notifications
2. Toggle notifications for: Success, Failure, Start

### Webhooks

Trigger tests via API calls (e.g., from CI/CD):

1. Job Template → Details → Enable Webhook
2. Copy Webhook URL and Key
3. Use in CI/CD:
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"extra_vars": {"test_model": "Qwen/Qwen3-0.6B"}}' \
     https://awx.example.com/api/v2/job_templates/123/github/ \
     -H "X-Hub-Signature: sha1=$(echo -n '{...}' | openssl dgst -sha1 -hmac 'WEBHOOK_KEY' | cut -d' ' -f2)"
   ```

## Next Steps

- **Customize Surveys**: Add more questions for fine-grained control
- **Build Workflows**: Orchestrate complex test scenarios
- **Integrate CI/CD**: Trigger tests from GitHub/GitLab
- **Enable Notifications**: Get alerted when tests complete
- **Setup RBAC**: Control who can run which tests

## Resources

- [AWX Documentation](https://ansible.readthedocs.io/projects/awx/en/latest/)
- [AWX GitHub Repository](https://github.com/ansible/awx)
- [Ansible Playbook Documentation](https://docs.ansible.com/ansible/latest/playbook_guide/)
- [vLLM Performance Testing Playbooks](../ansible/playbooks/)

## Support

For issues with:
- **AWX Setup**: https://github.com/ansible/awx/issues
- **Playbooks/Testing**: https://github.com/your-org/vllm-cpu-perf-eval/issues
