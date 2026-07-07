"""Trivial smoke test proving the pytest harness is wired up."""


def test_true():
    assert True


async def test_async_true():
    """Proves pytest-asyncio is configured (asyncio_mode = auto)."""
    assert True
