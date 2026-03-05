# Run Concurrency Test on EC2 via AWX

Your AWX has been configured with:
- **DUT**: ec2-3-144-245-130.us-east-2.compute.amazonaws.com (ec2-user)
- **Load Generator**: ec2-18-222-252-249.us-east-2.compute.amazonaws.com
- **Project Branch**: concurrency-tests-awx

## Step 1: Add SSH Credential (2 minutes)

1. Open AWX: [http://localhost:30080](http://localhost:30080)
2. Login: `admin` / `password`
3. Navigate to: **Resources** → **Credentials** → **Add**
4. Fill out:
   - **Name**: `DUT SSH Key`
   - **Credential Type**: Machine
   - **Username**: `ec2-user`
   - **SSH Private Key**: Paste contents of `~/.ssh/mtahhan-key-pair-useast2.pem`
5. **Save**

## Step 2: Add HuggingFace Token (2 minutes)

Since you're testing `meta-llama/Llama-3.2-1B-Instruct`, you need a HuggingFace token.

1. Navigate to: **Resources** → **Credentials** → **Add**
2. Fill out:
   - **Name**: `HuggingFace Token`
   - **Credential Type**: HuggingFace Token (custom type already created)
   - **HuggingFace API Token**: Your token (e.g., `hf_xxxxx`)
3. **Save**

## Step 3: Launch Your Concurrency Test (1 minute)

1. Navigate to: **Resources** → **Templates**
2. Find: **LLM Concurrent Load Test**
3. Click the **Launch** button (🚀 rocket icon)
4. In the launch dialog:

   **Credentials Tab:**
   - Select: `DUT SSH Key`
   - Select: `HuggingFace Token`

   **Variables Tab:** (paste this YAML)
   ```yaml
   test_model: meta-llama/Llama-3.2-1B-Instruct
   base_workload: chat
   requested_cores: 16
   skip_phase_2: true
   skip_phase_3: true
   guidellm_max_seconds: 300
   concurrency_levels: [1, 2, 4]
   health_check_wait_timeout: 2400
   ```

5. Click **Next** → **Launch**

## What Will Happen

AWX will now:
1. ✓ Connect to your DUT via SSH
2. ✓ Detect NUMA topology on the DUT
3. ✓ Auto-allocate 16 cores with optimal NUMA configuration
4. ✓ Start vLLM container with Llama-3.2-1B-Instruct model
5. ✓ Wait up to 2400 seconds for vLLM to become healthy
6. ✓ Run GuideLLM concurrent load tests at levels: 1, 2, 4 concurrent users
7. ✓ Each concurrency level runs for max 300 seconds
8. ✓ Collect results and logs

## Watch Progress

- Real-time job output in AWX
- Each concurrency level will show throughput and latency metrics
- Phase 2 and 3 are skipped (only baseline/phase 1 runs)

## Results Location

Results will be stored on the load generator at:
```
~/benchmark-results/meta-llama__Llama-3.2-1B-Instruct/chat-<timestamp>/
```

And locally fetched to:
```
results/llm/meta-llama__Llama-3.2-1B-Instruct/chat-<timestamp>/
```

## Alternative: Quick Command Line Test

If you prefer to test connectivity first without AWX:

```bash
# Set environment variables
export DUT_HOSTNAME=ec2-3-144-245-130.us-east-2.compute.amazonaws.com
export LOADGEN_HOSTNAME=ec2-18-222-252-249.us-east-2.compute.amazonaws.com
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_SSH_KEY=$HOME/.ssh/mtahhan-key-pair-useast2.pem
export HF_TOKEN=hf_xxxxx

# Test connectivity
cd automation/test-execution/ansible
ansible -i inventory/hosts.yml all -m ping

# Run test directly (if connectivity works)
ansible-playbook -i inventory/hosts.yml llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "requested_cores=16" \
  -e "skip_phase_2=true" \
  -e "skip_phase_3=true" \
  -e "guidellm_max_seconds=300" \
  -e "concurrency_levels=[1,2,4]" \
  -e "health_check_wait_timeout=2400"
```

## Troubleshooting

**Job fails with "Permission denied":**
- Verify SSH key is correct in AWX credential
- Test manually: `ssh -i ~/.ssh/mtahhan-key-pair-useast2.pem ec2-user@ec2-3-144-245-130.us-east-2.compute.amazonaws.com`

**Job fails with "HuggingFace authentication required":**
- Ensure HuggingFace Token credential is selected when launching
- Verify token has access to meta-llama models

**vLLM health check times out:**
- Check DUT has sufficient resources (CPU, RAM)
- Large models may take longer to load - 2400s should be enough
- View DUT logs in job output for specific error

**GuideLLM connection fails:**
- Ensure security groups allow traffic from loadgen to DUT on port 8000
- Check if running on same VPC or public internet

## Expected Timeline

- Model download (first run only): 2-10 minutes
- vLLM startup: 30-120 seconds
- Health check: 5-10 seconds
- Each concurrency level test: ~300 seconds (5 minutes)
- Total test duration: ~20-25 minutes (including warmup)

---

**Ready to run!** Open [AWX](http://localhost:30080) and launch your test.
