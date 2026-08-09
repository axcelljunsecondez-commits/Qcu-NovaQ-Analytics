# QCU Queueing Theory Dashboard

[![CI](https://github.com/axcelljunsecondez-commits/qcu-queueing-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/axcelljunsecondez-commits/qcu-queueing-dashboard/actions/workflows/ci.yml)

Streamlit dashboard for analyzing QCU service queues with M/M/1, M/M/c, M/G/c, M/M/c/K, and M/G/c/K queueing models. The app helps compare current staffing, optimized staffing, Monte Carlo simulation results, and cost trade-offs.

## Features

- Upload CSV or Excel queue data.
- Compute utilization, queue length, waiting time, and system time.
- Support M/M/1, M/M/c, M/G/c, M/M/c/K, and M/G/c/K.
- Recommend staffing changes based on utilization and cost.
- Run simulation and comparison pages for scenario review.
- Export tables for reporting.

## Quick Start

```bash
pip install -r requirements.txt && streamlit run legacy_streamlit/streamlit_app.py
```

## Requirements

- Python 3.10 or newer recommended
- Streamlit and the packages listed in `requirements.txt`

## Installation

From PowerShell:

```powershell
cd path\to\project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Or on Linux/macOS:

```bash
cd path/to/project
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

If the virtual environment already exists, activate it and install/update dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run The App

```powershell
streamlit run legacy_streamlit/streamlit_app.py
```

The dashboard opens at:

```text
http://localhost:8501
```

You can also use the included launcher:

```powershell
.\launch_dashboard.ps1
```

## Input Data

Required columns:

| Column | Description |
| --- | --- |
| `time` | Time segment label, such as `08:00-09:00` |
| `lambda` | Arrival rate per time unit |
| `mu` | Service rate per server per time unit |
| `c` | Number of servers |

Optional columns:

| Column | Description |
| --- | --- |
| `variance` | Service-time variance for M/G/c analysis |
| `K` | Total system capacity for finite-capacity models |

`K` means the maximum number of customers allowed in the whole system:

```text
K = customers being served + customers waiting
```

For example, if `c = 3` and `K = 10`, then 3 customers can be served and up to 7 can wait. Additional arrivals are blocked.

## Model Selection

The app chooses the model per row using these rules:

| Uploaded columns | Model |
| --- | --- |
| `c = 1`, no `variance`, no `K` | M/M/1 |
| `c > 1`, no `variance`, no `K` | M/M/c |
| `variance` present, no `K` | M/G/c |
| `K` present, no `variance` | M/M/c/K |
| `variance` and `K` present | M/G/c/K |

For finite-capacity rows, `K` must be greater than or equal to `c`.

Example CSV:

```csv
time,lambda,mu,c,variance,K
08:00-09:00,30,12,3,,12
09:00-10:00,45,12,4,,15
10:00-11:00,50,12,4,0.006,15
11:00-12:00,18,20,1,,
```

In this example:

- First row uses M/M/c/K.
- Second row uses M/M/c/K.
- Third row uses M/G/c/K.
- Fourth row uses M/M/1.

## Key Metrics

- `rho`: server utilization
- `Lq`: average queue length
- `Wq`: average waiting time in queue
- `L`: average number of customers in system
- `W`: average time in system

## Stability Rules

- M/M/1: `lambda < mu`
- M/M/c and M/G/c: `lambda < c * mu`
- M/M/c/K and M/G/c/K: finite-capacity systems are bounded, but high offered load increases blocking probability.

Rows that violate the stability condition are marked unstable and should be adjusted before relying on the reported queue metrics.

## Tests

Run the test suite with coverage:

```powershell
python -m pytest tests --cov=queue_models --cov=optimization --cov=simulation --cov=costing --cov-report=term-missing
```

Tests cover queue formulas, optimization logic, Monte Carlo simulation, and cost analysis.
