NovaQ observational queue inputs

Source: RAWR DATA (1).xlsx
SHA256: ee84ebfc5ba4cc1b3a833e381adf24866218c97eb34bb5dd5659667b5238088e

Only week 1 and week 2 customer observations are included. Daily/manual and duplicate personal sheets are excluded. All 1,600 records are retained, including 880 records involved in 683 same-cashier service overlaps. No timings were corrected or invented. This is observational queue data, not POS transaction data.

The CSV is a provisional import file, not validated production data. Lambda = arrivals / 14 hours of exposure per hourly slot, assuming each slot was observed for one full hour on each of 14 days. Mu = 60 / pooled mean service duration in minutes. Staffing c is copied from Avg_total_data_of_14_days.csv and remains an assumption. Weekday labels are supplied; calendar dates are unavailable.

At 11:00-12:00, the assumed two cashiers give utilization above 1. No finite steady-state waiting estimate is justified for that slot under M/M/c assumptions. Timing conflicts, observation coverage, and actual staffing must be confirmed before empirical validation or staffing recommendations. The workbook conflict list is a fixed audit of this source version; regenerate it after source corrections.

Import the CSV using NovaQ's CSV input flow. The source data is not hard-coded into application code and has not been uploaded to the running application.
