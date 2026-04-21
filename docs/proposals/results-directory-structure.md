# Results Directory Structure Proposal

## Executive Summary

This document proposes a unified, intuitive results directory structure across all test types in the repository, along with support for custom test run names.

**Related GitHub Issue:** [#73 - RFE: Support User Specified Testrun Names](https://github.com/redhat-et/vllm-cpu-perf-eval/issues/73)

This proposal addresses:
1. Inconsistent results directory structures across test types
2. Missing support for custom test run names (Issue #73)
3. Results overwrites in bash scripts (no test_run_id)
4. Future Streamlit visualization filtering by test run name

## Current State Analysis

### Current Directory Structures

#### 1. LLM Tests (Ansible - Single Test)
```
results/llm/{model}/{workload}-{test_run_id}/{core_config_name}/
└── Example: results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-20240315-143022/4c-tp1/
```

#### 2. LLM Tests (Ansible - Core Sweep)
```
results/llm/{model}/{workload}-{test_run_id}/cores_{N}/
└── Example: results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-20240315-143022/cores_8/
```

#### 3. Embedding Tests (Ansible)
```
results/embedding/{model}/{test_type}-{test_run_id}/
└── Example: results/embedding/ibm-granite__granite-embedding-278m-multilingual/baseline-20240315-143022/
```

#### 4. Embedding Tests (Bash Scripts)
```
results/embedding-models/{model_basename}/{test_type}/
└── Example: results/embedding-models/granite-embedding-278m-multilingual/baseline/
└── NO test_run_id - results get overwritten!
```

### Identified Issues

1. **Inconsistent top-level directories**: `llm/` vs `embedding/` vs `embedding-models/`
2. **Missing test_run_id**: Bash scripts don't use test run IDs, causing result overwrites
3. **No custom naming**: Auto-generated timestamps only (e.g., `20240315-143022`)
4. **Different structures**: Core sweep uses `cores_{N}`, single tests use `{core_config_name}`
5. **Confusing workload prefix**: `{workload}-{test_run_id}` mixes semantics
6. **Model name escaping**: Inconsistent handling of `/` in model names

## Proposed Unified Structure

### Design Principles

1. **Consistency**: Same structure across all test types
2. **Clarity**: Clear semantic naming at each level
3. **Flexibility**: Support both auto-generated and custom run names
4. **No Overwrites**: Every test run gets a unique directory
5. **Discoverability**: Easy to find and navigate results

### Proposed Directory Structure

```
results/
├── llm/                                        # Top-level: model type
│   └── {test_suite}/                          # Test suite (concurrent-load, scalability, etc.)
│       └── {model_safe}/                      # Model (slashes replaced with __)
│           └── {workload}/                    # Workload (chat, code, summarization, rag)
│               └── {run_name}/                # Run name (custom or auto-timestamp)
│                   └── {config}/              # Configuration (cores_8, 4c-tp1, etc.)
│                       ├── benchmarks.json
│                       ├── benchmarks.csv
│                       ├── guidellm.log
│                       ├── test-metadata.json
│                       ├── vllm-server.log
│                       └── system-metrics.log
│
└── embedding/                                  # Top-level: model type
    └── {scenario}/                            # Test scenario (baseline, latency, concurrent)
        └── {model_safe}/                      # Model (slashes replaced with __)
            └── {run_name}/                    # Run name (custom or auto-timestamp)
                └── {config}/                  # Configuration (if applicable)
                    ├── benchmarks.json
                    ├── test-metadata.json
                    └── ...
```

### Hierarchy Levels Explained

#### LLM Tests (6 levels)
1. **Model Type** (`llm/`) - Top-level categorization
2. **Test Suite** - Which test methodology (concurrent-load, scalability, resource-contention, etc.)
3. **Model** - Specific model being tested
4. **Workload** - Test scenario (chat, code, summarization, rag)
5. **Run Name** - Unique identifier (custom or timestamp)
6. **Config** - Hardware/software configuration (cores_8, 4c-tp1, etc.)

#### Embedding Tests (5 levels)
1. **Model Type** (`embedding/`) - Top-level categorization
2. **Scenario** - Test scenario (baseline, latency, concurrent)
3. **Model** - Specific model being tested
4. **Run Name** - Unique identifier (custom or timestamp)
5. **Config** - Configuration (if applicable - often just files at run_name level)
```

### Path Examples

#### LLM Examples

```text
Concurrent load test with auto-generated timestamp:
results/llm/concurrent-load/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat/20240315-143022/4c-tp1/

Concurrent load test with custom run name:
results/llm/concurrent-load/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat/baseline-comparison/4c-tp1/

Scalability core sweep with auto-generated timestamp:
results/llm/scalability/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat/20240315-143022/cores_8/
results/llm/scalability/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat/20240315-143022/cores_16/

Scalability core sweep with custom run name:
results/llm/scalability/meta-llama__Llama-3.2-3B-Instruct/summarization/prod-validation-v2/cores_8/
results/llm/scalability/meta-llama__Llama-3.2-3B-Instruct/summarization/prod-validation-v2/cores_16/

Resource contention test:
results/llm/resource-contention/Qwen__Qwen2.5-3B-Instruct/code/multi-tenant-test/shared-cores/
```

#### Embedding Examples

```text
Baseline test with auto-generated timestamp:
results/embedding/baseline/ibm-granite__granite-embedding-278m-multilingual/20240315-143022/sweep-inf.json
results/embedding/baseline/ibm-granite__granite-embedding-278m-multilingual/20240315-143022/sweep-25pct.json

Baseline test with custom run name:
results/embedding/baseline/ibm-granite__granite-embedding-278m-multilingual/prod-release-candidate/sweep-inf.json

Latency test with different concurrency levels:
results/embedding/latency/ibm-granite__granite-embedding-english-r2/20240315-154530/concurrent-16.json
results/embedding/latency/ibm-granite__granite-embedding-english-r2/20240315-154530/concurrent-32.json
results/embedding/latency/ibm-granite__granite-embedding-english-r2/20240315-154530/concurrent-64.json
```

### How Test Suite is Determined

**For LLM Tests:**
- Test suite can be passed as a parameter: `-e "test_suite=concurrent-load"`
- Or inferred from the playbook name:
  - `llm-benchmark-concurrent-load.yml` → `concurrent-load`
  - `llm-core-sweep-auto.yml` → `scalability`
  - Future: `llm-resource-contention.yml` → `resource-contention`
- Default: `scalability` (for backwards compatibility with core sweeps)

**For Embedding Tests:**
- Test scenario is already part of the test definition (baseline, latency)
- No additional parameter needed

### Structure Benefits

1. **Hierarchical Organization**: Natural grouping by test type → test suite → model → scenario → run
2. **No Overwrites**: Each run gets its own directory under the run name
3. **Easy Comparison**: All runs for a model/scenario in one place
4. **Clear Semantics**: Each level has a clear meaning
5. **Test Suite Isolation**: Different test methodologies don't mix results
6. **Custom Naming**: Users can specify meaningful run names
7. **Backwards Compatible**: Can coexist with old structure during migration

## Custom Test Run Names

### Implementation Approach

#### 1. Add Optional Parameter to All Test Scripts

**Variable Name**: `test_run_name` (optional)

**GitHub Issue #73 Requirements:**
- Users can specify arbitrary test run names at invocation time
- Example from issue: `test_run_name=cores_4_8_12-rag-chat-code_PI34`
- This enables grouping related test runs together
- Supports test tracking and organization (e.g., by project, sprint, or experiment)

**Behavior**:
- If `test_run_name` is provided: Use it as-is (with validation/sanitization)
- If `test_run_name` is NOT provided: Auto-generate timestamp `YYYYMMDD-HHMMSS`
- Environment variable support: `TEST_RUN_NAME=my-test ./run-test.sh`

#### 2. Name Validation

Allowed characters: `a-z`, `A-Z`, `0-9`, `-`, `_`

Invalid characters replaced with `_` (sanitization approach - more user-friendly than rejection)

**Examples of sanitization:**
- Input: `"my test run!"` → Output: `"my_test_run_"`
- Input: `"cores_4_8_12-rag-chat-code_PI34"` → Output: `"cores_4_8_12-rag-chat-code_PI34"` (no change)

#### Benefits of Custom Naming (Issue #73)

1. **Human-readable organization** - No need to remember what `20240315-143022` was testing
2. **Project tracking** - Link results to project initiatives (e.g., `PI34`, `JIRA-1234`)
3. **Easy comparison** - Compare `baseline-v1` vs `optimized-v1` without checking timestamps
4. **Streamlit filtering** - Filter/search by meaningful names in visualization
5. **Collaboration** - Team members can identify test purposes without documentation
6. **Automation-friendly** - CI/CD can use build numbers or commit SHAs as run names

#### 3. Parameter Examples

**Ansible Playbooks:**
```bash
# Auto-generated timestamp (current behavior)
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores=16"

# Custom run name
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "test_run_name=baseline-v1"

# Custom run name + specify test suite
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "test_suite=concurrent-load" \
  -e "test_run_name=prod-validation"
```

**Bash Scripts:**
```bash
# Auto-generated timestamp
./run-baseline.sh ibm-granite/granite-embedding-278m-multilingual

# Custom run name
./run-baseline.sh ibm-granite/granite-embedding-278m-multilingual \
  --run-name prod-release-candidate
```

**Core Sweep Script:**
```bash
# Auto-generated timestamp
./scripts/run-core-sweep.sh TinyLlama/TinyLlama-1.1B-Chat-v1.0 chat "8,16,32"

# Custom run name
./scripts/run-core-sweep.sh TinyLlama/TinyLlama-1.1B-Chat-v1.0 chat "8,16,32" \
  --run-name scalability-test-march

# Example from Issue #73 - project-specific naming
./scripts/run-core-sweep.sh meta-llama/Llama-3.2-3B-Instruct chat "4,8,12" \
  --run-name cores_4_8_12-rag-chat-code_PI34
```

**Environment Variable Support:**
```bash
# Set via environment variable
export TEST_RUN_NAME=my-baseline-test
./scripts/run-core-sweep.sh TinyLlama/TinyLlama-1.1B-Chat-v1.0 chat "8,16,32"

# Or inline
TEST_RUN_NAME=Q1-validation ./run-baseline.sh ibm-granite/granite-embedding-278m-multilingual
```

## Migration Strategy

### Phase 1: Add New Structure Support (Non-Breaking)
1. Update all playbooks to support the new structure
2. Keep old structure as default
3. Add `use_new_results_structure` flag (default: false)

### Phase 2: Parallel Support
1. Document both structures
2. Allow users to opt into new structure
3. Update examples to use new structure

### Phase 3: Switch Default (Breaking Change)
1. Make new structure the default
2. Update all documentation
3. Provide migration script for existing results

### Phase 4: Deprecate Old Structure
1. Remove old structure support after N releases
2. Keep migration script available

## Streamlit Visualization Support

As mentioned in [Issue #73](https://github.com/redhat-et/vllm-cpu-perf-eval/issues/73), the Streamlit visualization tool needs to support filtering by test run name.

### Required Changes

1. **Update results discovery logic** to handle new directory structure
2. **Add test run name filter** in the UI
3. **Support test suite filtering** (concurrent-load, scalability, etc.)
4. **Parse test-metadata.json** to extract run name if needed

### Example Streamlit Filter UI

```python
# Streamlit sidebar filters
test_suite = st.sidebar.selectbox("Test Suite", ["All", "concurrent-load", "scalability", "resource-contention"])
test_run_name = st.sidebar.text_input("Test Run Name (filter)", "")
model = st.sidebar.selectbox("Model", available_models)
workload = st.sidebar.selectbox("Workload", available_workloads)
```

### Benefits for Visualization

- **Group related runs**: Filter by project name (e.g., `PI34`, `Q1-baseline`)
- **Compare experiments**: View all runs matching a pattern (e.g., `cores_*`)
- **Test suite isolation**: View only concurrent-load or scalability results
- **Time-based filtering**: Still possible with timestamp-based run names

**Note:** Streamlit implementation details should be tracked in a separate issue/PR once the core directory structure is finalized.

## Use Cases for Custom Test Run Names

### 1. Project/Sprint Tracking (Issue #73 Example)
```bash
# Group all tests for Project Initiative 34
TEST_RUN_NAME=cores_4_8_12-rag-chat-code_PI34 ./run-core-sweep.sh ...
```
Result: `results/llm/scalability/{model}/{workload}/cores_4_8_12-rag-chat-code_PI34/`

### 2. Experiment Comparison
```bash
# Baseline before optimization
TEST_RUN_NAME=baseline-v1 ./llm-benchmark-auto.yml ...

# After optimization
TEST_RUN_NAME=optimized-v1 ./llm-benchmark-auto.yml ...

# Compare results:
# results/llm/concurrent-load/{model}/chat/baseline-v1/
# results/llm/concurrent-load/{model}/chat/optimized-v1/
```

### 3. Release Validation
```bash
# Pre-release testing
TEST_RUN_NAME=v1.2.0-rc1 ./run-all-tests.sh

# Production validation
TEST_RUN_NAME=v1.2.0-prod ./run-all-tests.sh
```

### 4. Hardware Configuration Testing
```bash
# Test different hardware configs with descriptive names
TEST_RUN_NAME=spr-96c-512gb ./run-core-sweep.sh ...
TEST_RUN_NAME=icx-64c-256gb ./run-core-sweep.sh ...
```

### 5. Date-based Organization (Still Supported)
```bash
# Users can still use timestamps manually
TEST_RUN_NAME=2024-03-15_baseline ./run-tests.sh
# Or let the system auto-generate: 20240315-143022
```

### 6. Multi-User Testing Environment
```bash
# Each user can prefix with their name
TEST_RUN_NAME=alice-feature-test ./run-tests.sh
TEST_RUN_NAME=bob-performance-test ./run-tests.sh
```

## Implementation Checklist

### Core Changes

- [ ] Define `test_run_name` variable in all playbooks
- [ ] Define `test_suite` variable in LLM playbooks (with default)
- [ ] Add name validation/sanitization function/filter
- [ ] Update path construction in all playbooks:
  - [ ] `llm-benchmark.yml`
  - [ ] `llm-benchmark-auto.yml`
  - [ ] `llm-core-sweep-auto.yml`
  - [ ] `embedding-benchmark.yml`
- [ ] Update bash scripts:
  - [ ] `run-baseline.sh`
  - [ ] `run-latency.sh`
  - [ ] `run-all.sh`
  - [ ] `run-core-sweep.sh`
- [ ] Update results collection tasks
- [ ] Update metadata generation to include:
  - [ ] `test_run_name`
  - [ ] `test_suite` (for LLM tests)

### Documentation Updates

- [ ] Update [automation/test-execution/ansible/ansible.md](../automation/test-execution/ansible/ansible.md)
- [ ] Update [README.md](../README.md)
- [ ] Update [results/results.md](../results/results.md) (if exists)
- [ ] Add migration guide
- [ ] Update all example commands in documentation

### Streamlit Visualization Updates (Issue #73)

- [ ] Update results directory scanning to support new structure
- [ ] Add test suite filter/selector
- [ ] Add test run name filter (text input or dropdown)
- [ ] Update path parsing to extract all hierarchy levels
- [ ] Test filtering by custom run names
- [ ] Document new filtering capabilities

### Testing

- [ ] Test single LLM run with auto name
- [ ] Test single LLM run with custom name
- [ ] Test single LLM run with custom name via env var
- [ ] Test core sweep with auto name
- [ ] Test core sweep with custom name
- [ ] Test embedding baseline with auto name
- [ ] Test embedding baseline with custom name
- [ ] Test embedding latency with auto name
- [ ] Test embedding latency with custom name
- [ ] Verify no overwrites occur
- [ ] Verify invalid names are sanitized correctly
- [ ] Verify special characters in names are handled
- [ ] Test example from Issue #73: `cores_4_8_12-rag-chat-code_PI34`

## Example Implementation Code

### Ansible Variable Setup

```yaml
# In playbook vars section
vars:
  # Use custom name if provided, otherwise generate timestamp
  test_run_name_raw: "{{ test_run_name | default(lookup('pipe', 'date +%Y%m%d-%H%M%S')) }}"

  # Sanitize the name (replace invalid chars with _)
  test_run_name_safe: "{{ test_run_name_raw | regex_replace('[^a-zA-Z0-9_-]', '_') }}"

  # Build new-style path
  results_base_dir: "{{ playbook_dir }}/../../../results"
  model_safe: "{{ test_model | replace('/', '__') }}"

  # For LLM tests
  test_suite: "concurrent-load"  # or "scalability", "resource-contention"
  results_path: "{{ results_base_dir }}/llm/{{ test_suite }}/{{ model_safe }}/{{ workload_type }}/{{ test_run_name_safe }}/{{ core_configuration.name }}"

  # For embedding tests
  test_scenario: "baseline"  # or "latency"
  results_path: "{{ results_base_dir }}/embedding/{{ test_scenario }}/{{ model_safe }}/{{ test_run_name_safe }}"
```

### Bash Script Parameter Parsing

```bash
# Default to auto-generated timestamp
TEST_RUN_NAME="${TEST_RUN_NAME:-$(date +%Y%m%d-%H%M%S)}"

# Parse --run-name argument
while [[ $# -gt 0 ]]; do
  case $1 in
    --run-name)
      TEST_RUN_NAME="$2"
      shift 2
      ;;
    # ... other args
  esac
done

# Sanitize name
TEST_RUN_NAME=$(echo "$TEST_RUN_NAME" | sed 's/[^a-zA-Z0-9_-]/_/g')

# Build path
# For embedding tests: results/embedding/{scenario}/{model}/{run_name}/
RESULT_PATH="${RESULTS_DIR}/${TEST_SCENARIO}/${MODEL_BASENAME}/${TEST_RUN_NAME}"
```

## Alternatives Considered

### Alternative 1: Flat Structure with Longer Names
```
results/llm__TinyLlama__chat__20240315-143022__4c-tp1/
```
**Rejected**: Hard to browse, no logical grouping

### Alternative 2: Date-based Directory Structure
```
results/2024/03/15/llm/TinyLlama/...
```
**Rejected**: Prioritizes date over test type/model, hard to find related tests

### Alternative 3: Keep Current Structure, Add Run Name to Timestamp
```
results/llm/{model}/{workload}-baseline-20240315-143022/
```
**Rejected**: Still mixes semantics, doesn't fully solve organization issues

## Questions for Review

### Directory Structure
1. Should we support subdirectories in custom run names? (e.g., `2024-Q1/baseline`)
2. Should we add a top-level timestamp directory for archival? (e.g., `results/2024-03-15/llm/...`)
3. Should embedding tests have a config level like LLM tests? (probably not needed currently)

### Custom Run Names (Issue #73)

1. Should custom names be validated (reject invalid) or sanitized (auto-fix)?
   - **Current proposal:** Sanitize (more user-friendly)
2. Should we enforce a maximum length for run names? (e.g., 100 characters)
3. Should we support environment variable `TEST_RUN_NAME` in addition to command-line args?
   - **Current proposal:** Yes

### Metadata and Indexing

1. Should we add a `results.json` index file at the workload/scenario level for faster discovery?
2. Should test-metadata.json include the full path structure for easier parsing?

### Streamlit Integration

1. Should Streamlit changes be part of this PR or a separate follow-up issue?
   - **Recommendation:** Separate issue once directory structure is finalized
2. Should we add a `--list-runs` flag to CLI tools to show available test run names?

## Recommendations

1. **Start with Phase 1**: Implement new structure support without breaking existing workflows
2. **Document thoroughly**: Clear examples and migration guides
3. **Get feedback early**: Test with a few users before making it default
4. **Keep it simple**: Don't over-engineer, the proposed structure handles 95% of use cases
5. **Plan for growth**: Structure should accommodate future test types easily

## Summary: What This Proposal Delivers

### For Issue #73 - Custom Test Run Names
✅ **User-specified test run names** via command-line args or environment variables
✅ **Arbitrary naming** with sanitization (e.g., `cores_4_8_12-rag-chat-code_PI34`)
✅ **Backwards compatible** - auto-generates timestamps if not specified
✅ **Streamlit filtering support** - foundation for visualization filtering

### For Repository Organization
✅ **Unified structure** - consistent across LLM and embedding tests
✅ **Test suite isolation** - concurrent-load vs scalability vs resource-contention
✅ **No overwrites** - every test run gets unique directory
✅ **Clear hierarchy** - intuitive navigation from test type → suite → model → scenario → run → config

### Implementation Phases
1. **Phase 1 (Non-Breaking)**: Add new structure support with opt-in flag
2. **Phase 2 (Parallel)**: Document both structures, update examples
3. **Phase 3 (Breaking)**: Switch default to new structure
4. **Phase 4 (Cleanup)**: Deprecate old structure support

### Example: Issue #73 Use Case

**Before (Current):**
```bash
# No way to specify custom name
./run-core-sweep.sh meta-llama/Llama-3.2-3B-Instruct rag "4,8,12"
# Results: ./results/llm/meta-llama__Llama-3.2-3B-Instruct/rag-20240315-143022/cores_4/
#          Hard to identify what this test was for!
```

**After (With This Proposal):**
```bash
# Custom name as requested in Issue #73
TEST_RUN_NAME=cores_4_8_12-rag-chat-code_PI34 \
  ./run-core-sweep.sh meta-llama/Llama-3.2-3B-Instruct rag "4,8,12"

# Results: ./results/llm/scalability/meta-llama__Llama-3.2-3B-Instruct/rag/cores_4_8_12-rag-chat-code_PI34/cores_4/
#          Clear project tracking! Can filter in Streamlit by "PI34"
```

### Follow-up Work
- **Streamlit visualization**: Update to support new structure and filtering (separate PR)
- **Migration script**: Convert existing results to new structure (optional)
- **Documentation**: Update all guides and examples

## Next Steps

1. **Review this proposal** with the team
2. **Answer open questions** (see Questions for Review section)
3. **Get feedback on Issue #73** - does this meet the requirements?
4. **Create implementation tasks** (break down checklist into GitHub issues)
5. **Start with Ansible playbooks** (higher priority than bash scripts)
6. **Write tests** to verify behavior
7. **Update documentation** as changes are made
8. **Create follow-up issue for Streamlit** once core structure is merged
