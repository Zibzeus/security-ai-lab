from dataclasses import dataclass
from typing import Any, Callable


CommandBuilder = Callable[[dict[str, Any], dict[str, str], str], list[str]]


@dataclass(frozen=True)
class Capability:
    name: str
    category: str
    timeout: int
    command: CommandBuilder | None = None
    api_action: str | None = None


def nxc(protocol: str) -> CommandBuilder:
    def build(args: dict[str, Any], secrets: dict[str, str], output: str) -> list[str]:
        return ["nxc", protocol, str(args["target"]), "--log", f"{output}/nxc.log"]

    return build


def certipy_find(
    args: dict[str, Any], secrets: dict[str, str], output: str
) -> list[str]:
    credential = secrets[str(args["credential_ref"])]
    return [
        "certipy",
        "find",
        "-u",
        str(args["username"]),
        "-p",
        credential,
        "-dc-ip",
        str(args["dc_ip"]),
        "-target",
        str(args["target"]),
        "-json",
        "-output",
        f"{output}/certipy",
    ]


CAPABILITIES = {
    item.name: item
    for item in [
        Capability(
            "bas.list_capabilities",
            "read_only",
            30,
            api_action="list_capabilities",
        ),
        Capability("nxc.smb_discover", "active_scan", 300, nxc("smb")),
        Capability("nxc.ldap_discover", "active_scan", 300, nxc("ldap")),
        Capability("certipy.find", "authenticated_enumeration", 600, certipy_find),
        Capability("caldera.list_agents", "read_only", 60, api_action="list_agents"),
        Capability(
            "caldera.list_adversaries", "read_only", 60, api_action="list_adversaries"
        ),
        Capability(
            "caldera.list_operations", "read_only", 60, api_action="list_operations"
        ),
        Capability(
            "caldera.get_operation", "read_only", 60, api_action="get_operation"
        ),
        Capability(
            "caldera.get_operation_report",
            "read_only",
            120,
            api_action="get_operation_report",
        ),
        Capability(
            "caldera.get_operation_event_logs",
            "read_only",
            120,
            api_action="get_operation_event_logs",
        ),
        Capability(
            "caldera.launch_operation",
            "adversary_emulation",
            60,
            api_action="launch_operation",
        ),
        Capability(
            "bloodhound.cypher_query",
            "read_only",
            120,
            api_action="bloodhound_cypher_query",
        ),
        Capability(
            "shell.execute",
            "remote_execution",
            900,
            api_action="shell_execute",
        ),
    ]
}
