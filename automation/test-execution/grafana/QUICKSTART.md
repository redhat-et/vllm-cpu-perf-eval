# Quick Start Guide - Prometheus Monitoring on Ansible Controller

This guide shows you how to run the Prometheus monitoring stack on your **local machine** (Ansible controller) to monitor vLLM performance tests running on AWS EC2.

## Architecture

```
┌──────────────────────────────┐
│ DUT (AWS EC2)                │
│  - vLLM server :8000         │
│  - Exposes /metrics          │
│  - Shut down after tests ✓   │
└────────────┬─────────────────┘
             │ SSH forward tunnel (optional, live metrics)
             │
┌────────────▼─────────────────┐
│ LOADGEN (AWS EC2)            │
│  - Runs GuideLLM benchmarks  │
│  - Ansible client            │
│  - Shut down after tests ✓   │
└────────────┬─────────────────┘
             │ SSH reverse tunnel + HTTP push
             │
┌────────────▼───────────────────────────────────┐
│ YOUR LAPTOP (Ansible Controller) ← RUNS HERE! │
│  ┌──────────────────────────────────────────┐ │
│  │ Prometheus Pushgateway :9091             │ │
│  │  ← Receives results from LOADGEN         │ │
│  └──────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────┐ │
│  │ Prometheus :9090                         │ │
│  │  - Scrapes Pushgateway (GuideLLM results)│ │
│  │  - Scrapes vLLM live metrics (optional)  │ │
│  │  - Stores ALL data locally               │ │
│  └──────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────┐ │
│  │ Grafana :3000                            │ │
│  │  - Dashboards for analysis               │ │
│  │  - Always accessible at localhost:3000   │ │
│  └──────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ No cloud costs for monitoring infrastructure
- ✅ Shut down expensive EC2 instances immediately after tests
- ✅ Keep all historical data on your local machine forever
- ✅ Access Grafana anytime at <http://localhost:3000>
- ✅ No exposed ports or router configuration needed (uses SSH tunnels)

## Prerequisites

- Docker or Podman installed on your local machine
- SSH access to AWS EC2 instances (DUT and LOADGEN)
- SSH key for EC2 instances (e.g., `~/mtahhan.pem`)

## Step 1: Start Monitoring Stack Locally

On your local machine:

```bash
cd automation/test-execution/grafana

# Start Prometheus, Pushgateway, and Grafana
docker-compose up -d

# Verify all services are running
docker-compose ps

# Check logs if needed
docker-compose logs -f
```

Expected output:
```
NAME                STATUS              PORTS
vllm-grafana        Up (healthy)       0.0.0.0:3000->3000/tcp
vllm-prometheus     Up (healthy)       0.0.0.0:9090->9090/tcp
vllm-pushgateway    Up (healthy)       0.0.0.0:9091->9091/tcp
```

**Access the services:**
- Grafana: <http://localhost:3000> (admin/admin)
- Prometheus: <http://localhost:9090>
- Pushgateway: <http://localhost:9091>

## Step 2: Set Up SSH Tunnels

The SSH tunnels allow:
1. **Reverse tunnel** - LOADGEN pushes results to your local Pushgateway
2. **Forward tunnel** - Your Prometheus scrapes live vLLM metrics from DUT

```bash
cd automation/test-execution/grafana/scripts

# Set your environment (or edit the script)
export DUT_HOSTNAME=ec2-3-17-205-30.us-east-2.compute.amazonaws.com
export LOADGEN_HOSTNAME=ec2-18-216-8-240.us-east-2.compute.amazonaws.com
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_SSH_KEY=~/mtahhan.pem

# Run the setup script
./setup-tunnels.sh setup
```

Expected output:
```
=== vLLM Metrics SSH Tunnel Setup ===

✓ Pushgateway reverse tunnel established
  Ansible on LOADGEN can now push to: http://localhost:9091

✓ vLLM metrics forward tunnel established
  Prometheus can now scrape: http://localhost:8000/metrics

=== Tunnel Status ===
✓ Pushgateway reverse tunnel: ACTIVE
✓ vLLM metrics forward tunnel: ACTIVE
```

**Check tunnel status anytime:**
```bash
./setup-tunnels.sh status
```

**Stop tunnels:**
```bash
./setup-tunnels.sh stop
```

## Step 3: Run Benchmarks with Prometheus Publishing

Now run your benchmarks. Results will automatically be pushed to your local Prometheus.

```bash
cd automation/test-execution/ansible

# Run benchmark with Prometheus publishing enabled
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "publish_to_prometheus=true"
```

**What happens:**
1. GuideLLM runs on LOADGEN
2. Test completes, results saved locally on LOADGEN
3. Ansible role `prometheus_publisher` runs
4. Results pushed through reverse SSH tunnel to your local Pushgateway
5. Prometheus scrapes and stores the metrics
6. Available immediately in Grafana!

## Step 4: View Results in Grafana

Open Grafana: **<http://localhost:3000>**

**Login:** admin / admin (change on first login)

**Available Dashboards:**

1. **vLLM Load Sweep Analysis** - GuideLLM benchmark results
   - Throughput vs load curves
   - Latency breakdowns (TTFT, ITL, E2E)
   - Platform comparisons
   - Historical trends

2. **vLLM Live Metrics** - Real-time server performance (during tests)
   - Request latencies
   - Token throughput
   - Queue metrics
   - Cache usage

## Network/Firewall Rules

**Good news:** With the reverse SSH tunnel approach, you don't need to:
- ❌ Open any ports on your local machine
- ❌ Configure your router/firewall
- ❌ Expose Pushgateway to the internet
- ❌ Deal with dynamic IP addresses

The SSH tunnel handles everything securely!

**What you DO need:**
- ✅ Outbound SSH access from your machine to AWS EC2 (port 22)
- ✅ AWS security groups allowing SSH from your IP

**AWS Security Group Requirements:**
```yaml
# DUT security group
Inbound:
  - Port 22 (SSH) from your IP
  - Port 8000 (vLLM API) from LOADGEN IP

# LOADGEN security group
Inbound:
  - Port 22 (SSH) from your IP
```

No other ports need to be opened!

## Monitoring During Tests

### Option A: Watch Live Metrics

If you want to see real-time vLLM metrics during a test:

1. **Start SSH tunnel** (covered in Step 2)
2. **Start vLLM with metrics enabled:**
   ```bash
   # On DUT
   vllm serve meta-llama/Llama-3.2-1B-Instruct --enable-metrics
   ```
3. **Open Grafana:** <http://localhost:3000>
4. **Select:** vLLM Live Metrics dashboard
5. **Run benchmark** and watch metrics update in real-time!

### Option B: Just Get Results

If you only care about final results (not live monitoring):

1. **Don't start forward tunnel** (only reverse tunnel needed)
2. **Run benchmark** with `publish_to_prometheus=true`
3. **View results** in Grafana after test completes

## Shutting Down Cloud Resources

After your benchmark completes:

```bash
# Results are already on your local machine via Pushgateway
# Safe to shut down EC2 instances to save costs!

# Stop DUT
ssh ec2-user@$DUT_HOSTNAME "sudo shutdown now"

# Stop LOADGEN
ssh ec2-user@$LOADGEN_HOSTNAME "sudo shutdown now"
```

Your data persists locally in:
- `automation/test-execution/grafana/prometheus-data/`
- `automation/test-execution/grafana/pushgateway-data/`

## Troubleshooting

### Pushgateway Not Receiving Metrics

**Check tunnel is active:**
```bash
cd automation/test-execution/grafana/scripts
./setup-tunnels.sh status
```

**Test from LOADGEN:**
```bash
# SSH to LOADGEN
ssh ec2-user@$LOADGEN_HOSTNAME

# Test Pushgateway is reachable
curl http://localhost:9091/-/healthy

# Should return: Pushgateway is Healthy.
```

### vLLM Metrics Not Showing

**Check forward tunnel:**
```bash
./setup-tunnels.sh status
```

**Check vLLM is running with metrics:**
```bash
# On DUT
curl http://localhost:8000/metrics
```

**Check from local machine:**
```bash
curl http://localhost:8000/metrics
```

### Tunnels Disconnecting

The tunnels use `ServerAliveInterval=60` to stay connected. If they still disconnect:

```bash
# Add to ~/.ssh/config
Host ec2-*.compute.amazonaws.com
    ServerAliveInterval 60
    ServerAliveCountMax 3
    TCPKeepAlive yes
```

## Example Workflow

Complete end-to-end workflow:

```bash
# 1. Start monitoring stack locally
cd automation/test-execution/grafana
docker-compose up -d

# 2. Set up SSH tunnels
cd scripts
export DUT_HOSTNAME=ec2-3-17-205-30.us-east-2.compute.amazonaws.com
export LOADGEN_HOSTNAME=ec2-18-216-8-240.us-east-2.compute.amazonaws.com
./setup-tunnels.sh setup

# 3. Run benchmark (Ansible on local machine)
cd ../../ansible
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "guidellm_rate=[0.1,0.5,1.0,1.5,2.0]" \
  -e "publish_to_prometheus=true"

# 4. View results
open http://localhost:3000

# 5. Shut down cloud resources (data already local!)
ssh ec2-user@$DUT_HOSTNAME "sudo shutdown now"
ssh ec2-user@$LOADGEN_HOSTNAME "sudo shutdown now"

# 6. Stop tunnels (no longer needed)
cd ../grafana/scripts
./setup-tunnels.sh stop
```

## Keeping Monitoring Stack Running

The monitoring stack is lightweight and can run continuously on your laptop:

```bash
# Check resource usage
docker stats

# Typical usage:
# Prometheus: ~200MB RAM, minimal CPU
# Pushgateway: ~50MB RAM, minimal CPU
# Grafana: ~100MB RAM, minimal CPU
```

To stop when not needed:
```bash
cd automation/test-execution/grafana
docker-compose down  # Stops but preserves data

# To remove everything including data:
docker-compose down -v
```

## Next Steps

- Review [PROMETHEUS.md](PROMETHEUS.md) for detailed configuration
- Check [README.md](README.md) for dashboard customization
- Explore [Grafana PromQL](https://prometheus.io/docs/prometheus/latest/querying/basics/) for custom queries

## Support

Issues? Check:
1. `docker-compose logs` - Service logs
2. `./setup-tunnels.sh status` - Tunnel status
3. <http://localhost:9090/targets> - Prometheus scrape status
4. <http://localhost:9091> - Pushgateway metrics browser
