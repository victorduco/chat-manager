"""Configuration for Telegram bot commands and permissions."""

# Admin user IDs who have access to admin commands
ADMIN_USER_IDS = [
    118497177,  # Add more admin user IDs here
]

# Command definitions
# Format: "command_name": {
#     "command": "/command",
#     "description": "Description of what the command does",
#     "admin_only": bool,
#     "node_prep": "node_name_prep",
#     "node_action": "node_name"
# }

COMMANDS = {
    "show_all_users": {
        "command": "/show_all_users",
        "description": "Show all users from all groups with intro status",
        "admin_only": True,
        "node_prep": "show_all_users_prep",
        "node_action": "show_all_users"
    },
    "set_intro_status": {
        "command": "/set_intro_status",
        "description": "Set intro status for a user (admin only). Usage: /set_intro_status <@username|telegram:ID|ID|all> <done|pending>",
        "admin_only": True,
        "node_prep": "set_intro_status_prep",
        "node_action": "set_intro_status",
    },
    # Legacy commands - can be removed later
    # "clear_context": {
    #     "command": "/clear_context",
    #     "description": "Clear conversation context",
    #     "admin_only": False,
    #     "node_prep": "clear_context_prep",
    #     "node_action": "clear_context"
    # },
    # "show_context": {
    #     "command": "/show_context",
    #     "description": "Show current conversation context",
    #     "admin_only": False,
    #     "node_prep": "show_context_prep",
    #     "node_action": "show_context"
    # },
    # "show_thinking": {
    #     "command": "/show_thinking",
    #     "description": "Show bot's last reasoning process",
    #     "admin_only": False,
    #     "node_prep": "show_thinking_prep",
    #     "node_action": "show_thinking"
    # },
}


def is_admin(user_id: int) -> bool:
    """Check if user has admin privileges."""
    return user_id in ADMIN_USER_IDS


def get_available_commands(user_id: int) -> dict[str, dict]:
    """Get commands available to a specific user."""
    available = {}
    for cmd_name, cmd_config in COMMANDS.items():
        if not cmd_config["admin_only"] or is_admin(user_id):
            available[cmd_name] = cmd_config
    return available


def get_command_mapping() -> dict[str, str]:
    """Get mapping of command strings to prep nodes."""
    return {
        cmd_config["command"]: cmd_config["node_prep"]
        for cmd_config in COMMANDS.values()
    }
