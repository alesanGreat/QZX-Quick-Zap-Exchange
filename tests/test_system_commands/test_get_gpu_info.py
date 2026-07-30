from types import SimpleNamespace

from qzx.commands.system.get_gpu_info import GetGpuInfoCommand


def test_linux_inventory_avoids_shell_and_filters_gpu_controllers():
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "0000:00:02.0 VGA compatible controller: "
                "Intel Corporation Graphics [8086:1234]\n"
                "0000:00:1f.3 Audio device: Intel Corporation Audio\n"
                "0000:03:00.0 3D controller: "
                "NVIDIA Corporation Device [10de:5678]\n"
            ),
            stderr="",
        )

    command = GetGpuInfoCommand(
        runner=fake_run,
        path_lookup=lambda name: f"/tools/{name}" if name == "lspci" else None,
        system_name="Linux",
    )

    result = command.execute()

    assert result["success"] is True
    assert result["gpu_count"] == 2
    assert result["detected_vendors"] == ["Intel", "NVIDIA"]
    assert calls == [
        (
            ["/tools/lspci", "-D", "-nn"],
            {
                "capture_output": True,
                "text": True,
                "check": False,
                "timeout": 15,
                "errors": "replace",
            },
        )
    ]


def test_windows_inventory_uses_cim_and_normalizes_memory():
    def fake_run(arguments, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '{"Name":"AMD Radeon RX","AdapterCompatibility":"AMD",'
                '"AdapterRAM":8589934592,"DriverVersion":"1.2.3",'
                '"VideoProcessor":"Radeon"}'
            ),
            stderr="",
        )

    command = GetGpuInfoCommand(
        runner=fake_run,
        path_lookup=lambda name: "powershell.exe"
        if name == "powershell"
        else None,
        system_name="Windows",
    )

    result = command.execute(detailed=True)

    assert result["success"] is True
    assert result["detected_vendors"] == ["AMD"]
    assert result["gpus"][0]["memory"] == {
        "total_bytes": 8589934592,
        "total_readable": "8.00 GiB",
    }
    assert result["details"]["sources"] == ["Win32_VideoController"]


def test_unavailable_inventory_is_structured_without_stdout_side_effects():
    command = GetGpuInfoCommand(
        path_lookup=lambda _name: None,
        system_name="Linux",
    )

    result = command.execute()

    assert result["success"] is True
    assert result["gpu_count"] == 0
    assert result["warnings"][0]["code"] == "lspci_unavailable"


def test_invalid_detailed_value_fails_closed():
    result = GetGpuInfoCommand(system_name="Linux").execute("sometimes")

    assert result["success"] is False
    assert result["error_code"] == "invalid_detailed"
