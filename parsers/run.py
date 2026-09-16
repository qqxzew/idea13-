"""CLI parseru.

    python -m parsers.run all                 # katalog + praha13 + provazani
    python -m parsers.run katalog --limit 500
    python -m parsers.run praha13 --limit 30
    python -m parsers.run link
    python -m parsers.run lookup "zivnost"    # vyhledani sluzby v katalogu
    python -m parsers.run report              # seznam neoverenych lhut k rucni praci
    python -m parsers.run shape               # diagnostika struktury dumpu
    python -m parsers.run selftest            # offline test parseru na vzorove strance
    python -m parsers.run status
"""

import argparse
import json
import os
import sys
import time
import uuid

import db
from parsers import katalog, praha13


class Logger:
    """Loguje soucasne na obrazovku, do logs/parser.log a do tabulky parse_log."""

    def __init__(self, conn, run_id=None, quiet=False):
        self.conn = conn
        self.run_id = run_id or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        self.quiet = quiet
        os.makedirs(db.LOG_DIR, exist_ok=True)
        self.path = os.path.join(db.LOG_DIR, "parser.log")
        self.counts = {"ok": 0, "warning": 0, "error": 0, "skipped": 0}

    def __call__(self, source, target, status, message=""):
        self.counts[status] = self.counts.get(status, 0) + 1
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        line = "%s [%s] %-8s %-8s %s :: %s" % (
            stamp, self.run_id, source, status.upper(), (target or "")[:110], message)
        if not self.quiet and status != "skipped":
            print(line)
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass
        try:
            self.conn.execute(
                "INSERT INTO parse_log (run_id, ts, source, target, status, message)"
                " VALUES (?,?,?,?,?,?)",
                (self.run_id, stamp, source, target, status, message))
            self.conn.commit()
        except Exception:
            pass  # logovani nesmi nikdy shodit beh

    def summary(self):
        return "beh %s: ok %d, varovani %d, chyb %d, preskoceno %d" % (
            self.run_id, self.counts.get("ok", 0), self.counts.get("warning", 0),
            self.counts.get("error", 0), self.counts.get("skipped", 0))


def keywords_of(situation):
    raw = situation["katalog_keywords"] or ""
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def cmd_link(conn, logger):
    """Priradi stazenym strankam praha13.cz konkretni situace podle klicovych slov.

    Meni jen odkazy (source_url / praha13_url). Lhuty ani sankce se timto
    nikdy neprepisuji - ty zustavaji na rucnim overeni.
    """
    pages = conn.execute(
        "SELECT url, title, points FROM praha13_pages WHERE status != 'failed'").fetchall()
    if not pages:
        logger("link", "-", "warning", "zadne stazene stranky praha13.cz, spust nejdriv 'praha13'")
        return {"linked": 0}

    haystacks = []
    for page in pages:
        text = (page["title"] or "") + " " + (page["points"] or "")
        haystacks.append((page["url"], praha13.strip_accents(text)))

    linked = 0
    for situation in conn.execute(
            "SELECT id, slug, title_cs, katalog_keywords FROM situations").fetchall():
        keys = [praha13.strip_accents(k) for k in keywords_of(situation)]
        if not keys:
            continue
        best_url, best_score = None, 0
        for url, hay in haystacks:
            score = sum(1 for key in keys if key and key in hay)
            if score > best_score:
                best_url, best_score = url, score
        if best_url and best_score >= 2:
            conn.execute("UPDATE situations SET praha13_url = ? WHERE id = ?",
                         (best_url, situation["id"]))
            conn.execute(
                "UPDATE steps SET source_url = ?"
                " WHERE situation_id = ? AND source_type = 'praha13'",
                (best_url, situation["id"]))
            linked += 1
            logger("link", situation["slug"], "ok",
                   "-> %s (shoda %d klicovych slov)" % (best_url, best_score))
        else:
            logger("link", situation["slug"], "warning", "zadna dost dobra shoda na praha13.cz")
    conn.commit()
    logger("link", "-", "ok", "provazano situaci: %d" % linked)
    return {"linked": linked}


def cmd_report(conn):
    """Pracovni seznam pro cloveka: co je potreba rucne overit."""
    rows = conn.execute(
        """SELECT s.slug, s.title_cs AS situace, st.step_order, st.title_cs AS krok,
                  st.verify_hint, p.deadline_text_raw
             FROM steps st
             JOIN situations s ON s.id = st.situation_id
        LEFT JOIN praha13_pages p ON p.url = s.praha13_url
            WHERE st.deadline_status = 'manual_todo'
         ORDER BY s.sort_order, st.step_order""").fetchall()
    out = ["NEOVERENE LHUTY (deadline_status = manual_todo): %d kroku" % len(rows),
           "Doplnuj vyhradne do data/manual/situations.json a pak spust: python seed.py", ""]
    for row in rows:
        out.append("[%s] krok %d: %s" % (row["slug"], row["step_order"], row["krok"]))
        if row["verify_hint"]:
            out.append("    kde overit: %s" % row["verify_hint"])
        if row["deadline_text_raw"]:
            snippet = " ".join(row["deadline_text_raw"].split())[:300]
            out.append("    bod 13 ze stazene stranky (NEOVERENO): %s" % snippet)
    return "\n".join(out)


def cmd_status(conn):
    counts = db.counts(conn)
    lines = ["Databaze: %s" % db.DB_PATH]
    for key, value in counts.items():
        lines.append("  %-22s %d" % (key, value))
    last = conn.execute(
        "SELECT run_id, MIN(ts) AS zacatek, COUNT(*) AS zaznamu,"
        " SUM(status='error') AS chyby, SUM(status='warning') AS varovani"
        " FROM parse_log GROUP BY run_id ORDER BY zacatek DESC LIMIT 5").fetchall()
    if last:
        lines.append("Posledni behy parseru:")
        for row in last:
            lines.append("  %s  %s  zaznamu %d, chyb %s, varovani %s"
                         % (row["zacatek"], row["run_id"], row["zaznamu"],
                            row["chyby"], row["varovani"]))
    return "\n".join(lines)


def cmd_selftest():
    """Overi parser sablony bez site - na vzorove strance v data/fixtures/."""
    path = os.path.join(db.DATA_DIR, "fixtures", "praha13_vzor_zivotni_situace.html")
    with open(path, encoding="utf-8") as fh:
        row = praha13.parse_page("https://www.praha13.cz/jak-si-zaridit/vzor/", fh.read())
    checks = [
        ("nazev", bool(row["title"])),
        ("bod 8 - utvar", bool(row["department"])),
        ("bod 9 - adresa", bool(row["address"])),
        ("bod 9 - uredni hodiny", bool(row["office_hours"])),
        ("bod 10 - doklady", len(json.loads(row["documents"])) >= 3),
        ("bod 11 - formulare", len(json.loads(row["forms"])) >= 1),
        ("bod 13 - lhuta jen jako surovy text", bool(row["deadline_text_raw"])),
        ("bod 20 - sankce", bool(row["sanctions"])),
        ("bod 25 - odpovedny utvar", bool(row["responsible_department"])),
        ("obsah <script> se neparsuje", "scriptu" not in (row["sanctions"] or "")),
    ]
    ok = all(passed for _, passed in checks)
    lines = ["%s  %s" % ("OK  " if passed else "CHYBA", name) for name, passed in checks]
    lines.append("SELFTEST: %s" % ("vse proslo" if ok else "neco neproslo"))
    return "\n".join(lines), ok


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m parsers.run",
                                     description="Parsery portalu zivotnich situaci Praha 13")
    parser.add_argument("command", choices=[
        "init", "katalog", "praha13", "all", "link", "lookup", "report",
        "shape", "selftest", "status"])
    parser.add_argument("query", nargs="?", help="hledany vyraz pro 'lookup'")
    parser.add_argument("--limit", type=int, default=None, help="max. poctu zaznamu/stranek")
    parser.add_argument("--force", action="store_true", help="ignorovat cache a stahnout znovu")
    parser.add_argument("--max-age", type=int, default=None,
                        help="stari cache v sekundach, po kterem se stahuje znovu")
    parser.add_argument("--jsonld", action="store_true", help="misto .json pouzit .jsonld")
    args = parser.parse_args(argv)

    if args.command == "selftest":
        text, ok = cmd_selftest()
        print(text)
        return 0 if ok else 1

    conn = db.init(db.connect())
    logger = Logger(conn)
    katalog_url = katalog.JSONLD_URL if args.jsonld else katalog.JSON_URL

    if args.command == "init":
        print("Schema pripraveno:", db.DB_PATH)
    elif args.command == "katalog":
        katalog.run(conn, logger, url=katalog_url, limit=args.limit,
                    force=args.force, max_age=args.max_age)
    elif args.command == "praha13":
        praha13.run(conn, logger, limit=args.limit, force=args.force, max_age=args.max_age)
    elif args.command == "all":
        katalog.run(conn, logger, url=katalog_url, limit=args.limit,
                    force=args.force, max_age=args.max_age)
        praha13.run(conn, logger, limit=args.limit, force=args.force, max_age=args.max_age)
        cmd_link(conn, logger)
    elif args.command == "link":
        cmd_link(conn, logger)
    elif args.command == "lookup":
        if not args.query:
            print("Pouziti: python -m parsers.run lookup \"cast nazvu sluzby\"")
            return 2
        rows = katalog.lookup(conn, args.query, limit=args.limit or 20)
        if not rows:
            print("Nic nenalezeno. Je katalog stazeny? (python -m parsers.run katalog)")
        for row in rows:
            print("- %s [%s]\n    agenda: %s\n    ohlasovatel: %s\n    zdroj: %s"
                  % (row["name"], row["code"] or "-", row["agenda_name"] or "-",
                     row["ohlasovatel_name"] or "-", row["source_url"] or "-"))
    elif args.command == "report":
        print(cmd_report(conn))
    elif args.command == "shape":
        print(katalog.shape(url=katalog_url, force=args.force))
    elif args.command == "status":
        print(cmd_status(conn))

    if args.command in ("katalog", "praha13", "all", "link"):
        print(logger.summary())
        print("Podrobny log: %s" % os.path.join(db.LOG_DIR, "parser.log"))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
