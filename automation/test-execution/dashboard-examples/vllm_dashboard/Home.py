"""vLLM CPU Performance - Dashboard Home.

Main landing page for the multipage dashboard app.
Navigate to different views using the sidebar.
"""

import streamlit as st
from pathlib import Path

# Page config
st.set_page_config(
    page_title="vLLM CPU Performance Dashboards",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark mode friendly CSS
st.markdown("""
<style>
    /* Remove light background from sidebar in dark mode */
    [data-testid="stSidebar"] {
        background-color: transparent;
    }

    /* Ensure sidebar text is readable in both modes */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: inherit;
    }

    /* Navigation links */
    [data-testid="stSidebar"] a {
        color: inherit;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🚀 vLLM CPU Performance Dashboards")
st.markdown("**Comprehensive performance analysis for vLLM CPU benchmarks**")
st.markdown("---")

# Welcome section
st.markdown("""
### Welcome!

This dashboard suite provides three complementary views of your vLLM CPU benchmark results:

📊 **Client-Side Metrics** - End-user performance (GuideLLM results)
🖥️ **Server-Side Metrics** - Internal server behavior (vLLM metrics)
🔄 **Unified View** - Combined client + server correlation analysis

**👈 Use the sidebar to navigate between dashboards**
""")

st.markdown("---")

# Dashboard overview cards
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📊 Client-Side")
    st.info("""
    **What**: GuideLLM benchmark results

    **Metrics**:
    - Throughput (tokens/sec)
    - TTFT, ITL, E2E latency
    - Success rates
    - Efficiency (tok/s/core)

    **Features**:
    - Platform comparison
    - Configurable X-axis
    - CSV data export
    - Percentile analysis
    """)

with col2:
    st.markdown("### 🖥️ Server-Side")
    st.info("""
    **What**: vLLM server metrics (Prometheus)

    **Metrics**:
    - Queue depth over time
    - CPU cache usage
    - Token generation rates
    - Request patterns

    **Features**:
    - Time-series analysis
    - Multi-test comparison
    - Raw data inspection
    """)

with col3:
    st.markdown("### 🔄 Unified")
    st.info("""
    **What**: Client + Server combined

    **Analysis**:
    - Correlation view
    - Side-by-side comparison
    - Unified filtering
    - Peak performance

    **Use for**:
    - Root cause analysis
    - Bottleneck identification
    - Performance validation
    """)

st.markdown("---")

# Quick start
st.markdown("### 🚀 Quick Start")

tab1, tab2, tab3 = st.tabs(["Run Tests", "View Results", "Features"])

with tab1:
    st.markdown("""
    #### Running Benchmarks

    ```bash
    # Single test
    ansible-playbook llm-benchmark-auto.yml \\
      -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \\
      -e "workload_type=chat" \\
      -e "requested_cores=16"

    # Core sweep
    ansible-playbook llm-core-sweep-auto.yml \\
      -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \\
      -e "workload_type=chat" \\
      -e "requested_cores_list=[8,16,32,64]"
    ```

    **Results are automatically saved to:** `results/llm/`

    Each dashboard loads from this directory - just run a test and refresh!
    """)

with tab2:
    st.markdown("""
    #### Viewing Your Results

    1. **Run a benchmark** (see "Run Tests" tab)
    2. **Navigate to a dashboard** using the sidebar (←)
    3. **Apply filters** to focus on specific tests
    4. **Analyze performance** using charts and metrics

    **Default Results Path**: `../../../results/llm`

    You can change this path in each dashboard's sidebar configuration.
    """)

with tab3:
    st.markdown("""
    #### Dashboard Features

    **All dashboards include:**
    - 🔍 Platform filtering
    - 📦 Model filtering
    - 📋 Workload filtering
    - ⚙️ Core count filtering
    - 🏷️ vLLM version filtering

    **Client Dashboard adds:**
    - 📊 Configurable X-axis (request rate or concurrency)
    - 📈 Multiple percentile views (P50, P95, P99)
    - 🔀 Platform comparison with % differences
    - 💾 CSV export for external analysis

    **Server Dashboard adds:**
    - ⏱️ Time-series charts
    - 🔄 Multi-test comparison mode
    - 📊 Summary statistics
    - 🔍 Raw data tab

    **Unified Dashboard provides:**
    - 🔗 Client-Server correlation
    - 📊 Side-by-side metrics
    - 🎯 Peak performance summary
    - 💡 Troubleshooting tips
    """)

st.markdown("---")

# System status
st.markdown("### 📊 System Status")

# Check for results
results_base = Path(__file__).parent.parent.parent.parent.parent / "results" / "llm"
if results_base.exists():
    # Count test runs (filter out hidden files like .DS_Store)
    model_dirs = [m for m in results_base.glob("*") if m.is_dir() and not m.name.startswith('.')]
    test_count = sum(len(list(m.rglob("test-metadata.json"))) for m in model_dirs)

    col1, col2, col3 = st.columns(3)
    col1.metric("Models Tested", len(model_dirs))
    col2.metric("Total Test Runs", test_count)
    col3.metric("Results Directory", "✓ Found")

    if test_count > 0:
        st.success(f"✓ Found {test_count} test results. Navigate to a dashboard to analyze!")
    else:
        st.warning("⚠️ No test results found yet. Run a benchmark to get started.")
else:
    st.warning(f"⚠️ Results directory not found: `{results_base}`")
    st.info("Run your first benchmark to create the results directory.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 📍 Navigation")
st.sidebar.caption("Use the links above to switch between dashboards")
st.sidebar.caption("Click 'Home' to return here")

st.sidebar.markdown("---")
st.sidebar.caption("**vLLM CPU Performance Dashboard Suite**")
st.sidebar.caption("v1.0.0")
