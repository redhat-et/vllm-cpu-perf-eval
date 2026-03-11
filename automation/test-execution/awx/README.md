# AWX Test Execution Environment

This directory contains the configuration for running vLLM performance tests using AWX (Ansible AWX).

## Quick Start

```bash
# From automation/test-execution/awx directory
make kind-quickstart
```

This will:
1. Create a local KIND cluster
2. Deploy AWX operator
3. Build custom execution environment
4. Deploy AWX with pre-configured job templates
5. Configure inventories and credentials

Access AWX at: <http://localhost:30080>
- Username: `admin`
- Password: `password`  <!-- pragma: allowlist secret -->

## What is an Execution Environment?

An **Execution Environment (EE)** is a containerized image that AWX uses to run Ansible playbooks. It's essentially a Docker/Podman image containing:

- Ansible core
- Python dependencies
- Ansible collections
- System packages
- Everything your playbooks need

**Why?** AWX runs playbooks inside containers for:
- ✅ **Isolation**: Different jobs can use different Ansible versions
- ✅ **Reproducibility**: Same environment every time
- ✅ **Portability**: Works on any AWX instance
- ✅ **Security**: Jobs are sandboxed from AWX control plane

## Our Custom Execution Environment: `vllm-awx-ee`

### What's Inside

```yaml
# execution-environment.yml
base_image: quay.io/ansible/awx-ee:latest

dependencies:
  galaxy: requirements.yml
    - containers.podman  # For managing vLLM containers on DUT
    - ansible.posix      # For rsync/synchronize module
```

### Why Custom?

The default AWX EE doesn't include:
- ❌ `containers.podman` collection (needed for vLLM container management)
- ❌ `ansible.posix` collection (needed for result collection)

### File Structure

```
automation/test-execution/awx/
├── execution-environment.yml    # EE definition
├── requirements.yml             # Ansible collections to install
├── configure-awx.yml           # AWX setup playbook
├── Makefile                    # Build/deploy commands
└── README.md                   # This file
```

## Building the Execution Environment

### Local Build (for KIND)

```bash
# Build EE image locally
make kind-build-ee

# Load into KIND cluster
make kind-load-ee

# Or do both at once
make kind-quickstart
```

### Build for Production (quay.io)

The execution environment is automatically built and pushed to quay.io via GitHub Actions:

**Registry**: `quay.io/octo-et/vllm-cpu-perf-eval`

**Trigger**: Push to `main` branch or manual workflow dispatch

**Workflow**: `.github/workflows/build-execution-environment.yml`

## Using the Execution Environment

### In AWX UI

1. Navigate to: **Administration > Execution Environments**
2. You'll see: `vLLM AWX EE` (image: `vllm-awx-ee:latest`)
3. Job templates automatically use this EE

### Changing EE for a Job

1. Go to: **Resources > Templates > [Your Template]**
2. Click **Edit**
3. Change **Execution Environment** dropdown
4. **Save**

### Using Production Image

To use the quay.io image instead of locally built:

```yaml
# In AWX deployment (awx-deployment.yml)
spec:
  ee_images:
    - name: vllm-awx-ee
      image: quay.io/octo-et/vllm-cpu-perf-eval:latest
```

## Customizing the Execution Environment

### Adding Ansible Collections

1. Edit `requirements.yml`:
   ```yaml
   collections:
     - name: community.general
       version: ">=8.0.0"
   ```

2. Rebuild:
   ```bash
   make kind-build-ee
   make kind-load-ee
   ```

### Adding Python Packages

1. Create `requirements.txt` in this directory:
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

3. Rebuild as above

### Adding System Packages

Use `additional_build_steps`:

```yaml
additional_build_steps:
  prepend_final:
    - RUN dnf install -y git vim
```

## Troubleshooting

### ImagePullBackOff Error

**Symptom**: AWX pods fail with "ImagePullBackOff"

**Cause**: KIND cluster can't find the EE image

**Fix**:
```bash
make kind-load-ee
```

### Collections Not Found

**Symptom**: "Collection not found" errors in job output

**Cause**: Collection not installed in EE

**Fix**:
1. Add collection to `requirements.yml`
2. Rebuild EE: `make kind-build-ee && make kind-load-ee`

### Python Module Not Found

**Symptom**: "ModuleNotFoundError: No module named 'X'"

**Cause**: Python package not in EE

**Fix**:
1. Create `requirements.txt` with the package
2. Update `execution-environment.yml` to include it
3. Rebuild EE

## Available Make Targets

```bash
make help                    # Show all available targets
make kind-quickstart         # Complete setup (recommended)
make kind-build-ee          # Build execution environment
make kind-load-ee           # Load EE into KIND cluster
make kind-status            # Show cluster status
make kind-logs              # Show AWX logs
make kind-configure         # Reconfigure AWX
make kind-stop              # Stop KIND cluster
make kind-restart           # Restart cluster
make clean-all              # Remove everything
```

## Architecture

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
│  Job Execution                           │
│  ├─ Pull EE image: vllm-awx-ee:latest   │
│  ├─ Launch container from EE             │
│  ├─ Run Ansible playbook inside          │
│  └─ Terminate container                  │
└─────────────────────────────────────────┘
```

## Production Deployment Considerations

### Using quay.io Image

For production AWX (not KIND), reference the public image:

```yaml
# awx.yaml
apiVersion: awx.ansible.com/v1beta1
kind: AWX
metadata:
  name: awx
spec:
  ee_images:
    - name: vllm-awx-ee
      image: quay.io/octo-et/vllm-cpu-perf-eval:latest
```

### Image Pull Credentials

If using a private registry, create a secret:

```bash
kubectl create secret docker-registry quay-creds \
  --docker-server=quay.io \
  --docker-username=<username> \
  --docker-password=<password> \
  -n awx
```

Then reference in AWX spec:
```yaml
spec:
  ee_pull_credentials_secret: quay-creds
```

### Version Pinning

Use tagged versions in production:

```yaml
spec:
  ee_images:
    - name: vllm-awx-ee
      image: quay.io/octo-et/vllm-cpu-perf-eval:v1.0.0
```

## Resources

- [Ansible Builder Documentation](https://ansible-builder.readthedocs.io/)
- [AWX Operator Documentation](https://ansible.readthedocs.io/projects/awx-operator/)
- [Execution Environment Guide](https://docs.ansible.com/automation-controller/latest/html/userguide/execution_environments.html)
- [KIND Documentation](https://kind.sigs.k8s.io/)

## Support

For issues:
1. Check logs: `make kind-logs`
2. Check status: `make kind-status`
3. Verify EE is loaded: `kubectl get awx awx -n awx -o yaml | grep -A 5 ee_images`
4. Open an issue on GitHub
