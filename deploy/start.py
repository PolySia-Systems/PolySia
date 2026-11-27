#!/usr/bin/env python3
"""Entry point inside an installed release. Keep mutable state outside its code."""

import http.client
import json
import os
import socket
import sys
import threading
from pathlib import Path

sys.dont_write_bytecode = True
release = Path(__file__).resolve().parent
sys.path.insert(0, str(release))
os.environ.setdefault("POLYSIA_DB", str(release.parents[1] / "data/workspace.sqlite3"))
os.umask(0o077)
from apps.server.__main__ import main

def serve_installed(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request("GET", "/api/v1/health")
        response = connection.getresponse()
        health = json.loads(response.read(8192))
        if response.status != 200 or health.get("status") != "ok" or health.get("artifactSha256") != release.name:
            raise ValueError("Installed release did not pass its storage and identity check.")
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"PolySia is running at {url}", flush=True)
        print(f"Version {health['version']} · Storage healthy · Simulated trading", flush=True)
        if not os.environ.get("NOTIFY_SOCKET"):
            print("Open the address on this Linux machine. Closing this terminal stops local mode.", flush=True)
        print("To try it offline, open Discover and choose Try a shadow replay.", flush=True)
        # A managed start finishes only after this process has served its own readiness probe.
        address = os.environ.get("NOTIFY_SOCKET")
        if address:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notify:
                notify.sendto(b"READY=1", "\0" + address[1:] if address.startswith("@") else address)
        thread.join()
    finally:
        connection.close()
        server.shutdown()
        thread.join()


main(artifact_sha256=release.name, serve_installed=serve_installed, installed_prefix=release.parents[1])
