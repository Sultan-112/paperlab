import json

from libs.audit import security_event


def test_audit_record_is_machine_readable_and_has_no_token(caplog):
    with caplog.at_level("WARNING", logger="paperlab.security"):
        security_event("authentication", "denied", transport="http")
    record = json.loads(caplog.records[-1].message)
    assert record["category"] == "security"
    assert record["event"] == "authentication"
    assert record["outcome"] == "denied"
    assert "token" not in caplog.records[-1].message.lower()
