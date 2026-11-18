# 📶 WiFiLog

See **who is on your home WiFi** and **collect your router's logs**, all in one local dashboard.
Pure Python (standard library only). No installs, no cloud, and your data stays on your computer.

## Run it (on a computer connected to your WiFi)
1. Install Python 3.9+ from python.org (Windows: tick "Add to PATH").
2. Download this `wifilog` folder.
3. Run `python wifilog.py` (Windows) or `python3 wifilog.py` (Mac/Linux).
4. Open **http://127.0.0.1:8080**.

Quick one-off list of devices: `python3 wifilog.py --once`

## What you get
- **Devices**: every device on your WiFi, with IP, MAC, hostname, first/last seen, and online/offline status.
- **Activity log**: when devices join or leave, IP changes, and an 🚨 **alert when an unknown device appears**.
- **Label and trust** devices ("Mum's iPhone"). Untrusted devices stay flagged.
- **Router logs**: point your router's *Remote/System Log (syslog)* setting at your PC. The dashboard shows the step-by-step instructions.
- **CSV export** for devices, events, and router logs. History is stored in `wifilog.db` (SQLite).

## Options
| Flag | Default | Purpose |
|---|---|---|
| `--subnet 192.168.0.0/24` | auto | Network to scan |
| `--interval 60` | 60 | Seconds between scans |
| `--port 8080` | 8080 | Dashboard port |
| `--syslog-port 514` | 5514 | Router log port (514 needs admin/sudo; 0 = off) |

## Limits (honest)
- It sees devices that answer on the network at scan time. Phones that are asleep may show as offline briefly.
- Phones using a "private WiFi address" show a random MAC (flagged as *private MAC*).
- Router logs need your router to support remote syslog (most TP-Link, Netgear, ASUS, OpenWrt, and Ubiquiti routers do; some ISP boxes don't).
- Use it only on networks you own or are authorised to monitor.
