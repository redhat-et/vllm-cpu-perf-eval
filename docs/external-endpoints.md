# External vLLM Endpoint Support

This guide explains how to run benchmarks against existing vLLM deployments without managing the vLLM container through Ansible.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Authentication](#authentication)
- [Cloud Provider Examples](#cloud-provider-examples)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

## Overview

The vLLM CPU Performance Evaluation framework supports two modes:

1. **Managed Mode** (default): Ansible sets up and manages vLLM in a Podman container on the DUT
2. **External Mode**: Run benchmarks against any existing vLLM HTTP endpoint

External mode is useful for testing:
- Production vLLM deployments
- Cloud-hosted vLLM instances (AWS, Azure, GCP)
- Kubernetes-managed vLLM services
- Development/staging environments
- vLLM instances managed by other tools

## Quick Start

### Basic HTTP Endpoint

Update your [inventory/hosts.yml](../automation/test-execution/ansible/inventory/hosts.yml):

```yaml
vllm_endpoint:
  mode: "external"
  external:
    url: "http://my-vllm-instance.example.com:8000"
```

Then run tests normally:

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_name=16cores-single-socket"
```

The playbook will:
- Skip vLLM container setup on DUT
- Configure the load generator to use your external endpoint
- Run health checks against the external endpoint
- Execute benchmarks normally
- Collect benchmark results (but skip DUT container logs)

## Configuration Reference

### Full Configuration Structure

```yaml
vllm_endpoint:
  # Mode: "managed" (default) or "external"
  mode: "external"

  # External endpoint configuration
  external:
    # Required: Full URL including protocol and port
    url: "http://vllm-host.example.com:8000"

    # Optional: API key authentication
    api_key:
      enabled: false
      source: "env"           # Options: env, file, vault, prompt
      env_var: "VLLM_API_KEY" # Used when source=env
      file_path: null         # Used when source=file
      vault_var: null         # Used when source=vault
```

### URL Format

The external URL must be a complete HTTP/HTTPS URL:

**Valid formats:**
```yaml
url: "http://10.0.1.50:8000"                      # Direct IP
url: "http://vllm-server.local:8000"              # Hostname
url: "https://vllm-prod.company.com"              # HTTPS (port 443 assumed)
url: "http://vllm-lb.k8s.cluster.local:8000"      # Kubernetes service
```

**Invalid formats:**
```yaml
url: "vllm-server:8000"           # Missing protocol
url: "10.0.1.50"                  # Missing port and protocol
url: "http://vllm-server"         # Missing port (will default to 8000)
```

## Authentication

### Environment Variable (Recommended)

```yaml
vllm_endpoint:
  mode: "external"
  external:
    url: "https://vllm-prod.company.com"
    api_key:
      enabled: true
      source: "env"
      env_var: "VLLM_API_KEY"
```

```bash
export VLLM_API_KEY="your-api-key-here"  # pragma: allowlist secret

ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test.yml \
  ...
```

### File-based

Store the API key in a file:

```bash
echo "your-api-key" > /etc/secrets/vllm-api-key
chmod 600 /etc/secrets/vllm-api-key
```

Configure in inventory:

```yaml
vllm_endpoint:
  mode: "external"
  external:
    url: "https://vllm-prod.company.com"
    api_key:
      enabled: true
      source: "file"
      file_path: "/etc/secrets/vllm-api-key"
```

### Ansible Vault

Store the API key in an Ansible vault:

```bash
ansible-vault encrypt_string 'your-api-key' --name 'vllm_api_key_secret'
```

Add to your inventory:

```yaml
vllm_api_key_secret: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          ...encrypted content...

vllm_endpoint:
  mode: "external"
  external:
    url: "https://vllm-prod.company.com"
    api_key:
      enabled: true
      source: "vault"
      vault_var: "{{ vllm_api_key_secret }}"
```

### Interactive Prompt

```yaml
vllm_endpoint:
  mode: "external"
  external:
    url: "https://vllm-prod.company.com"
    api_key:
      enabled: true
      source: "prompt"
```

Ansible will prompt for the API key when the playbook runs.

## Cloud Provider Examples

### AWS ECS

For a vLLM service running in AWS ECS:

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Use the ECS service load balancer DNS
    url: "http://vllm-lb-1234567890.us-east-1.elb.amazonaws.com:8000"
    api_key:
      enabled: false
```

### AWS EKS (Kubernetes)

For vLLM running in EKS with a LoadBalancer service:

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Use the Kubernetes LoadBalancer external IP/DNS
    url: "http://a1b2c3d4e5f6.us-west-2.elb.amazonaws.com:8000"
    api_key:
      enabled: true
      source: "env"
      env_var: "VLLM_API_KEY"
```

### Azure Container Instances

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Use the container instance FQDN
    url: "http://vllm-instance.eastus.azurecontainer.io:8000"
    api_key:
      enabled: false
```

### Azure Kubernetes Service

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Use the LoadBalancer service external IP
    url: "http://20.10.30.40:8000"
    api_key:
      enabled: true
      source: "env"
      env_var: "VLLM_API_KEY"
```

### Google Cloud Run

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Cloud Run provides HTTPS URLs
    url: "https://vllm-service-abc123-uc.a.run.app"
    api_key:
      enabled: true
      source: "env"
      env_var: "VLLM_API_KEY"
```

### Google GKE (Kubernetes)

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Use the GKE LoadBalancer external IP
    url: "http://34.56.78.90:8000"
    api_key:
      enabled: false
```

### Generic Kubernetes with Ingress

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Use the ingress hostname
    url: "https://vllm.mycompany.com"
    api_key:
      enabled: true
      source: "file"
      file_path: "/etc/kubernetes/secrets/vllm-api-key"
```

### Local vLLM Instance (for testing)

```yaml
vllm_endpoint:
  mode: "external"
  external:
    # Direct IP of another machine running vLLM
    url: "http://192.168.1.100:8000"
    api_key:
      enabled: false
```

## Troubleshooting

### Connection Refused

**Error:**
```
TASK [Wait for vLLM health endpoint] ***
fatal: [my-loadgen]: FAILED! => {"msg": "Connection refused"}
```

**Solutions:**
1. Verify the URL is correct and accessible from the load generator
2. Check firewall rules allow traffic to the vLLM endpoint
3. Ensure the vLLM service is running:
   ```bash
   curl http://your-vllm-endpoint:8000/health
   ```

### Authentication Failures

**Error:**
```
TASK [Wait for vLLM health endpoint] ***
fatal: [my-loadgen]: FAILED! => {"status": 401}
```

**Solutions:**
1. Verify the API key is correctly configured
2. Check the API key environment variable is set:
   ```bash
   echo $VLLM_API_KEY
   ```
3. For file-based keys, verify file permissions and content:
   ```bash
   ls -l /path/to/api-key-file
   cat /path/to/api-key-file
   ```

### Health Check Timeout

**Error:**
```
TASK [Wait for vLLM health endpoint] ***
fatal: [my-loadgen]: FAILED! => {"msg": "Timed out waiting for vLLM health check"}
```

**Solutions:**
1. Check if the endpoint is reachable but slow to respond
2. Increase health check timeout in [inventory/hosts.yml](../automation/test-execution/ansible/inventory/hosts.yml):
   ```yaml
   health_check:
     timeout: 600   # Increase from 300 to 600 seconds
     interval: 10   # Increase polling interval
   ```
3. Verify the model is loaded and ready:
   ```bash
   curl http://your-vllm-endpoint:8000/v1/models
   ```

### Wrong Model Loaded

**Error:**
```
Model mismatch: expected 'meta-llama/Llama-3.2-1B-Instruct' but found 'different-model'
```

**Solution:**
Ensure your external vLLM instance has the correct model loaded for your test. The framework expects the model specified in `test_model` to be available at the endpoint.

### SSL/TLS Certificate Errors

**Error:**
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solutions:**
1. For self-signed certificates, you may need to disable verification (not recommended for production):
   - This requires modifying the health-check.yml to add `validate_certs: false`
2. Better: Add the certificate to your system's trusted certificates
3. Or use HTTP instead of HTTPS for internal testing

## Limitations

When using external endpoints, the following limitations apply:

### No DUT Container Logs

The framework cannot collect vLLM container logs from external endpoints. Log collection is skipped in external mode.

**Workaround:** Access logs directly from your vLLM hosting environment:
- **Kubernetes:** `kubectl logs deployment/vllm`
- **Docker:** `docker logs vllm-container`
- **Cloud services:** Use the provider's logging solution (CloudWatch, Cloud Logging, etc.)

### No Container Metrics

System metrics (CPU usage, memory, container stats) from the DUT are not available in external mode.

**Workaround:** Use your hosting platform's monitoring:
- **Kubernetes:** Prometheus/Grafana, kubectl top
- **Cloud:** CloudWatch, Azure Monitor, Cloud Monitoring

### No Automatic Model Loading

The framework assumes the external endpoint already has the correct model loaded. It does not manage model loading.

**Workaround:** Ensure your vLLM instance is configured to load the required model before running tests.

### No Core/NUMA Configuration

Auto-configured tests (run-*-auto.yml playbooks) that detect NUMA topology and allocate cores will skip these steps in external mode.

**Impact:** These playbooks will work but won't configure CPU affinity on the external endpoint.

### No Cleanup

The framework cannot stop or cleanup external vLLM instances. Cleanup tasks are skipped in external mode.

**Impact:** The external vLLM instance continues running after tests complete.

## Switching Between Modes

You can easily switch between managed and external modes by changing the `mode` setting:

**Managed mode** (default behavior):
```yaml
vllm_endpoint:
  mode: "managed"  # or omit entirely, defaults to managed
```

**External mode:**
```yaml
vllm_endpoint:
  mode: "external"
  external:
    url: "http://your-endpoint:8000"
```

No other configuration changes are required. All playbooks support both modes.

## See Also

- [Main README](../README.md) - Project overview and getting started
- [Inventory Configuration](../automation/test-execution/ansible/inventory/hosts.yml) - Full inventory reference
- [Test Execution Guide](../automation/test-execution/ansible/README.md) - Running tests
