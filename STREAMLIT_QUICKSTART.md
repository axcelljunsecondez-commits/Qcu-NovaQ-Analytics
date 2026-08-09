"""
Streamlit Multi-Page Queueing Theory Dashboard
==============================================

QUICK START GUIDE

1. ENVIRONMENT SETUP
───────────────────────────────────────────────────────────────────────────────

PowerShell:
    cd "c:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main"
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt


2. RUN THE APP
───────────────────────────────────────────────────────────────────────────────

    streamlit run legacy_streamlit/streamlit_app.py

The dashboard will open in your browser at:
    http://localhost:8501


3. WORKFLOW
───────────────────────────────────────────────────────────────────────────────

PAGE 1: Current Metrics
  ✅ Upload CSV/Excel with 9 required columns
  ✅ Validate schema
  ✅ Convert numeric columns
  ✅ Compute M/M/c metrics
  ✅ Store in st.session_state["current_data"]

PAGE 2: Optimization
  ✅ Load current_data
  ✅ For each row: while ρ >= 0.70, increment servers
  ✅ Recompute all metrics
  ✅ Store in st.session_state["recommended_data"]
  ✅ Export to Excel

PAGE 3: Comparison
  ✅ Pre-check: current_data exists
  ✅ Pre-check: recommended_data exists
  ✅ Inner merge with suffixes
  ✅ Calculate deltas
  ✅ Visualize improvements

PAGE 4: Simulation
  ✅ Pre-check: recommended_data exists
  🚨 CRITICAL: Use ONLY recommended_data
  ✅ Run 100 Monte Carlo simulations per row
  ✅ Arrival variation: ±20%, Service variation: ±10%
  ✅ Output: failure_rate, avg_utilization, max_utilization
  ✅ PASS if failure_rate ≤ 10%


4. DATA SCHEMA (REQUIRED)
───────────────────────────────────────────────────────────────────────────────

Column Name          Type      Example    Description
─────────────────────────────────────────────────────────────────────────────
time_interval        string    08:00-09:00  Time period
arrival_rate (λ)     float     30.0        Arrivals per hour
service_rate (μ)     float     15.0        Service completions per server/hour
servers (c)          int       3           Number of servers/staff
utilization (ρ)      float     0.667       ρ = λ/(c*μ)
Lq                   float     0.5         Average queue length
Wq                   float     0.016       Average wait time in queue (hours)
Ls                   float     2.5         Average system length
Ws                   float     0.083       Average time in system (hours)


5. FORMULAS
───────────────────────────────────────────────────────────────────────────────

M/M/c Queue:
  ρ (utilization) = λ / (c * μ)
  
  Erlang-C Formula:
    Pw = C(c, a) / [C(c, a) + (1 - ρ) * Σ(a^n / n!)]
    where a = λ/μ and C(c, a) = (a^c / c!) / Σ(a^i / i!)
  
  queue metrics:
    Lq = (Pw * ρ) / (c * (1 - ρ))
    Wq = Lq / λ
    Ls = Lq + λ/μ
    Ws = Wq + 1/μ


6. ERROR HANDLING (DEFENSIVE PROGRAMMING)
───────────────────────────────────────────────────────────────────────────────

✅ Page 1:
  - Validate schema (all 9 columns present)
  - Convert numeric columns (check for NaN)
  - Handle div-by-zero in metrics computation
  - Sample data provided for testing

✅ Page 2:
  - Pre-check: current_data exists (stop if not)
  - Safety limit: max 20 servers to prevent infinite loops
  - Validation: skip rows with invalid inputs
  
✅ Page 3:
  - Pre-check: current_data exists (stop if not)
  - Pre-check: recommended_data exists (stop if not)
  - Inner merge with suffixes to prevent column conflicts
  
✅ Page 4:
  - Pre-check: recommended_data exists (stop if not)
  - 🚨 CRITICAL: Uses ONLY st.session_state["recommended_data"]
  - Handles edge cases: zero denominators, inf values
  - Pass/Fail verdict clear (failure_rate ≤ 10%)


7. MODULAR FUNCTIONS (utils.py)
───────────────────────────────────────────────────────────────────────────────

compute_metrics(lambda_, mu, c)
  → Returns dict with utilization, Lq, Wq, Ls, Ws

optimize_servers(row, target_utilization, max_servers)
  → Returns pd.Series with optimized servers and metrics

run_simulation(row, num_simulations, failure_threshold)
  → Returns dict with avg_util, max_util, failure_rate, status

validate_schema(df)
  → Returns (success: bool, message: str)

validate_and_convert_numeric(df)
  → Returns (success: bool, message: str, converted_df: DataFrame)


8. SESSION STATE STRUCTURE
───────────────────────────────────────────────────────────────────────────────

st.session_state["current_data"]
  - Set by Page 1
  - Used by Page 2, Page 3
  - Schema: 9 columns
  - Type: pd.DataFrame

st.session_state["recommended_data"]
  - Set by Page 2
  - Used by Page 3, Page 4
  - Schema: 9 columns
  - Type: pd.DataFrame

st.session_state["comparison_data"]
  - Set by Page 3
  - Schema: merged with suffixes
  - Type: pd.DataFrame

st.session_state["simulation_results"]
  - Set by Page 4
  - Schema: time_interval, servers, avg_util, max_util, failure_rate, status
  - Type: pd.DataFrame


9. EXPORT FILES
───────────────────────────────────────────────────────────────────────────────

Page 1: current_data.csv
Page 2: recommended_data.csv, recommended_optimized_data.xlsx
Page 3: comparison_data.csv
Page 4: simulation_results.csv


10. TROUBLESHOOTING
───────────────────────────────────────────────────────────────────────────────

❌ "current_data NOT found" on Page 2
  → Complete Page 1 first and click "Save as Current Data"

❌ "recommended_data NOT found" on Page 3
  → Complete Page 2 first and click "Run Optimization"

❌ "recommended_data NOT found" on Page 4
  → Complete Page 2 first

❌ KeyError on merge
  → Check that both dataframes have "time_interval" column
  → Check that suffixes are applied (_current, _recommended)

❌ NaN values in metrics
  → Page 1 validation may have failed
  → Try processing a smaller CSV with cleaner data

❌ Infinite loop in optimization
  → Safety limit enforced: max 20 servers
  → May indicate input data issues


11. STOPPING THE APP
───────────────────────────────────────────────────────────────────────────────

In terminal: Ctrl+C
In VS Code: Stop button


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ Ready to use! Open streamlit_app.py and let's optimize your queue system.

"""
