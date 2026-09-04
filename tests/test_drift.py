"""Drift detection tests — temp SQLite DBs, no network."""

from model_regression_detection.eval import drift_status, init_db, recent_live_rates


def _seed(db_path, rates, mocked_flags=None):
    conn = init_db(db_path)
    for i, rate in enumerate(rates):
        mocked = (mocked_flags or [0] * len(rates))[i]
        conn.execute(
            "INSERT INTO runs(ts,prompt_version,model,pass_rate,total,passed,regression,mocked)"
            " VALUES(?,?,?,?,?,?,?,?)",
            ("ts", "v1", "m", rate, 30, int(rate * 30), 0, mocked),
        )
    conn.commit()
    return conn


def test_drift_fires_below_threshold(tmp_path):
    conn = _seed(tmp_path / "t.db", [0.85] * 7)
    rates = recent_live_rates(conn, 7)
    drift, avg, n = drift_status(rates, 7, 0.90)
    assert (drift, round(avg, 3), n) == (True, 0.85, 7)
    conn.close()


def test_no_drift_above_threshold(tmp_path):
    conn = _seed(tmp_path / "t.db", [1.0, 0.97, 1.0, 0.93, 1.0, 0.97, 1.0])
    rates = recent_live_rates(conn, 7)
    drift, avg, n = drift_status(rates, 7, 0.90)
    assert drift is False and n == 7 and avg > 0.90
    conn.close()


def test_warming_up_until_window_full(tmp_path):
    conn = _seed(tmp_path / "t.db", [0.5, 0.5, 0.5])
    rates = recent_live_rates(conn, 7)
    drift, avg, n = drift_status(rates, 7, 0.90)
    assert (drift, avg, n) == (False, None, 3)
    conn.close()


def test_mocked_runs_excluded(tmp_path):
    conn = _seed(tmp_path / "t.db", [0.5] * 7, mocked_flags=[1] * 7)
    assert recent_live_rates(conn, 7) == []
    conn.close()


def test_migration_adds_mocked_column(tmp_path):
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE runs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, prompt_version TEXT,"
        " model TEXT, pass_rate REAL, total INTEGER, passed INTEGER, regression INTEGER)"
    )
    conn.commit()
    conn.close()
    conn = init_db(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()]
    assert "mocked" in cols
    conn.close()
