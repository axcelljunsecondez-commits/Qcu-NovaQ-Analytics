"""Tests for the POS connector robustness guards."""

import pandas as pd
import pytest

from backend.queueing_engine.statistics.pos_connector import (
    compute_lambda_mu,
    load_transactions,
    to_novamart_csv,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-08-01 09:00", "2026-08-01 09:05", "2026-08-01 09:10"]
            ),
            "lane_id": ["A", "A", "B"],
            "transaction_duration_sec": [45.0, 60.0, 30.0],
        }
    )


class TestLoadTransactions:
    def test_empty_dataframe_raises(self):
        df = _sample_df().iloc[0:0]
        with pytest.raises(ValueError, match="transaction rows"):
            load_transactions(df)

    def test_nan_duration_raises(self):
        df = _sample_df()
        df.loc[1, "transaction_duration_sec"] = float("nan")
        with pytest.raises(ValueError, match="duration"):
            load_transactions(df)

    def test_nan_lane_id_raises(self):
        df = _sample_df()
        df.loc[1, "lane_id"] = None
        with pytest.raises(ValueError, match="lane"):
            load_transactions(df)


class TestComputeLambdaMu:
    def test_empty_dataframe_raises(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime([]),
                "lane_id": [],
                "transaction_duration_sec": [],
            }
        )
        with pytest.raises(ValueError, match="transaction rows"):
            compute_lambda_mu(df)

    def test_missing_lane_col_raises(self):
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-08-01 09:00"]),
                "transaction_duration_sec": [45.0],
            }
        )
        with pytest.raises(ValueError, match="lane"):
            compute_lambda_mu(df, lane_col="register_id")


class TestToNovamartCsv:
    def test_keeps_variance_and_k_when_present(self):
        df = pd.DataFrame(
            {
                "time": ["09:00"],
                "lambda": [10.0],
                "mu": [12.0],
                "c": [2],
                "variance": [0.5],
                "K": [20],
            }
        )
        out = to_novamart_csv(df)
        assert "variance" in out
        assert ",K" in out
        assert "0.5" in out
