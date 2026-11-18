#!/usr/bin/env python3
"""
WiFiLog — see who is on your home WiFi and collect your router's logs.

Runs on your own computer (Windows / macOS / Linux), connected to your WiFi.
Pure Python standard library: no installs, no cloud, all data stays local.

  python3 wifilog.py                 # scan every 60s + dashboard on http://127.0.0.1:8080
  python3 wifilog.py --once          # one scan, print the table, exit
  python3 wifilog.py --syslog-port 514   # receive router logs on the standard port (needs admin/sudo)

Only use this on networks you own or are authorised to monitor.
"""
import argparse
import csv
import io
import ipaddress
import json
import platform
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

OS = platform.system()  # 'Windows', 'Darwin', 'Linux'
MAC_RE = re.compile(r"((?:[0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2})")
IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")
DB_LOCK = threading.Lock()


def now():
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- database
class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices(
              mac TEXT PRIMARY KEY, ip TEXT, hostname TEXT, label TEXT DEFAULT '',
              trusted INTEGER DEFAULT 0, first_seen TEXT, last_seen TEXT, online INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, mac TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS syslog(
              id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, source TEXT, message TEXT);
            """
        )
        self.db.commit()

    def q(self, sql, args=(), commit=False):
        with DB_LOCK:
            cur = self.db.execute(sql, args)
            if commit:
                self.db.commit()
            return [dict(r) for r in cur.fetchall()]

    def event(self, kind, mac, detail):
        self.q("INSERT INTO events(ts,kind,mac,detail) VALUES(?,?,?,?)",
               (now(), kind, mac, detail), commit=True)
        print(f"[{now()}] {kind.upper():8} {mac}  {detail}", flush=True)

    def record_scan(self, found):
        """found: {mac: (ip, hostname)} -> logs joins / leaves / new devices."""
        ts = now()
        known = {d["mac"]: d for d in self.q("SELECT * FROM devices")}
        for mac, (ip, host) in found.items():
            d = known.get(mac)
            if d is None:
                self.q("INSERT INTO devices(mac,ip,hostname,first_seen,last_seen,online) "
                       "VALUES(?,?,?,?,?,1)", (mac, ip, host, ts, ts), commit=True)
                self.event("new", mac, f"NEW DEVICE {ip} {host or ''} {mac_note(mac)}".strip())
            else:
                if not d["online"]:
                    self.event("joined", mac, f"{d['label'] or host or ip} came online ({ip})")
                if d["ip"] != ip:
                    self.event("ip", mac, f"IP changed {d['ip']} -> {ip}")
                self.q("UPDATE devices SET ip=?, hostname=COALESCE(NULLIF(?,''),hostname), "
                       "last_seen=?, online=1 WHERE mac=?", (ip, host, ts, mac), commit=True)
        for mac, d in known.items():
            if d["online"] and mac not in found:
                self.q("UPDATE devices SET online=0 WHERE mac=?", (mac,), commit=True)
                self.event("left", mac, f"{d['label'] or d['hostname'] or d['ip']} went offline")


def mac_note(mac):
    # Phones/laptops with "private WiFi address" set the locally-administered bit.
    try:
        return "(randomised/private MAC)" if int(mac.split(":")[0], 16) & 2 else ""
    except ValueError:
        return ""


# ---------------------------------------------------------------- scanning
def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the WiFi interface
        return s.getsockname()[0]
    finally:
        s.close()


def ping(ip):
    if OS == "Windows":
        cmd = ["ping", "-n", "1", "-w", "600", ip]
    elif OS == "Darwin":
        cmd = ["ping", "-c", "1", "-t", "1", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except Exception:
        pass


def norm_mac(m):
    return ":".join(p.zfill(2) for p in re.split("[:-]", m.lower()))


def read_arp_table():
    cmds = [["ip", "neigh"], ["arp", "-a"]] if OS == "Linux" else [["arp", "-a"]]
    table = {}
    for cmd in cmds:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
        except Exception:
            continue
        for line in out.splitlines():
            ip, mac = IP_RE.search(line), MAC_RE.search(line)
            if not ip or not mac or "FAILED" in line or "incomplete" in line:
                continue
            m = norm_mac(mac.group(1))
            first = int(m.split(":")[0], 16)
            if m == "ff:ff:ff:ff:ff:ff" or m == "00:00:00:00:00:00" or first & 1:
                continue  # broadcast / multicast
            table[m] = ip.group(1)
        if table:
            break
    return table


def hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def scan(subnet):
    net = ipaddress.ip_network(subnet, strict=False)
    with ThreadPoolExecutor(max_workers=64) as pool:
        list(pool.map(ping, [str(h) for h in net.hosts()]))
    arp = {m: ip for m, ip in read_arp_table().items() if ipaddress.ip_address(ip) in net}
    me_ip = local_ip()
    node = uuid.getnode()
    if ipaddress.ip_address(me_ip) in net and not (node >> 40) & 1:  # skip if OS gave a fake MAC
        arp[norm_mac(":".join(f"{(node >> i) & 0xff:02x}" for i in range(40, -1, -8)))] = me_ip
    with ThreadPoolExecutor(max_workers=32) as pool:
        names = dict(zip(arp, pool.map(hostname, arp.values())))
    return {m: (ip, names[m]) for m, ip in arp.items()}


def scan_loop(store, subnet, interval, stop):
    while not stop.is_set():
        try:
            found = scan(subnet)
            store.record_scan(found)
        except Exception as e:
            print("scan error:", e, file=sys.stderr)
        stop.wait(interval)


# ---------------------------------------------------------------- syslog receiver
def syslog_loop(store, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as e:
        print(f"! Could not open syslog port {port}: {e}  (try --syslog-port 5514, or run as admin)",
              file=sys.stderr)
        return
    print(f"* Router log receiver listening on UDP {port}")
    while True:
        data, addr = sock.recvfrom(8192)
        msg = re.sub(r"^<\d+>", "", data.decode("utf-8", "replace")).strip()
        store.q("INSERT INTO syslog(ts,source,message) VALUES(?,?,?)", (now(), addr[0], msg), commit=True)


# ---------------------------------------------------------------- dashboard
PAGE = (Path(__file__).with_name("dashboard.html"))


def make_handler(store, ctx):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/state":
                return self.send(200, json.dumps({
                    "info": ctx,
                    "devices": store.q("SELECT * FROM devices ORDER BY online DESC, last_seen DESC"),
                    "events": store.q("SELECT * FROM events ORDER BY id DESC LIMIT 300"),
                    "syslog": store.q("SELECT * FROM syslog ORDER BY id DESC LIMIT 500"),
                }))
            if path.endswith(".csv") and path[1:-4] in ("devices", "events", "syslog"):
                rows = store.q(f"SELECT * FROM {path[1:-4]} ORDER BY 1")
                buf = io.StringIO()
                if rows:
                    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
                    w.writeheader()
                    w.writerows(rows)
                return self.send(200, buf.getvalue(), "text/csv")
            self.send(404, '{"error":"not found"}')

        def do_POST(self):
            path = urlparse(self.path).path
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if path == "/api/device":
                store.q("UPDATE devices SET label=?, trusted=? WHERE mac=?",
                        (str(body.get("label", ""))[:60], 1 if body.get("trusted") else 0, body["mac"]),
                        commit=True)
                return self.send(200, '{"ok":true}')
            if path == "/api/scan":
                threading.Thread(target=lambda: store.record_scan(scan(ctx["subnet"])), daemon=True).start()
                return self.send(200, '{"ok":true}')
            self.send(404, '{"error":"not found"}')
    return H


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="See who is on your WiFi and collect router logs.")
    ap.add_argument("--subnet", help="e.g. 192.168.1.0/24 (auto-detected)")
    ap.add_argument("--interval", type=int, default=60, help="seconds between scans (default 60)")
    ap.add_argument("--port", type=int, default=8080, help="dashboard port (default 8080)")
    ap.add_argument("--syslog-port", type=int, default=5514, help="UDP port for router logs (0 = off)")
    ap.add_argument("--db", default=str(Path(__file__).with_name("wifilog.db")))
    ap.add_argument("--once", action="store_true", help="scan once, print, exit")
    a = ap.parse_args()

    ip = local_ip()
    subnet = a.subnet or str(ipaddress.ip_network(f"{ip}/24", strict=False))
    gateway = str(next(ipaddress.ip_network(subnet).hosts()))
    store = Store(a.db)
    print(f"* This computer: {ip}   network: {subnet}   router (likely): http://{gateway}")

    if a.once:
        found = scan(subnet)
        store.record_scan(found)
        print(f"\n{len(found)} devices on {subnet}\n{'IP':16} {'MAC':18} HOSTNAME")
        for mac, (dip, host) in sorted(found.items(), key=lambda kv: ipaddress.ip_address(kv[1][0])):
            print(f"{dip:16} {mac:18} {host} {mac_note(mac)}")
        return

    ctx = {"ip": ip, "subnet": subnet, "gateway": gateway, "syslog_port": a.syslog_port,
           "interval": a.interval}
    stop = threading.Event()
    threading.Thread(target=scan_loop, args=(store, subnet, a.interval, stop), daemon=True).start()
    if a.syslog_port:
        threading.Thread(target=syslog_loop, args=(store, a.syslog_port), daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(store, ctx))
    print(f"* Dashboard: http://127.0.0.1:{a.port}   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
