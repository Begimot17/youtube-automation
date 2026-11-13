from src.utils.auth import extract_token, is_authorized


def test_extract_token():
    assert extract_token({"X-API-Token": " abc "}) == "abc"
    assert extract_token({"Authorization": "Bearer xyz"}) == "xyz"
    assert extract_token({"Authorization": "bearer xyz"}) == "xyz"
    assert extract_token({"Authorization": "Basic xyz"}) == ""
    assert extract_token({}) == ""


def test_open_when_no_token_configured():
    assert is_authorized({}, None)
    assert is_authorized({}, "")


def test_token_required_when_configured():
    assert is_authorized({"X-API-Token": "s3cret"}, "s3cret")
    assert is_authorized({"Authorization": "Bearer s3cret"}, "s3cret")
    assert not is_authorized({}, "s3cret")
    assert not is_authorized({"X-API-Token": "nope"}, "s3cret")
    assert not is_authorized({"X-API-Token": "s3cre"}, "s3cret")
