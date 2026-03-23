# Grafana Live Metrics Setup

This guide explains how to view real-time vLLM server metrics in Grafana during benchmark execution.

## Overview

Grafana can display two types of metrics:

1. **Batch Metrics** (Post-Test) - GuideLLM results pushed after benchmark completes
   - Always available via Pushgateway
   - No additional setup required

2. **Live Metrics** (During Test) - Real-time vLLM server metrics
   - Requires SSH tunnel to remote vLLM server
   - Shows queue depth, cache usage, token rates in real-time
   - **Setup required** (documented below)

## Architecture

```
┌─────────────────────┐
│  Remote vLLM Server │
│  (AWS/Cloud)        │
│  Port 8000/metrics  │
└──────────┬──────────┘
           │
           │ SSH Tunnel
           │ (forwards remote port 8000 → local port 8000)
           │
┌──────────▼──────────┐
│  Local Machine      │
│  localhost:8000     │
└──────────┬──────────┘
           │
           │ Scrapes every 10s
           │
┌──────────▼──────────┐
│  Prometheus         │
│  (in container)     │
└──────────┬──────────┘
           │
           │ Queries
           │
┌──────────▼──────────┐
│  Grafana Dashboard  │
│  localhost:3000     │
└─────────────────────┘
```

## Prerequisites

- Grafana stack running: `ansible-playbook start-grafana.yml`
- SSH access to vLLM server
- Environment variables set:
  - `DUT_HOSTNAME` - vLLM server hostname/IP
  - `ANSIBLE_SSH_KEY` - Path to SSH private key

## Setup SSH Tunnel

### Before Running Your Benchmark

```bash
# 1. Verify environment variables
echo $DUT_HOSTNAME        # Should show: ec2-xx-xx-xx-xx.compute.amazonaws.com (or similar)
echo $ANSIBLE_SSH_KEY     # Should show: /path/to/your/key.pem

# 2. Create SSH tunnel
ssh -L 8000:localhost:8000 ec2-user@$DUT_HOSTNAME -N -f -i $ANSIBLE_SSH_KEY

# 3. Verify tunnel is active
ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep

# 4. Test metrics endpoint
curl http://localhost:8000/metrics | head -20
```

**Command Breakdown:**
- `-L 8000:localhost:8000` - Forward local port 8000 to remote port 8000
- `-N` - Don't execute remote commands (just forward ports)
- `-f` - Run in background
- `-i $ANSIBLE_SSH_KEY` - Use your SSH private key

### Verify Prometheus is Scraping

```bash
# Check Prometheus targets page
open http://localhost:9090/targets

# You should see:
# - pushgateway (always UP)
# - vllm-live (UP when tunnel active, DOWN when no tunnel)
```

### View Live Metrics in Grafana

```bash
# Open Grafana
open http://localhost:3000

# Navigate to the vLLM dashboard
# Dashboards → vLLM CPU Performance

# You should see real-time data updating every 10 seconds:
# - Request queue depth (running/waiting)
# - CPU cache usage
# - Token generation rates
# - Request processing metrics
```

## During Your Benchmark

Once the tunnel is active, run your benchmark normally:

```bash
ansible-playbook -i inventory/hosts.yml \
    llm-benchmark-concurrent-load.yml \
    -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
    -e "base_workload=chat" \
    -e "requested_cores=16" \
    -e "guidellm_rate=[1,2,4,8]"
```

**Watch Grafana in real-time** to see:
- Queue building up as load increases
- Cache utilization changes
- Token generation rates
- Server-side bottlenecks

## After Your Benchmark

### Close the SSH Tunnel

```bash
# Find the tunnel process
ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep

# Kill the tunnel (replace PID with actual process ID)
kill <PID>

# Or kill all SSH tunnels to that host
pkill -f "ssh.*$DUT_HOSTNAME.*8000"
```

### Verify Tunnel Closed

```bash
# Should return nothing
ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep

# Prometheus target should show vllm-live as DOWN
# http://localhost:9090/targets
```

## Troubleshooting

### Tunnel Won't Connect

```bash
# Test SSH connectivity first
ssh -i $ANSIBLE_SSH_KEY ec2-user@$DUT_HOSTNAME

# Check if vLLM is running on remote server
ssh -i $ANSIBLE_SSH_KEY ec2-user@$DUT_HOSTNAME "curl http://localhost:8000/metrics | head -5"

# Check for existing tunnel blocking the port
lsof -i :8000
```

### Grafana Shows No Data

**Check 1: Is tunnel active?**
```bash
ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep
curl http://localhost:8000/metrics
```

**Check 2: Is Prometheus scraping?**
```bash
# Visit: http://localhost:9090/targets
# vllm-live should show as UP
```

**Check 3: Check Prometheus query**
```bash
# Visit: http://localhost:9090/graph
# Query: vllm_num_requests_running
# Should return results if tunnel is working
```

**Check 4: Grafana data source**
```bash
# Visit: http://localhost:3000/datasources
# Prometheus should be default and working
# Click "Test" to verify connection
```

### Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill existing tunnel
pkill -f "ssh.*8000"

# Or use a different local port
ssh -L 8001:localhost:8000 ec2-user@$DUT_HOSTNAME -N -f -i $ANSIBLE_SSH_KEY

# Update prometheus.yml to scrape localhost:8001 instead
```

### SSH Key Permission Issues

```bash
# SSH keys must have restricted permissions
chmod 600 $ANSIBLE_SSH_KEY

# Verify
ls -la $ANSIBLE_SSH_KEY
# Should show: -rw------- (600)
```

## What Metrics Are Available?

### vLLM Server Metrics (via /metrics endpoint)

**Queue Metrics:**
- `vllm:num_requests_running` - Currently executing requests
- `vllm:num_requests_waiting` - Queued requests waiting for execution

**Cache Metrics:**
- `vllm:cpu_cache_usage_perc` - CPU KV cache utilization percentage
- `vllm:gpu_cache_usage_perc` - GPU KV cache utilization (if applicable)

**Token Processing:**
- `vllm:prompt_tokens_total` - Total prompt tokens processed
- `vllm:generation_tokens_total` - Total generated tokens
- `vllm:time_to_first_token_seconds` - TTFT latency histogram
- `vllm:time_per_output_token_seconds` - Token generation time histogram

**Request Metrics:**
- `vllm:request_success_total` - Successfully completed requests
- `vllm:e2e_request_latency_seconds` - End-to-end request latency

## Best Practices

### 1. Start Tunnel Before Test
```bash
# Start tunnel
ssh -L 8000:localhost:8000 ec2-user@$DUT_HOSTNAME -N -f -i $ANSIBLE_SSH_KEY

# Wait for Prometheus to detect (10-15 seconds)
sleep 15

# Verify in Prometheus targets
curl http://localhost:9090/targets | grep vllm-live

# Then run benchmark
```

### 2. Keep Tunnel Open for Entire Test
- Don't close tunnel until benchmark completes
- Tunnel automatically stays open even if SSH session disconnects
- Background process (`-f`) means you can close terminal

### 3. Monitor Tunnel Health
```bash
# Periodically check tunnel is still active
watch -n 30 'ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep'

# Or set up a script to auto-restart if tunnel dies
```

### 4. Clean Up After Tests
```bash
# Always close tunnel when done
pkill -f "ssh.*$DUT_HOSTNAME.*8000"

# Verify closed
lsof -i :8000  # Should return nothing
```

## Alternative: Automation Script

If you run tests frequently, create a helper script:

```bash
# File: scripts/grafana-tunnel.sh
#!/bin/bash

set -e

command=$1

case $command in
    start)
        echo "Starting SSH tunnel to vLLM server..."
        if ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep > /dev/null; then
            echo "✓ Tunnel already running"
        else
            ssh -L 8000:localhost:8000 ec2-user@$DUT_HOSTNAME -N -f -i $ANSIBLE_SSH_KEY
            sleep 3
            if ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep > /dev/null; then
                echo "✓ Tunnel started successfully"
                echo "Testing metrics endpoint..."
                curl -s http://localhost:8000/metrics | head -5
            else
                echo "✗ Failed to start tunnel"
                exit 1
            fi
        fi
        ;;

    stop)
        echo "Stopping SSH tunnel..."
        pkill -f "ssh.*$DUT_HOSTNAME.*8000" || echo "No tunnel found"
        echo "✓ Tunnel stopped"
        ;;

    status)
        if ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep > /dev/null; then
            echo "✓ Tunnel is ACTIVE"
            ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep
        else
            echo "✗ Tunnel is NOT running"
        fi
        ;;

    test)
        echo "Testing tunnel connectivity..."
        if curl -s http://localhost:8000/metrics | head -5; then
            echo "✓ Metrics endpoint accessible"
        else
            echo "✗ Cannot reach metrics endpoint"
            exit 1
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|status|test}"
        exit 1
        ;;
esac
```

**Usage:**
```bash
# Make executable
chmod +x scripts/grafana-tunnel.sh

# Start tunnel
./scripts/grafana-tunnel.sh start

# Check status
./scripts/grafana-tunnel.sh status

# Test connectivity
./scripts/grafana-tunnel.sh test

# Stop tunnel
./scripts/grafana-tunnel.sh stop
```

## Summary

**Live Grafana metrics require an SSH tunnel** because:
1. vLLM server runs on remote cloud infrastructure (AWS/Azure/etc.)
2. Port 8000 (`/metrics` endpoint) is not publicly exposed
3. Prometheus runs locally and needs to scrape remote metrics
4. SSH tunnel forwards remote port 8000 to local port 8000

**Quick Start:**
```bash
# 1. Start tunnel
ssh -L 8000:localhost:8000 ec2-user@$DUT_HOSTNAME -N -f -i $ANSIBLE_SSH_KEY

# 2. Verify
curl http://localhost:8000/metrics | head -20

# 3. Check Prometheus
open http://localhost:9090/targets

# 4. Open Grafana
open http://localhost:3000

# 5. Run your benchmark
ansible-playbook ...

# 6. Clean up
pkill -f "ssh.*$DUT_HOSTNAME.*8000"
```

**Remember:** The tunnel must be active BEFORE and DURING your benchmark for live metrics to appear in Grafana!
