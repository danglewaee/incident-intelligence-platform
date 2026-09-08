from __future__ import annotations

from typing import Any


def infer_iforest_anomaly(history_rows: list[tuple[Any, ...]], candidate_row: tuple[Any, ...]) -> float | None:
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except Exception:
        return None

    if len(history_rows) < 40:
        return None

    def _to_vec(row: tuple[Any, ...]) -> list[float]:
        latency, level, metric_val, has_deploy = row
        is_error = 1.0 if str(level) in {"error", "critical"} else 0.0
        return [
            float(latency or 0.0),
            is_error,
            float(metric_val or 0.0),
            float(has_deploy or 0.0),
        ]

    X_hist = np.array([_to_vec(row) for row in history_rows], dtype=float)
    x_new = np.array([_to_vec(candidate_row)], dtype=float)

    try:
        model = IsolationForest(contamination=0.08, random_state=42)
        model.fit(X_hist)
        pred = model.predict(x_new)[0]
        if pred != -1:
            return None

        scores = model.decision_function(x_new)
        # Lower decision score means more anomalous; invert to positive anomaly score.
        anomaly_score = max(0.0, float(-scores[0]))
        return anomaly_score
    except Exception:
        return None
