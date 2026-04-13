"""
Operational Bottleneck Simulator — Streamlit App
Model multi-stage workflows, identify bottlenecks, and test capacity changes.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from simulator import (
    BottleneckSimulator,
    StageConfig,
    results_to_df,
    default_stages,
)

st.set_page_config(
    page_title="Bottleneck Simulator",
    page_icon="⚙",
    layout="wide",
)

st.title("⚙ Operational Bottleneck Simulator")
st.caption(
    "Model multi-stage operational workflows using discrete-event simulation. "
    "Adjust arrival rates and stage capacity to surface bottlenecks before they hit production."
)

# ── Sidebar: workflow builder ────────────────────────────────────────────────
with st.sidebar:
    st.header("Workflow Configuration")

    arrival_rate = st.slider(
        "Job arrival rate (per hour)", min_value=5, max_value=200, value=60, step=5
    )
    sim_hours = st.slider(
        "Simulation duration (hours)", min_value=1, max_value=48, value=8, step=1
    )
    seed = st.number_input("Random seed", value=42, step=1)

    st.divider()
    st.subheader("Workflow Stages")
    st.caption("Add or edit stages. Each stage can have multiple parallel servers.")

    use_preset = st.button("Load preset workflow")

    if "stages" not in st.session_state or use_preset:
        st.session_state.stages = [
            {"name": s.name, "servers": s.servers,
             "avg_svc": s.avg_service_time, "std_svc": s.std_service_time}
            for s in default_stages()
        ]

    n_stages = st.number_input("Number of stages", min_value=1, max_value=8, value=len(st.session_state.stages), step=1)

    while len(st.session_state.stages) < n_stages:
        st.session_state.stages.append({"name": f"Stage {len(st.session_state.stages)+1}", "servers": 1, "avg_svc": 5.0, "std_svc": 1.5})
    while len(st.session_state.stages) > n_stages:
        st.session_state.stages.pop()

    for i, stage in enumerate(st.session_state.stages):
        with st.expander(f"Stage {i+1}: {stage['name']}", expanded=(i < 2)):
            stage["name"] = st.text_input(f"Name##{i}", value=stage["name"])
            stage["servers"] = st.number_input(f"Servers (parallel workers)##{i}", min_value=1, max_value=20, value=stage["servers"])
            stage["avg_svc"] = st.number_input(f"Avg service time (min)##{i}", min_value=0.1, max_value=120.0, value=stage["avg_svc"], step=0.5)
            stage["std_svc"] = st.number_input(f"Std dev service time (min)##{i}", min_value=0.0, max_value=30.0, value=stage["std_svc"], step=0.25)

    run_btn = st.button("Run Simulation", type="primary", use_container_width=True)

# ── Run ──────────────────────────────────────────────────────────────────────
if run_btn or "last_results" not in st.session_state:
    stages = [
        StageConfig(
            name=s["name"],
            servers=s["servers"],
            avg_service_time=s["avg_svc"],
            std_service_time=s["std_svc"],
        )
        for s in st.session_state.stages
    ]

    with st.spinner("Simulating..."):
        sim = BottleneckSimulator(
            stages=stages,
            arrival_rate=arrival_rate,
            sim_duration=sim_hours * 60,
            seed=int(seed),
        )
        results = sim.run()
        st.session_state.last_results = results
        st.session_state.last_arrival = arrival_rate

results = st.session_state.last_results
df = results_to_df(results)

# ── Top metrics ──────────────────────────────────────────────────────────────
bottleneck = next((r for r in results if r.is_bottleneck), results[0])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Arrival Rate", f"{st.session_state.get('last_arrival', arrival_rate)} jobs/hr")
col2.metric("Bottleneck Stage", bottleneck.stage_name)
col3.metric("Bottleneck Utilization", f"{bottleneck.utilization*100:.1f}%")
col4.metric("Bottleneck Avg Queue", f"{bottleneck.avg_queue_length:.1f} jobs")

st.divider()

tab1, tab2, tab3 = st.tabs(["Utilization & Queues", "Wait Times", "Full Results Table"])

# Tab 1 — Utilization bar chart + queue lengths
with tab1:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Utilization by Stage")
        colors = ["#e05252" if r.is_bottleneck else "#2d7dd2" for r in results]
        fig1 = go.Figure(go.Bar(
            x=[r.stage_name for r in results],
            y=[r.utilization * 100 for r in results],
            marker_color=colors,
            text=[f"{r.utilization*100:.1f}%" for r in results],
            textposition="outside",
        ))
        fig1.add_hline(y=85, line_dash="dash", line_color="orange",
                       annotation_text="85% threshold", annotation_position="top right")
        fig1.update_layout(
            height=350, yaxis=dict(range=[0, 110], title="Utilization (%)"),
            xaxis_title="Stage", margin=dict(l=10, r=10, t=10, b=80),
            showlegend=False,
        )
        st.plotly_chart(fig1, use_container_width=True)
        st.caption("Red bar = identified bottleneck. Dashed line = 85% utilization warning threshold.")

    with col_b:
        st.subheader("Average Queue Length")
        fig2 = go.Figure(go.Bar(
            x=[r.stage_name for r in results],
            y=[r.avg_queue_length for r in results],
            marker_color=["#e05252" if r.is_bottleneck else "#5aab8f" for r in results],
            text=[f"{r.avg_queue_length:.1f}" for r in results],
            textposition="outside",
        ))
        fig2.update_layout(
            height=350, yaxis_title="Avg Jobs Waiting",
            xaxis_title="Stage", margin=dict(l=10, r=10, t=10, b=80),
        )
        st.plotly_chart(fig2, use_container_width=True)

# Tab 2 — Wait times
with tab2:
    st.subheader("Average Wait Time Before Each Stage")
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        name="Wait Time (queue)",
        x=[r.stage_name for r in results],
        y=[r.avg_wait_time for r in results],
        marker_color="#e05252",
    ))
    fig3.add_trace(go.Bar(
        name="Service Time (processing)",
        x=[r.stage_name for r in results],
        y=[r.avg_service_time for r in results],
        marker_color="#2d7dd2",
    ))
    fig3.update_layout(
        barmode="stack", height=380,
        yaxis_title="Minutes", xaxis_title="Stage",
        margin=dict(l=10, r=10, t=20, b=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.caption("Red = time waiting in queue. Blue = actual processing time. A large red segment = upstream pressure from the bottleneck.")

# Tab 3 — Full table
with tab3:
    st.subheader("Full Simulation Results")
    st.dataframe(
        df.style.apply(
            lambda row: ["background-color: #fff0f0" if row["Bottleneck"] else "" for _ in row],
            axis=1,
        ),
        use_container_width=True,
        hide_index=True,
    )

    csv = df.to_csv(index=False)
    st.download_button("Download results CSV", csv, file_name="sim_results.csv", mime="text/csv")

# ── What-if callout ──────────────────────────────────────────────────────────
st.divider()
st.markdown("**What-if analysis:** Add a server to the bottleneck stage in the sidebar and re-run to see utilization and queue length drop.")
