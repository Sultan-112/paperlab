from collections import deque

import pytest

from libs.config import Settings
from services.runtime import Runtime


def test_public_live_requires_explicit_rights_and_admin_secret():
    with pytest.raises(ValueError, match="APP_TOKEN"):
        Settings(mode="replay", token="", public_demo=True)
    with pytest.raises(ValueError, match="redistribution"):
        Settings(mode="live", token="private", public_demo=True)
    Settings(mode="replay", token="private", public_demo=True, public_demo_loop=True)
    Settings(mode="live", token="private", public_demo=True, public_live_data_allowed=True)
    with pytest.raises(ValueError, match="PUBLIC_DEMO_LOOP"):
        Settings(mode="replay", token="private", public_demo_loop=True)


def test_synthetic_demo_rewind_discards_old_observations():
    engine = Runtime()
    engine.replay_rows = [{"timestamp": "1700000000"}, {"timestamp": "1700003600"}]
    engine.cursor = 2
    engine.replay_clock = 1700003601
    engine.quotes["US:AAPL"] = {"price": 100}
    engine.history["US:AAPL"] = deque([100], maxlen=20)
    engine.decisions["US:AAPL"] = {"action": "BUY"}
    engine.rewind_public_demo()
    assert engine.cursor == 0
    assert engine.replay_clock == 1700000000
    assert not engine.quotes and not engine.history and not engine.decisions
    assert engine.replay_cycles == 1
