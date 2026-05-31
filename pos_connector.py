"""POS transaction connector for QCU.



Ingests transaction logs from a local CSV file, an S3 URI, or a raw DataFrame
and produces the arrival-rate / service-rate inputs needed by the queueing
dashboard.
"""

from __future__ import annotations

import io
import warnings
from collections.abc import Mapping
from typing import Optional, Union

from log import get_logger

logger = get_logger(__name__)

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

# ──────────────────────────────────────────────────────────────────────────────
# Data ingestion
# ──────────────────────────────────────────────────────────────────────────────

def load_transactions(
    source: str | pd.DataFrame,
) -> pd.DataFrame:
    """Load a transaction log from *source* and return a cleaned DataFrame.

    Parameters
    ----------
    source : str or pd.DataFrame
        One of:

        - A local file path (``.csv``) — read with ``pd.read_csv``.
        - An S3 URI (``s3://bucket/key``) — uses *boto3* (optional dependency).
        - A ``pd.DataFrame`` — passed through unchanged.

    Returns
    -------
    pd.DataFrame
        Columns: ``timestamp`` (datetime), ``lane_id``, ``transaction_duration_sec``.

    Raises
    ------
    FileNotFoundError
        If *source* is a local path that does not exist.
    ValueError
        If required columns are missing or contain invalid values.
    ImportError
        If *source* is an S3 URI and *boto3* is not installed.
    """
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    elif isinstance(source, str) and source.startswith("s3://"):
        try:
            import boto3  # noqa: F811
        except ImportError:
            raise ImportError(
                "boto3 is required to read S3 URIs. "
                "Install it with: pip install boto3"
            )
        s3 = boto3.client("s3")
        bucket, key = source[5:].split("/", 1)
        obj = s3.get_object(Bucket=bucket, Key=key)
        df = pd.read_csv(io.BytesIO(obj["Body"].read()))
    else:
        df = pd.read_csv(source)

    # Normalise column names
    df.columns = df.columns.str.strip().str.lower()

    # Required columns
    for col in ("timestamp", "lane_id", "transaction_duration_sec"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: '{col}'")

    # Parse timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    null_ts = df["timestamp"].isna()
    if null_ts.any():
        raise ValueError(
            f"{null_ts.sum()} row(s) have null or unparseable timestamps."
        )

    # Validate duration
    if (df["transaction_duration_sec"] <= 0).any():
        raise ValueError("transaction_duration_sec must be > 0 for all rows.")

    return df[["timestamp", "lane_id", "transaction_duration_sec"]].reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────────
# Aggregation → lambda / mu / c
# ──────────────────────────────────────────────────────────────────────────────

def compute_lambda_mu(
    df: pd.DataFrame,
    segment_minutes: int = 60,
    lane_col: str = "lane_id",
) -> pd.DataFrame:
    """Aggregate transaction data into time buckets and estimate queueing parameters.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns ``timestamp`` (datetime), ``transaction_duration_sec``,
        and the column identified by *lane_col*.
    segment_minutes : int
        Width of each time bucket in minutes (default 60).
    lane_col : str
        Name of the column that identifies individual lanes / registers.

    Returns
    -------
    pd.DataFrame
        Columns: ``time`` (bucket start as ``"HH:MM"`` string),
        ``lambda`` (arrivals/hour), ``mu`` (service rate/hour), ``c`` (lane count).
    """
    ts = df["timestamp"]
    start = ts.min().floor(f"{segment_minutes}min")
    end = ts.max().ceil(f"{segment_minutes}min")

    buckets = pd.date_range(start=start, end=end, freq=f"{segment_minutes}min", inclusive="left")
    rows: list[dict] = []

    for bucket_start in buckets:
        bucket_end = bucket_start + pd.Timedelta(minutes=segment_minutes)
        mask = (ts >= bucket_start) & (ts < bucket_end)
        bucket_df = df[mask]

        n_transactions = len(bucket_df)
        lambda_ = n_transactions / (segment_minutes / 60.0)  # arrivals per hour
        mu = (
            3600.0 / bucket_df["transaction_duration_sec"].mean()
            if n_transactions > 0
            else 0.0
        )
        c = int(bucket_df[lane_col].nunique())

        rows.append(
            {
                "time": bucket_start.strftime("%H:%M"),
                "lambda": round(lambda_, 4),
                "mu": round(mu, 4) if mu > 0 else 0.0,
                "c": max(c, 1),
            }
        )

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────────
# Export
# ──────────────────────────────────────────────────────────────────────────────

def to_novamart_csv(df: pd.DataFrame, output_path: str | None = None) -> str:
    """Serialise a parameter DataFrame to QCU's expected CSV format.



    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns ``time``, ``lambda``, ``mu``, ``c``.
    output_path : str or None
        If provided, the CSV is written to this file path.  If None, the CSV
        string is returned.

    Returns
    -------
    str
        CSV string (when *output_path* is None).

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    required = {"time", "lambda", "mu", "c"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    out = df[["time", "lambda", "mu", "c"]].to_csv(index=False)

    if output_path is not None:
        with open(output_path, "w", newline="") as fh:
            fh.write(out)

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Statistical tests
# ──────────────────────────────────────────────────────────────────────────────

def test_poisson_arrivals(
    df_transactions: pd.DataFrame,
    segment_minutes: int = 60,
    alpha: float = 0.05,
) -> dict:
    """Test whether transaction arrivals follow a Poisson process.

    Groups transactions into time buckets of *segment_minutes* width, counts
    arrivals per bucket, and runs a chi-squared goodness-of-fit test against
    the Poisson distribution with the observed mean arrival rate.

    Parameters
    ----------
    df_transactions : pd.DataFrame
        Must contain a ``timestamp`` column (datetime).
    segment_minutes : int
        Bucket width in minutes (default 60).
    alpha : float
        Significance level for the chi-squared test (default 0.05).

    Returns
    -------
    dict
        ``is_poisson`` — True if we fail to reject H₀ at the *alpha* level.
        ``chi2_stat`` — Chi-squared test statistic.
        ``p_value`` — P-value of the test.
        ``mean_arrivals`` — Mean arrivals per bucket.
        ``dispersion_index`` — Variance / mean ratio (~1.0 for Poisson).
        ``warning`` — Human-readable warning or None.

    Raises
    ------
    ValueError
        If fewer than 10 buckets can be formed.
    """
    ts = df_transactions["timestamp"]
    start = ts.min().floor(f"{segment_minutes}min")
    end = ts.max().ceil(f"{segment_minutes}min")

    buckets = pd.date_range(start=start, end=end, freq=f"{segment_minutes}min", inclusive="left")

    if len(buckets) < 10:
        raise ValueError(
            f"At least 10 buckets are required for the Poisson test, "
            f"but only {len(buckets)} could be formed. "
            f"Try a smaller *segment_minutes* value or provide more data."
        )

    counts_raw: list[int] = []
    for bucket_start in buckets:
        bucket_end = bucket_start + pd.Timedelta(minutes=segment_minutes)
        mask = (ts >= bucket_start) & (ts < bucket_end)
        counts_raw.append(int(mask.sum()))

    counts = np.array(counts_raw, dtype=float)
    mean_arrivals = float(np.mean(counts))
    dispersion_index = float(np.var(counts, ddof=1) / mean_arrivals) if mean_arrivals > 0 else 0.0

    # Chi-squared goodness-of-fit against Poisson(mean_arrivals)
    # Bin observed counts so each expected bin >= 5
    max_count = int(counts.max()) + 2
    observed_binned, edges = np.histogram(counts, bins=range(0, max_count))

    # Collapse tail bins with expected < 5
    poisson_pmf = sp_stats.poisson.pmf(np.arange(len(edges) - 1), mean_arrivals)
    expected = poisson_pmf * len(counts)

    while len(observed_binned) > 1 and expected[-1] < 5:
        observed_binned[-2] += observed_binned[-1]
        observed_binned = observed_binned[:-1]
        expected[-2] += expected[-1]
        expected = expected[:-1]

    # Drop any remaining bins with expected < 1
    valid = expected >= 1.0
    observed_binned = observed_binned[valid]
    expected = expected[valid]

    # Degrees of freedom: bins - 1 (estimated 1 parameter = mean)
    if len(observed_binned) < 2:
        # Too few bins after collapsing — test is inconclusive
        return {
            "is_poisson": False,
            "chi2_stat": float("nan"),
            "p_value": float("nan"),
            "mean_arrivals": mean_arrivals,
            "dispersion_index": dispersion_index,
            "warning": (
                "Insufficient data variation to perform chi-squared test. "
                "Collect more data or reduce bucket size."
            ),
        }

    chi2_stat, p_value = sp_stats.chisquare(observed_binned, f_exp=expected, ddof=1)
    chi2_stat = float(chi2_stat)
    p_value = float(p_value)
    is_poisson = p_value >= alpha

    warning: str | None = None
    if not is_poisson:
        warning = (
            f"Arrivals deviate significantly from Poisson (p = {p_value:.4f}). "
            f"The dispersion index is {dispersion_index:.2f} "
            f"({'over-dispersed' if dispersion_index > 1.2 else 'under-dispersed'})."
        )
    elif abs(dispersion_index - 1.0) > 0.2:
        warning = (
            f"While the chi-squared test does not reject Poisson (p = {p_value:.4f}), "
            f"the dispersion index ({dispersion_index:.2f}) deviates from 1.0 — "
            "consider whether arrivals are truly homogeneous."
        )

    return {
        "is_poisson": is_poisson,
        "chi2_stat": round(chi2_stat, 4),
        "p_value": round(p_value, 4),
        "mean_arrivals": round(mean_arrivals, 4),
        "dispersion_index": round(dispersion_index, 4),
        "warning": warning,
    }


def fit_service_distribution(
    df_transactions: pd.DataFrame,
) -> dict:
    """Fit an exponential distribution to transaction durations.

    Estimates the MLE rate parameter and performs a Kolmogorov-Smirnov
    goodness-of-fit test against the exponential distribution.

    Parameters
    ----------
    df_transactions : pd.DataFrame
        Must contain a ``transaction_duration_sec`` column.

    Returns
    -------
    dict
        ``mu_mle`` — MLE service rate (customers per hour).
        ``mean_duration_sec`` — Mean service time in seconds.
        ``cv`` — Coefficient of variation (std / mean).
        ``is_exponential`` — Whether the KS test fails to reject exponential (α = 0.05).
        ``ks_stat`` — KS test statistic.
        ``ks_pvalue`` — KS test p-value.
        ``warning`` — Human-readable warning or None.

    Raises
    ------
    ValueError
        If fewer than 30 observations are available.
    """
    durations = df_transactions["transaction_duration_sec"].dropna().values.astype(float)

    if len(durations) < 30:
        raise ValueError(
            f"At least 30 observations are required for service distribution fitting, "
            f"but only {len(durations)} are available."
        )

    mean_dur = float(np.mean(durations))
    std_dur = float(np.std(durations, ddof=1))
    cv = std_dur / mean_dur if mean_dur > 0 else 0.0

    # MLE for Exponential(scale = mean)
    # mu_mle = 1 / mean_dur (in events per second), then convert to per hour
    mu_mle = 3600.0 / mean_dur if mean_dur > 0 else 0.0

    # KS test against exponential with the MLE scale
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ks_stat, ks_pvalue = sp_stats.kstest(
            durations, "expon", args=(0, mean_dur)
        )

    ks_stat = float(ks_stat)
    ks_pvalue = float(ks_pvalue)
    is_exponential = ks_pvalue >= 0.05

    warning: str | None = None
    if not is_exponential:
        warning = (
            f"Service times deviate significantly from exponential (KS p = {ks_pvalue:.4f}). "
            "Consider using a general distribution (M/G/c) in the queueing model."
        )
    elif cv > 1.3:
        warning = (
            f"Coefficient of variation ({cv:.2f}) exceeds 1.3 — service times are "
            "more variable than exponential. M/G/c may yield more accurate results."
        )

    return {
        "mu_mle": round(mu_mle, 4),
        "mean_duration_sec": round(mean_dur, 4),
        "cv": round(cv, 4),
        "is_exponential": is_exponential,
        "ks_stat": round(ks_stat, 4),
        "ks_pvalue": round(ks_pvalue, 4),
        "warning": warning,
    }
