# AWX Quick Start Guide (15 Minutes)

Get your first vLLM performance test running in AWX in 15 minutes.

## Step 1: Install AWX (5 minutes)

**Option A: Automated Install (Recommended)**

```bash
# One command to install and start AWX!
cd automation/test-execution/awx
make quickstart

# This will:
# - Auto-detect Docker/Podman
# - Clone AWX repository
# - Start all containers
# - Wait for AWX to be ready
# - Show access credentials

# Access: http://localhost:8052
# Login: admin / password
```

**Option B: Manual Install**

```bash
# Clone AWX
git clone https://github.com/ansible/awx.git
cd awx

# Start AWX with Docker Compose
make docker-compose

# Wait for startup (check logs)
docker logs -f awx_task

# When you see "Successfully registered instance awx", it's ready!
# Access: http://localhost:8052
# Login: admin / password
```

**Useful Makefile Commands:**

```bash
make help          # Show all available commands
make start         # Start AWX
make stop          # Stop AWX
make restart       # Restart AWX
make logs          # View logs
make status        # Check container status
make health        # Check AWX health endpoint
make open          # Open AWX in browser
make clean         # Remove containers (keeps data)
make clean-all     # Remove everything (DESTRUCTIVE!)
```

## Step 2: Import This Project (2 minutes)

1. Login to AWX: http://localhost:8052
2. **Resources** → **Projects** → **Add**
3. Fill out:
   - **Name**: `vLLM CPU Perf Eval`
   - **Organization**: Default
   - **SCM Type**: Git
   - **SCM URL**: `https://github.com/your-org/vllm-cpu-perf-eval.git`
   - **SCM Branch**: `feature/inventory-split` (or `main` after merge)
4. **Save**
5. Click **Sync** button (circular arrows)

## Step 3: Add Your DUT Credentials (2 minutes)

1. **Resources** → **Credentials** → **Add**
2. Fill out:
   - **Name**: `DUT SSH Key`
   - **Credential Type**: Machine
   - **Username**: `ec2-user` (or your SSH user)
   - **SSH Private Key**: Paste your `~/.ssh/your-key.pem` contents
3. **Save**

## Step 4: Create Inventory (3 minutes)

1. **Resources** → **Inventories** → **Add** → **Add inventory**
2. **Name**: `vLLM Test Infrastructure`
3. **Save**
4. **Hosts** tab → **Add**
5. Add DUT:
   - **Name**: `my-dut`
   - **Variables**:
     ```yaml
     ansible_host: your-dut-hostname.com
     ansible_user: ec2-user
     ```
   - **Save**
6. **Add** again for Load Generator:
   - **Name**: `my-loadgen`
   - **Variables**:
     ```yaml
     ansible_host: localhost
     ansible_connection: local
     ansible_become: false
     bench_config:
       vllm_host: your-dut-hostname.com
       vllm_port: 8000
       results_dir: /tmp/benchmark-results
     ```
   - **Save**
7. **Groups** tab → **Add** twice:
   - Group `dut`: Add host `my-dut`
   - Group `load_generator`: Add host `my-loadgen`

## Step 5: Create Job Template (3 minutes)

1. **Resources** → **Templates** → **Add** → **Add job template**
2. Fill out:
   - **Name**: `LLM Performance Test`
   - **Job Type**: Run
   - **Inventory**: vLLM Test Infrastructure
   - **Project**: vLLM CPU Perf Eval
   - **Playbook**: `automation/test-execution/ansible/playbooks/llm/run-guidellm-test.yml`
   - **Credentials**: Select `DUT SSH Key`
   - **Options**: ✓ Prompt on launch (for credentials)
3. **Save**
4. **Survey** tab → **On** (toggle)
5. **Add** survey questions (quick version - just the essentials):

   **Question 1:**
   - **Question**: Model to Test
   - **Answer Variable Name**: `test_model`
   - **Answer Type**: Multiple Choice
   - **Multiple Choice Options**:
     ```
     Qwen/Qwen3-0.6B
     meta-llama/Llama-3.2-1B-Instruct
     facebook/opt-125m
     ```
   - **Default Answer**: `Qwen/Qwen3-0.6B`
   - **Save**

   **Question 2:**
   - **Question**: Workload Type
   - **Answer Variable Name**: `workload_type`
   - **Answer Type**: Multiple Choice
   - **Multiple Choice Options**:
     ```
     chat
     summarization
     code
     rag
     ```
   - **Default Answer**: `chat`
   - **Save**

   **Question 3:**
   - **Question**: Core Configuration
   - **Answer Variable Name**: `core_config_name`
   - **Answer Type**: Multiple Choice
   - **Multiple Choice Options**:
     ```
     8cores-single-socket
     16cores-single-socket
     32cores-single-socket
     ```
   - **Default Answer**: `16cores-single-socket`
   - **Save**

6. **Survey Enabled** → **On** (toggle at top)
7. **Save** template

## Step 6: Run Your First Test! (1 minute)

1. **Resources** → **Templates**
2. Click **Launch** (🚀 rocket icon) next to "LLM Performance Test"
3. Survey form appears:
   - **Model**: Qwen/Qwen3-0.6B (public, no token needed)
   - **Workload**: chat
   - **Core Config**: 16cores-single-socket
4. **Next** → **Launch**
5. Watch the job run in real-time!

## What's Happening?

AWX is now:
1. ✓ Connecting to your DUT via SSH
2. ✓ Starting vLLM container with Qwen/Qwen3-0.6B model
3. ✓ Waiting for vLLM to become healthy
4. ✓ Running GuideLLM benchmark
5. ✓ Collecting results

Results will be in: `/tmp/benchmark-results/Qwen3-0.6B/chat/16cores-single-socket/`

## Next Steps

### Add More Configuration Options

Go back to your job template survey and add more questions from [`surveys/llm-guidellm-test.yml`](surveys/llm-guidellm-test.yml):
- vLLM container image
- GuideLLM max requests
- Results directory
- etc.

### Test Gated Models (meta-llama)

1. **Administration** → **Credential Types** → **Add**
2. Use configuration from [`credentials/huggingface-token.yml`](credentials/huggingface-token.yml)
3. **Resources** → **Credentials** → **Add**
   - **Type**: HuggingFace Token
   - **Token**: `hf_xxxxx` (from https://huggingface.co/settings/tokens)
4. When launching job, select this credential
5. Now you can test meta-llama models!

### Create Test Suites

Follow the [main README](README.md) to create workflows that run multiple tests in sequence or parallel.

### Schedule Tests

1. Job Template → **Schedules** → **Add**
2. Set frequency (daily, weekly, etc.)
3. Tests run automatically!

## Troubleshooting

**AWX won't start:**
```bash
# Check container logs
docker logs awx_task
docker logs awx_web

# Restart if needed
docker-compose restart
```

**Job fails with "Permission denied":**
- Check SSH key is correct in credential
- Test SSH manually: `ssh -i key.pem user@dut-host`

**vLLM container fails to start:**
- Check DUT has enough resources (CPU, RAM)
- Check container image is correct
- View full job output for error details

**Results not found:**
- Check `results_dir` path in inventory
- Ensure directory exists and is writable
- Check load generator logs

## Get Help

- [Full AWX Documentation](README.md)
- [AWX Issues](https://github.com/ansible/awx/issues)
- [Testing Framework Issues](https://github.com/your-org/vllm-cpu-perf-eval/issues)

---

**Congratulations!** You've just run your first vLLM performance test through AWX without editing a single configuration file! 🎉
