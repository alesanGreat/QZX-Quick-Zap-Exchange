from qzx.commands.system.get_current_date_time import GetCurrentDateTimeCommand


def test_iso_output_is_timezone_aware_and_internally_consistent():
    result = GetCurrentDateTimeCommand().execute("iso")

    assert result["success"] is True
    assert result["output_format"] == "iso"
    assert result["output"] == result["iso_format"]
    assert result["time"]["utc_offset"] in result["iso_format"]
    assert result["timestamp"] > 0


def test_invalid_output_format_returns_a_structured_error():
    result = GetCurrentDateTimeCommand().execute("decorated")

    assert result["success"] is False
    assert result["error_code"] == "invalid_output_format"
    assert result["details"]["supported"] == ["full", "simple", "iso"]
