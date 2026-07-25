import json
import platform
import uuid

from qzx import telemetry


class FakeResponse:
    def __init__(self, status=202):
        self.status = status
        self.closed = False

    def getcode(self):
        return self.status

    def close(self):
        self.closed = True


def test_telemetry_can_be_disabled_explicitly(tmp_path):
    status = telemetry.schedule_version_telemetry(
        "0.2.3",
        environ={"QZX_TELEMETRY": "0"},
        state_directory=tmp_path,
    )

    assert status["success"] is True
    assert status["details"] == {"scheduled": False, "reason": "disabled"}
    assert not telemetry.telemetry_state_path(state_directory=tmp_path).exists()


def test_telemetry_honours_do_not_track(tmp_path):
    status = telemetry.schedule_version_telemetry(
        "0.2.3",
        environ={"DO_NOT_TRACK": "1"},
        state_directory=tmp_path,
    )

    assert status["details"]["reason"] == "disabled"


def test_payload_contains_only_the_documented_real_environment_allow_list():
    event = telemetry.build_event(
        "0.2.3",
        "9c148b7f-93fb-45d2-ae22-34e017d27e39",
        "98412369-135d-4dce-9440-605139e5296e",
        environ={"CI": "true"},
    )

    assert set(event) == {
        "schema_version",
        "event",
        "event_id",
        "installation_id",
        "qzx_version",
        "python_version",
        "python_implementation",
        "os_name",
        "os_release",
        "os_kernel",
        "architecture",
        "virtual_environment",
        "ci",
    }
    assert event == {
        "schema_version": 1,
        "event": "version_first_run",
        "event_id": "98412369-135d-4dce-9440-605139e5296e",
        "installation_id": "9c148b7f-93fb-45d2-ae22-34e017d27e39",
        "qzx_version": "0.2.3",
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "os_name": telemetry._normalise_os_name(platform.system()),
        "os_release": telemetry._os_details()[1],
        "os_kernel": telemetry._os_details()[2],
        "architecture": platform.machine() or "unknown",
        "virtual_environment": telemetry._is_virtual_environment(),
        "ci": True,
    }
    assert "username" not in event
    assert "hostname" not in event
    assert "argv" not in event
    assert "cwd" not in event


def test_successful_event_is_sent_once_per_version(tmp_path):
    requests = []

    def opener(outgoing, timeout):
        requests.append(
            {
                "payload": json.loads(outgoing.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        return FakeResponse(202)

    first = telemetry.schedule_version_telemetry(
        "0.2.3",
        environ={"QZX_TELEMETRY": "1"},
        state_directory=tmp_path,
        opener=opener,
    )
    # The fake transport completes immediately, so joining all named workers
    # keeps this test deterministic without exposing thread internals.
    for worker in list(telemetry.threading.enumerate()):
        if worker.name == "qzx-telemetry":
            worker.join(timeout=2)

    second = telemetry.schedule_version_telemetry(
        "0.2.3",
        environ={"QZX_TELEMETRY": "1"},
        state_directory=tmp_path,
        opener=opener,
    )

    assert first["details"]["scheduled"] is True
    assert first["details"]["notice"] is True
    assert second["details"] == {
        "scheduled": False,
        "reason": "already_sent",
    }
    assert len(requests) == 1
    uuid.UUID(requests[0]["payload"]["installation_id"])
    uuid.UUID(requests[0]["payload"]["event_id"])


def test_failed_delivery_reuses_event_and_installation_ids(tmp_path):
    state_path = telemetry.telemetry_state_path(state_directory=tmp_path)
    state = telemetry._new_state()
    event_id = str(uuid.uuid4())
    state["pending_versions"]["0.2.3"] = event_id
    telemetry._write_state(state_path, state)
    event = telemetry.build_event(
        "0.2.3",
        state["installation_id"],
        event_id,
        environ={},
    )

    result = telemetry.send_event(
        event,
        state_path,
        opener=lambda outgoing, timeout: FakeResponse(503),
    )
    reloaded = telemetry._load_state(state_path)

    assert result["success"] is False
    assert reloaded["installation_id"] == state["installation_id"]
    assert reloaded["pending_versions"]["0.2.3"] == event_id
    assert "0.2.3" not in reloaded["sent_versions"]
