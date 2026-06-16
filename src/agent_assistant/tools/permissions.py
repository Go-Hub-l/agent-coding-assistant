"""Tool permission definitions — code constants mapping roles to allowed tools."""

from agent_assistant.pipeline.agent import AgentRole

# Permission maps: which tools each agent role can use.
# These are code constants — changed only through code releases.
TOOL_PERMISSIONS: dict[AgentRole, set[str]] = {
    AgentRole.PM: {
        "read_file",
        "list_directory",
    },
    AgentRole.ARCHITECT: {
        "read_file",
        "list_directory",
    },
    AgentRole.CODER: {
        "read_file",
        "write_file",
        "list_directory",
    },
    AgentRole.REVIEWER: {
        "read_file",
        "list_directory",
    },
    AgentRole.TESTER: {
        "read_file",
        "list_directory",
        "run_test",
    },
}


def get_tools_for_role(role: AgentRole) -> set[str]:
    """Get the set of tool names permitted for a given agent role."""
    return TOOL_PERMISSIONS.get(role, set())
