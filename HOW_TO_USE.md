# 📚 HOW TO USE — NOVAMART Queueing Theory Dashboard

**Complete Step-by-Step Guide for Running and Using the System**

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation & Setup](#installation--setup)
3. [Starting the Dashboard](#starting-the-dashboard)
4. [Using the Dashboard](#using-the-dashboard)
5. [Page-by-Page Workflow](#page-by-page-workflow)
6. [Adjusting Costing Parameters](#adjusting-costing-parameters)
7. [Troubleshooting](#troubleshooting)
8. [Examples & Scenarios](#examples--scenarios)

---

## ✅ Prerequisites

### **What You Need**

- ✅ **Windows PC/Laptop**
- ✅ **Python 3.11+ installed** (should already be installed)
- ✅ **Virtual Environment (.venv)** (already created)
- ✅ **Project folder:** `c:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main`
- ✅ **Data file:** `merged_daily_data.csv` (ready to upload)

### **Check Your Setup**

Open PowerShell and verify:

```powershell
# Check if Python is installed
python --version
# Should show: Python 3.11.x

# Navigate to project
cd "c:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main"

# Check if virtual environment exists
ls .venv
# Should show: Scripts, Lib, pyvenv.cfg
```

---

## 🔧 Installation & Setup

### **Step 1: Open PowerShell**

**Method A: Press Windows Key + R**
```
Type: powershell
Press: Enter
```

**Method B: Right-click Desktop → Open PowerShell here**

---

### **Step 2: Navigate to Project Folder**

Copy-paste this command:

```powershell
cd "c:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main"
```

**You should see the path in your terminal:**
```
C:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main>
```

---

### **Step 3: (Optional) Activate Virtual Environment**

This activates the Python environment with all required packages:

```powershell
.\.venv\Scripts\Activate.ps1
```

**You should see `(.venv)` at the start of the line:**
```
(.venv) C:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main>
```

---

## 🚀 Starting the Dashboard

### **Command to Start**

Run this command:

```powershell
.\.venv\Scripts\python.exe -m streamlit run legacy_streamlit/streamlit_app.py
```

**Or if venv is activated:**

```powershell
python -m streamlit run legacy_streamlit/streamlit_app.py
```

---

### **Expected Output**

You should see:

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8502
  Network URL: http://192.168.1.32:8502
```

---

### **Step 4: Open Dashboard in Browser**

Click the link or open manually:

```
http://localhost:8502
```

**You should see:**
- Left sidebar with "📊 Queueing Theory Optimizer"
- 4 page options (Page 1-4)
- Costing parameters section
- Main content area

✅ **Dashboard is now running!**

---

## 🎯 Using the Dashboard

### **Dashboard Layout**

```
┌─────────────────────────────────────────────────────────┐
│ STREAMLIT                                               │
├──────────────────┬──────────────────────────────────────┤
│                  │                                      │
│  LEFT SIDEBAR    │      MAIN CONTENT AREA              │
│                  │                                      │
│ 📊 Title         │  Page-specific content:             │
│                  │  - Forms                            │
│ Page 1-4 links   │  - Charts                           │
│                  │  - Tables                           │
│ Costing          │  - Buttons                          │
│ Parameters       │  - Metrics                          │
│                  │                                      │
│ 💼 Cost/hr       │                                      │
│ ⏳ Wait Cost     │                                      │
│ ❌ Abandon       │                                      │
│                  │                                      │
└──────────────────┴──────────────────────────────────────┘
```

---

## 📄 Page-by-Page Workflow

### **Complete Workflow: 4 Pages in Order**

#### **⏱️ Total Time: ~10-15 minutes**

---

## **PAGE 1: Upload & Validate Current Metrics** 📥

### **What This Page Does**
- Accepts your queue data (CSV/Excel)
- Validates the format
- Computes M/M/c queue metrics (Lq, Wq, Ls, Ws)
- Stores data for optimization

### **Step-by-Step**

**1. Click "Page 1: Current Metrics" (Left Sidebar)**

You'll see a form with:
- "Upload file (CSV/Excel only)"
- "Sample Data Loader" button
- Data table below

**2. Upload Your Data**

**Option A: Use your prepared data**
- Click "Browse files"
- Select `merged_daily_data.csv`
- File uploads (shows in table)

**Option B: Generate sample data** (for testing)
- Click "📊 Generate Sample Data & Save"
- Automatically creates sample data

**3. Verify Data Structure**

The table should show 9 columns:
```
time_interval | arrival_rate | service_rate | servers | 
utilization | Lq | Wq | Ls | Ws
```

Example row:
```
05:00-06:00 | 15.2 | 8.5 | 2 | 0.894 | 2.34 | 0.154 | 3.53 | 0.232
```

**4. Save Data**

Click blue button: **"✅ Save as Current Data"**

You should see:
```
✅ Data saved successfully!
Schema valid ✓
All numeric columns valid ✓
```

**✅ Page 1 Complete!**

---

## **PAGE 2: Generate Optimized Recommendations** ⚙️

### **What This Page Does**
- Optimizes server count by increasing servers until ρ < 0.70
- Recomputes all queue metrics
- **Calculates costs** (Server, Wait, Abandonment)
- Shows daily/monthly/annual savings
- Exports recommendations

### **Step-by-Step**

**1. Click "Page 2: Optimization Engine" (Left Sidebar)**

**2. (OPTIONAL) Adjust Costing Parameters**

**Option A: Via Sidebar**
- Left sidebar → "💰 Costing Parameters"
- Adjust 3 sliders:
  - 💼 Cost per Cashier: 87 (default)
  - ⏳ Cost of Wait: 100 (default)
  - ❌ Cost per Abandon: 60 (default)

**Option B: Via Page 2 "Costing Settings" Tab**
- Click "⚙️ Configuration & Costing"
- Tab: "Costing Settings"
- Same 3 input fields

**3. Run Optimization**

Click big blue button: **"🚀 Run Optimization"**

⏳ **Wait (30-60 seconds)** - Progress bar shows progress

You should see:
```
✅ Optimization complete!
```

**4. Review Optimization Results**

Scroll down to see:

**Metrics Summary:**
- Avg Utilization (before vs after)
- Max Utilization
- Total Servers (Δ change)
- Rows Improved

**Comparison Table:**
| Time | Current Servers | Recommended Servers | Delta | ρ Change |
|------|-----------------|-------------------|-------|----------|
| 05:00-06:00 | 2 | 2 | 0 | -0.05 |
| 06:00-07:00 | 2 | 3 | +1 | -0.12 |

**5. View Cost Analysis** 💰

**Scroll to "💰 Cost Analysis" section:**

**Cost Summary:**
```
Current Total Cost (24h):      ₱18,750
Recommended Total Cost (24h):  ₱15,200
Daily Savings:                 🟢 ₱3,550 (18.9%)
Monthly Savings (30d):         ₱106,500
```

**Cost Breakdown Table:**
| Time | Current Servers | Server Cost | Wait Cost | Abandon Cost | Total |
|------|-----------------|------------|-----------|--------------|-------|
| 05:00-06:00 | 2 | ₱726 | ₱482 | ₱129 | ₱1,337 |

**Cost Component Chart:**
Visual bar chart showing cost comparison (Current vs Recommended)

**6. Download Results** (Optional)

- Click "📥 Download CSV" to save CSV
- Click "📊 Download Excel" to save Excel

**✅ Page 2 Complete!**

---

## **PAGE 3: Compare & View Savings** 📊

### **What This Page Does**
- Merges current and recommended data
- Shows improvements in metrics
- **Displays cost savings** (daily/monthly/annual)
- Visualizes all deltas
- Enables side-by-side comparison

### **Step-by-Step**

**1. Click "Page 3: Comparison" (Left Sidebar)**

**2. Check Dependencies** ✅

You should see:
```
✅ current_data exists
✅ recommended_data exists
✅ Merged 13 rows
```

If red ❌: Go back to Page 1 & 2 first!

**3. Review Delta Metrics**

Table showing Average changes:
| Metric | Current | Recommended | Δ | % Change |
|--------|---------|------------|---|----------|
| Servers | 2.3 | 2.7 | +0.4 | +17% |
| ρ (Util) | 0.82 | 0.68 | -0.14 | -17% |
| Lq | 2.45 | 0.89 | -1.56 | -64% |
| Wq | 0.162 | 0.059 | -0.103 | -64% |

**4. View Key Insights** 🎯

Four metrics boxes show:
- Server Count (Δ)
- Avg Utilization (Δ)
- Avg Wait Time (Δ)
- Intervals Improved (%)

**5. View Visualizations**

Four interactive charts:
1. **Utilization Comparison** (bar chart)
2. **Server Allocation** (bar chart)
3. **Queue Metrics** (Lq & Wq side-by-side)
4. **Cost Breakdown** (Server vs Wait vs Abandon)

**6. View Cost Analysis** 💰

**Scroll to "💰 Cost Analysis & Savings" section:**

**Cost Savings Summary:**
```
Current Total Cost (24h):        ₱18,750
Recommended Total Cost (24h):    ₱15,200
Daily Savings:                   🟢 ₱3,550 (18.9%)
Monthly Savings (30 days):       ₱106,500
Annual Savings (365 days):       ₱1,296,750
```

**Cost Component Breakdown:**
| Component | Current (₱) | Recommended (₱) | Savings (₱) |
|-----------|------------|-----------------|------------|
| Server Cost | 8,700 | 11,200 | -2,500 |
| Wait Cost | 8,400 | 3,100 | 5,300 |
| Abandonment | 1,650 | 900 | 750 |
| **TOTAL** | **18,750** | **15,200** | **3,550** |

**Cost Component Chart:**
Visual showing cost breakdown comparison

**7. Detailed Comparison Table**

Full time-interval breakdown with all metrics and costs

**8. Download** (Optional)

Click "📥 Download Comparison CSV"

**✅ Page 3 Complete!**

---

## **PAGE 4: Monte Carlo Simulation** 🔁

### **What This Page Does**
- Runs 100 Monte Carlo simulations per row
- Tests stability with ±20% arrival variability, ±10% service variation
- Calculates failure rate (when ρ > 0.80)
- **Pass/Fail verdict** (Pass if failure_rate ≤ 10%)
- Validates optimization recommendation

### **Step-by-Step**

**1. Click "Page 4: Simulation" (Left Sidebar)**

**2. Check Dependency** ✅

You should see:
```
✅ recommended_data exists
```

If red ❌: Go back to Pages 1-3 first!

**3. Run Simulation**

Click big blue button: **"🎲 Run 100x Simulation"**

⏳ **Wait (60-120 seconds)** - Progress bar shows progress

You should see:
```
✅ Simulation complete!
```

**4. Review Results**

**Simulation Summary Table for each interval:**
| Time | Avg Util | Max Util | Failures | Fail Rate | Status |
|------|----------|----------|----------|-----------|--------|
| 05:00-06:00 | 0.567 | 0.742 | 2 | 2.0% | ✅ PASS |
| 06:00-07:00 | 0.638 | 0.891 | 7 | 7.0% | ✅ PASS |
| 14:00-15:00 | 0.701 | 0.925 | 9 | 9.0% | ✅ PASS |

**5. Overall Verdict**

Large box at top shows:
```
🟢 RECOMMENDATION VALID
All intervals passed validation (failure_rate ≤ 10%)
Optimization is robust and recommended for deployment.
```

OR

```
🔴 RECOMMENDATION NEEDS REVIEW
Some intervals failed validation.
Consider adding more servers or adjusting costing.
```

**6. What This Means**

**✅ PASS** = Recommendation is robust
- Even with ±20% arrival and ±10% service variability
- System stays stable
- Safe to deploy

**❌ FAIL** = Recommendation may be risky
- Go back to Page 2
- Either add more servers or adjust costing parameters
- Rerun optimization

**✅ Page 4 Complete!**

---

## 💰 Adjusting Costing Parameters

### **Two Ways to Adjust Costs**

#### **Method 1: Sidebar (Permanent for Session)**

Left sidebar → "💰 Costing Parameters"

```
💼 Cost per Cashier (₱/hr)        [slider: 10-500]
⏳ Cost of Customer Wait (₱/hr)   [slider: 10-500]
❌ Cost per Abandonment (₱)       [slider: 10-500]
```

**Summary shows current values**

---

#### **Method 2: Page 2 Local (Quick Preview)**

Page 2 → "⚙️ Configuration & Costing" → "Costing Settings" tab

Same 3 parameters with descriptions

---

### **What Each Parameter Controls**

| Parameter | Symbol | Unit | Formula Component | Impact |
|-----------|--------|------|-------------------|--------|
| **Cost per Cashier** | Cₛ | ₱/hr | Servers × Cₛ × hours | Higher = fewer servers recommended |
| **Cost of Wait** | Cw | ₱/hr | Wq × λ × Cw | Higher = more servers recommended |
| **Cost per Abandon** | Ca | ₱ | λ × 0.10 × Ca | Higher = more servers recommended |

---

### **Costing Formula**

For each time interval:
```
Total Cost = (Servers × Cₛ × 1hr) + (Wq × λ × Cw) + (λ × 0.10 × Ca)
```

---

### **Example Scenarios**

#### **Scenario 1: Budget Mode (Minimize Staff)**
```
Set:
  Cₛ = ₱60/hr (low wage contractor)
  Cw = ₱50/hr (low-value customers)
  Ca = ₱30 (low-basket customers)

Result: FEWER servers recommended, lowest cost
```

#### **Scenario 2: Quality Mode (Best Service)**
```
Set:
  Cₛ = ₱100/hr (full-time employee)
  Cw = ₱150/hr (premium customers)
  Ca = ₱100 (high-basket customers)

Result: MORE servers recommended, best service
```

#### **Scenario 3: Balanced (Default)**
```
Set:
  Cₛ = ₱87/hr (standard)
  Cw = ₱100/hr (standard)
  Ca = ₱60 (standard)

Result: BALANCED optimization
```

---

## 🔧 Troubleshooting

### **Issue 1: Dashboard won't start**

**Error:** "No module named streamlit"

**Solution:**
```powershell
# Reinstall dependencies
pip install -r requirements.txt

# Try again
python -m streamlit run legacy_streamlit/streamlit_app.py
```

---

### **Issue 2: Port 8502 already in use**

**Error:** "Port 8502 already in use"

**Solution:**
```powershell
# Use different port
streamlit run legacy_streamlit/streamlit_app.py --server.port 8503

# Open: http://localhost:8503
```

---

### **Issue 3: File not found**

**Error:** "File does not exist: streamlit_app.py"

**Solution:**
```powershell
# Make sure you're in the correct directory
Get-Location

# Should show:
# C:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main

# If not, navigate to it:
cd "c:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main"
```

---

### **Issue 4: Data upload fails**

**Error:** "Schema validation failed" or "Missing columns"

**Solution:**
```
Make sure your CSV has exactly 9 columns:
1. time_interval
2. arrival_rate
3. service_rate
4. servers
5. utilization
6. Lq
7. Wq
8. Ls
9. Ws

All numeric columns must be numbers (no text like "N/A")
```

---

### **Issue 5: Optimization shows all ∞ (infinity)**

**Cause:** Unstable system (ρ ≥ 1.0)

**Solution:**
```
This means demand > capacity for that time slot
- Increase service_rate (faster service)
- OR Increase servers (more cashiers)
- OR Reduce arrival_rate (not possible, but data quality issue)
```

---

### **Issue 6: Dashboard keeps crashing**

**Error:** Various runtime errors

**Solution:**
```powershell
# Stop dashboard (Ctrl + C in terminal)

# Clear cache
streamlit cache clear

# Restart
python -m streamlit run legacy_streamlit/streamlit_app.py
```

---

## 📋 Examples & Scenarios

### **Complete End-to-End Example**

#### **Scenario: NOVAMART Morning Rush**

**Given:**
- Morning period (6-9 AM): high arrival rate (20+ customers/hr)
- 2 cashiers currently
- Customers waiting >10 minutes on average
- Manager wants to know if adding 1 cashier helps

**Workflow:**

**Step 1: Upload Data (Page 1)**
- Upload `merged_daily_data.csv`
- Click "Save as Current Data"

**Step 2: Optimize (Page 2)**
- Go to Page 2
- **DON'T change costing** (use defaults: ₱87, ₱100, ₱60)
- Click "Run Optimization"
- **Results:**
  ```
  Morning slots (6-9 AM):
    Current: 2 servers, ρ = 0.92
    Recommended: 3 servers, ρ = 0.68
  
  Daily Cost Analysis:
    Current: ₱18,750
    Recommended: ₱15,200
    Savings: ₱3,550/day (18.9%)
  ```

**Step 3: Compare (Page 3)**
- Go to Page 3
- See morning improvement:
  - Wait time: 8.2 min → 2.1 min (74% reduction)
  - Queue length: 2.7 → 0.6 customers
  - Service level: Much better

**Step 4: Validate (Page 4)**
- Go to Page 4
- Run simulation
- Result: ✅ PASS (All intervals < 10% failure)
- **Conclusion:** Adding 1 cashier is SAFE and SAVES ₱3,550/day!

---

### **Example 2: Test Different Staffing Costs**

**Question:** How does recommendation change if we hire cheaper (₱60/hr) vs expensive (₱120/hr) staff?

**Step 1: Test Cheap Option (₱60/hr)**
```
Sidebar: Change "Cost per Cashier" to 60
Go to Page 2: Click "Run Optimization"
Note: Fewer servers recommended, higher wait times
Daily cost: Lower
See savings: Smaller
```

**Step 2: Test Expensive Option (₱120/hr)**
```
Sidebar: Change "Cost per Cashier" to 120
Go to Page 2: Click "Run Optimization"
Note: More servers recommended, shorter wait times
Daily cost: Higher
See savings: Larger (more wait cost reduction)
```

**Step 3: Compare**
```
Cheap (₱60): 2.2 servers avg, ₱11,500 daily cost
Balanced (₱87): 2.7 servers avg, ₱15,200 daily cost
Expensive (₱120): 3.1 servers avg, ₱17,800 daily cost

Decision: Which fits your business model?
```

---

### **Example 3: Customer Value Testing**

**Question:** Does improving wait times justify adding servers?

**Step 1: Current Customer Value (₱100/hr)**
```
Sidebar: Keep "Cost of Customer Wait" at 100

Go to Page 2: Run Optimization
See: Recommendation adds X servers
Daily savings: ₱Y
```

**Step 2: Premium Market (₱150/hr)**
```
Sidebar: Change "Cost of Customer Wait" to 150

Go to Page 2: Run Optimization
See: Optimization recommends MORE servers
Daily savings: HIGHER (more benefit to reducing wait)
Conclusion: High-value customers justify more investment
```

**Step 3: Budget Market (₱50/hr)**
```
Sidebar: Change "Cost of Customer Wait" to 50

Go to Page 2: Run Optimization
See: Fewer servers recommended
Daily savings: LOWER (less benefit to reducing wait)
Conclusion: Budget customers don't justify high staffing
```

---

## 📞 Quick Reference

### **Command to Start:**
```powershell
cd "c:\Users\krizel\Desktop\O.R AKSELS\QUEUING_THEORY_NOVAMART-main\QUEUING_THEORY_NOVAMART-main"; .\.venv\Scripts\python.exe -m streamlit run legacy_streamlit/streamlit_app.py
```

### **Open Dashboard:**
```
http://localhost:8502
```

### **Stop Dashboard:**
```
Ctrl + C (in PowerShell)
```

### **Page Order:**
```
1. Page 1 → Upload & validate
2. Page 2 → Optimize & calculate costs
3. Page 3 → Compare & view savings
4. Page 4 → Simulate & validate
```

### **Key Files:**
```
legacy_streamlit/streamlit_app.py        ← Main entry point
pages/1_current_metrics.py    ← Upload page
pages/2_optimization.py       ← Optimization + costs
pages/3_comparison.py         ← Comparison + savings
pages/4_simulation.py         ← Simulation test
utils.py                ← Helper functions
merged_daily_data.csv   ← Your data
```

---

## ✨ Tips & Best Practices

1. **Always start with Page 1** — Upload your data first
2. **Don't skip steps** — Pages must run in order (1→2→3→4)
3. **Adjust costing for your business** — Use real costs for accurate recommendations
4. **Review Page 3 savings** — Check if the ROI justifies staffing changes
5. **Validate with Page 4** — Ensure recommendations pass simulation
6. **Export results** — Save CSV/Excel for reporting and archiving
7. **Test scenarios** — Try different costing values to understand sensitivity

---

## 🎉 You're Ready!

**Next step:** Start the dashboard and upload your data!

```powershell
.\.venv\Scripts\python.exe -m streamlit run legacy_streamlit/streamlit_app.py
```

Then open: **http://localhost:8502**

---

## 📞 Need Help?

- **Dashboard won't start?** → See Troubleshooting section
- **Data validation error?** → Check column names and data types
- **Unclear results?** → Review Page 3 explanation of what each metric means
- **Want to run again?** → Page 1 allows multiple uploads

**Happy optimizing!** 🚀
