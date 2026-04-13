# Operational Bottleneck Simulator

Discrete-event simulation of multi-stage operational workflows. Model queue buildup, server utilization, and throughput under variable arrival rates — then identify bottleneck nodes and test capacity changes before they hit production.

**Built from:** the manual process mapping and root cause analysis work at Quadcore Innovations on the Nuff Cash platform.

## Stack
- Python · SimPy · Streamlit · Plotly

## Usage

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Features
- Configure any multi-stage workflow (up to 8 stages)
- Set arrival rate, server count, and service time per stage
- Discrete-event simulation via SimPy (exponential inter-arrivals, normal service times)
- Identifies bottleneck stage by utilization
- Visualizes: utilization bars, queue lengths, wait time vs service time breakdown
- What-if analysis: add a server, re-run, see the delta instantly
- Preset workflow: simplified Nuff Cash transaction pipeline (Intake → Fraud Screening → Payment Processing → Ledger Update → Notification)

## How it works

Each "job" (transaction/request) moves through stages sequentially. At each stage it joins a queue, waits for a free server, gets processed, then moves on. SimPy handles the event scheduling. The simulator collects queue lengths, wait times, service times, and utilization across the full simulation window.

The bottleneck is the stage with the highest server utilization — the one constraining overall throughput.
