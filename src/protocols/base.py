from src.models.target import Target


class DeviceProtocol:
    """
    Abstract protocol for parsing device output and building commands.

    Each supported firmware implements this to translate between the
    app's unified target model and the firmware's serial interface.
    """

    name = "base"
    commands: dict[str, str] = {}

    @staticmethod
    def _to_int(s):
        """Parse an untrusted numeric field (a regex group / token from device output) into an int, or
        None. Device text is untrusted and device_tab calls parse_line with NO try/except, so a naive
        int() would crash the GUI thread on a pathologically long digit run (CPython caps int<-str at
        4300 digits and raises past it). Reject anything longer than a sane channel/RSSI first."""
        if s is None or len(s) > 10:
            return None
        try:
            return int(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_float(s):
        """Like _to_int for a decimal field (e.g. a fractional RSSI). Bounds the length (so float()
        can't build an inf from a huge digit run) and rejects malformed/non-finite values, returning
        None instead of raising ValueError/OverflowError out of parse_line."""
        if s is None or len(s) > 12:
            return None
        try:
            v = float(s)
        except (ValueError, TypeError, OverflowError):
            return None
        if v != v or v in (float("inf"), float("-inf")):   # NaN / +/-inf
            return None
        return v

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
