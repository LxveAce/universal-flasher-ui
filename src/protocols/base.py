from src.models.target import Target


class DeviceProtocol:
    """
    Abstract protocol for parsing device output and building commands.

    Each supported firmware implements this to translate between the
    app's unified target model and the firmware's serial interface.
    """

    name = "base"
    commands: dict[str, str] = {}

    def parse_line(self, line: str, source_port: str) -> Target | None:
        """Parse a serial output line into a Target, or None if not a discovery."""
        return None

    def build_command(self, action: str, target: Target = None) -> str:
        """Build a serial command string for an action, optionally targeting a specific target."""
        return action

    def get_scan_command(self) -> str:
        """Return the command to start scanning/discovering."""
        return ""

    def get_stop_command(self) -> str:
        """Return the command to stop current operation."""
        return ""

    def list_commands(self) -> dict[str, str]:
        """Return available commands with descriptions."""
        return self.commands
