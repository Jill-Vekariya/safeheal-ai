import hashlib
import json
import sqlite3

import pytest

from scripts.controlled_core import encoded
from scripts.reproduce import artifact, audit_events, verify, verify_instrument


def test_inventory_rejects_escape_and_modified_bytes(tmp_path):
    path=tmp_path/"data.txt"; path.write_text("original")
    manifest={"schema_version":"safeheal-reproduction-v1", "cohorts":[],
              "sha256":{"data.txt":hashlib.sha256(path.read_bytes()).hexdigest()}}
    assert verify(tmp_path,manifest)["verified_artifacts"]==1
    path.write_text("changed")
    with pytest.raises(ValueError,match="integrity"):
        verify(tmp_path,manifest)
    for value in ("../data.txt",str(tmp_path/"data.txt"),"folder\\data.txt"):
        with pytest.raises(ValueError):
            artifact(tmp_path,value)


def test_audit_verification_is_read_only_and_detects_changed_chain(tmp_path):
    path=tmp_path/"audit.sqlite3"
    body=encoded({"stage":"verified"}); prior="0"*64
    digest=hashlib.sha256(encoded({"seq":1,"body":body,"previous":prior}).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE audit(seq INTEGER,body TEXT,previous TEXT,hash TEXT)")
        db.execute("INSERT INTO audit VALUES(?,?,?,?)",(1,body,prior,digest))
    before=path.read_bytes()
    assert audit_events(path)==1 and before==path.read_bytes()
    with sqlite3.connect(path) as db:
        db.execute("UPDATE audit SET body=?",(json.dumps({"stage":"invented"}),))
    with pytest.raises(ValueError,match="chain"):
        audit_events(path)


def test_unfinalized_extra_raw_file_is_rejected(tmp_path):
    folder=tmp_path/"run"; folder.mkdir()
    raw=folder/"manifest.json"; raw.write_text(json.dumps({"sha256":{}}))
    extra=folder/"unlisted.json"; extra.write_text("{}")
    manifest={"schema_version":"safeheal-reproduction-v1",
              "cohorts":[{"directory":"run","analysis":"analysis.json"}],
              "sha256":{"run/manifest.json":hashlib.sha256(raw.read_bytes()).hexdigest()}}
    with pytest.raises(ValueError,match="inventory"):
        verify(tmp_path,manifest)


def test_historical_instrument_must_match_declared_protocol_bytes(tmp_path):
    path=tmp_path/"as-run.py"; path.write_text("original instrument")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    entry={"instrument_sources":{"scripts/runner.py":"as-run.py"}}
    plan={"source_sha256":{"scripts/runner.py":digest}}
    inventory={"as-run.py":digest}
    assert verify_instrument(tmp_path,entry,plan,inventory)==1
    path.write_text("later revised instrument")
    with pytest.raises(ValueError,match="instrument"):
        verify_instrument(tmp_path,entry,plan,inventory)
