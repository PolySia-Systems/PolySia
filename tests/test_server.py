import http.client
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event, Thread

from apps.server import public_shadow
from apps.server.archive import copy_workspace
from apps.server.http import LocalServer
from apps.server.store import Workspace
from test_public_shadow import ID, STARTED, WALLET, observed_buy, observed_sell

ADDRESS = "0x" + "AB" * 20


def public_snapshot(address):
    return {
        "address": address, "status": "available",
        "source": "HTTP test fixture", "observedAt": "2026-11-01T00:00:00Z",
        "checkedAt": "2026-11-01T00:00:00Z", "message": "One fixture position.",
        "positions": [{"market": "Fixture", "outcome": "Yes", "shares": "2.50"}],
        "complete": True, "nextCursor": None,
    }


class WorkspaceHttpTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        (self.dist / "index.html").write_text("<!doctype html>PolySia")
        self.launch()
        self.addCleanup(self.shutdown)

    def launch(self):
        self.server = LocalServer(0, Workspace(self.root / "workspace.db"), self.dist, public_snapshot)
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()

    def shutdown(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            header_values = {"Content-Type": "application/json"}
            header_values.update(headers or {})
            conn.request(method, path, json.dumps(body) if body is not None else None, header_values)
            result = conn.getresponse()
            data = result.read()
            self.assertTrue(result.getheader("X-Request-ID"))
            if result.getheader("Content-Type").startswith("application/json") and data:
                data = json.loads(data)
            return result.status, data
        finally:
            conn.close()

    def test_startup_browser_and_preferences_survive_restart(self):
        self.assertEqual((200, b"<!doctype html>PolySia"), self.request("GET", "/discover"))
        self.assertEqual(404, self.request("GET", "/assets/missing.js")[0])
        status, health = self.request("GET", "/api/v1/health")
        self.assertEqual((200, "ok", False), (status, health["status"], health["liveExecution"]))
        self.assertEqual((200, b""), self.request("HEAD", "/api/v1/health"))
        status, workspace = self.request("GET", "/api/v1/workspace")
        self.assertEqual((200, None, None, "light"), (status, workspace["run"], workspace["account"], workspace["settings"]["theme"]))
        preference = {**workspace["settings"], "theme": "dark"}
        status, updated = self.request("PUT", "/api/v1/settings", preference)
        self.assertEqual(200, status)
        self.assertEqual(409, self.request("PUT", "/api/v1/settings", preference)[0])
        self.shutdown()
        self.launch()
        self.assertEqual(updated, self.request("GET", "/api/v1/workspace")[1]["settings"])

    def test_budget_check_counts_complete_partial_and_unknown_without_creating_run(self):
        def compare(allocation, cap):
            return self.request("POST", "/api/v1/leaders/coverage", {"allocation": allocation, "orderSize": cap})

        status, result = compare("500.00", "500.00")
        self.assertEqual((200, "500.00", "500.00", "scenario"),
                         (status, result["allocation"], result["orderSize"], result["source"]))
        candidates = {row["leaderId"]: row for row in result["candidates"]}
        atlas = candidates["atlas"]
        self.assertEqual((1, 1, 2, 1), (atlas["full"], atlas["partial"], atlas["skipped"], atlas["missingBook"]))
        self.assertEqual(0, candidates["cobalt"]["full"])
        self.assertTrue(all(row["full"] == 0 for row in compare("1000", "1000")[1]["candidates"]))
        self.assertEqual(400, compare("5", "50")[0])
        self.assertIsNone(self.request("GET", "/api/v1/workspace")[1]["run"])

    def test_public_observation_is_explicit_fixed_window_and_serialized(self):
        address = ADDRESS.lower()
        endpoint = f"/api/v1/public/traders/{address}/observe"
        entered, release = Event(), Event()
        result = {"status": "waiting", "wallet": address}

        def observe(command, **kwargs):
            self.assertEqual(command, [sys.executable, "-B", "-m", "apps.server.observe", address, "--seconds", "5"])
            self.assertEqual(kwargs["timeout"], 20)
            entered.set()
            self.assertTrue(release.wait(3))
            return subprocess.CompletedProcess(command, 0, json.dumps(result).encode())

        with patch("apps.server.observe.subprocess.run", side_effect=observe) as process:
            self.assertEqual(self.request("GET", endpoint)[0], 405)
            self.assertEqual(self.request("POST", endpoint, {"seconds": 99})[0], 400)
            self.assertEqual(self.request("GET", f"/api/v1/public/traders/{address}")[0], 200)
            process.assert_not_called()
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(self.request, "POST", endpoint, {})
                try:
                    self.assertTrue(entered.wait(3))
                    self.assertEqual(self.request("POST", endpoint, {})[0], 409)
                finally:
                    release.set()
                self.assertEqual(first.result(), (200, result))
            process.assert_called_once()
        with patch("apps.server.observe.subprocess.run", side_effect=subprocess.TimeoutExpired("probe", 20)):
            self.assertEqual(self.request("POST", endpoint, {})[0], 504)
        with patch("apps.server.observe.subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"{}")) as probe:
            for value in ("0", "1000.01", "1e2", "1.001", None, True, 5):
                self.assertEqual(self.request("POST", endpoint, {"budget": value})[0], 400)
            for options in ({"retryEmpty": True}, {"budget": "10", "retryEmpty": 1},
                            {"budget": "10", "retryEmpty": "true"}, {"budget": "10", "retryEmpty": None}):
                self.assertEqual(self.request("POST", endpoint, options)[0], 400)
            probe.assert_not_called()
            self.assertEqual(self.request("POST", endpoint, {"budget": "12.5"})[0], 200)
            self.assertEqual(probe.call_args.args[0][-4:], ["--seconds", "2", "--budget", "12.50"])
            self.assertEqual(self.request("POST", endpoint, {"budget": "10", "retryEmpty": True})[0], 200)
            self.assertIn("--retry-empty", probe.call_args.args[0])
        self.assertIsNone(self.request("GET", "/api/v1/workspace")[1]["account"])
        self.assertIsNone(self.request("GET", "/api/v1/workspace")[1]["run"])

    def test_public_pause_supersedes_inflight_buy_and_busy_has_no_decision(self):
        route = "/api/v1/public-runs/" + ID
        config = {"name": "Paper", "wallet": WALLET, "capital": "25", "cap": "10"}
        self.assertEqual(400, self.request("PUT", route, {**config, "cap": "26"})[0])
        self.assertEqual(200, self.request("PUT", route, config)[0])
        self.assertEqual(400, self.request("POST", route + "/sample", {"revision": 1, "receipt": {}})[0])
        entered, release = Event(), Event()

        def delayed(wallet, budget, *, retry_empty, check_sales):
            self.assertTrue(check_sales)
            self.assertTrue(retry_empty)
            entered.set()
            self.assertTrue(release.wait(3))
            return observed_buy(wallet, budget)

        with patch.object(self.server, "sample_buy", side_effect=delayed), ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.request, "POST", route + "/sample", {"revision": 1})
            try:
                self.assertTrue(entered.wait(3))
                status, paused = self.request("POST", route + "/pause", {"revision": 1})
                self.assertEqual((status, paused["status"]), (200, "paused"))
            finally:
                release.set()
            self.assertEqual(pending.result()[0], 409)
        self.shutdown()
        self.launch()
        self.assertEqual(self.request("GET", route)[1], paused)
        self.assertEqual(self.request("POST", route + "/sample", {"revision": 2})[0], 409)
        self.request("POST", route + "/resume", {"revision": 2})
        with self.server.observation_lock:
            self.assertEqual(self.request("POST", route + "/sample", {"revision": 3})[0], 409)
        with patch("apps.server.observe.sample_once", side_effect=TimeoutError("Observation deadline reached.")):
            status, failed = self.request("POST", route + "/sample", {"revision": 3})
            self.assertEqual((status, failed["revision"], failed["cash"], failed["decisions"][0]["kind"]),
                             (200, 4, "25", "unavailable"))
        self.assertIsNone(self.request("GET", "/api/v1/workspace")[1]["account"])

    def test_closed_position_supersedes_inflight_mark(self):
        route = "/api/v1/public-runs/" + ID + "/positions/734"
        with self.server.store.connection() as db, patch.object(public_shadow, "timestamp", return_value=STARTED):
            public_shadow.create(db, ID, WALLET, "Paper", "25", "10")
        with self.server.store.connection() as db, patch.object(public_shadow, "timestamp", return_value="2020-01-02T00:00:00Z"):
            public_shadow.record(db, ID, 1, observed_buy(WALLET, "10.00", start=1577836810))
        entered, release = Event(), Event()
        def price(basis, *, include_payouts):
            self.assertTrue(include_payouts)
            entered.set()
            self.assertTrue(release.wait(4))
            return {"value": "9.5", "shares": basis["shares"]}

        with (patch("apps.server.http.public_marks.read_mark", side_effect=price),
              patch.object(self.server, "sample_sell", side_effect=lambda w, s: observed_sell(w, s, depth="19")),
              ThreadPoolExecutor(max_workers=1) as pool):
            release.set()
            self.assertEqual(self.request("POST", route + "/mark", {"revision": 2}), (200, {"value": "9.5", "shares": "19"}))
            entered.clear()
            release.clear()
            pending = pool.submit(self.request, "POST", route + "/mark", {"revision": 2})
            try:
                self.assertTrue(entered.wait(3))
                status, closed = self.request("POST", route + "/observe-sell", {"revision": 2, "maxShares": "19"})
                self.assertEqual((status, closed["revision"], closed["positions"]), (200, 3, []))
            finally:
                release.set()
            self.assertEqual(pending.result()[0], 409)

    def test_stop_supersedes_inflight_sell_and_valuation(self):
        route = "/api/v1/public-runs/" + ID
        with self.server.store.connection() as db, patch.object(public_shadow, "timestamp", return_value="2020-01-01T00:00:00Z"):
            public_shadow.create(db, ID, WALLET, "Paper", "25", "10")
        with self.server.store.connection() as db:
            public_shadow.record(db, ID, 1, observed_buy(WALLET, "10.00"))
        sell = route + "/positions/734/observe-sell"
        for limit in ("0", "20", "1.2", 1):
            self.assertEqual(400, self.request("POST", sell, {"revision": 2, "maxShares": limit})[0])
        self.assertEqual(409, self.request("POST", sell, {"revision": 1, "maxShares": "5"})[0])
        selling, pricing, release = Event(), Event(), Event()
        self.assertEqual(400, self.request("POST", route + "/valuation", {"revision": 2, "includePayouts": "false"})[0])

        def sample(wallet, scope):
            selling.set()
            self.assertTrue(release.wait(4))
            return {"wallet": wallet, "exitScope": scope, "status": "waiting", "reason": "Quiet window."}

        def price(basis):
            pricing.set()
            self.assertTrue(release.wait(4))
            return {"revision": basis["revision"]}

        with (patch.object(self.server, "sample_sell", side_effect=sample),
              patch("apps.server.http.public_marks.portfolio_value", side_effect=price),
              ThreadPoolExecutor(max_workers=2) as workers):
            sale = workers.submit(self.request, "POST", sell, {"revision": 2, "maxShares": "5"})
            value = workers.submit(self.request, "POST", route + "/valuation", {"revision": 2, "includePayouts": True})
            try:
                self.assertTrue(selling.wait(3) and pricing.wait(3))
                self.assertEqual(409, self.request("POST", route + "/valuation", {"revision": 2})[0])
                status, stopped = self.request("POST", route + "/stop", {"revision": 2})
                self.assertEqual((200, "stopped", "19"), (status, stopped["status"], stopped["positions"][0]["shares"]))
            finally:
                release.set()
            self.assertEqual((409, 409), (sale.result()[0], value.result()[0]))
        self.assertEqual(self.request("GET", route)[1], stopped)
        self.assertEqual([d["kind"] for d in self.request("GET", route + "?view=trades")[1]["decisions"]], ["entry"])

    def test_public_profile_is_stateless_and_rejects_invalid_wallets(self):
        status, inspected = self.request("GET", "/api/v1/public/traders/" + ADDRESS)
        self.assertEqual((status, inspected["address"]), (200, ADDRESS.lower()))
        self.assertIsNone(self.request("GET", "/api/v1/workspace")[1]["account"])
        self.assertEqual(self.request("GET", "/api/v1/public/traders/unknown")[0], 400)
        self.assertEqual(self.request("GET", "/api/v1/public/leaders?period=unknown")[0], 400)

    def test_public_holdings_value_preserves_watch_and_covers_whole_wallet(self):
        saved = self.request("POST", "/api/v1/account", {"address": ADDRESS, "revision": 0})
        self.assertEqual(saved[0], 200)
        before = self.request("GET", "/api/v1/workspace")
        trader = "0x" + "cd" * 20
        route = f"/api/v1/public/traders/{trader}/value"
        with patch("apps.server.provider.read_public_json", return_value={"data": {"proxy_wallet": trader, "value": 0}}) as read:
            self.assertEqual(self.request("GET", route + "?condition=some-market")[0], 400)
            read.assert_not_called()
            status, result = self.request("GET", route)
            self.assertEqual((status, result["address"], result["value"]), (200, trader, "0"))
            read.assert_called_once()
        self.assertEqual(self.request("GET", "/api/v1/workspace"), before)

    def test_watch_refresh_failure_and_disconnect(self):
        calls = []

        def inspect(address):
            calls.append(address)
            result = public_snapshot(address)
            if len(calls) > 1:
                result.update(status="unavailable", positions=[], observedAt=None, complete=False,
                              message="Provider unavailable.")
            return result

        self.server.inspect_account = inspect
        self.assertEqual(400, self.request("POST", "/api/v1/account", {"address": "invalid", "revision": 0})[0])
        self.assertEqual([], calls)
        with self.assertLogs("apps.server.http", level="INFO") as logs:
            status, account = self.request("POST", "/api/v1/account", {"address": ADDRESS, "revision": 0})
        self.assertEqual(len(logs.output), 2)
        self.assertEqual(logs.records[0].args[0], logs.records[1].args[0])
        self.assertIn("positions lookup available", logs.output[0])
        self.assertNotIn(ADDRESS.lower(), " ".join(logs.output).lower())
        self.assertEqual((200, ADDRESS.lower(), "2.50"), (status, account["address"], account["positions"][0]["shares"]))
        self.assertEqual(account, self.request("GET", "/api/v1/workspace")[1]["account"])
        _, refresh = self.request("POST", "/api/v1/account", {"address": ADDRESS, "revision": 1})
        self.assertEqual(("unavailable", None, False), (refresh["status"], refresh["observedAt"], refresh["complete"]))
        self.assertEqual((200, {"account": None}), self.request("DELETE", "/api/v1/account", {"revision": 2}))
        self.assertIsNone(self.request("GET", "/api/v1/workspace")[1]["account"])
        self.assertEqual([ADDRESS.lower()] * 2, calls)

    def test_watch_preserves_only_the_latest_success_for_the_same_wallet(self):
        path = "/api/v1/account"
        other = "0x" + "22" * 20
        latest = {**public_snapshot(ADDRESS.lower()), "complete": False,
                  "observedAt": "2026-11-03T12:23:45Z", "nextCursor": "more"}

        def update(address, revision):
            status, record = self.request("POST", path, {"address": address, "revision": revision})
            self.assertEqual(status, 200)
            return record

        update(ADDRESS, 0)
        self.server.inspect_account = lambda address: latest
        update(ADDRESS, 1)

        def unavailable(address):
            return {**public_snapshot(address), "status": "unavailable",
                    "observedAt": None, "positions": [], "complete": False}

        self.server.inspect_account = unavailable
        failed = update(ADDRESS, 2)
        retained = {key: latest[key] for key in ("source", "observedAt", "positions", "complete")}
        self.assertEqual(failed["positions"], [])
        self.assertEqual(failed["lastSuccessful"], retained)
        self.shutdown()
        self.launch()
        self.assertEqual(self.request("GET", "/api/v1/workspace")[1]["account"], failed)
        self.server.inspect_account = unavailable
        self.assertEqual(update(ADDRESS, 3)["lastSuccessful"], retained)
        # Stateless profile reads and other watches cannot reveal the retained rows.
        self.assertNotIn("lastSuccessful", self.request("GET", "/api/v1/public/traders/" + ADDRESS)[1])
        self.assertNotIn("lastSuccessful", update(other, 4))
        self.assertNotIn("lastSuccessful", update(ADDRESS, 5))
        self.server.inspect_account = public_snapshot
        self.assertNotIn("lastSuccessful", update(ADDRESS, 6))
        self.server.inspect_account = unavailable
        self.assertIn("lastSuccessful", update(ADDRESS, 7))
        self.assertEqual(self.request("DELETE", path, {"revision": 8})[0], 200)
        self.assertNotIn("lastSuccessful", update(ADDRESS, 9))

    def test_stale_tab_cannot_replace_or_forget_a_different_account(self):
        path = "/api/v1/account"
        revision = self.request("GET", "/api/v1/workspace")[1]["accountRevision"]
        second_address = "0x" + "01" * 20
        status, second = self.request("POST", path, {"address": second_address, "revision": revision})
        self.assertEqual(200, status)
        self.server.inspect_account = lambda _: self.fail("A stale request reached the provider")
        self.assertEqual(409, self.request("POST", path, {"address": ADDRESS, "revision": revision})[0])
        self.assertEqual(409, self.request("DELETE", path, {"revision": revision})[0])
        self.assertEqual(400, self.request("DELETE", path, {"revision": True})[0])
        workspace = self.request("GET", "/api/v1/workspace")[1]
        self.assertEqual(second, workspace["account"])
        self.assertEqual(revision + 1, workspace["accountRevision"])

    def test_disconnect_wins_over_inflight_watch(self):
        started, released = Event(), Event()

        def delayed(address):
            started.set()
            released.wait(3)
            return public_snapshot(address)

        self.server.inspect_account = delayed
        with ThreadPoolExecutor(max_workers=1) as pool:
            attempt = pool.submit(self.request, "POST", "/api/v1/account", {"address": ADDRESS, "revision": 0})
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(200, self.request("DELETE", "/api/v1/account", {"revision": 0})[0])
            finally:
                released.set()
            self.assertEqual(409, attempt.result(timeout=3)[0])
        self.assertIsNone(self.request("GET", "/api/v1/workspace")[1]["account"])

    def test_replay_duplicate_steps_restart_and_stop_leave_attributed_position(self):
        _, directory = self.request("GET", "/api/v1/leaders")
        creation = {"leaderId": directory["leaders"][0]["id"], "allocation": "100.00", "orderSize": "10.00"}
        status, run = self.request("POST", "/api/v1/runs", creation)
        self.assertEqual((200, "shadow", "0", []), (status, run["mode"], run["quantity"], run["events"]))
        self.assertEqual(409, self.request("POST", "/api/v1/runs", creation)[0])
        route = "/api/v1/runs/" + run["id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = [pool.submit(self.request, "POST", route + "/step", {"revision": run["revision"]}) for _ in range(2)]
            self.assertEqual([200, 409], sorted(f.result()[0] for f in attempts))
        _, first = self.request("GET", route)
        self.assertEqual(1, len(first["events"]))
        self.assertGreater(int(first["quantity"]), 0)
        _, paused = self.request("POST", route + "/pause", {"revision": first["revision"]})
        self.shutdown()
        self.launch()
        self.assertEqual(paused, self.request("GET", "/api/v1/workspace")[1]["run"])
        _, stopped = self.request("POST", route + "/stop", {"revision": paused["revision"]})
        self.assertEqual(("stopped", first["quantity"], first["cash"]), (stopped["status"], stopped["quantity"], stopped["cash"]))
        self.assertEqual(400, self.request("POST", route + "/resume", {"revision": stopped["revision"]})[0])
        status, second = self.request("POST", "/api/v1/runs", creation)
        self.assertEqual((200, "0", "100.00"), (status, second["quantity"], second["cash"]))
        self.assertEqual(stopped, self.request("GET", route)[1])
        _, history = self.request("GET", "/api/v1/runs")
        archived = history["runs"][1]
        self.assertEqual((stopped["id"], "-0.265", "0.00"),
                         (archived["id"], archived["marked_net_result"], archived["realized_pnl"]))

    def test_foreign_origins_unsupported_fields_and_authority_rejected(self):
        data = {"version": 1, "revision": 0, "theme": "dark"}
        for header in ({"Host": "unrelated.example"}, {"Origin": "https://unrelated.example"},
                       {"X-Forwarded-For": "192.0.2.1"}):
            self.assertEqual(403, self.request("PUT", "/api/v1/settings", data, header)[0])
        self.assertEqual(415, self.request("PUT", "/api/v1/settings", data, {"Content-Type": "text/plain"})[0])
        for invalid in ({**data, "live": True}, {**data, "version": True}, {**data, "revision": "0"},
                        {**data, "theme": []}, {**data, "theme": "other"}):
            self.assertEqual(400, self.request("PUT", "/api/v1/settings", invalid)[0])
        self.assertEqual(404, self.request("POST", "/api/v1/trade", {})[0])
        self.assertEqual("light", self.request("GET", "/api/v1/workspace")[1]["settings"]["theme"])

    def test_history_pagination_is_stable_across_new_runs(self):
        creation = {"leaderId": "atlas", "allocation": "100", "orderSize": "10"}

        def finished_run():
            _, run = self.request("POST", "/api/v1/runs", creation)
            self.request("POST", "/api/v1/runs/" + run["id"] + "/stop", {"revision": run["revision"]})
            return run["id"]

        ids = [finished_run() for _ in range(21)]
        _, first = self.request("GET", "/api/v1/runs")
        self.assertEqual(ids[:0:-1], [r["id"] for r in first["runs"]])
        self.assertNotIn("events", first["runs"][0])
        finished_run()
        _, second = self.request("GET", "/api/v1/runs?before=" + first["nextCursor"])
        self.assertEqual([ids[0]], [r["id"] for r in second["runs"]])
        self.assertIsNone(second["nextCursor"])
        self.assertEqual(400, self.request("GET", "/api/v1/runs?before=missing")[0])

    def test_restore_requires_the_exact_workspace_schema(self):
        additions = (
            "CREATE TRIGGER audit_insert AFTER INSERT ON runs BEGIN SELECT 1; END",
            "CREATE VIEW run_ids AS SELECT id FROM runs",
            "CREATE INDEX by_theme ON workspace(theme)",
            "CREATE TABLE notes (body TEXT)",
            "ALTER TABLE runs ADD COLUMN label TEXT",
        )
        for index, ddl in enumerate(additions):
            with self.subTest(ddl=ddl):
                source = self.root / f"source-{index}.db"
                destination = self.root / f"restore-{index}.db"
                Workspace(source)
                with sqlite3.connect(source) as db:
                    db.execute(ddl)
                with self.assertRaisesRegex(ValueError, "workspace schema"):
                    copy_workspace(source, destination)
                self.assertFalse(destination.exists())
                self.assertEqual(list(self.root.glob(".polysia-backup-*")), [])

    def test_restore_refuses_unreadable_history_and_disagreeing_balances(self):
        store = self.server.store
        old = store.create_run("atlas", "100", "10")
        store.change_run(old["id"], "step", old["revision"])
        store.change_run(old["id"], "step", old["revision"] + 1)
        old = store.change_run(old["id"], "stop", old["revision"] + 2)
        store.create_run("mira", "20", "5")  # Damage is in an older run.
        destination = self.root / "recovered.db"
        altered_fill = {**old["events"][0], "quantity": 19.9}
        first, second = old["events"]
        # Add exactly one dollar to each total; their difference still reconciles.
        inflated_basis = str(Decimal(old["cost_basis"]) + 1)
        for corrupted in ("{", "{}", json.dumps({**old, "fees": "0.00"}),
                          json.dumps({**old, "cost_basis": inflated_basis, "realized_pnl": "1.00"}),
                          json.dumps({**old, "remaining_steps": 0}),
                          json.dumps({**old, "marked_value": "NaN"}),
                          json.dumps({**old, "events": [altered_fill, second]}),
                          json.dumps({**old, "order_size": "9.60"}),
                          json.dumps({**old, "events": [first, {**second, "source_order": first["source_order"]}]}),
                          json.dumps({**old, "events": [{**first, "entry_state": "paused"}, second]})):
            with self.subTest(corrupted=corrupted), sqlite3.connect(store.path) as db:
                db.execute("UPDATE runs SET record = ? WHERE id = ?", (corrupted, old["id"]))
                db.commit()
                self.assertEqual(db.execute("PRAGMA quick_check").fetchone(), ("ok",))
                with self.assertRaisesRegex(ValueError, "Saved replay .* failed its integrity check"):
                    copy_workspace(store.path, destination)
                self.assertFalse(destination.exists())

    def test_restore_checks_retained_position_pages_and_accepts_older_rows(self):
        store = self.server.store
        account = public_snapshot(ADDRESS.lower())
        historical = {key: account[key] for key in ("source", "positions", "observedAt", "complete")}
        failed = {**account, "status": "unavailable", "positions": [], "observedAt": None,
                  "complete": False, "lastSuccessful": historical}
        store.save_account(account, 0)
        store.save_account(failed, 1)
        destination = self.root / "legacy-positions.db"
        copy_workspace(store.path, destination)
        self.assertEqual(Workspace(destination).read()["account"], failed)
        historical["positions"] = [None]
        with sqlite3.connect(store.path) as db:
            db.execute("UPDATE workspace SET account = ? WHERE id = 1", (json.dumps(failed),))
        with self.assertRaisesRegex(ValueError, "saved account watch"):
            copy_workspace(store.path, self.root / "bad.db")
        self.assertFalse((self.root / "bad.db").exists())

    def test_accent_publication_is_independent_validated_and_owner_scoped(self):
        route = "/api/v1/settings/accent"
        valid = {"preset": "ocean", "revision": 0}
        self.assertEqual(self.request("PUT", route, valid, headers={"Origin": "https://elsewhere.invalid"})[0], 403)
        for invalid in ({"preset": "#fff", "revision": 0}, {"preset": ["ocean"], "revision": 0},
                        {**valid, "revision": True}, {**valid, "theme": "dark"}):
            self.assertEqual(self.request("PUT", route, invalid)[0], 400)
        self.assertEqual(self.request("PUT", route, valid), (200, {"preset": "ocean", "revision": 1}))
        self.assertEqual(self.request("PUT", route, {"preset": "forest", "revision": 0})[0], 409)
        self.assertEqual(self.request("PUT", "/api/v1/settings", {"version": 1, "revision": 0, "theme": "dark"})[0], 200)
        self.assertEqual(self.server.store.read()["accent"], {"preset": "ocean", "revision": 1})
        self.assertEqual(self.request("PUT", route, {"preset": "forest", "revision": 1})[0], 200)
        self.assertEqual(self.server.store.read()["settings"], {"version": 1, "revision": 1, "theme": "dark"})

    def test_completed_replay_with_sales_round_trips_through_backup(self):
        store = self.server.store
        run = store.create_run("atlas", "100", "10")
        while run["remaining_steps"]:
            run = store.change_run(run["id"], "step", run["revision"])
        self.assertTrue(any(e["side"] == "SELL" and e["status"] != "skipped" for e in run["events"]))
        destination = self.root / "completed.db"
        copy_workspace(store.path, destination)
        self.assertEqual(Workspace(destination).get_run(run["id"]), run)

    def test_competing_backups_publish_one_verified_snapshot(self):
        first = self.server.store
        second = Workspace(self.root / "second.db")
        second.set_theme(1, 0, "dark")
        target = self.root / "shared-backup.db"
        ready = Barrier(2)
        publish = os.link

        def publish_together(staging, destination):
            ready.wait(timeout=5)
            publish(staging, destination)

        with patch("apps.server.archive.os.link", side_effect=publish_together), ThreadPoolExecutor(2) as pool:
            jobs = [(store, pool.submit(copy_workspace, store.path, target)) for store in (first, second)]
            winners = []
            for store, job in jobs:
                try:
                    job.result(timeout=10)
                    winners.append(store)
                except FileExistsError:
                    pass
        self.assertEqual(len(winners), 1)
        self.assertEqual(Workspace(target).read(), winners[0].read())
        self.assertEqual(list(self.root.glob(".polysia-backup-*")), [])

    def test_online_backup_and_restore_to_new_database_preserve_workspace(self):
        env = {**os.environ, "POLYSIA_DB": str(self.root / "workspace.db")}
        self.request("PUT", "/api/v1/settings", {"version": 1, "revision": 0, "theme": "dark"})
        _, run = self.request("POST", "/api/v1/runs", {"leaderId": "atlas", "allocation": "100", "orderSize": "10"})
        route = "/api/v1/runs/" + run["id"]
        _, filled = self.request("POST", route + "/step", {"revision": run["revision"]})
        self.request("POST", route + "/pause", {"revision": filled["revision"]})
        expected = self.request("GET", "/api/v1/workspace")[1]
        backup, restored = self.root / "backup.sqlite3", self.root / "restored.sqlite3"
        cli = [sys.executable, "-m", "apps.server"]

        def invoke(*args, check=True):
            return subprocess.run([*cli, *args], cwd=Path(__file__).resolve().parents[1],
                                  env=env, capture_output=True, check=check, timeout=5)

        invoke("backup", "--to", backup)
        duplicate = invoke("backup", "--to", backup, check=False)
        self.assertNotEqual(0, duplicate.returncode)
        self.assertIn(b"already exists", duplicate.stderr)
        self.request("POST", route + "/stop", {"revision": expected["run"]["revision"]})
        invoke("restore", "--from", backup, "--to", restored)
        recovered = Workspace(restored)
        self.assertEqual(expected, recovered.read())
        recovered.set_theme(1, expected["settings"]["revision"], "light")
        self.assertEqual(expected["run"], recovered.get_run(run["id"]))
        self.assertEqual("paused", expected["run"]["status"])
        self.assertGreater(int(expected["run"]["quantity"]), 0)
        conflict = invoke("restore", "--from", backup, "--to", self.root / "workspace.db", check=False)
        self.assertNotEqual(0, conflict.returncode)
        self.assertEqual("stopped", self.request("GET", route)[1]["status"])
        invalid = self.root / "invalid.sqlite3"
        invalid.write_text("unrelated data")
        bad_dest = self.root / "bad-restore.sqlite3"
        self.assertNotEqual(0, invoke("restore", "--from", invalid, "--to", bad_dest, check=False).returncode)
        self.assertFalse(bad_dest.exists())


if __name__ == "__main__":
    unittest.main()
