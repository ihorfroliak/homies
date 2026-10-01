"""A TCP proxy in front of a test PostgreSQL that a test can stop or freeze.

Shared by the readiness (PR-001R F11) and database-deadline (PR-003) fault
suites. *Stop*: connections refused and reset. *Freeze*: connections still
accepted and bytes still acknowledged by the kernel, but nothing forwarded —
what a paused container or a stalled server looks like to a client.
"""

import socket
import threading
import time

from sqlalchemy.engine import make_url

# PostgreSQL ReadyForQuery, status idle: 'Z', length 5, 'I'. Seen once the
# startup/authentication exchange is complete.
READY_FOR_QUERY = b"Z\x00\x00\x00\x05I"


class FreezableProxy:
    def __init__(self, upstream: tuple[str, int], database_url: str):
        self.upstream = upstream
        self.database_url = database_url
        # freeze_on: freeze everything at the first client bytes that contain
        # this marker (e.g. b"COMMIT") — after the server received nothing of it.
        self.freeze_on: bytes | None = None
        self.frozen_on_marker = threading.Event()
        self.running = threading.Event()
        self.running.set()  # cleared = frozen
        self.stopped = False
        # freeze_after_ready: freeze everything at the first client bytes sent
        # on a connection whose handshake has completed (i.e. the query).
        self.freeze_after_ready = False
        self.frozen_mid_query = threading.Event()
        self.sockets: list[socket.socket] = []
        self.lock = threading.Lock()
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(64)
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _track(self, *socks):
        with self.lock:
            self.sockets.extend(socks)

    def _accept(self):
        # Polling accept: on Linux, closing a listener does not wake a thread
        # blocked in accept(), and the socket would keep accepting.
        self.listener.settimeout(0.1)
        while not self.stopped:
            try:
                client, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            client.settimeout(None)
            try:
                upstream = socket.create_connection(self.upstream, timeout=5)
                upstream.settimeout(None)
            except OSError:
                client.close()
                continue
            self._track(client, upstream)
            state = {"ready": False}
            for src, dst, direction in ((client, upstream, "c2s"), (upstream, client, "s2c")):
                threading.Thread(target=self._pump, args=(src, dst, state, direction),
                                 daemon=True).start()

    def _pump(self, src, dst, state, direction):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                if direction == "s2c" and READY_FOR_QUERY in data:
                    state["ready"] = True  # set before the client can answer it
                if (direction == "c2s" and self.freeze_after_ready and state["ready"]
                        and not self.frozen_mid_query.is_set()):
                    self.running.clear()
                    self.frozen_mid_query.set()
                if (direction == "c2s" and self.freeze_on is not None and self.freeze_on in data
                        and not self.frozen_on_marker.is_set()):
                    self.running.clear()
                    self.frozen_on_marker.set()
                while not self.running.wait(0.1):  # frozen: hold the bytes
                    if self.stopped:
                        return
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def freeze(self):
        self.running.clear()

    def resume(self):
        self.running.set()

    def stop(self):
        self.stopped = True
        self.running.set()
        time.sleep(0.3)  # let the accept loop observe `stopped`
        self.listener.close()
        with self.lock:
            for s in self.sockets:
                try:
                    s.close()
                except OSError:
                    pass

    def url(self) -> str:
        return make_url(self.database_url).set(
            host="127.0.0.1", port=self.port).render_as_string(hide_password=False)
