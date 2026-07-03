from PyQt5.QtCore import QObject, QThread, pyqtSignal


class SerialReaderThread(QThread):
    """Background thread that continuously reads from a serial port."""

    data_received = pyqtSignal(str, str)  # (port, data)

    def __init__(self, port, connection):
        super().__init__()
        self.port = port
        self.connection = connection
        self._running = True

    def run(self):
        while self._running and self.connection.is_open:
            try:
                if self.connection.in_waiting:
                    raw = self.connection.read(self.connection.in_waiting)
                    text = raw.decode(errors="replace")
                    self.data_received.emit(self.port, text)
                else:
                    self.msleep(50)
            except Exception:
                break

    def stop(self):
        self._running = False
        self.wait(2000)


class SerialHandler(QObject):
    """Manages per-device reader threads and dispatches data."""

    line_received = pyqtSignal(str, str)  # (port, line)

    # A device that streams without newlines (raw binary chatter, a wedged board spewing bytes) would
    # otherwise grow the per-port line buffer without bound. Flush an over-long partial line as its own
    # line so the bytes still reach consumers and memory stays bounded.
    _MAX_LINE_BUFFER = 65536

    def __init__(self):
        super().__init__()
        self._readers: dict[str, SerialReaderThread] = {}
        self._buffers: dict[str, str] = {}

    def start_reading(self, port, connection):
        existing = self._readers.get(port)
        if existing is not None:
            if existing.isRunning():
                return  # a live reader already owns this port
            # A previous reader exited (e.g. on disconnect) but was never
            # unregistered; drop it so a fresh reader can attach on reconnect.
            self._readers.pop(port, None)
            self._buffers.pop(port, None)
        reader = SerialReaderThread(port, connection)
        reader.data_received.connect(self._on_data)
        self._readers[port] = reader
        self._buffers[port] = ""
        reader.start()

    def stop_reading(self, port):
        reader = self._readers.pop(port, None)
        if reader:
            reader.stop()
        self._buffers.pop(port, None)

    def stop_all(self):
        for port in list(self._readers.keys()):
            self.stop_reading(port)

    def _on_data(self, port, data):
        buf = self._buffers.get(port, "") + data
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            self.line_received.emit(port, line.strip())
        if len(buf) > self._MAX_LINE_BUFFER:
            # No newline in a very long run of bytes — flush it rather than buffer forever.
            self.line_received.emit(port, buf.strip())
            buf = ""
        self._buffers[port] = buf
