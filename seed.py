"""Naplni databazi 20 zivotnimi situacemi z data/manual/situations.json.

Seeder je idempotentni: pri kazdem behu situace a kroky prepise (parsovana
data z katalogu a z praha13.cz zustavaji nedotcena).

Zaroven hlida pravidla prototypu a pri jejich poruseni skonci chybou:
  * presne 20 situaci, unikatni slug, kazda aspon 3 kroky,
  * deadline_status 'verified' => vyplneny deadline_text i deadline_source,
  * deadline_status 'manual_todo' => lhuta MUSI byt prazdna (zadne vymysleni),
  * kazdy krok ma bud source_url, nebo je oznaceny jako manual_todo.
"""

import json
import os
import sys

import db

SITUATIONS_FILE = os.path.join(db.MANUAL_DIR, "situations.json")

STEP_DEFAULTS = {
    "title_uk": None, "title_ru": None,
    "body_cs": None, "body_uk": None, "body_ru": None,
    "deadline_text": None, "deadline_days": None, "deadline_source": None,
    "deadline_status": "manual_todo",
    "sanction_text": None, "sanction_source": None,
    "authority": None, "location": None, "office_hours": None,
    "documents": [], "source_type": "manual", "source_url": None,
    "verify_hint": None,
}
SITUATION_DEFAULTS = {
    "title_uk": None, "title_ru": None,
    "summary_cs": None, "summary_uk": None, "summary_ru": None,
    "praha13_url": None, "katalog_keywords": None,
}


def load(path=SITUATIONS_FILE):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["situations"]


def validate(situations):
    """Vrati seznam chyb. Prazdny seznam = data vyhovuji pravidlum prototypu."""
    errors = []
    if len(situations) != 20:
        errors.append("ocekavano presne 20 situaci, nalezeno %d" % len(situations))

    slugs = set()
    for situation in situations:
        slug = situation.get("slug")
        where = "situace '%s'" % (slug or "?")
        if not slug:
            errors.append("situace bez slugu: %s" % situation.get("title_cs"))
            continue
        if slug in slugs:
            errors.append("%s: duplicitni slug" % where)
        slugs.add(slug)
        if not situation.get("title_cs"):
            errors.append("%s: chybi title_cs" % where)
        if situation.get("audience") not in db.AUDIENCES:
            errors.append("%s: neplatna audience %r" % (where, situation.get("audience")))

        steps = situation.get("steps") or []
        if len(steps) < 3:
            errors.append("%s: ma jen %d kroku, minimum jsou 3" % (where, len(steps)))

        for index, step in enumerate(steps, start=1):
            place = "%s, krok %d" % (where, index)
            status = step.get("deadline_status", STEP_DEFAULTS["deadline_status"])
            if status not in db.DEADLINE_STATUSES:
                errors.append("%s: neplatny deadline_status %r" % (place, status))
            if step.get("source_type", "manual") not in db.SOURCE_TYPES:
                errors.append("%s: neplatny source_type %r" % (place, step.get("source_type")))
            if not step.get("title_cs"):
                errors.append("%s: chybi title_cs" % place)

            if status == "verified":
                if not step.get("deadline_text"):
                    errors.append("%s: verified lhuta bez deadline_text" % place)
                if not step.get("deadline_source"):
                    errors.append("%s: verified lhuta bez deadline_source (URL nebo § zakona)" % place)
            if status == "manual_todo":
                if step.get("deadline_text") or step.get("deadline_days") or step.get("deadline_source"):
                    errors.append("%s: manual_todo nesmi mit vyplnenou lhutu - prototyp lhuty nevymysli" % place)
                if not step.get("verify_hint"):
                    errors.append("%s: manual_todo bez verify_hint (kde se ma lhuta dohledat)" % place)
            if step.get("sanction_text") and not step.get("sanction_source"):
                errors.append("%s: sankce bez uvedeneho zdroje" % place)
            if not step.get("source_url") and status != "manual_todo":
                errors.append("%s: krok bez source_url musi byt oznacen jako manual_todo" % place)
            if not isinstance(step.get("documents", []), list):
                errors.append("%s: documents musi byt pole" % place)
    return errors


def seed(conn, situations):
    conn.execute("DELETE FROM steps")
    conn.execute("DELETE FROM situations")
    for order, raw in enumerate(situations, start=1):
        situation = dict(SITUATION_DEFAULTS)
        situation.update({k: v for k, v in raw.items() if k != "steps"})
        situation["sort_order"] = order
        columns = [c for c in situation if c in (
            "slug", "title_cs", "title_uk", "title_ru", "summary_cs", "summary_uk",
            "summary_ru", "category", "audience", "praha13_url", "katalog_keywords",
            "sort_order")]
        cursor = conn.execute(
            "INSERT INTO situations (%s) VALUES (%s)"
            % (", ".join(columns), ", ".join(":" + c for c in columns)),
            {c: situation[c] for c in columns})
        situation_id = cursor.lastrowid

        for step_order, raw_step in enumerate(raw.get("steps", []), start=1):
            step = dict(STEP_DEFAULTS)
            step.update(raw_step)
            step["documents"] = json.dumps(step["documents"] or [], ensure_ascii=False)
            step["situation_id"] = situation_id
            step["step_order"] = step_order
            keys = list(STEP_DEFAULTS) + ["title_cs", "situation_id", "step_order"]
            conn.execute(
                "INSERT INTO steps (%s) VALUES (%s)"
                % (", ".join(keys), ", ".join(":" + k for k in keys)),
                {k: step[k] for k in keys})
    conn.commit()


def main():
    situations = load()
    errors = validate(situations)
    if errors:
        print("SEED NEPROBEHL - data porusuji pravidla prototypu:", file=sys.stderr)
        for error in errors:
            print("  - " + error, file=sys.stderr)
        return 1

    conn = db.init(db.connect())
    seed(conn, situations)
    counts = db.counts(conn)
    print("Naplneno: %d situaci, %d kroku" % (counts["situations"], counts["steps"]))
    print("  lhuty overene:     %d" % counts["steps_verified"])
    print("  lhuty k overeni:   %d  (deadline_status = manual_todo)" % counts["steps_manual_todo"])
    print("  lhuta se netyka:   %d" % counts["steps_not_applicable"])
    print("Seznam k rucni praci: python -m parsers.run report")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
