from executor.registry import CAPABILITIES


def test_registered_capability_categories() -> None:
    assert CAPABILITIES["bas.list_capabilities"].category == "read_only"
    command = CAPABILITIES["bas.list_capabilities"].command({}, {}, "/tmp")
    assert command is not None
    assert '"shell.execute"' in command[-1]
    assert CAPABILITIES["shell.execute"].category == "remote_execution"
    assert CAPABILITIES["nxc.smb_discover"].category == "active_scan"
    assert CAPABILITIES["caldera.launch_operation"].category == "adversary_emulation"
    assert CAPABILITIES["caldera.get_operation_report"].category == "read_only"
    assert CAPABILITIES["bloodhound.cypher_query"].category == "read_only"
