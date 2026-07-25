#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-platform tests for system-service discovery."""

from qzx.commands.system.list_system_services import ListSystemServicesCommand


def test_execute_lists_services_from_the_real_service_manager():
    result = ListSystemServicesCommand().execute()

    assert result["success"] is True, result
    assert result["service_manager"]
    assert result["status_filter"] == "all"
    assert result["total_services"] > 0
    assert result["total_services"] == len(result["services"])
    assert isinstance(result["errors"], list)
    for service in result["services"]:
        assert service["name"]
        assert service["status"] in {"running", "stopped"}


def test_running_filter_is_applied_to_real_services():
    result = ListSystemServicesCommand().execute(status="running")

    assert result["success"] is True, result
    assert result["status_filter"] == "running"
    assert all(service["status"] == "running" for service in result["services"])
