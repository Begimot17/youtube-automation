from src.config import Config


def test_config_importable():
    assert Config.PORT > 0
