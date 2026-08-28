from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from version import APP_ID


class SingleInstanceGuard(QObject):
    activation_requested = Signal()

    def __init__(self, server_name: str | None = None, parent=None):
        super().__init__(parent)
        self.server_name = server_name or APP_ID.replace(".", "-")
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept_connections)
        self.is_primary = False

    def acquire(self) -> bool:
        if self._notify_running_instance():
            return False

        QLocalServer.removeServer(self.server_name)
        if self.server.listen(self.server_name):
            self.is_primary = True
            return True

        self._notify_running_instance()
        return False

    def _notify_running_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(250):
            socket.abort()
            return False
        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(250)
        socket.disconnectFromServer()
        return True

    def _accept_connections(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            socket.readAll()
            socket.disconnectFromServer()
            socket.deleteLater()
            self.activation_requested.emit()

    def close(self) -> None:
        if self.server.isListening():
            self.server.close()
        if self.is_primary:
            QLocalServer.removeServer(self.server_name)
        self.is_primary = False
