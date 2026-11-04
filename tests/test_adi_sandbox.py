import pytest

from scripts.adi_sandbox import check_identity

GOOD = {"Account": "952337755619", "Arn": "arn:aws:sts::952337755619:assumed-role/WSParticipantRole/i-test"}
CFG = {"region": "us-west-2", "archive_uri": "file://./archive", "local_archive_uri": "file://./archive"}


def test_guard_accepts_workshop_and_refuses_wrong_identity(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    check_identity(GOOD, CFG)
    with pytest.raises(ValueError):
        check_identity({**GOOD, "Account": "000000000000"}, CFG)
    with pytest.raises(ValueError):
        check_identity({**GOOD, "Arn": "arn:aws:iam::952337755619:user/personal"}, CFG)


def test_guard_refuses_inherited_resources_and_profile(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for extra in [
        {"region": "us-east-1"},
        {"archive_uri": "s3://miguel"},
        {"lgnd_secret_id": "arn:aws:secretsmanager:us-west-2:892605951158:secret:other"},
    ]:
        with pytest.raises(ValueError):
            check_identity(GOOD, {**CFG, **extra})
    monkeypatch.setenv("AWS_PROFILE", "personal")
    with pytest.raises(ValueError):
        check_identity(GOOD, CFG)
