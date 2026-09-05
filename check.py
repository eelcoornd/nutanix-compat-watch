#!/usr/bin/env python3
"""
Weekly check of Nutanix Compatibility & Interoperability Matrix (Platform Compatibility)
for two platforms, AHV hypervisor, sorted by latest AOS version.

Source: https://portal.nutanix.com/api/v1/compatibilityMatrixPlatform
(public JSON API backing the portal UI; no auth needed; query params are
ignored by the server, so we fetch the full dataset and filter locally).

Writes/updates data.json and index.html in the repo root, and prints a
one-line summary (used by the cron job as the notification body / commit msg).
"""
import json
import os
import sys
import datetime
import urllib.request

PLATFORMS = [
    {
        "key": "NX-1175S-G8",
        "label": "NX-1175S-G8 (Ice Lake, AHV)",
        "platform": "NX-1175S-G8",
    },
    {
        "key": "NX-1175S-G10",
        "label": "NX-1175S-G10 (Intel Xeon 6505P / Granite Rapids, AHV)",
        "platform": "NX-1175S-G10",
    },
]

API_URL = "https://portal.nutanix.com/api/v1/compatibilityMatrixPlatform"
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def ver_key(v):
    parts = []
    for p in str(v).split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return parts


def fetch_all():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def latest_for_platform(rows, platform_name):
    pairs = []
    for row in rows:
        plats = row.get("platform") or []
        if platform_name not in plats:
            continue
        ahvs = [h for h in (row.get("hypervisor") or []) if h.startswith("AHV")]
        if not ahvs:
            continue
        for aos in row.get("aos") or []:
            for ahv in ahvs:
                pairs.append((aos, ahv))
    if not pairs:
        return None
    pairs.sort(key=lambda p: ver_key(p[0]), reverse=True)
    aos, ahv = pairs[0]
    return {"aos": aos, "ahv": ahv}


def load_previous():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"platforms": {}}


def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def render_html(data):
    rows_html = []
    for p in PLATFORMS:
        info = data["platforms"].get(p["key"], {})
        latest = info.get("latest", {})
        changed = info.get("changed_at")
        badge = f'<span class="new">NEW as of {changed}</span>' if info.get("is_new") else ""
        err = info.get("check_error")
        err_html = f'<div class="err">check error: {err}</div>' if err else ""
        rows_html.append(f"""
        <tr>
          <td>{p['label']}</td>
          <td><code>{latest.get('aos', 'unknown')}</code></td>
          <td><code>{latest.get('ahv', 'unknown')}</code></td>
          <td>{badge}{err_html}</td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Nutanix Compatibility Watch</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 16px; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #ddd; }}
  th {{ background: #f5f5f5; }}
  code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }}
  .new {{ background: #ffe58f; color: #7a4a00; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 600; }}
  .err {{ color: #b00; font-size: 0.85em; margin-top: 4px; }}
  .meta {{ color: #666; font-size: 0.9em; margin-top: 1.5rem; }}
  a {{ color: #0969da; }}
</style>
</head>
<body>
  <h1>Nutanix Platform Compatibility Watch</h1>
  <p>Latest supported AOS / recommended AHV version per platform (source: Nutanix Compatibility &amp; Interoperability Matrix, AHV hypervisor). Checked weekly.</p>
  <table>
    <thead><tr><th>Platform</th><th>Latest AOS</th><th>Recommended AHV</th><th></th></tr></thead>
    <tbody>{''.join(rows_html)}</tbody>
  </table>
  <p class="meta">Last checked: {data.get('last_checked', 'never')} &middot;
    <a href="https://portal.nutanix.com/page/compatibility-interoperability-matrix/platform-compatibility?selectedHypervisorTypes=AHV&selectedHardwareVendors=Nutanix&selectedHardwares=NX-1175S-G8&selectedAos=all&selectedHypervisors=all">source matrix (G8)</a>
    &middot; <a href="https://portal.nutanix.com/page/compatibility-interoperability-matrix/platform-compatibility?selectedHypervisorTypes=AHV&selectedHardwareVendors=Nutanix&selectedHardwares=NX-1175S-G10&selectedAos=all&selectedHypervisors=all">source matrix (G10)</a>
    &middot; <a href="https://github.com/eelcoornd/nutanix-compat-watch">repo / history</a>
  </p>
</body>
</html>"""
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "w") as f:
        f.write(html)


def main():
    data = load_previous()
    data.setdefault("platforms", {})
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    data["last_checked"] = now

    summary_lines = []
    any_new = False

    try:
        rows = fetch_all()
        fetch_err = None
    except Exception as e:
        rows = None
        fetch_err = str(e)

    for p in PLATFORMS:
        prev = data["platforms"].get(p["key"], {})
        prev_latest = prev.get("latest", {})

        if rows is None:
            summary_lines.append(f"{p['label']}: AUTO-CHECK FAILED ({fetch_err}) -- needs manual check")
            data["platforms"][p["key"]] = {**prev, "check_error": fetch_err}
            continue

        latest = latest_for_platform(rows, p["platform"])
        if latest is None:
            summary_lines.append(f"{p['label']}: no data found for platform in API response")
            data["platforms"][p["key"]] = {**prev, "check_error": "platform not found in API response"}
            continue

        is_new = bool(latest.get("aos")) and latest.get("aos") != prev_latest.get("aos")
        entry = {
            "latest": latest,
            "is_new": is_new,
            "changed_at": now if is_new else prev.get("changed_at"),
            "check_error": None,
        }
        data["platforms"][p["key"]] = entry
        if is_new:
            any_new = True
            summary_lines.append(
                f"{p['label']}: NEW latest AOS {latest.get('aos')} (AHV {latest.get('ahv')}), was {prev_latest.get('aos', 'unknown')}"
            )
        else:
            summary_lines.append(f"{p['label']}: unchanged, latest AOS {latest.get('aos')}")

    save(data)
    render_html(data)

    print("\n".join(summary_lines))
    print(f"ANY_NEW={'1' if any_new else '0'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
