"""vLLM MTEB Embedding Quality Dashboard.

Evaluates embedding model quality across MTEB tasks (classification,
retrieval, clustering, STS, etc.) independent of throughput benchmarks.
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_mteb_data(results_dir: str) -> pd.DataFrame:
    """Load MTEB benchmark results from directory structure.

    Supports two result layouts:

    Format 1 (reorganized):
      results/mteb/MODEL/TIMESTAMP/TaskName/test.json

    Format 2 (raw MTEB output):
      results/mteb/MODEL/TIMESTAMP/no_model_name_available/no_revision_available/TaskName.json
    """
    results_path = Path(results_dir)
    all_results = []

    if not results_path.exists():
        logger.warning(f"MTEB results directory not found: {results_path}")
        return pd.DataFrame()

    for summary_file in results_path.rglob("run_summary.json"):
        try:
            with open(summary_file) as f:
                summary = json.load(f)

            model = summary.get("model", "unknown")
            timestamp = summary.get("timestamp", "unknown")
            task_preset = summary.get("task_preset", "custom")
            platform = summary.get("platform", "unknown")

            test_run_dir = summary_file.parent
            task_files = []

            # Format 1: TaskName/test.json subdirectories
            for task_dir in test_run_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                test_file = task_dir / "test.json"
                if test_file.exists():
                    task_files.append((task_dir.name, test_file))

            format1_tasks = {name for name, _ in task_files}

            # Format 2: no_model_name_available/no_revision_available/*.json
            mteb_output_dir = test_run_dir / "no_model_name_available" / "no_revision_available"
            if mteb_output_dir.exists():
                for result_file in mteb_output_dir.glob("*.json"):
                    if result_file.name == "model_meta.json":
                        continue
                    if result_file.stem in format1_tasks:
                        continue
                    task_files.append((result_file.stem, result_file))

            seen_tasks: set[str] = set()
            for task_name, task_file in task_files:
                if task_name in seen_tasks:
                    continue
                seen_tasks.add(task_name)
                try:
                    with open(task_file) as f:
                        task_results = json.load(f)

                    test_scores = task_results.get("test")
                    if test_scores is None:
                        test_scores = task_results.get("scores", {}).get("test", [])

                    if isinstance(test_scores, dict):
                        test_scores = [test_scores]
                    elif not test_scores:
                        logger.warning(f"No test scores in {task_file}")
                        continue

                    scores_per_experiment = test_scores[0].get("scores_per_experiment", [])

                    if not scores_per_experiment:
                        test_metrics = test_scores[0]
                    else:
                        test_metrics = {}
                        metric_keys = [
                            "accuracy", "f1", "precision", "recall",
                            "ndcg_at_10", "map", "mrr", "v_measure",
                            "cosine_spearman", "cosine_pearson",
                        ]
                        for key in metric_keys:
                            values = [e.get(key) for e in scores_per_experiment if e.get(key) is not None]
                            if values:
                                test_metrics[key] = np.mean(values)

                    all_results.append({
                        "model": model,
                        "timestamp": timestamp,
                        "task_preset": task_preset,
                        "platform": platform,
                        "task_name": task_name,
                        "accuracy": test_metrics.get("accuracy"),
                        "f1": test_metrics.get("f1"),
                        "precision": test_metrics.get("precision"),
                        "recall": test_metrics.get("recall"),
                        "ndcg_at_10": test_metrics.get("ndcg_at_10"),
                        "map": test_metrics.get("map"),
                        "mrr": test_metrics.get("mrr"),
                        "v_measure": test_metrics.get("v_measure"),
                        "cosine_spearman": test_metrics.get("cosine_spearman"),
                        "cosine_pearson": test_metrics.get("cosine_pearson"),
                    })

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse {task_file}: {e}")
                except Exception as e:
                    logger.warning(f"Error processing {task_file}: {e}")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse {summary_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading {summary_file}: {e}")
            raise

    logger.info(f"MTEB data loading complete: {len(all_results)} task results loaded")
    return pd.DataFrame(all_results)


def plot_mteb_radar_chart(df: pd.DataFrame, models: list):
    """Radar chart of model performance across task categories (MTEB leaderboard style)."""
    if df.empty:
        return

    task_categories = {
        "Classification": ["Banking77Classification", "EmotionClassification",
                           "ToxicConversationsClassification", "MTOPDomainClassification",
                           "MTOPIntentClassification"],
        "Clustering": ["ArxivClusteringP2P", "TwentyNewsgroupsClustering",
                       "RedditClustering", "StackExchangeClustering"],
        "Pair Classification": ["TwitterSemEval2015", "TwitterURLCorpus",
                                "SprintDuplicateQuestions"],
        "Reranking": ["AskUbuntuDupQuestions", "MindSmallReranking", "SciDocsRR"],
        "Retrieval": ["ArguAna", "NFCorpus", "SCIDOCS", "FiQA2018", "TRECCOVID",
                      "Touche2020", "DBPedia", "HotpotQA", "MSMARCO"],
        "STS": ["STS12", "STS13", "STS14", "STS15", "STS16", "STS17", "STS22",
                "STSBenchmark", "SICKRelatedness"],
        "Summarization": ["SummEval"],
        "BitextMining": ["Tatoeba", "BUCC"],
    }

    category_metrics = {
        "Classification": "accuracy",
        "Clustering": "v_measure",
        "Pair Classification": "accuracy",
        "Reranking": "map",
        "Retrieval": "ndcg_at_10",
        "STS": "cosine_spearman",
        "Summarization": "cosine_spearman",
        "BitextMining": "f1",
    }

    category_scores = []
    for model in models:
        model_df = df[df["model"] == model]
        scores = {}
        for category, tasks in task_categories.items():
            category_tasks = [t for t in tasks if t in model_df["task_name"].values]
            if not category_tasks:
                continue
            metric = category_metrics.get(category)
            if not metric:
                continue
            values = []
            for task in category_tasks:
                task_df = model_df[model_df["task_name"] == task]
                if not task_df.empty:
                    val = task_df[metric].iloc[0]
                    if pd.notna(val):
                        values.append(val)
            if values:
                scores[category] = np.mean(values)
        if scores:
            category_scores.append({"model": model.split("/")[-1], **scores})

    if not category_scores:
        st.info("Not enough data across task categories for radar chart. Run more comprehensive MTEB tests.")
        return

    radar_df = pd.DataFrame(category_scores)
    categories = [col for col in radar_df.columns if col != "model"]

    if len(categories) < 3:
        st.info("Need at least 3 task categories for a meaningful radar chart.")
        return

    fig = go.Figure()
    colors = px.colors.qualitative.Set2

    for idx, row in radar_df.iterrows():
        values = [row.get(cat, 0) * 100 for cat in categories]
        values.append(values[0])
        cats = categories + [categories[0]]
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=cats,
            fill="toself",
            name=row["model"],
            line=dict(color=colors[idx % len(colors)], width=2),
            opacity=0.7,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%",
                            showline=False, gridcolor="lightgray"),
            angularaxis=dict(gridcolor="lightgray"),
        ),
        showlegend=True,
        title="Model Performance Across Task Categories",
        height=600,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📖 What Do These Categories Mean?", expanded=False):
        st.markdown("""
        ### Task Categories Explained

        **Classification** — Text categorization. *Metric: Accuracy*

        **Retrieval** — Finding relevant documents from large collections. *Metric: NDCG@10*

        **STS** — Semantic textual similarity vs human judgments. *Metric: Spearman correlation*

        **Reranking** — Improving ranking of an initial result list. *Metric: MAP*

        **Pair Classification** — Relationship between text pairs. *Metric: Accuracy*

        **Clustering** — Unsupervised grouping of similar documents. *Metric: V-measure*

        **Summarization** — Embedding quality for summarization evaluation. *Metric: Spearman correlation*

        **BitextMining** — Finding equivalent sentences across languages. *Metric: F1*

        ---
        Scores shown are averages across tasks in each category, normalized to 0–100%. Higher is better.
        """)

        display_radar = radar_df.copy()
        for cat in categories:
            if cat in display_radar.columns:
                display_radar[cat] = (display_radar[cat] * 100).round(1)
        display_radar.columns = ["Model"] + [f"{cat} (%)" for cat in categories]
        st.dataframe(display_radar, use_container_width=True, hide_index=True)


def plot_mteb_quality_metrics(df: pd.DataFrame):
    """Plot MTEB quality metrics across models and tasks."""
    if df.empty:
        st.warning("No MTEB quality data to display")
        st.info("""
        Run MTEB quality benchmarks first:

        ```bash
        ansible-playbook mteb-benchmark.yml \\
          -e "test_model=RedHatAI/granite-embedding-english-r2" \\
          -e "mteb_task_preset=quick"
        ```
        """)
        return

    models = sorted(df["model"].unique())
    all_tasks = sorted(df["task_name"].unique())

    st.markdown("""
    **MTEB (Massive Text Embedding Benchmark)** evaluates embedding quality across multiple dimensions:
    - **Classification**: Text categorization accuracy
    - **Retrieval**: Information retrieval performance (NDCG, MAP, MRR)
    - **Clustering**: Document clustering quality (V-measure)
    - **STS**: Semantic textual similarity correlation

    Higher scores indicate better quality. All metrics range from 0 to 1 (or 0 to 100%).
    """)

    with st.expander("📖 Metric Definitions", expanded=False):
        st.markdown("""
        ### Classification Metrics

        **Accuracy** (0–1, higher is better) — Percentage of correct guesses.

        **F1 Score** (0–1, higher is better) — Balanced measure accounting for rare categories.

        **Precision** (0–1, higher is better) — When model predicts "yes", how often is it right?

        **Recall** (0–1, higher is better) — Of all real positives, how many were found?

        ---

        ### Retrieval Metrics

        **NDCG@10** (0–1) — Quality of top 10 results, rewarding relevant results ranked higher.

        **MAP** (0–1) — Mean Average Precision; rewards putting relevant results near the top.

        **MRR** (0–1) — How far down you scroll to find the first good result.

        ---

        ### Clustering Metrics

        **V-Measure** (0–1) — Balance of cluster purity and completeness.

        ---

        ### Semantic Similarity Metrics

        **Spearman Correlation** (–1 to 1) — Agreement with human similarity judgments.

        **Pearson Correlation** (–1 to 1) — Similar to Spearman, stricter about proportional scores.

        ---

        | Score Range | Classification/V-Measure | Retrieval | Correlation |
        |-------------|--------------------------|-----------|-------------|
        | 0.90–1.00 | Excellent | Excellent | Very Strong |
        | 0.80–0.89 | Very Good | Very Good | Strong |
        | 0.70–0.79 | Good | Good | Moderate-Strong |
        | 0.60–0.69 | Fair | Fair | Moderate |
        | 0.50–0.59 | Weak | Weak | Weak |
        | <0.50 | Poor | Poor | Very Weak |
        """)

    # Human Benchmark filter
    human_benchmark_tasks = ["STS12", "STS13", "STS14", "STS15", "STS16", "STS17",
                             "STSBenchmark", "SICKRelatedness"]

    st.markdown("### 🔍 Filters")
    include_human_benchmark = st.checkbox(
        "Human Benchmark",
        value=True,
        help="Include tasks with human-annotated similarity scores (e.g., STS tasks)",
    )

    benchmark_filtered_tasks = all_tasks.copy() if include_human_benchmark else [
        t for t in all_tasks if t not in human_benchmark_tasks
    ]

    task_domains = {
        "Code": ["StackOverflowDupQuestions", "CodeSearchNet"],
        "Legal": ["LegalBenchConsumerContractsQA", "LegalBenchCorporateLobbying", "LegalSummarization"],
        "Medical": ["MedicalQARetrieval", "PubMedQA", "BioASQ"],
        "Financial": ["Banking77Classification", "FiQA2018"],
        "Scientific": ["SCIDOCS", "SciDocsRR", "ArxivClusteringP2P", "ArxivClusteringS2S"],
        "Social Media": ["TwitterSemEval2015", "TwitterURLCorpus", "TweetSentimentExtraction"],
        "News": ["TwentyNewsgroupsClustering"],
        "General": ["ArguAna", "NFCorpus", "EmotionClassification", "ToxicConversationsClassification",
                    "STS12", "STS13", "STS14", "STS15", "STS16", "STS17", "STS22",
                    "AskUbuntuDupQuestions", "MindSmallReranking", "SprintDuplicateQuestions",
                    "STSBenchmark", "SICKRelatedness"],
    }

    all_mapped_tasks = {t for tasks in task_domains.values() for t in tasks}
    unmapped = [t for t in benchmark_filtered_tasks if t not in all_mapped_tasks]
    if unmapped:
        task_domains["Other"] = unmapped

    st.markdown("### 🏷️ Task Selection")
    col1, col2 = st.columns([1, 2])

    with col1:
        available_domains = [
            d for d, tasks in task_domains.items()
            if any(t in benchmark_filtered_tasks for t in tasks)
        ]
        selected_domains = st.multiselect(
            "Domain",
            options=available_domains,
            default=available_domains,
            help="Filter tasks by domain.",
        )

    if selected_domains:
        domain_tasks = []
        for d in selected_domains:
            domain_tasks.extend(t for t in task_domains[d] if t in benchmark_filtered_tasks)
        available_task_options = sorted(set(domain_tasks))
    else:
        available_task_options = benchmark_filtered_tasks

    with col2:
        selected_tasks = st.multiselect(
            "Tasks",
            options=available_task_options,
            default=available_task_options,
            help="Choose which MTEB tasks to display.",
        )

    if not selected_tasks:
        st.warning("Please select at least one task (or choose a domain)")
        return

    filtered_df = df[df["task_name"].isin(selected_tasks)]

    # Deduplicate: keep most recent run per (model, platform, task_name)
    filtered_df = (
        filtered_df.sort_values("timestamp", ascending=False)
        .drop_duplicates(subset=["model", "platform", "task_name"], keep="first")
    )

    metric_labels = {
        "accuracy": "Accuracy",
        "f1": "F1 Score",
        "precision": "Precision",
        "recall": "Recall",
        "ndcg_at_10": "NDCG@10",
        "map": "MAP",
        "mrr": "MRR",
        "v_measure": "V-Measure",
        "cosine_spearman": "Spearman Correlation",
        "cosine_pearson": "Pearson Correlation",
    }

    available_metrics = [
        m for m in ["accuracy", "f1", "ndcg_at_10", "map", "mrr", "v_measure", "cosine_spearman"]
        if m in filtered_df.columns and filtered_df[m].notna().any()
    ]

    if not available_metrics:
        st.warning("No metrics found in selected tasks")
        return

    filter_info = []
    if not include_human_benchmark:
        filter_info.append("Excluding Human Benchmark tasks")
    if selected_domains and len(selected_domains) < len(available_domains):
        filter_info.append(f"Domains: {', '.join(selected_domains)}")
    if filter_info:
        st.info(f"📊 Showing {len(selected_tasks)} tasks | Filters: {' | '.join(filter_info)}")

    st.subheader("📊 Model Performance by Task Category")
    plot_mteb_radar_chart(filtered_df, models)

    st.subheader("Model Comparison by Task")

    for metric in available_metrics:
        metric_df = filtered_df[filtered_df[metric].notna()].copy()
        if metric_df.empty:
            continue
        metric_df["model_short"] = metric_df["model"].apply(lambda x: x.split("/")[-1])

        fig = px.bar(
            metric_df,
            x="task_name",
            y=metric,
            color="model_short",
            barmode="group",
            title=f"{metric_labels.get(metric, metric)} by Task",
            text=metric,
        )
        fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
        fig.update_layout(
            xaxis_title="Task",
            yaxis_title=metric_labels.get(metric, metric),
            height=500,
            legend_title="Model",
            legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5,
                        font=dict(size=10)),
            margin=dict(b=150),
        )
        st.plotly_chart(fig, use_container_width=True)

    def classify_score(score):
        if pd.isna(score):
            return "N/A"
        if score >= 0.90:
            return "⭐ Excellent"
        elif score >= 0.80:
            return "✅ Very Good"
        elif score >= 0.70:
            return "👍 Good"
        elif score >= 0.60:
            return "👌 Fair"
        elif score >= 0.50:
            return "⚠️ Weak"
        return "❌ Poor"

    st.subheader("Quality Metrics Summary")
    summary_data = []
    for model in models:
        model_df = filtered_df[filtered_df["model"] == model]
        row = {"Model": model.split("/")[-1], "Tasks": len(model_df)}
        for m in available_metrics:
            vals = model_df[m].dropna()
            if not vals.empty:
                row[metric_labels.get(m, m)] = vals.mean()
        summary_data.append(row)

    if summary_data:
        summary_df = pd.DataFrame(summary_data).round(3)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        ratings = []
        for row in summary_data:
            r = {"Model": row["Model"]}
            for m in available_metrics:
                label = metric_labels.get(m, m)
                if label in row:
                    r[label] = classify_score(row[label])
            ratings.append(r)
        st.dataframe(pd.DataFrame(ratings), use_container_width=True, hide_index=True)
        st.caption("""
        **Rating Scale:**
        ⭐ Excellent (0.90–1.00) | ✅ Very Good (0.80–0.89) | 👍 Good (0.70–0.79) |
        👌 Fair (0.60–0.69) | ⚠️ Weak (0.50–0.59) | ❌ Poor (<0.50)
        """)

    def get_task_domain(task_name):
        for domain, tasks in task_domains.items():
            if task_name in tasks:
                return domain
        return "Unknown"

    st.subheader("Detailed Task Results")
    display_df = filtered_df.copy()
    display_df["model_short"] = display_df["model"].apply(lambda x: x.split("/")[-1])
    display_df["domain"] = display_df["task_name"].apply(get_task_domain)
    display_cols = ["model_short", "task_name", "domain", "platform", "task_preset"] + available_metrics
    display_df = display_df[display_cols]
    display_df.columns = ["Model", "Task", "Domain", "Platform", "Preset"] + [
        metric_labels.get(m, m) for m in available_metrics
    ]
    st.dataframe(display_df.round(3), use_container_width=True)


def main():
    """Main MTEB Quality dashboard."""
    st.title("🎯 MTEB Embedding Quality")
    st.markdown("Embedding model quality evaluation using the Massive Text Embedding Benchmark")

    with st.sidebar:
        st.header("Configuration")

        config = DashboardConfig()
        default_mteb_dir = str(Path(config.get_results_directory()).parent / "mteb")

        mteb_dir_input = st.text_input(
            "MTEB Results Directory",
            value=default_mteb_dir,
            help="Path to MTEB quality results directory",
            key="results_dir_mteb",
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()

        st.markdown("---")
        st.markdown("**Quality Metrics:**")
        st.markdown("""
        - Classification Accuracy / F1
        - Retrieval Performance (NDCG@10, MAP, MRR)
        - Clustering Quality (V-measure)
        - Semantic Similarity (Spearman / Pearson)
        """)

    df = load_mteb_data(mteb_dir_input)

    if df.empty:
        st.error(f"No MTEB results found in `{mteb_dir_input}`")
        st.info("""
        Run MTEB quality benchmarks first:

        ```bash
        ansible-playbook mteb-benchmark.yml \\
          -e "test_model=RedHatAI/granite-embedding-english-r2" \\
          -e "mteb_task_preset=quick"
        ```
        """)
        return

    # ── Platform filter ──────────────────────────────────────────────────────
    known_platforms = sorted(p for p in df["platform"].unique() if p and p != "unknown")
    has_unknown = (df["platform"] == "unknown").any()
    platform_options = known_platforms + (["unknown"] if has_unknown else [])

    if len(platform_options) > 1:
        selected_platforms = st.multiselect(
            "Platforms",
            options=platform_options,
            default=platform_options,
            help="Filter by CPU platform recorded during the MTEB run",
        )
        if not selected_platforms:
            st.warning("Please select at least one platform")
            return
        df = df[df["platform"].isin(selected_platforms)]
    elif len(platform_options) == 1:
        st.caption(f"Platform: {platform_options[0]}")
    # else: no platform metadata — show all rows

    # ── Model filter ─────────────────────────────────────────────────────────
    models = sorted(df["model"].unique())
    selected_models = st.multiselect(
        "Models",
        options=models,
        default=models,
        help="Filter by embedding model",
    )
    if not selected_models:
        st.warning("Please select at least one model")
        return
    df = df[df["model"].isin(selected_models)]

    n_runs = df.drop_duplicates(subset=["model", "platform", "timestamp"]).shape[0]
    n_platforms = df["platform"].nunique()
    st.success(
        f"✓ Loaded {len(df)} task results from {n_runs} run(s) "
        f"across {n_platforms} platform(s)"
    )

    plot_mteb_quality_metrics(df)


if __name__ == "__main__":
    main()
