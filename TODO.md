# vLLM CPU Performance Evaluation - TODO & Roadmap

This document tracks planned features, enhancements, and technical debt for the vLLM CPU Performance Evaluation framework.

## High Priority


### 2. Real-time GuideLLM Output Streaming

**Goal:** Stream GuideLLM test output in real-time during test execution for better visibility and debugging.

**Requirements:**
- Non-interfering: Must not affect benchmark accuracy or performance
- Real-time visibility: See progress, errors, and intermediate results
- Log preservation: All output captured for post-test analysis

**Implementation:**
- [ ] Investigate GuideLLM output buffering behavior
- [ ] Add `--verbose` or streaming flags to GuideLLM invocation
- [ ] Configure Ansible task to stream stdout/stderr in real-time
- [ ] Add optional `stream_output: true` parameter
- [ ] Test impact on benchmark accuracy (ensure no performance degradation)
- [ ] Document streaming configuration and trade-offs

**Technical Considerations:**
- Use `ansible.builtin.shell` with `stdout_callback` for streaming
- Consider `async` + `poll` for long-running tests
- Evaluate impact of logging overhead on latency measurements

**Related Files:**
- `automation/test-execution/ansible/playbooks/llm/run-guidellm-test.yml`
- `automation/test-execution/ansible/playbooks/embedding/run-vllm-bench-serve.yml`

---

### 3. vLLM Bench Serve as Full Load Generator

**Goal:** Add `vllm bench serve` as a comprehensive load generator comparable to GuideLLM for cross-validation.

**Motivation:**
- Official vLLM benchmarking tool
- Compare GuideLLM vs vLLM bench serve results
- Validate metrics across different load generators
- Support for embedding models (already partially implemented)

**Implementation:**
- [ ] Extend existing `vllm bench serve` playbooks for LLM workloads
- [ ] Add test scenarios matching GuideLLM test suites:
  - [ ] Concurrent load testing (P1 equivalent)
  - [ ] Scalability testing (P2 equivalent)
  - [ ] Resource contention testing (P3 equivalent)
- [ ] Implement result parsing and normalization
- [ ] Add comparative analysis scripts (GuideLLM vs vllm bench serve)
- [ ] Document metric mappings and differences
- [ ] Add side-by-side comparison reports

**Test Matrix:**
```yaml
load_generators:
  - guidellm:      # Primary tool for LLM generative models
      backends: [openai-chat, openai-completions]
  - vllm_bench:    # Official vLLM tool, cross-validation
      backends: [openai-embeddings, openai-chat, openai-completions]
```

**Related Files:**
- `automation/test-execution/ansible/playbooks/embedding/run-vllm-bench-serve.yml`
- `tests/embedding-models/` (already uses vllm bench serve)

---

## Medium Priority

### 4. Grafana Dashboard for Test Results

**Goal:** Real-time and historical visualization of test results via Grafana dashboards.

**Features:**
- Real-time monitoring during test execution
- Historical trend analysis
- Model comparison dashboards
- Core count scaling visualization
- Latency distribution heatmaps

**Implementation:**
- [ ] Design Grafana dashboard layout
- [ ] Set up Prometheus for metrics collection
- [ ] Export test results to Prometheus format
- [ ] Create dashboard JSON templates:
  - [ ] Overview dashboard (all models, latest runs)
  - [ ] Model-specific dashboard (deep dive per model)
  - [ ] Comparative dashboard (model vs model, run vs run)
  - [ ] Core scaling dashboard (throughput vs cores)
- [ ] Add Ansible playbook for Grafana/Prometheus deployment
- [ ] Document dashboard setup and customization
- [ ] Add alerting rules for performance regressions

**Metrics to Track:**
- Throughput (requests/sec)
- Latency (P50, P95, P99 TTFT, ITL, E2E)
- Resource utilization (CPU, memory, network)
- Test metadata (model, workload, core count, configuration)

**Related Files:**
- `results/metrics/prometheus/` (directory structure exists)
- New: `automation/dashboards/grafana/`

---

### 5. Add Graphing Scripts from intel_doc Branch

**Goal:** Integrate existing graphing scripts from intel_doc branch for result visualization.

**Implementation:**
- [ ] Identify graphing scripts in `intel_doc` branch
- [ ] Review and adapt scripts for current directory structure
- [ ] Add to `automation/analysis/` directory
- [ ] Update scripts to work with new result format:
  - `results/by-suite/`
  - `results/by-model/`
- [ ] Add requirements.txt for graphing dependencies (matplotlib, seaborn, plotly)
- [ ] Create example notebooks (Jupyter) for interactive analysis
- [ ] Document graph generation workflow
- [ ] Add graph types:
  - [ ] Throughput vs core count
  - [ ] Latency distribution plots
  - [ ] P95/P99 comparison charts
  - [ ] Model comparison bar charts
  - [ ] Time series for longitudinal analysis

**Related Files:**
- New: `automation/analysis/graphs/`
- New: `automation/analysis/notebooks/`

---

### 6. Docker/Podman Compose for Test Suites

**Goal:** Use docker-compose/podman-compose alongside Ansible for simplified test execution.

**Use Cases:**
- Single-node testing (dev/CI environments)
- Quick local testing without Ansible
- Container-based test orchestration
- CI/CD pipeline integration

**Implementation:**
- [ ] Create compose files for common scenarios:
  - [ ] `docker-compose.single-node.yml` - DUT + Load Generator on same host
  - [ ] `docker-compose.llm.yml` - LLM test suite
  - [ ] `docker-compose.embedding.yml` - Embedding test suite
- [ ] Add environment variable configuration
- [ ] Integrate with Ansible (optional compose vs Ansible mode)
- [ ] Add healthchecks for vLLM and GuideLLM containers
- [ ] Document compose workflow vs Ansible workflow
- [ ] Add CI/CD examples (GitHub Actions, GitLab CI)

**Example Structure:**
```yaml
# docker-compose.single-node.yml
services:
  vllm:
    image: quay.io/mtahhan/vllm:0.14.0
    cpuset: "0-15"
    environment:
      - HF_TOKEN=${HF_TOKEN}

  guidellm:
    image: quay.io/mtahhan/guidellm:saturation-fix
    depends_on:
      - vllm
    cpuset: "16-31"
```

**Related Files:**
- New: `docker-compose/`
- `automation/test-execution/ansible/` (integration point)

---

## Low Priority / Future Enhancements

### 7. Multi-Instance vLLM Support

**Goal:** Support multiple vLLM instances running concurrently on same DUT.

**Use Cases:**
- Multi-model serving
- A/B testing different configurations
- Load balancing scenarios

**Implementation:**
- [ ] Extend `clean-restart-vllm.yml` to support container lists
- [ ] Add port allocation for multiple instances
- [ ] CPU affinity management for multiple instances
- [ ] Update health checks for multiple endpoints
- [ ] Add load balancing configuration

**Related Files:**
- `automation/test-execution/ansible/playbooks/common/tasks/clean-restart-vllm.yml`

**Status:** TODO comment already added in clean-restart-vllm.yml

---

### 8. Advanced Analysis and Reporting

**Goal:** Automated result analysis and report generation.

**Features:**
- [ ] Performance regression detection
- [ ] Statistical significance testing
- [ ] Model ranking and recommendations
- [ ] Cost-performance analysis (cores vs throughput)
- [ ] Automated HTML/PDF report generation
- [ ] Slack/Email notifications for test completion

**Related Files:**
- `automation/analysis/`
- `results/reports/`

---

### 9. Continuous Benchmarking

**Goal:** Automated, scheduled performance testing and tracking.

**Features:**
- [ ] Scheduled test runs (daily/weekly)
- [ ] Performance trend tracking over time
- [ ] Regression detection and alerting
- [ ] Integration with CI/CD pipelines
- [ ] Historical performance database

---

### 10. Additional Load Generators

**Goal:** Support for additional benchmarking tools beyond GuideLLM and vllm bench serve.

**Candidates:**
- [ ] Locust (HTTP load testing)
- [ ] wrk/wrk2 (HTTP benchmarking)
- [ ] Apache Bench (ab)
- [ ] Custom Python load generator

---

## Technical Debt

### Code Quality
- [ ] Add unit tests for Ansible filter plugins
- [ ] Add integration tests for playbooks
- [ ] Improve error handling in playbooks
- [ ] Add retry logic for transient failures

### Documentation
- [ ] Add architecture diagrams
- [ ] Create video tutorials/walkthroughs
- [ ] Add troubleshooting guide
- [ ] Document best practices for different hardware configurations

### Infrastructure
- [ ] Add Terraform/CloudFormation templates for cloud deployment
- [ ] Kubernetes deployment manifests
- [ ] Add support for ARM CPUs

---

## Completed Items

✅ Consolidate model documentation into single file (models/models.md)
✅ Refactor "phases" to "test suites" with descriptive names
✅ Add pre-commit hooks for secrets detection
✅ Address PR #7 review comments
✅ Add embedding model test suite
✅ Replace SLATE models with Granite models
✅ **External vLLM Endpoint Support** - Test against production/cloud vLLM deployments
- ✅ Added `vllm_endpoint` configuration with external mode support
- ✅ Implemented endpoint URL parsing and validation
- ✅ Added API key authentication (env, file, vault, prompt sources)
- ✅ Updated health checks to support external endpoints with auth headers
- ✅ Updated all 6 main playbooks with external endpoint support
- ✅ Created comprehensive documentation with cloud provider examples ([docs/external-endpoints.md](docs/external-endpoints.md))
- See [External Endpoints Guide](docs/external-endpoints.md) for usage

---

## Contributing

To propose new features or enhancements:

1. Check this TODO list to avoid duplicates
2. Open an issue describing the feature request
3. Discuss implementation approach
4. Submit PR with implementation

## Priority Definitions

- **High Priority**: Actively planned or in progress, significant user value
- **Medium Priority**: Desirable enhancements, scheduled for future milestones
- **Low Priority**: Nice-to-have features, no immediate timeline
- **Technical Debt**: Code quality, testing, documentation improvements
