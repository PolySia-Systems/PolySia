"""Loopback HTTP boundary for the single-user workstation."""

import json
import logging
import mimetypes
import re
import sqlite3
from threading import Lock
from time import monotonic
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from . import VERSION, observe, provider, public_depth, public_history, public_leaders, public_marks, public_shadow, shadow
from .store import Conflict, Workspace

API = "/api/v1"
STATIC = Path(__file__).resolve().parents[1] / "web" / "dist"
log = logging.getLogger(__name__)


class RequestError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class LocalServer(ThreadingHTTPServer):
    def __init__(self, port, store: Workspace, static_dir=STATIC, inspect_account=None, *, artifact_sha256=None):
        self.artifact_sha256 = artifact_sha256
        self.observation_lock = Lock()
        self.store = store
        self.static_dir = Path(static_dir).resolve()
        self.inspect_account = inspect_account or provider.inspect_account
        super().__init__(("127.0.0.1", port), Handler)

    def sample_buy(self, address, budget=None, *, retry_empty=False):
        # Run the same CLI as an operator. Its process deadline also bounds slow
        # provider reads that can outlast an individual socket timeout.
        if not self.observation_lock.acquire(blocking=False):
            raise RequestError(409, "One public observation is already in progress. Try again after it finishes.")
        try:
            return observe.sample_once(address, 2 if budget is not None else 5, budget, retry_empty=retry_empty)
        except TimeoutError as exc:
            raise RequestError(504, str(exc)) from None
        except OSError:
            raise RequestError(503, "The public observation could not complete. Try a new window.") from None
        finally:
            self.observation_lock.release()

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
            message = "Public shadow run not found." if self.operation == "public-runs" else "Replay not found."
            self.send_json(404, {"error": message})
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

    def body(self, fields, optional=()):
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
        if type(data) is not dict or not set(fields) <= set(data) <= set(fields) | set(optional):
            if optional:
                raise RequestError(400, "Supported optional fields: " + ", ".join(optional) + ".")
            raise RequestError(400, "Expected exactly these fields: " + ", ".join(fields) + ".")
        return data

    def api(self, path):
        store = self.server.store
        method = "GET" if self.command == "HEAD" else self.command
        # Only known route names enter logs. Exclude query strings, wallet
        # addresses, run IDs, provider body content and user-controlled labels.
        resource = path.removeprefix(API + "/").partition("/")[0]
        self.operation = resource if resource in ("health", "workspace", "leaders", "settings", "account", "runs", "public-runs") else "unknown"
        if path == API + "/health" and method == "GET":
            store.account_revision()  # Confirm an initialized database is actually readable.
            return {"status": "ok", "mode": "local", "liveExecution": False, "version": VERSION,
                    "artifactSha256": self.server.artifact_sha256}
        if path == API + "/workspace" and method == "GET":
            return store.read()
        if path == API + "/public-runs" or path.startswith(API + "/public-runs/"):
            return self.public_runs_api(path, method)
        if path == API + "/public/leaders" and self.command == "GET":
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=1)
            if query.keys() - {"period"}:
                raise ValueError("Use the period filter for public rankings.")
            self.operation = "public-rankings"
            return public_leaders.leaderboard(query.get("period", ["month"])[0])
        observation = re.fullmatch(API + r"/public/traders/(0x[0-9a-fA-F]{40})/observe", path)
        if observation:
            if self.command != "POST":
                raise RequestError(405, "Start an observation with an explicit request.")
            options = self.body((), optional=("budget", "retryEmpty"))
            budget = public_depth.budget_amount(options["budget"]) if "budget" in options else None
            retry_empty = options.get("retryEmpty", False)
            if type(retry_empty) is not bool or (retry_empty and budget is None):
                raise ValueError("Use a boolean for retryEmpty and include a research budget to enable it.")
            self.operation = "public-observation"
            return self.server.sample_buy(provider.validate_address(observation[1]), budget, retry_empty=retry_empty)
        history = re.fullmatch(API + r"/public/traders/(0x[0-9a-fA-F]{40})/history", path)
        if history and self.command == "GET":
            self.operation = "public-history"
            return public_history.pnl_history(history[1])
        valuation = re.fullmatch(API + r"/public/traders/(0x[0-9a-fA-F]{40})/value", path)
        if valuation and self.command == "GET":
            if urlsplit(self.path).query:
                raise ValueError("Holdings value covers the full trading wallet.")
            self.operation = "public-holdings-value"
            return provider.holdings_value(valuation[1])
        if path.startswith(API + "/public/traders/") and self.command == "GET":
            address = provider.validate_address(path.removeprefix(API + "/public/traders/"))
            self.operation = "public-trader"
            return self.server.inspect_account(address)
        if path == API + "/leaders" and method == "GET":
            return {"leaders": shadow.leaders(), "policy": shadow.POLICY, "limits": shadow.LIMITS}
        if path == API + "/leaders/coverage" and method == "POST":
            data = self.body(("allocation", "orderSize"))
            return shadow.compare_entry_coverage(data["allocation"], data["orderSize"])
        if path == API + "/settings" and method == "PUT":
            return store.set_theme(**self.body(("version", "revision", "theme")))
        if path == API + "/account":
            if method == "DELETE":
                revision = self.body(("revision",))["revision"]
                store.check_account_revision(revision)
                store.save_account(None, revision)
                return {"account": None}
            if method == "POST":
                data = self.body(("address", "revision"))
                address = provider.validate_address(data["address"])
                revision = data["revision"]
                store.check_account_revision(revision)
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

    def public_runs_api(self, path, method):
        store = self.server.store
        mark = re.fullmatch(API + r"/public-runs/([0-9a-f]{32})/positions/([0-9]{1,78})/mark", path)
        if mark:
            if method != "POST" or urlsplit(self.path).query:
                raise RequestError(405, "Request a position mark with its displayed run revision.")
            revision = self.body(("revision",))["revision"]
            with store.connection(write=False) as db:
                basis = public_shadow.position_basis(db, mark[1], mark[2], revision)
            return public_marks.read_mark(basis)
        match = re.fullmatch(API + r"/public-runs(?:/([0-9a-f]{32})(?:/(sample|pause|resume|stop|export))?)?", path)
        if not match:
            raise RequestError(404, "Unknown public shadow run.")
        run_id, action = match.groups()
        query = urlsplit(self.path).query
        before = None
        if query:
            pattern = r"before=([1-9][0-9]{0,17})" if run_id else r"before=([0-9a-f]{32})"
            cursor = re.fullmatch(pattern, query)
            if method != "GET" or action or not cursor:
                raise ValueError("Unsupported public run query.")
            before = int(cursor[1]) if run_id else cursor[1]
        if method == "GET" and action in (None, "export"):
            with store.connection(write=False) as db:
                if run_id is None:
                    return public_shadow.listing(db, before)
                return public_shadow.report(db, run_id, export=action == "export", before=before)
        if method == "PUT" and run_id and not action:
            config = self.body(("wallet", "name", "capital", "cap"))
            with store.connection() as db:
                return public_shadow.create(db, run_id, **config)
        if method == "POST" and action in ("sample", *public_shadow.CONTROLS):
            revision = self.body(("revision",))["revision"]
            if action != "sample":
                with store.connection() as db:
                    return public_shadow.control(db, run_id, revision, action)
            with store.connection(write=False) as db:
                wallet, budget = public_shadow.sampling_terms(db, run_id, revision)
            try:
                receipt = self.server.sample_buy(wallet, budget, retry_empty=True)
            except RequestError as exc:
                if exc.status not in (503, 504):
                    raise
                receipt = {"status": "unavailable", "reason": str(exc), "wallet": wallet, "researchBudget": budget}
            # A stop, pause or concurrent decision while the provider was reading supersedes this result.
            with store.connection() as db:
                return public_shadow.record(db, run_id, revision, receipt)
        raise RequestError(405, "Unsupported method for this public shadow operation.")

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
