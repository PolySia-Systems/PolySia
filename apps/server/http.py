"""Loopback HTTP boundary for the single-user workstation."""

import json
import logging
import mimetypes
import re
import sqlite3
from time import monotonic
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from . import provider, shadow
from .store import Conflict, Workspace

API = "/api/v1"
STATIC = Path(__file__).resolve().parents[1] / "web" / "dist"
VERSION = "0.1.0"
log = logging.getLogger(__name__)


class RequestError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class LocalServer(ThreadingHTTPServer):
    def __init__(self, port, store: Workspace, static_dir=STATIC, inspect_account=None):
        self.store = store
        self.static_dir = Path(static_dir).resolve()
        self.inspect_account = inspect_account or provider.inspect_account
        super().__init__(("127.0.0.1", port), Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    server_version = "PolySia/" + VERSION
    sys_version = ""

    def do_GET(self):
        self.dispatch()

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET
    do_OPTIONS = do_GET

    def log_message(self, *args):
        # Request targets may contain public wallet addresses or arbitrary input.
        # Correlate diagnostics by the opaque response ID instead.
        pass

    def dispatch(self):
        self.request_id = uuid4().hex
        self.started_at = monotonic()
        self.operation = None
        try:
            self.enforce_local()
            path = urlsplit(self.path).path
            if path.startswith("/api/") or path == "/api":
                result = self.api(path)
                self.send_json(200, result)
            elif self.command in ("GET", "HEAD"):
                self.static(path)
            else:
                raise RequestError(HTTPStatus.METHOD_NOT_ALLOWED, "Unsupported method.")
        except RequestError as exc:
            self.send_json(exc.status, {"error": str(exc)})
        except Conflict as exc:
            self.send_json(409, {"error": str(exc)})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except KeyError:
            self.send_json(404, {"error": "Replay not found."})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except (sqlite3.Error, OSError) as exc:
            log.error("%s storage or service unavailable (%s)", self.request_id, type(exc).__name__)
            self.send_json(503, {"error": "Local service unavailable. Check its storage and retry."})
        except Exception as exc:
            log.error("%s unexpected service error (%s)", self.request_id, type(exc).__name__)
            self.send_json(500, {"error": "Unexpected local service error. Check the request ID."})

    def enforce_local(self):
        port = self.server.server_port
        hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        if port == 80:
            hosts.update(("localhost", "127.0.0.1"))
        host = self.headers.get("Host", "")
        if len(self.headers.get_all("Host", [])) != 1 or host not in hosts:
            raise RequestError(403, "Use the local PolySia address.")
        origins = self.headers.get_all("Origin", [])
        if origins and origins != ["http://" + host]:
            raise RequestError(403, "Cross-origin requests are unavailable.")
        if any(key in self.headers for key in ("Forwarded", "X-Forwarded-For", "X-Forwarded-Host")):
            raise RequestError(403, "This workspace requires a direct local connection.")

    def body(self, fields):
        content_length = self.headers.get_all("Content-Length", [])
        if self.headers.get_content_type() != "application/json":
            raise RequestError(415, "Use application/json for this request.")
        if self.headers.get("Transfer-Encoding") or len(content_length) != 1 or not re.fullmatch(r"[0-9]{1,10}", content_length[0]):
            raise RequestError(400, "Provide one valid JSON body length.")
        length = int(content_length[0])
        if length > 4096:
            raise RequestError(413, "Request exceeds the 4 KiB input limit.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError):
            raise RequestError(400, "Provide a valid UTF-8 JSON object.") from None
        if type(data) is not dict or set(data) != set(fields):
            raise RequestError(400, "Expected exactly these fields: " + ", ".join(fields) + ".")
        return data

    def api(self, path):
        store = self.server.store
        method = "GET" if self.command == "HEAD" else self.command
        # Only known route names enter logs. Exclude query strings, wallet
        # addresses, run IDs, provider body content and user-controlled labels.
        resource = path.removeprefix(API + "/").partition("/")[0]
        self.operation = resource if resource in ("health", "workspace", "leaders", "settings", "account", "runs") else "unknown"
        if path == API + "/health" and method == "GET":
            store.account_revision()  # Confirm an initialized database is actually readable.
            return {"status": "ok", "mode": "local", "liveExecution": False, "version": VERSION}
        if path == API + "/workspace" and method == "GET":
            return store.read()
        if path == API + "/leaders" and method == "GET":
            return {"leaders": shadow.leaders(), "policy": shadow.POLICY, "limits": shadow.LIMITS}
        if path == API + "/settings" and method == "PUT":
            return store.set_theme(**self.body(("version", "revision", "theme")))
        if path == API + "/account":
            if method == "DELETE":
                store.disconnect()
                return {"account": None}
            if method == "POST":
                data = self.body(("address",))
                address = provider.validate_address(data["address"])
                revision = store.account_revision()
                snapshot = self.server.inspect_account(address)
                outcome = "available" if snapshot.get("status") == "available" else "unavailable"
                log.info("%s positions lookup %s", self.request_id, outcome)
                return store.save_account(snapshot, revision)
        if path == API + "/runs":
            if method == "GET":
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=1)
                if not query:
                    return store.run_history(None)
                if "before" not in query or not re.fullmatch("[0-9a-f]{32}", query["before"][0]):
                    raise ValueError("Provide a replay ID as the history cursor.")
                return store.run_history(query["before"][0])
            if method == "POST":
                data = self.body(("leaderId", "allocation", "orderSize"))
                return store.create_run(data["leaderId"], data["allocation"], data["orderSize"])
        run_match = re.fullmatch(API + r"/runs/([0-9a-f]{32})(?:/(step|pause|resume|stop))?", path)
        if run_match:
            run_id, action = run_match.groups()
            if method == "GET" and action is None:
                return store.get_run(run_id)
            if method == "POST" and action is not None:
                revision = self.body(("revision",))["revision"]
                return store.change_run(run_id, action, revision)
        raise RequestError(404, "Unknown API operation.")

    def static(self, path):
        root = self.server.static_dir
        relative = unquote(path).lstrip("/")
        if "\x00" in relative or ".." in Path(relative).parts:
            raise RequestError(404, "File not found.")
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise RequestError(404, "File not found.")
        # Vite's entry point also serves client-side routes. Missing assets
        # must produce an error so a broken build is visible during install.
        if not Path(relative).suffix and not target.is_file():
            target = (root / "index.html").resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise RequestError(404, "File not found. Build the web application first.")
        self.reply(200, mimetypes.guess_type(target.name)[0] or "application/octet-stream", target.read_bytes())

    def send_json(self, status, obj):
        self.reply(status, "application/json; charset=utf-8", json.dumps(obj, allow_nan=False).encode("utf-8"))

    def reply(self, status, mime, body):
        if self.operation:
            elapsed_ms = round((monotonic() - self.started_at) * 1000)
            log.info("%s %s %s %s %dms", self.request_id, self.command, self.operation, status, elapsed_ms)
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Request-ID", self.request_id)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
