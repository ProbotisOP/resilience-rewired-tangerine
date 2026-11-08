"""
Tests for the 6-month overdraft-risk service.
"""
 
import math
 
import numpy as np
import pandas as pd
import pytest
 
from src.data.local_repository import LocalDataRepository
from overdraft_risk.service import (
    compute_features,
    format_probability,
    get_overdraft_risk,
    load_model,
    predict_probability,
)
 
 
def _monthly(n=8):
    return pd.DataFrame({
        "account_id": [99999] * n,
        "month": [f"2025-{i:02d}" for i in range(1, n + 1)],
        "money_in": [1000.0] * n,
        "money_out": [800, 900, 1000, 1200, 1100, 1300, 1400, 5000][:n],
        "cash_withdrawals_genuine": [400.0] * n,
        "loan_payments": [100.0] * n,
        "min_balance": [500, 400, 300, 200, -50, 100, 150, 99999][:n],
        "avg_daily_balance": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 99999][:n],
        "days_below_zero": [0, 0, 0, 0, 2, 0, 0, 0][:n],
    })
 
 
def test_format_probability():
    assert format_probability(0.303549) == "30.35%"
    assert format_probability(0.0) == "0.00%"
    assert format_probability(1.0) == "100.00%"
 
 
def test_artifact_is_consistent():
    model = load_model()
    k = len(model["features"])
    assert k == 12
    for key in ("impute_median", "scaler_mean", "scaler_scale", "coef"):
        assert len(model[key]) == k
    assert model["horizon_months"] == 6
    assert model["training_cutoffs"][-1] == "2024-06"
 
 
def test_prediction_at_training_mean_equals_sigmoid_of_intercept():
    model = load_model()
    features = dict(zip(model["features"], model["scaler_mean"]))
    expected = 1 / (1 + math.exp(-model["intercept"]))
    assert predict_probability(features, model) == pytest.approx(expected)
 
 
def test_missing_values_use_training_median():
    model = load_model()
    with_nan = dict(zip(model["features"], model["scaler_mean"]))
    with_median = dict(with_nan)
    with_nan["cash_wd_share"] = float("nan")
    with_median["cash_wd_share"] = model["impute_median"][model["features"].index("cash_wd_share")]
    assert predict_probability(with_nan, model) == pytest.approx(predict_probability(with_median, model))
 
 
def test_compute_features_uses_only_months_up_to_as_of():
    # As of 2025-07 the window is 2025-02..2025-07; the extreme 2025-08 row must not change anything.
    args = dict(n_clients=2, standing_order_total=300.0, penalty_months=np.array([], dtype=np.int64))
    with_future = compute_features(_monthly(8), pd.Period("2025-07", "M"), **args)
    without_future = compute_features(_monthly(7), pd.Period("2025-07", "M"), **args)
    assert with_future == pytest.approx(without_future)
 
 
def test_compute_features_hand_values():
    f = compute_features(_monthly(), pd.Period("2025-07", "M"), n_clients=2,
                         standing_order_total=300.0, penalty_months=np.array([], dtype=np.int64))
    out = np.array([900, 1000, 1200, 1100, 1300, 1400], dtype=float)
    avg_out = out.mean()
    buffer = np.mean([1100, 1200, 1300, 1400, 1500, 1600])
    assert f["outflow_months_share"] == pytest.approx(4 / 6)
    assert f["neg_months_win"] == 1.0                                 # 2025-05: days_below_zero 2, min_balance -50
    assert f["min_bal_to_out"] == pytest.approx(-50 / avg_out)
    assert f["buffer_months"] == pytest.approx(buffer / avg_out)
    assert f["log_buffer6"] == pytest.approx(np.log1p(buffer))
    assert f["spend_trend"] == pytest.approx(np.log1p(np.mean([1100, 1300, 1400])) - np.log1p(np.mean([900, 1000, 1200])))
    assert f["cash_wd_share"] == pytest.approx(2400 / out.sum())
    assert f["loanpay_to_in"] == pytest.approx(600 / 6000)
    assert f["so_to_in"] == pytest.approx(300 / 1000, rel=1e-6)
    assert f["joint"] == 1.0
    assert f["penalty_hist"] == 0.0
 
 
def test_penalty_history_respects_as_of():
    pen = np.array([pd.Period("2025-08", "M").ordinal])
    before = compute_features(_monthly(), pd.Period("2025-07", "M"), 1, 0.0, pen)
    after = compute_features(_monthly(), pd.Period("2025-08", "M"), 1, 0.0, pen)
    assert before["penalty_hist"] == 0.0
    assert after["penalty_hist"] == 1.0
 
 
def test_insufficient_history_raises():
    with pytest.raises(ValueError):
        compute_features(_monthly(), pd.Period("2025-05", "M"), 1, 0.0, np.array([], dtype=np.int64))
 
 
def test_real_account_output_format():
    repo = LocalDataRepository.get_instance()
    result = get_overdraft_risk(20111, repo)
    assert result is not None
    assert result.horizon_months == 6
    assert result.display.endswith("%")
    assert 0.0 <= result.probability_pct <= 100.0
    assert result.display == f"{result.probability_pct:.2f}%"
    assert get_overdraft_risk(1, repo) is None
 
 
def test_service_matches_training_feature_builder():
    """The per-account service must reproduce the batch features the model was trained on."""
    from overdraft_risk.training.features import build, load
 
    model = load_model()
    names = model["features"]
    d = load()
    cut = pd.Series(pd.Period("2024-06", "M"), index=d["ms"]["account_id"].unique(), name="cut")
    cut.index.name = "account_id"
    batch, _ = build(d, cut, min_hist=6, win=6)
    batch = batch.set_index("account_id")
    repo = LocalDataRepository.get_instance()
    for account_id in batch.index[:: max(1, len(batch) // 50)]:
        result = get_overdraft_risk(int(account_id), repo, as_of="2024-06")
        expected = batch.loc[account_id, names].astype(float).to_numpy()
        actual = np.array([result.features[n] for n in names])
        np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-9, equal_nan=True)
        assert result.probability_pct == round(predict_probability(dict(zip(names, expected)), model) * 100, 2)
