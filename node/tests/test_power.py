from grid_node import power as power_mod


def test_estimate_watts_zero_cpu_is_idle():
    assert power_mod.estimate_watts(0, idle_watts=40.0, max_watts=150.0) == 40.0


def test_estimate_watts_full_cpu_is_max():
    assert power_mod.estimate_watts(100, idle_watts=40.0, max_watts=150.0) == 150.0


def test_estimate_watts_midpoint():
    assert power_mod.estimate_watts(50, idle_watts=40.0, max_watts=150.0) == 95.0


def test_estimate_watts_none_cpu_percent_is_none():
    assert power_mod.estimate_watts(None, idle_watts=40.0, max_watts=150.0) is None


def test_estimate_watts_clamps_above_100():
    assert power_mod.estimate_watts(150, idle_watts=40.0, max_watts=150.0) == 150.0


def test_estimate_watts_clamps_below_0():
    assert power_mod.estimate_watts(-10, idle_watts=40.0, max_watts=150.0) == 40.0
