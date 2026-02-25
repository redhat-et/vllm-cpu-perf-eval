# AWX Configuration Files Reference

This directory contains all configuration files needed to run vLLM performance tests through AWX.

## Directory Structure

```
awx/
├── README.md                          # Complete AWX setup and usage guide
├── QUICKSTART.md                      # 15-minute quick start guide
├── FILES.md                           # This file - overview of all files
│
├── credentials/                       # Custom credential type definitions
│   └── huggingface-token.yml          # HF_TOKEN credential type (for gated models)
│
├── surveys/                           # Survey specifications (web form definitions)
│   └── llm-guidellm-test.yml          # Survey for LLM test configuration
│
├── job-templates/                     # Job template definitions
│   └── llm-guidellm-test.yml          # Single LLM test job template
│
├── workflows/                         # Workflow template definitions
│   └── llm-model-test-suite.yml       # Multi-test suite workflow
│
└── inventory/                         # Dynamic inventory scripts
    └── awx-dynamic-inventory.py       # Generate inventory from AWX survey inputs
```

## File Purposes

### Documentation

#### `README.md`
**Purpose**: Complete setup and usage guide for AWX integration
**Audience**: Users setting up AWX for the first time
**Contains**:
- AWX installation instructions (Docker, K8s, RPM)
- Step-by-step configuration walkthrough
- How to create projects, credentials, inventories, job templates
- How to run tests and view results
- Troubleshooting guide
- Advanced configuration (RBAC, notifications, webhooks)

#### `QUICKSTART.md`
**Purpose**: Get first test running in 15 minutes
**Audience**: Users who want to try AWX quickly
**Contains**:
- Minimal installation (Docker Compose only)
- Essential configuration steps
- Single test execution
- Basic troubleshooting

#### `FILES.md`
**Purpose**: Reference guide for this directory's contents
**Audience**: Developers/maintainers
**Contains**:
- File structure overview
- Purpose of each file
- How to use each file in AWX

### Credentials

#### `credentials/huggingface-token.yml`
**Purpose**: Define custom credential type for HuggingFace tokens
**How to Use**:
1. **Administration** → **Credential Types** → **Add**
2. Copy/paste the YAML content into:
   - **Input Configuration**: How user enters the token
   - **Injector Configuration**: How token is passed to playbooks
3. After creating the credential type, create actual credentials:
   - **Resources** → **Credentials** → **Add**
   - **Type**: HuggingFace Token
   - **Token**: Your actual `hf_xxxxx` token

**What it Does**:
- Securely stores HF_TOKEN in AWX's encrypted database
- Injects token as environment variable (`HF_TOKEN`) when job runs
- Allows testing gated models (meta-llama/*) without hardcoding tokens

### Surveys

#### `surveys/llm-guidellm-test.yml`
**Purpose**: Define web form for collecting test configuration
**How to Use**:
1. Create job template first
2. **Job Template** → **Survey** tab
3. Click **Add** for each question in this file
4. Copy question properties (name, type, choices, default)
5. **Survey Enabled** → **On**

**What it Does**:
- Presents web form when user launches test
- Collects configuration without file editing:
  - DUT hostname, SSH user
  - Load generator mode (localhost or remote)
  - Container images (vLLM, GuideLLM)
  - Model selection
  - Workload type
  - Core configuration
  - Advanced options (max requests, duration, results dir)
- Passes values as Ansible `extra_vars`

**Survey Questions**:
| Question | Variable | Type | Purpose |
|----------|----------|------|---------|
| DUT Hostname | `dut_host` | Text | Where vLLM runs |
| DUT SSH User | `dut_user` | Text | SSH username |
| Load Generator Mode | `loadgen_mode` | Choice | localhost or remote |
| vLLM Image | `vllm_image` | Text | Container image for vLLM |
| GuideLLM Image | `guidellm_image` | Text | Container image for GuideLLM |
| Model | `test_model` | Choice | HuggingFace model to test |
| Workload | `workload_type` | Choice | chat, summarization, code, rag |
| Core Config | `core_config_name` | Choice | CPU allocation profile |
| Max Requests | `guidellm_max_requests` | Integer | Test length limit |
| Max Duration | `guidellm_max_seconds` | Integer | Test time limit |

### Job Templates

#### `job-templates/llm-guidellm-test.yml`
**Purpose**: Define job template for running a single LLM test
**How to Use**:
1. **Resources** → **Templates** → **Add** → **Add job template**
2. Use this file as reference for field values:
   - **Name**: LLM GuideLLM Performance Test
   - **Playbook**: `automation/test-execution/ansible/playbooks/llm/run-guidellm-test.yml`
   - **Credentials**: Select your SSH credential
   - **Survey**: Enable and add questions from `surveys/llm-guidellm-test.yml`
   - **Extra Vars**: Copy the extra_vars section

**What it Does**:
- Links AWX UI to your Ansible playbook
- Defines which playbook to run
- Specifies which inventory and credentials to use
- Maps survey inputs to playbook variables
- Sets execution options (verbosity, timeout, etc.)

**Extra Vars Mapping**:
```yaml
# Survey → Playbook Variable Mapping
dut_host → ansible_host_dut
dut_user → ansible_user_dut
test_model → test_model (passed to playbook)
workload_type → workload_type (passed to playbook)
vllm_image → container_runtime.image
guidellm_image → benchmark_tool.guidellm.container_image
```

### Workflows

#### `workflows/llm-model-test-suite.yml`
**Purpose**: Define workflow for running multiple tests (test suite)
**How to Use**:
1. **Resources** → **Templates** → **Add** → **Add workflow template**
2. Use this file as reference for:
   - **Name**: LLM Model Test Suite
   - **Survey**: Collect suite-level configuration
3. Click **Visualizer** to add workflow nodes:
   - Setup → Test Matrix → Collect Results → Generate Report → Cleanup

**What it Does**:
- Orchestrates multiple tests in sequence or parallel
- Tests one model across multiple workloads and core configs
- Example: Test Qwen/Qwen3-0.6B with:
  - Workloads: chat, summarization, rag
  - Cores: 8c, 16c, 32c
  - = 9 total tests (3 workloads × 3 core configs)
- Automatically collects and aggregates results
- Handles failures gracefully (cleanup on failure)

**Workflow Structure**:
```
Setup Environment
  ↓
Test Matrix (expands based on survey input)
  ├─ Test 1: chat + 8c
  ├─ Test 2: chat + 16c
  ├─ Test 3: chat + 32c
  ├─ Test 4: summarization + 8c
  ├─ Test 5: summarization + 16c
  ├─ Test 6: summarization + 32c
  ├─ Test 7: rag + 8c
  ├─ Test 8: rag + 16c
  └─ Test 9: rag + 32c
  ↓
Collect All Results
  ↓
Generate Comparison Report
  ↓
Cleanup (always runs)
```

### Inventory

#### `inventory/awx-dynamic-inventory.py`
**Purpose**: Generate Ansible inventory dynamically from AWX survey inputs
**How to Use**:
1. **Resources** → **Inventories** → Select inventory
2. **Sources** tab → **Add**
3. **Source**: Custom Script
4. Paste this Python script
5. **Sync** to generate inventory

**What it Does**:
- Reads configuration from environment variables (set by AWX from survey)
- Generates Ansible inventory JSON dynamically
- Eliminates need for static inventory files
- Allows users to change DUT/load gen via survey without editing files

**Environment Variables Used**:
- `DUT_HOST`: DUT hostname/IP
- `DUT_USER`: SSH user for DUT
- `LOADGEN_MODE`: "localhost" or "remote"
- `LOADGEN_HOST`: Load gen hostname (if remote)
- `LOADGEN_USER`: SSH user for load gen (if remote)
- `VLLM_IMAGE`: vLLM container image
- `GUIDELLM_IMAGE`: GuideLLM container image
- `RESULTS_DIR`: Results directory path

**Output**:
```json
{
  "all": {
    "children": ["dut", "load_generator"]
  },
  "dut": {
    "hosts": {
      "my-dut": {
        "ansible_host": "ec2-3-144-144-132.us-east-2.compute.amazonaws.com",
        "ansible_user": "ec2-user"
      }
    }
  },
  "load_generator": {
    "hosts": {
      "my-loadgen": {
        "ansible_host": "localhost",
        "ansible_connection": "local",
        ...
      }
    }
  }
}
```

## How Files Work Together

```
1. User opens AWX web UI
   ↓
2. Clicks "Launch" on Job Template
   (defined in job-templates/llm-guidellm-test.yml)
   ↓
3. Survey form appears
   (defined in surveys/llm-guidellm-test.yml)
   ↓
4. User fills out form:
   - DUT: ec2-3-144-144-132.us-east-2.compute.amazonaws.com
   - Model: Qwen/Qwen3-0.6B
   - Workload: chat
   - Cores: 16cores-single-socket
   ↓
5. AWX sets environment variables from survey
   ↓
6. Dynamic inventory script runs
   (inventory/awx-dynamic-inventory.py)
   - Reads environment variables
   - Generates inventory JSON
   ↓
7. AWX runs Ansible playbook
   (playbooks/llm/run-guidellm-test.yml)
   - Uses generated inventory
   - Uses SSH credential for DUT access
   - Uses HF Token credential (if attached)
   - Passes survey vars as extra_vars
   ↓
8. Playbook executes on DUT and load generator
   ↓
9. Results collected and displayed in AWX UI
```

## Import Checklist

When setting up AWX, import in this order:

- [ ] 1. **Credential Type**: `credentials/huggingface-token.yml`
  - Administration → Credential Types → Add

- [ ] 2. **Credentials**: Create actual credentials
  - Resources → Credentials → Add (Machine credential for SSH)
  - Resources → Credentials → Add (HuggingFace Token)

- [ ] 3. **Project**: Link to Git repository
  - Resources → Projects → Add

- [ ] 4. **Inventory**: Create inventory
  - Resources → Inventories → Add
  - Option A: Static (add hosts manually)
  - Option B: Dynamic (add source with `inventory/awx-dynamic-inventory.py`)

- [ ] 5. **Job Template**: `job-templates/llm-guidellm-test.yml`
  - Resources → Templates → Add → Job Template
  - Link to project, playbook, inventory, credentials

- [ ] 6. **Survey**: `surveys/llm-guidellm-test.yml`
  - Job Template → Survey → Add questions

- [ ] 7. **Workflow** (Optional): `workflows/llm-model-test-suite.yml`
  - Resources → Templates → Add → Workflow Template
  - Visualizer → Add nodes

- [ ] 8. **Test**: Launch a job!
  - Resources → Templates → Launch

## Customization

### Adding More Models

Edit `surveys/llm-guidellm-test.yml`:
```yaml
- question_name: "Model"
  choices:
    - "Qwen/Qwen3-0.6B"
    - "your-org/your-model"  # Add here
```

### Adding More Workloads

1. Define workload in `ansible/inventory/group_vars/all/test-workloads.yml`
2. Add to survey choices in `surveys/llm-guidellm-test.yml`

### Adding More Core Configs

1. Define in `ansible/inventory/group_vars/all/hardware-profiles.yml`
2. Add to survey choices in `surveys/llm-guidellm-test.yml`

### Custom Job Templates

Copy `job-templates/llm-guidellm-test.yml` and modify:
- Change playbook path
- Add/remove survey questions
- Adjust extra_vars mapping

## Maintenance

### Updating Playbooks

AWX project syncs from Git:
1. Push changes to Git repository
2. **Resources** → **Projects** → **Sync** (circular arrows)
3. Job templates automatically use updated playbooks

### Backing Up Configuration

Export AWX configuration:
```bash
awx-cli export \
  --credentials \
  --inventory \
  --job_templates \
  --workflow_job_templates \
  > awx-backup.json
```

Restore:
```bash
awx-cli import < awx-backup.json
```

### Upgrading AWX

```bash
# Docker Compose
cd awx
git pull
make docker-compose

# Kubernetes
kubectl set image deployment/awx awx=<new-version>
```

## See Also

- [AWX Official Documentation](https://ansible.readthedocs.io/projects/awx/en/latest/)
- [Ansible Playbooks Documentation](https://docs.ansible.com/ansible/latest/playbook_guide/)
- [Main Testing Framework README](../../README.md)
