"""Provision one owner-protected Cloudflare hostname for an installed PolySia workspace."""
import base64
import email.utils
import fnmatch
import getpass
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode, urlsplit


def hostname(value):
    value = value.strip()
    if value.startswith("https://"):
        value = value[8:]
    value = value.removesuffix("/").lower()
    if (len(value) > 253 or "." not in value
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in value.split("."))):
        raise ValueError("Enter a hostname such as polysia.example.com, without a path or port.")
    return value


def owner_email(value):
    value = value.strip()
    if not value.isascii():
        raise ValueError("Use the owner's ASCII sign-in email.")
    value = value.lower()
    if (len(value) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", value)
            or email.utils.parseaddr(value)[1] != value):
        raise ValueError("Enter the owner's sign-in email, such as owner@example.com.")
    local, domain = value.split("@")
    if local.startswith(".") or local.endswith(".") or ".." in local or len(local) > 64:
        raise ValueError("Enter a valid owner email.")
    hostname(domain)
    return value


def field(env, prompt, validate, default=None):
    value = os.getenv(env)
    if value is not None:
        return validate(value)
    if not sys.stdin.isatty():
        if default is None:
            raise ValueError(f"Set {env} for unattended deployment.")
        return validate(default)
    while True:
        raw = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ")
        try:
            return validate(raw or default or "")
        except ValueError as exc:
            print(exc, file=sys.stderr)


class API:
    def __init__(self, token):
        self.token = token

    def request(self, method, path, body=None, missing=False):
        conn = http.client.HTTPSConnection("api.cloudflare.com", timeout=20)
        try:
            conn.request(method, "/client/v4" + path,
                         None if body is None else json.dumps(body).encode(),
                         {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
            response = conn.getresponse()
            if missing and response.status == 404:
                return {"result": None}
            data = response.read(4194305)
            if len(data) > 4194304:
                raise ValueError("Cloudflare response exceeded the read limit.")
            if response.status >= 400:
                # Error bodies can echo resource names, request parameters or confidential fields.
                raise ValueError(f"Cloudflare {method} {path.split('?')[0]} returned HTTP {response.status}. "
                                 "Check the token scope and account settings, then rerun the same command.")
            parsed = json.loads(data)
            if not isinstance(parsed, dict) or parsed.get("success") is not True or "result" not in parsed:
                raise ValueError("Unexpected Cloudflare response. Check the resource before retrying.")
            return parsed
        finally:
            conn.close()

    def rows(self, path, **query):
        rows = []
        for page in range(1, 101):
            args = urlencode({**query, "page": page, "per_page": 50})
            data = self.request("GET", f"{path}?{args}")
            batch = data["result"]
            if not isinstance(batch, list) or any(not isinstance(row, dict) for row in batch):
                raise ValueError("Unexpected Cloudflare inventory response.")
            rows.extend(batch)
            info = data.get("result_info") or {}
            if page >= info.get("total_pages", 1000) or len(rows) >= info.get("total_count", 10**9):
                return rows
            if len(batch) < int(info.get("per_page") or 50):
                return rows
        raise ValueError("Cannot establish complete Cloudflare inventory within the deployment limit.")


def resource_id(row):
    value = row.get("id")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F-]{32,36}", value):
        raise ValueError("Cloudflare returned an invalid resource identifier.")
    return value


def write_private(path, text):
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as stream:
        staged = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            staged.unlink(missing_ok=True)
            raise
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


class UnsafeAccess(ValueError):
    """The provider returned an explicit configuration that breaks owner-only routing."""


class Journal:
    def __init__(self, path, host, owner, *, deferred=False):
        self.path = path
        self.deferred = deferred
        if path.exists():
            self.state = json.loads(path.read_bytes())
            if self.state["host"] != host or self.state["owner"] != owner:
                raise ValueError("The existing deployment has a different hostname or owner. Use its original settings.")
        else:
            self.state = {"host": host, "owner": owner, "marker": "polysia-" + uuid.uuid4().hex}
            self.save()

    def save(self):
        if self.deferred:
            return
        write_private(self.path, json.dumps(self.state, indent=2) + "\n")

    def ensure(self, api, key, path, candidates, ours, body):
        """Recover an uncertain create only by a unique, installation-specific marker."""
        known = self.state.get(key)
        if candidates:
            if len(candidates) != 1 or not ours(candidates[0]) or (known and resource_id(candidates[0]) != known):
                raise ValueError(f"Conflicting Cloudflare {key}. Existing resources have been preserved.")
            row = candidates[0]
        else:
            if known:
                raise ValueError(f"Recorded Cloudflare {key} is missing. Review the deployment before retrying.")
            row = api.request("POST", path, body)["result"]
        self.state[key] = resource_id(row)
        self.save()
        return row


def access_names(row):
    values = [row.get("domain", ""), *(row.get("self_hosted_domains") or [])]
    values.extend(d.get("uri", "") for d in row.get("destinations", []) if d.get("type") == "public")
    return {value.strip().lower() for value in values if isinstance(value, str) and value.strip()}


def applies(row, host):
    return any(fnmatch.fnmatchcase(host, value.split("/", 1)[0]) for value in access_names(row))


def verify_app(app, host, otp, marker):
    if (app.get("type") != "self_hosted" or app.get("name") != marker or access_names(app) != {host}
            or app.get("allowed_idps") != [otp] or not re.fullmatch(r"[0-9a-f]{64}", app.get("aud") or "")):
        raise UnsafeAccess("The Access application's hostname, owner sign-in method or audience has drifted.")


def verify_policy(policy, owner, marker):
    if (policy.get("name") != marker or policy.get("decision") != "allow" or
            policy.get("include") != [{"email": {"email": owner}}] or policy.get("exclude") or policy.get("require")):
        raise UnsafeAccess("The Access policy must allow only the configured owner's email.")


def discover_zone(api, host):
    parts = host.split(".")
    for start in range(len(parts) - 1):
        name = ".".join(parts[start:])
        matches = api.rows("/zones", name=name, status="active")
        if len(matches) == 1 and matches[0].get("name") == name:
            if start == 0:
                raise ValueError("Use a dedicated subdomain rather than the zone apex.")
            return resource_id(matches[0]), resource_id(matches[0]["account"])
    raise ValueError("No active Cloudflare zone for this hostname is visible to the token.")


def login_team(host):
    """Verify Access on both protected entry points before connecting the origin."""
    team = None
    for path in ("/", "/api/v1/health"):
        conn = http.client.HTTPSConnection(host, timeout=5)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            if 200 <= response.status < 300:
                raise UnsafeAccess("Cloudflare allowed an anonymous request. Inspect the Access application.")
            target = urlsplit(response.getheader("Location") or "")
            match = re.fullmatch(r"([a-z0-9-]+)\.cloudflareaccess\.com", target.netloc)
            if (response.status not in (302, 303, 307) or target.scheme != "https" or not match
                    or target.path.rstrip("/") != "/cdn-cgi/access/login/" + host):
                raise ValueError("Waiting for the Cloudflare Access login challenge.")
            if team and team != match.group(1):
                raise UnsafeAccess("The application and API login teams disagree.")
            team = match.group(1)
        finally:
            conn.close()
    return team


def wait_for(operation, seconds):
    end = time.monotonic() + seconds
    while True:
        try:
            return operation()
        except UnsafeAccess:
            raise
        except (ValueError, OSError, http.client.HTTPException):
            if time.monotonic() >= end:
                raise
            time.sleep(2)


def disconnected(api, tunnel_url):
    details = api.request("GET", tunnel_url)["result"]
    if (details.get("status") not in ("inactive", "down")
            or details.get("connections") or api.request("GET", tunnel_url + "/connections")["result"] != []):
        raise ValueError("The tunnel has an active connector. Confirm exclusive ownership before retrying.")


LEGACY_SOCKET = "/var/lib/polysia-test/.local/share/polysia/remote/origin.sock"
SERVICE_SOCKET = "/var/lib/polysia-service/.local/share/polysia/remote/origin.sock"


def configure_ingress(api, cfg_url, host, sock, team, aud, already_configured, *, allow_legacy=False, transfer_url=None):
    """With no known team, accept only a fresh, disconnected tunnel with no routable upstream."""
    expected = [{"hostname": host, "service": "unix:" + str(sock), "originRequest": {
        "httpHostHeader": host, "access": {"required": True, "teamName": team, "audTag": [aud]}}},
        {"service": "http_status:404"}]

    def read():
        result = api.request("GET", cfg_url, missing=True)["result"] or {}
        config = result.get("config") or {}
        if config.keys() - {"ingress", "warp-routing", "originRequest"}:
            raise ValueError("Unrecognized tunnel settings. Inspect the configuration before retrying.")
        if config.get("originRequest") or config.get("warp-routing") not in (None, {}, {"enabled": False}):
            raise UnsafeAccess("Conflicting global tunnel configuration.")
        rules = [{k: v for k, v in rule.items() if not (k == "originRequest" and v == {})}
                 for rule in config.get("ingress", [])]
        return config, rules

    config, prior = read()
    if team and prior == expected:
        return
    legacy = [{**expected[0], "service": "unix:" + LEGACY_SOCKET}, expected[1]]
    if (allow_legacy or transfer_url) and team and str(sock) == SERVICE_SOCKET and prior == legacy:
        if allow_legacy:
            return True  # Defer migration until workspace verification succeeds.
        disconnected(api, transfer_url)
    elif already_configured or prior not in ([], [{"service": "http_status:404"}]):
        raise UnsafeAccess("Unexpected tunnel configuration. Inspect it before retrying.")
    if team:
        api.request("PUT", cfg_url, {"config": {**config, "ingress": expected}})
        if read()[1] != expected:
            raise ValueError("Cloudflare has not confirmed the owner-protected ingress rules.")


def command(*args):
    proc = subprocess.run(args, capture_output=True, text=True, timeout=45)
    if proc.returncode:
        raise ValueError(f"{args[0]} {args[1]} failed. Inspect the user manager and retry. " +
                         (proc.stderr.strip()[:300] if args[0] in ("systemctl", "loginctl") else ""))
    return proc.stdout.strip()


def unit_arg(value):
    if not value.isprintable():
        raise ValueError("The deployment paths must contain printable characters.")
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def unit_text(description, argv, marker):
    return (f"# Managed by {marker}\n[Unit]\nDescription={description}\n"
            "[Service]\nType=simple\nUMask=0077\nUnsetEnvironment=POLYSIA_DB PYTHONPATH PYTHONHOME\n"
            "Restart=on-failure\nRestartSec=5\nExecStart=" + " ".join(unit_arg(str(a)) for a in argv)
            + "\n[Install]\nWantedBy=default.target\n")


def unit_state(name):
    data = subprocess.run(["systemctl", "--user", "show", name, "--all", "-p", "LoadState",
                           "-p", "FragmentPath", "-p", "DropInPaths", "-p", "ActiveState", "-p", "InvocationID", "-p", "UnitFileState"],
                          capture_output=True, text=True, timeout=10)
    state = dict(line.split("=", 1) for line in data.stdout.splitlines() if "=" in line)
    if data.returncode not in (0, 4) or not state.get("LoadState"):
        raise ValueError(f"Cannot verify {name} in the user service manager.")
    return state


def check_local_service():
    state = unit_state("polysia.service")
    if state["LoadState"] == "not-found" and state.get("ActiveState") == "inactive":
        return
    if state.get("ActiveState") in ("inactive", "failed") and state.get("UnitFileState") in ("disabled", "masked"):
        return
    raise ValueError("Disable and stop the local polysia.service before deploying owner-only HTTPS "
                     "under this dedicated service user.")


def ensure_unit(path, definition, create):
    if path.is_symlink() or (path.exists() and path.read_text() != definition):
        raise ValueError(f"Conflicting service configuration at {path}. Inspect before retrying.")
    state = unit_state(path.name)
    if (state["LoadState"] not in ("loaded", "not-found") or state.get("DropInPaths") or state.get("FragmentPath") not in ("", str(path))
            or (state.get("FragmentPath") and not path.exists())):
        raise ValueError(f"Cannot verify exclusive ownership of {path.name}.")
    if create and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as folder:
            staged = Path(folder) / path.name
            staged.write_text(definition)
            os.link(staged, path)


def discover_tunnel(api, zone, host):
    dns = "/zones/" + zone + "/dns_records"
    records = api.rows(dns, name=host)
    if len(records) != 1 or records[0].get("name") != host or records[0].get("type") != "CNAME" or records[0].get("proxied") is not True:
        raise ValueError("Recovery requires one proxied tunnel CNAME for this hostname.")
    target = records[0].get("content") or ""
    tunnel_id = target.removesuffix(".cfargotunnel.com")
    if not target.endswith(".cfargotunnel.com") or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", tunnel_id):
        raise ValueError("The hostname does not point to a Cloudflare tunnel.")
    aliases = api.rows(dns, type="CNAME", **{"content.exact": target})
    if len(aliases) != 1 or resource_id(aliases[0]) != resource_id(records[0]):
        raise ValueError("The tunnel DNS target must belong to this hostname alone in its zone.")
    return tunnel_id


def select_recovery(api, base, tunnel_id, journal):
    endpoint = api.request("GET", base + "/cfd_tunnel/" + tunnel_id)["result"]
    marker = endpoint.get("name") or ""
    remote_config = endpoint.get("config_src") == "cloudflare" if "config_src" in endpoint else endpoint.get("remote_config") is True
    if (resource_id(endpoint) != tunnel_id or not remote_config
            or endpoint.get("deleted_at") or not re.fullmatch(r"polysia-[a-f0-9]{32}", marker)):
        raise ValueError("Select the active PolySia-managed tunnel ID from the Cloudflare dashboard.")
    if any(key in journal.state for key in ("app", "tunnel", "policy", "dns")) and (
            journal.state["marker"] != marker or journal.state.get("tunnel", tunnel_id) != tunnel_id):
        raise ValueError("This prefix belongs to another deployment. Use the matching prefix.")
    return marker


def valid_token(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_=+./-]{20,8192}", value)


def transfer_token(api, tunnel_url, name):
    disconnected(api, tunnel_url)
    secret = base64.b64encode(os.urandom(32)).decode("ascii")
    updated = api.request("PATCH", tunnel_url, {"name": name, "tunnel_secret": secret})["result"]
    if resource_id(updated) != tunnel_url.rsplit("/", 1)[1]:
        raise ValueError("Cloudflare did not confirm the selected tunnel. Retry recovery.")
    disconnected(api, tunnel_url)
    if updated.get("token"):
        return updated["token"]
    # Some API versions return only tunnel metadata. Bind the fetched credential
    # to this rotation before handing it to the connector.
    token = api.request("GET", tunnel_url + "/token")["result"]
    try:
        payload = json.loads(base64.b64decode(token, validate=True))
        if payload["s"] == secret and payload["t"] == updated["id"]:
            return token
    except (TypeError, ValueError, KeyError):
        pass
    raise ValueError("Cloudflare did not return this transfer's credential. Check for another transfer and retry.")


def check_origin(sock, host):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(3)
        probe.connect(str(sock))
        probe.sendall(f"GET /api/v1/health HTTP/1.0\r\nHost: {host}\r\n\r\n".encode("ascii"))
        with probe.makefile("rb") as stream:
            if not re.match(rb"HTTP/1\.[01] 403 ", stream.readline(512)):
                raise ValueError("Private origin did not reject anonymous health access.")


def service_invocations(*units):
    ids = []
    for unit in units:
        state = unit_state(unit.name)
        invocation = state.get("InvocationID") or ""
        if (state.get("ActiveState") != "active" or state.get("UnitFileState") != "enabled"
                or not re.fullmatch("[a-f0-9]{32}", invocation)):
            return []
        ids.append(invocation)
    return ids


def healthy_connector(api, tunnel_url):
    clients = api.request("GET", tunnel_url + "/connections")["result"]
    if (api.request("GET", tunnel_url)["result"].get("status") != "healthy"
            or not isinstance(clients, list) or len(clients) != 1):
        raise ValueError("Expected one healthy connector. Inspect the tunnel in Cloudflare.")
    return resource_id(clients[0])


def deployment_connector():
    if sys.platform != "linux" or os.getuid() == 0:
        raise ValueError("Run deployment as the dedicated, non-root Linux service user.")
    try:
        import cryptography
        import jwt
        from jwt.algorithms import RSAAlgorithm
    except ImportError as exc:
        raise ValueError("The deployment interpreter needs PyJWT 2.x with cryptography for Access JWT verification.") from exc
    if not jwt.__version__.startswith("2.") or "RS256" not in jwt.algorithms.get_default_algorithms():
        raise ValueError("Install the supported PyJWT 2.x with RS256 support in the service interpreter.")
    if command("loginctl", "show-user", str(os.getuid()), "-p", "Linger", "--value") != "yes":
        raise ValueError("Enable systemd user lingering for this dedicated OS account first.")
    check_local_service()
    connector = shutil.which("cloudflared")
    if not connector:
        raise ValueError("Install the authenticated cloudflared package first, then retry.")
    if "--token-file" not in command(connector, "tunnel", "run", "--help"):
        raise ValueError("The installed cloudflared must support tunnel run --token-file.")
    return connector


def setup(*, archive, prefix, install, recovery_id=None, backup=None, empty_workspace=False):
    connector = deployment_connector()
    remote = prefix / "remote"
    remote.mkdir(mode=0o700, exist_ok=True)
    if (remote.is_symlink() or remote.stat().st_uid != os.getuid() or stat.S_IMODE(remote.stat().st_mode) != 0o700):
        raise ValueError("The remote deployment directory must be owned by this user and mode 0700.")
    sock = remote / "origin.sock"
    if len(os.fsencode(sock)) >= 108:
        raise ValueError("The installation path is too long for a Unix socket. Choose a shorter prefix.")
    path = remote / "deployment.json"
    previous = json.loads(path.read_bytes()) if path.exists() else {}
    host = field("POLYSIA_HOSTNAME", "Application hostname (polysia.example.com)", hostname, previous.get("host"))
    owner = field("POLYSIA_OWNER_EMAIL", "Owner email (owner@example.com)", owner_email, previous.get("owner"))
    j = Journal(path, host, owner, deferred=bool(recovery_id))
    token = (getpass.getpass("Cloudflare management API token (hidden): ") if sys.stdin.isatty()
             else sys.stdin.readline(1025).strip())
    if not token or not token.isascii() or not all(32 < ord(c) < 127 for c in token) or len(token) > 1024:
        raise ValueError("Supply a scoped Cloudflare token on standard input or at the hidden prompt.")
    api = API(token)
    zone, account = discover_zone(api, host)
    for key, actual in (("zone", zone), ("account", account)):
        if j.state.get(key, actual) != actual:
            raise ValueError("The active Cloudflare account or zone has changed.")
        j.state[key] = actual
    j.save()
    base = "/accounts/" + account
    if recovery_id:
        discovered = discover_tunnel(api, zone, host)
        if recovery_id not in ("auto", discovered):
            raise ValueError("The supplied tunnel ID differs from the hostname's DNS target.")
        recovery_id = discovered
    if j.state.get("recovery") and j.state["recovery"] != recovery_id:
        raise ValueError("A transfer is incomplete. Rerun with the same hostname and --recover.")
    database = prefix / "data/workspace.sqlite3"
    machine = hashlib.sha256(Path("/etc/machine-id").read_bytes() + j.state["host"].encode()).hexdigest()
    if not recovery_id and j.state.get("machine", machine) != machine:
        raise ValueError("This journal came from another host. Use --recover for a host transfer.")
    if recovery_id:
        name = select_recovery(api, base, recovery_id, j)
        if backup and database.exists():
            raise ValueError("A workspace already exists. Inspect it and retry without --workspace-backup.")
        if not database.exists() and not (empty_workspace or backup):
            if not sys.stdin.isatty():
                raise ValueError("Supply --workspace-backup FILE or explicitly choose --empty-workspace.")
            print("No workspace was found on this server. Cloudflare cannot restore saved runs.")
            choice = input("Enter the absolute backup path on this server, or type EMPTY to start without history: ").strip()
            if choice == "EMPTY":
                empty_workspace = True
            elif Path(choice).is_absolute():
                backup = Path(choice)
            else:
                raise ValueError("Recovery stopped. Rerun with a readable backup or explicitly choose EMPTY.")
        if backup and not backup.is_file():
            raise ValueError("The service user must be able to read the workspace backup.")
        j.state.update(marker=name, recovery=recovery_id)
    name = j.state["marker"]
    units = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd/user"
    origin = units / "polysia-origin.service"
    tunnel = units / "polysia-tunnel.service"
    origin_text = unit_text("PolySia protected workspace", [sys.executable, "-I", prefix / "current/polysia",
                            "--origin-socket", sock, "--public-host", host, "--owner-email", owner], name)
    tunnel_text = unit_text("PolySia authenticated tunnel", [connector, "tunnel", "--no-autoupdate", "run",
                            "--token-file", remote / "connector.token"], name)
    ensure_unit(origin, origin_text, False)
    ensure_unit(tunnel, tunnel_text, False)
    if (not recovery_id and j.state.get("configured") and (origin.exists() or j.state.get("machine"))
            and (not database.is_file() or not database.stat().st_size)):
        raise ValueError("The saved workspace is missing or empty. Inspect the data directory and use --recover-tunnel.")
    try:
        tunnel_url, app, team, move_socket = provision(api, base, zone, host, owner, j, sock, recovery_id)
    except UnsafeAccess:
        if not recovery_id and tunnel.exists() and previous.get("configured") and previous["marker"] == name:
            command("systemctl", "--user", "disable", "--now", tunnel.name)
        raise
    access = json.dumps({"team": team, "audience": app["aud"]}) + "\n"
    if not recovery_id or previous.get("artifact"):
        credential = api.request("GET", tunnel_url + "/token")["result"]
        if not valid_token(credential):
            raise ValueError("The connector credential is unavailable.")
        local_token = remote / "connector.token"
        if not recovery_id and previous.get("configured") and local_token.is_file() and local_token.read_text() != credential:
            raise ValueError("The tunnel credential has changed. Confirm the active host and use --recover-tunnel.")
    # A healthy rerun can finish without changing the journal or withdrawing service.
    if (not move_socket and previous.get("artifact") and not previous.get("recovery")
            and database.is_file() and database.stat().st_size
            and previous["artifact"] == hashlib.sha256(archive.read_bytes()).hexdigest()):
        invocations = service_invocations(origin, tunnel)
        token_file = remote / "connector.token"
        access_file = remote / "access.json"
        if (invocations and invocations == previous.get("invocations")
                and token_file.is_file() and token_file.read_text() == credential
                and access_file.is_file() and access_file.read_text() == access
                and healthy_connector(api, tunnel_url) == previous.get("connector")):
            check_origin(sock, host)
            install(archive, prefix)
            print(f"PolySia is already running at https://{host}. No restart was needed.")
            return
    if recovery_id:
        disconnected(api, tunnel_url)
    j.deferred = False
    j.save()
    installed = install(archive, prefix)
    if recovery_id and (database.exists() or backup):
        database.parent.mkdir(mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=remote) as directory:
            source = backup or database
            target = database if backup else Path(directory) / "verified.sqlite3"
            result = subprocess.run([sys.executable, "-I", installed["launcher"], "restore",
                                     "--from", source, "--to", target])
            if result.returncode:
                raise ValueError("Workspace verification failed. Inspect the saved data before retrying.")
    write_private(remote / "access.json", access)
    if tunnel.exists():
        command("systemctl", "--user", "disable", "--now", tunnel.name)
    wait_for(lambda: disconnected(api, tunnel_url), 30)
    if recovery_id:
        credential = transfer_token(api, tunnel_url, name)
    if not valid_token(credential):
        raise ValueError("The connector credential is unavailable.")
    if move_socket:
        configure_ingress(api, tunnel_url + "/configurations", host, sock, team, app["aud"], True,
                          transfer_url=tunnel_url)
    write_private(remote / "connector.token", credential)
    ensure_unit(origin, origin_text, True)
    ensure_unit(tunnel, tunnel_text, True)
    command("systemctl", "--user", "daemon-reload")
    command("systemctl", "--user", "restart", origin.name)
    wait_for(lambda: check_origin(sock, host), 12)
    try:
        command("systemctl", "--user", "start", tunnel.name)
        client = wait_for(lambda: healthy_connector(api, tunnel_url), 45)
        if login_team(host) != team:
            raise ValueError("The protected hostname changed its Access team.")
        command("systemctl", "--user", "enable", origin.name, tunnel.name)
    except BaseException:
        command("systemctl", "--user", "stop", tunnel.name)
        raise
    j.state.pop("recovery", None)
    j.state.update(machine=machine, artifact=installed["artifactSha256"], connector=client,
                   invocations=service_invocations(origin, tunnel))
    j.save()
    print(f"PolySia is ready for owner sign-in at https://{host}.\n"
          f"Installed artifact {installed['artifactSha256'][:12]}. Anonymous browser and API access require sign-in.\n"
          "To withdraw access, run systemctl --user disable --now polysia-tunnel.service.")


def provision(api, base, zone, host, owner, j, sock, recovery_id):
    name = j.state["marker"]
    apps, tunnels, dns = base + "/access/apps", base + "/cfd_tunnel", "/zones/" + zone + "/dns_records"
    records = api.rows(dns, name=host)
    relevant = [a for a in api.rows(apps) if applies(a, host) or a.get("name") == name]
    candidates = api.rows(tunnels, name=name, is_deleted="false")
    if j.state.get("configured") and not any(resource_id(a) == j.state.get("app") for a in relevant):
        raise UnsafeAccess("The recorded Access application is missing. Inspect its hostname and owner policy.")
    if records and (len(records) != 1 or records[0].get("comment") != name):
        raise ValueError("DNS already contains a record at this hostname. See Recover an HTTPS site "
                         "in the operations guide for --recover, or choose an unused hostname.")
    if any(a.get("name") != name for a in relevant):
        raise UnsafeAccess("Another Access application covers this hostname. Choose an unused name.")
    providers = [row for row in api.rows(base + "/access/identity_providers") if row.get("type") == "onetimepin"]
    if len(providers) != 1:
        raise ValueError("An existing One-time PIN identity provider is required for owner login.")
    otp = resource_id(providers[0])

    if recovery_id:
        if (len(relevant) != 1 or len(records) != 1 or len(candidates) != 1
                or resource_id(candidates[0]) != recovery_id):
            raise ValueError("Recovery requires the existing Access app, DNS record and selected tunnel.")
        # Pin the inventory before reuse. A missing item must never fall through to creation.
        j.state["tunnel"] = recovery_id

    print("Configuring the owner-only Access application…", flush=True)
    app = j.ensure(api, "app", apps, relevant, lambda a: a.get("name") == name,
                   {"type": "self_hosted", "domain": host, "name": name, "allowed_idps": [otp],
                    "session_duration": "8h", "app_launcher_visible": False, "policies": []})
    app_url = apps + "/" + resource_id(app)
    app = api.request("GET", app_url)["result"]
    verify_app(app, host, otp, name)
    policies = app_url + "/policies"
    existing_policies = api.rows(policies)
    if j.state.get("configured") and (len(existing_policies) != 1 or existing_policies[0].get("id") != j.state.get("policy")):
        raise UnsafeAccess("The set of policies for the protected application changed.")
    if recovery_id and len(existing_policies) != 1:
        raise ValueError("Recovery requires one existing owner policy.")
    j.ensure(api, "policy", policies, existing_policies, lambda p: p.get("name") == name,
             {"name": name, "precedence": 1, "decision": "allow", "include": [{"email": {"email": owner}}],
              "require": [], "exclude": []})
    policy_list = api.rows(policies)
    if len(policy_list) != 1 or resource_id(policy_list[0]) != j.state["policy"]:
        raise UnsafeAccess("Expected exactly one verified owner policy.")
    verify_policy(api.request("GET", policies + "/" + j.state["policy"])["result"], owner, name)
    endpoint = j.ensure(api, "tunnel", tunnels, candidates, lambda t: t.get("name") == name,
                        {"name": name, "config_src": "cloudflare"})
    tunnel_url = tunnels + "/" + resource_id(endpoint)
    team = os.environ.get("POLYSIA_ACCESS_TEAM") or j.state.get("team")
    if team and (team != j.state.get("team", team) or not re.fullmatch("[a-z0-9-]{1,63}", team)):
        raise ValueError("Invalid or conflicting Cloudflare Access team name.")
    cfg_url = tunnel_url + "/configurations"

    if not (recovery_id or j.state.get("configured")):
        disconnected(api, tunnel_url)
    if not recovery_id:
        configure_ingress(api, cfg_url, host, sock, team, app["aud"], j.state.get("configured"))
    target = resource_id(endpoint) + ".cfargotunnel.com"
    dns_body = {"type": "CNAME", "name": host, "content": target, "proxied": True, "ttl": 1, "comment": name}
    record = j.ensure(api, "dns", dns, records, lambda r: r.get("comment") == name, dns_body)
    record = api.request("GET", dns + "/" + resource_id(record))["result"]
    if any(record.get(k) != dns_body[k] for k in ("type", "name", "content", "proxied", "comment")):
        raise ValueError("The deployment DNS record has drifted. Inspect the record before retrying.")

    print("Checking anonymous browser and API access before starting the connector…", flush=True)
    observed = wait_for(lambda: login_team(host), 90)
    if team and team != observed:
        raise UnsafeAccess("The observed Cloudflare Access team differs from the expected team.")
    team = observed
    j.state["team"] = team
    j.save()
    move_socket = configure_ingress(api, cfg_url, host, sock, team, app["aud"], recovery_id or j.state.get("configured"),
                                    allow_legacy=bool(recovery_id))
    j.state["configured"] = True
    j.save()
    return tunnel_url, app, team, move_socket
