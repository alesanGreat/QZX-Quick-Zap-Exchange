import json
from datetime import datetime, timezone

from qzx import telemetry, usage_telemetry


class FakeResponse:
    def __init__(self, status=202):
        self.status = status

    def getcode(self):
        return self.status

    def close(self):
        pass


def _prepare_activation_state(path):
    state = telemetry._new_state()
    telemetry._write_state(
        telemetry.telemetry_state_path(state_directory=path),
        state,
    )
    return state


def _join_usage_workers():
    for worker in list(usage_telemetry.threading.enumerate()):
        if worker.name == "qzx-telemetry-usage":
            worker.join(timeout=2)


def _interactive_evidence():
    return {
        "interactive": True,
        "foreground": True,
        "recent_input": True,
    }


def _command_result(command, duration):
    return {
        "success": True,
        "message": "ok",
        "meta": {"command": command, "duration_ms": duration},
    }


def _record_initial_usage_window(tmp_path, opener):
    env = {"QZX_TELEMETRY": "1"}
    for moment, command, duration in [
        (datetime(2026, 1, 1, 12, tzinfo=timezone.utc), "findFiles", 100.0),
        (datetime(2026, 1, 2, 12, tzinfo=timezone.utc), "findFiles", 300.0),
        (datetime(2026, 1, 5, 12, tzinfo=timezone.utc), "diagnoseProject", 800.0),
    ]:
        status = usage_telemetry.record_command_usage_and_schedule(
            "0.2.2.0.10",
            _command_result(command, duration),
            environ=env,
            state_directory=tmp_path,
            opener=opener,
            now=moment,
            interaction_provider=_interactive_evidence,
        )
        assert status["scheduled"] is False
    return env


def _assert_usage_event(event, activation):
    assert event["event"] == "usage_window"
    assert event["installation_id"] == activation["installation_id"]
    assert event["window_start"] == "2026-01-01"
    assert event["window_end"] == "2026-01-10"
    assert event["interaction_evidence"] == {
        "total_invocations": 3,
        "active_days": 3,
        "interactive_invocations": 3,
        "interactive_days": 3,
        "foreground_invocations": 3,
        "foreground_days": 3,
        "foreground_supported_invocations": 3,
        "foreground_supported_days": 3,
        "recent_input_invocations": 3,
        "recent_input_days": 3,
        "recent_input_supported_invocations": 3,
        "recent_input_supported_days": 3,
    }
    by_command = {row["command"]: row for row in event["command_usage"]}
    assert by_command["findFiles"] == {
        "command": "findFiles",
        "count": 2,
        "total_duration_ms": 400.0,
        "max_duration_ms": 300.0,
    }
    assert by_command["diagnoseProject"]["count"] == 1
    assert "getSystemInfo" not in by_command
    encoded = json.dumps(event)
    for forbidden in ("argv", "path", "cwd", "stdout", "terminal_input", "pointer"):
        assert forbidden not in encoded


def test_usage_telemetry_sends_one_closed_aligned_10_day_window(tmp_path):
    activation = _prepare_activation_state(tmp_path)
    requests = []

    def opener(outgoing, timeout):
        requests.append(json.loads(outgoing.data.decode("utf-8")))
        return FakeResponse(202)

    env = _record_initial_usage_window(tmp_path, opener)
    status = usage_telemetry.record_command_usage_and_schedule(
        "0.2.2.0.10",
        _command_result("getSystemInfo", 200.0),
        environ=env,
        state_directory=tmp_path,
        opener=opener,
        now=datetime(2026, 1, 11, 12, tzinfo=timezone.utc),
        interaction_provider=_interactive_evidence,
    )
    assert status == {
        "scheduled": True,
        "window_start": "2026-01-01",
        "window_end": "2026-01-10",
    }
    _join_usage_workers()

    assert len(requests) == 1
    _assert_usage_event(requests[0], activation)
    usage_state = json.loads(
        usage_telemetry._usage_state_path(state_directory=tmp_path).read_text(
            encoding="utf-8"
        )
    )
    assert "2026-01-01" in usage_state["sent_periods"]
    assert set(usage_state["days"]) == {"2026-01-11"}


def test_usage_telemetry_respects_opt_out_without_creating_state(tmp_path):
    _prepare_activation_state(tmp_path)
    status = usage_telemetry.record_command_usage_and_schedule(
        "0.2.2.0.10",
        {"meta": {"command": "findFiles", "duration_ms": 1.0}},
        environ={"QZX_TELEMETRY": "0"},
        state_directory=tmp_path,
    )
    assert status == {"scheduled": False, "reason": "disabled"}
    assert not usage_telemetry._usage_state_path(state_directory=tmp_path).exists()



def test_default_interaction_snapshot_is_coarse_only():
    snapshot = usage_telemetry.interaction_snapshot()

    assert set(snapshot) == {"interactive", "foreground", "recent_input"}
    assert isinstance(snapshot["interactive"], bool)
    assert snapshot["foreground"] in {True, False, None}
    assert snapshot["recent_input"] in {True, False, None}
