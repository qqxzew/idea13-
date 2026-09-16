"""Webovy server portalu zivotnich situaci MC Praha 13.

Spusteni (jeden prikaz, zadne zavislosti):

    python app.py

Server bezi lokalne, data cte z data/portal.sqlite3. Kdyz je databaze prazdna,
sam ji naplni ze souboru data/manual/situations.json. Vse funguje bez internetu.
"""

import argparse
import json
import mimetypes
import os
import posixpath
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import db
import seed

WEB_DIR = os.path.join(db.BASE_DIR, "web")


def situation_row(row):
    data = db.row_to_dict(row)
    data.pop("sort_order", None)
    return data


def step_row(row):
    data = db.row_to_dict(row)
    data["documents"] = db.load_json_column(data.get("documents"))
    return data


def list_situations(conn, query="", audience=""):
    sql = ["SELECT * FROM situations WHERE 1=1"]
    params = []
    if audience in ("citizen", "foreigner"):
        # 'all' situace se zobrazuji obema skupinam
        sql.append("AND audience IN ('all', ?)")
        params.append(audience)
    if query:
        like = "%" + db.normalize_text(query.strip()) + "%"
        sql.append("AND (norm(title_cs) LIKE ? OR norm(title_uk) LIKE ?"
                   " OR norm(title_ru) LIKE ?"
                   " OR norm(summary_cs) LIKE ?"
                   " OR norm(category) LIKE ?"
                   " OR norm(katalog_keywords) LIKE ?"
                   " OR id IN (SELECT situation_id FROM steps"
                   "            WHERE norm(title_cs) LIKE ? OR norm(authority) LIKE ?"
                   "               OR norm(documents) LIKE ?))")
        params.extend([like] * 9)
    if audience in ("citizen", "foreigner"):
        # situace primo pro danou skupinu davame nahoru, spolecne ('all') pod ne
        sql.append("ORDER BY CASE WHEN audience = ? THEN 0 ELSE 1 END, sort_order")
        params.append(audience)
    else:
        sql.append("ORDER BY sort_order")
    rows = conn.execute(" ".join(sql), params).fetchall()

    result = []
    for row in rows:
        item = situation_row(row)
        stats = conn.execute(
            "SELECT COUNT(*) AS steps,"
            " SUM(deadline_status='manual_todo') AS manual_todo,"
            " SUM(deadline_status='verified') AS verified"
            " FROM steps WHERE situation_id = ?", (row["id"],)).fetchone()
        item["step_count"] = stats["steps"] or 0
        item["manual_todo_count"] = stats["manual_todo"] or 0
        item["verified_count"] = stats["verified"] or 0
        result.append(item)
    return result


def get_situation(conn, slug):
    row = conn.execute("SELECT * FROM situations WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    data = situation_row(row)
    data["steps"] = [step_row(step) for step in conn.execute(
        "SELECT * FROM steps WHERE situation_id = ? ORDER BY step_order", (row["id"],)).fetchall()]

    # Souvisejici sluzby z Katalogu sluzeb verejne spravy, kdyz je stazeny.
    matches = []
    for keyword in (row["katalog_keywords"] or "").split(","):
        keyword = keyword.strip().lower()
        if len(keyword) < 4:
            continue
        for service in conn.execute(
                "SELECT id, code, name, agenda_name, ohlasovatel_name, source_url"
                " FROM katalog_services WHERE norm(name) LIKE ? LIMIT 3",
                ("%" + db.normalize_text(keyword) + "%",)).fetchall():
            item = db.row_to_dict(service)
            if item not in matches:
                matches.append(item)
    data["katalog_matches"] = matches[:8]

    page = None
    if row["praha13_url"]:
        page_row = conn.execute(
            "SELECT url, title, department, address, office_hours, responsible_department,"
            " deadline_text_raw, fetched_at FROM praha13_pages WHERE url = ?",
            (row["praha13_url"],)).fetchone()
        if page_row:
            page = db.row_to_dict(page_row)
    data["praha13_page"] = page
    return data


def stats(conn):
    data = db.counts(conn)
    data["categories"] = [r[0] for r in conn.execute(
        "SELECT DISTINCT category FROM situations ORDER BY category").fetchall()]
    data["parser_last_run"] = None
    row = conn.execute(
        "SELECT run_id, MIN(ts) AS ts FROM parse_log GROUP BY run_id"
        " ORDER BY ts DESC LIMIT 1").fetchone()
    if row:
        data["parser_last_run"] = {"run_id": row["run_id"], "ts": row["ts"]}
    return data


class Handler(BaseHTTPRequestHandler):
    server_version = "Praha13Portal/0.1"

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/"):
            sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _send(self, code, body, content_type, extra_headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, code=200):
        self._send(code, json.dumps(data, ensure_ascii=False, indent=1),
                   "application/json; charset=utf-8")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                return self.handle_api(path, query)
            return self.handle_static(path)
        except BrokenPipeError:
            pass
        except Exception as exc:  # demo nesmi spadnout na chybe jednoho requestu
            sys.stderr.write("CHYBA %s: %s\n" % (path, exc))
            self._json({"error": "vnitrni chyba serveru", "detail": str(exc)}, 500)

    def handle_api(self, path, query):
        conn = db.connect()
        try:
            if path == "/api/situations":
                return self._json({
                    "situations": list_situations(
                        conn,
                        query=(query.get("q") or [""])[0],
                        audience=(query.get("audience") or [""])[0]),
                })
            if path.startswith("/api/situations/"):
                slug = path[len("/api/situations/"):].strip("/")
                data = get_situation(conn, slug)
                if data is None:
                    return self._json({"error": "situace nenalezena", "slug": slug}, 404)
                return self._json(data)
            if path == "/api/katalog":
                from parsers.katalog import lookup
                rows = lookup(conn, (query.get("q") or [""])[0], limit=20)
                return self._json({"services": [db.row_to_dict(r) for r in rows]})
            if path == "/api/stats":
                return self._json(stats(conn))
            return self._json({"error": "neznamy endpoint", "path": path}, 404)
        finally:
            conn.close()

    def handle_static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        # zakaz vystupu z adresare web/
        safe = posixpath.normpath(path).lstrip("/")
        if safe.startswith("..") or os.path.isabs(safe):
            return self._send(403, "Zakazano", "text/plain; charset=utf-8")
        full = os.path.join(WEB_DIR, safe.replace("/", os.sep))
        if not os.path.isfile(full):
            return self._send(404, "Nenalezeno: %s" % path, "text/plain; charset=utf-8")
        content_type = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if content_type.startswith(("text/", "application/javascript", "application/json")):
            content_type += "; charset=utf-8"
        with open(full, "rb") as fh:
            return self._send(200, fh.read(), content_type)


def ensure_data(quiet=False):
    conn = db.init(db.connect())
    counts = db.counts(conn)
    if counts["situations"] == 0:
        if not quiet:
            print("Databaze je prazdna, plnim ji z data/manual/situations.json ...")
        situations = seed.load()
        errors = seed.validate(situations)
        if errors:
            conn.close()
            raise SystemExit("Data neprosla kontrolou:\n  - " + "\n  - ".join(errors))
        seed.seed(conn, situations)
        counts = db.counts(conn)
    conn.close()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Portal zivotnich situaci MC Praha 13")
    parser.add_argument("--port", type=int, default=8013)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-open", action="store_true",
                        help="neotevirat automaticky prohlizec")
    args = parser.parse_args(argv)

    counts = ensure_data()
    url = "http://%s:%d/" % (args.host, args.port)
    print("=" * 62)
    print(" Portal zivotnich situaci - MC Praha 13 (prototyp)")
    print(" Situaci: %d, kroku: %d (overenych lhut %d, k overeni %d)"
          % (counts["situations"], counts["steps"],
             counts["steps_verified"], counts["steps_manual_todo"]))
    print(" Katalog sluzeb: %d zaznamu | stranky praha13.cz: %d"
          % (counts["katalog_services"], counts["praha13_pages"]))
    print(" Bezi na: %s   (ukoncis pres Ctrl+C)" % url)
    print("=" * 62)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    if not args.no_open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nKonec.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
