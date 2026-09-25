"""SystemDoctor public facade composed from focused internal mixins."""

from qzx.core.command_base import CommandBase
from qzx.commands.system._system_doctor_core import SystemDoctorCoreMixin
from qzx.commands.system._system_doctor_environment import SystemDoctorEnvironmentMixin
from qzx.commands.system._system_doctor_extended import SystemDoctorExtendedMixin
from qzx.commands.system._system_doctor_resources import SystemDoctorResourcesMixin

class SystemDoctorCommand(
    SystemDoctorCoreMixin,
    SystemDoctorResourcesMixin,
    SystemDoctorEnvironmentMixin,
    SystemDoctorExtendedMixin,
    CommandBase,
):
    """
    Command to run a comprehensive diagnostic of the host operating system.
    """

    name = "systemDoctor"
    description = "Performs a complete diagnostic of the CPU, RAM, disks, network, PATH, services, ports, and system errors"
    category = "system"

    parameters = [
        {
            "name": "quick",
            "description": "If True, perform only a quick essential system check (default: False)",
            "required": False,
            "default": False,
        }
    ]

    examples = [
        {"command": "qzx systemDoctor", "description": "Run full system diagnostic"},
        {
            "command": "qzx systemDoctor --quick True",
            "description": "Run quick essential check",
        },
    ]
