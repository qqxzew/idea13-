"""Parser A: Katalog sluzeb verejne spravy (RPP open data, CC BY 4.0).

Zdroje:
  JSON    https://rpp-opendata.egon.gov.cz/odrpp/datovasada/sluzby.json
  JSON-LD https://rpp-opendata.egon.gov.cz/odrpp/datovasada/sluzby.jsonld
  SPARQL  https://rpp-opendata.egon.gov.cz/odrpp/sparql/
  Schema  https://ofn.gov.cz/registr-prav-a-povinnosti/sluzby/2024-10-03/

Dulezite: presne nazvy klicu v dumpu se mezi verzemi OFN meni, proto se
nic nehleda "natvrdo". Kazde pole se hleda pres seznam kandidatskych nazvu
porovnavanych bez diakritiky a bez podtrzitek. Kdyz se pole nenajde, zustane
prazdne a zaloguje se to - zadna hodnota se nedomysli.

Prikaz `python -m parsers.run shape` vypise skutecne klice prvniho zaznamu,
aby se kandidati dali rychle doplnit.
"""

import json
import time
import unicodedata

from parsers.http_cache import fetch_json

JSON_URL = "https://rpp-opendata.egon.gov.cz/odrpp/datovasada/sluzby.json"
JSONLD_URL = "https://rpp-opendata.egon.gov.cz/odrpp/datovasada/sluzby.jsonld"
SPARQL_URL = "https://rpp-opendata.egon.gov.cz/odrpp/sparql/"

CONTAINER_KEYS = ("polozky", "items", "data", "graph", "sluzby", "member", "records")

F_ID = ("iri", "id", "identifikator", "uri", "@id")
F_CODE = ("kod", "kod-sluzby", "cislo", "identifikator")
F_NAME = ("nazev", "name", "title", "preflabel", "label", "nazev-sluzby")
F_DESC = ("popis", "description", "comment", "popis-sluzby", "anotace")
F_AGENDA = ("agenda", "agenda-sluzby", "isagendou")
F_NORM = (
    "pravni-predpis", "pravni-predpisy", "ustanoveni-pravniho-predpisu",
    "ustanoveni-dokladajici-existenci-sluzby", "legislativa", "pravni-zaklad",
)
F_CHANNEL = (
    "kanal", "kanaly", "kanal-sluzby", "zpusob-poskytovani", "forma-poskytovani",
    "zpusob-vyrizeni", "channel",
)
F_OHLASOVATEL = ("ohlasovatel", "ohlasovatel-agendy", "publisher", "vydavatel")


def norm_key(key):
    """'Pravni_predpis' i 'právní předpis' -> 'pravni-predpis'."""
    key = str(key).lstrip("@")
    key = unicodedata.normalize("NFKD", key)
    key = "".join(ch for ch in key if not unicodedata.combining(ch))
    key = key.lower().replace("_", "-").replace(" ", "-")
    while "--" in key:
        key = key.replace("--", "-")
    return key.strip("-")


def text_of(value):
    """Rozbali {"cs": "..."} , {"@value": ...}, seznamy i holé retezce."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("cs", "@value", "value", "cs-CZ", "text"):
            if key in value:
                return text_of(value[key])
        for candidate in (F_NAME + F_ID):
            for key in value:
                if norm_key(key) == candidate:
                    return text_of(value[key])
        return None
    if isinstance(value, list):
        parts = [text_of(item) for item in value]
        parts = [part for part in parts if part]
        return " | ".join(parts) or None
    return None


def pick(record, candidates):
    normalized = {norm_key(key): value for key, value in record.items()}
    for candidate in candidates:
        if candidate in normalized and normalized[candidate] not in (None, "", [], {}):
            return normalized[candidate]
    return None


def pick_text(record, candidates):
    return text_of(pick(record, candidates))


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def find_container(payload):
    """Najde seznam zaznamu at uz je dump pole nebo obalka."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        normalized = {norm_key(key): value for key, value in payload.items()}
        for key in CONTAINER_KEYS:
            value = normalized.get(key)
            if isinstance(value, list):
                return value
        # posledni zachrana: nejdelsi seznam slovniku v dokumentu
        best = []
        for value in payload.values():
            if isinstance(value, list) and len(value) > len(best) and \
                    all(isinstance(item, dict) for item in value[:5]):
                best = value
        return best
    return []


def parse_service(record, fetched_at, source_url):
    """Jeden zaznam -> radek pro katalog_services. Vraci None, kdyz nejde o sluzbu."""
    service_id = pick_text(record, F_ID) or pick_text(record, F_CODE)
    name = pick_text(record, F_NAME)
    if not service_id and not name:
        return None

    agenda = pick(record, F_AGENDA)
    agenda_code = agenda_name = None
    if isinstance(agenda, dict):
        agenda_code = pick_text(agenda, F_CODE)
        agenda_name = pick_text(agenda, F_NAME)
    elif agenda is not None:
        agenda_name = text_of(agenda)

    ohlasovatel = pick(record, F_OHLASOVATEL)
    ohlasovatel_id = ohlasovatel_name = None
    if isinstance(ohlasovatel, dict):
        ohlasovatel_id = pick_text(ohlasovatel, F_ID)
        ohlasovatel_name = pick_text(ohlasovatel, F_NAME)
    elif ohlasovatel is not None:
        ohlasovatel_name = text_of(ohlasovatel)

    norms = [text_of(item) for item in as_list(pick(record, F_NORM))]
    channels = [text_of(item) for item in as_list(pick(record, F_CHANNEL))]

    return {
        "id": service_id or name,
        "code": pick_text(record, F_CODE),
        "name": name,
        "description": pick_text(record, F_DESC),
        "agenda_code": agenda_code,
        "agenda_name": agenda_name,
        "legal_norms": json.dumps([n for n in norms if n], ensure_ascii=False),
        "channels": json.dumps([c for c in channels if c], ensure_ascii=False),
        "ohlasovatel_id": ohlasovatel_id,
        "ohlasovatel_name": ohlasovatel_name,
        "source_url": service_id if (service_id or "").startswith("http") else source_url,
        "raw": json.dumps(record, ensure_ascii=False)[:20000],
        "fetched_at": fetched_at,
    }


def run(conn, logger, url=JSON_URL, limit=None, force=False, max_age=None):
    """Stahne dump, ulozi sluzby. Vraci statistiku."""
    stats = {"total": 0, "saved": 0, "skipped": 0, "failed": 0}
    kwargs = {"force": force, "ext": "jsonld" if url.endswith(".jsonld") else "json"}
    if max_age is not None:
        kwargs["max_age"] = max_age
    payload, result = fetch_json(url, logger=logger, **kwargs)
    if payload is None:
        logger("katalog", url, "error", "dump se nepodarilo ziskat: %s" % result.error)
        return stats

    records = find_container(payload)
    stats["total"] = len(records)
    if not records:
        logger("katalog", url, "error",
               "v dumpu nenalezen seznam zaznamu (klice: %s)" %
               (list(payload)[:10] if isinstance(payload, dict) else type(payload).__name__))
        return stats

    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for index, record in enumerate(records):
        if limit and len(rows) >= limit:
            break
        if not isinstance(record, dict):
            stats["skipped"] += 1
            continue
        try:
            row = parse_service(record, fetched_at, url)
        except Exception as exc:  # jeden rozbity zaznam nesmi shodit beh
            stats["failed"] += 1
            logger("katalog", "zaznam #%d" % index, "error", "%s: %s" % (type(exc).__name__, exc))
            continue
        if row is None:
            stats["skipped"] += 1
            continue
        rows.append(row)

    columns = list(rows[0].keys()) if rows else []
    if rows:
        conn.executemany(
            "INSERT OR REPLACE INTO katalog_services (%s) VALUES (%s)"
            % (", ".join(columns), ", ".join(":" + c for c in columns)),
            rows,
        )
        conn.commit()
    stats["saved"] = len(rows)

    missing_name = sum(1 for row in rows if not row["name"])
    if missing_name:
        logger("katalog", url, "warning",
               "%d zaznamu bez nazvu - zkontroluj kandidatske klice (parsers/katalog.py, F_NAME)"
               % missing_name)
    logger("katalog", url, "ok",
           "zaznamu v dumpu %d, ulozeno %d, preskoceno %d, chybnych %d"
           % (stats["total"], stats["saved"], stats["skipped"], stats["failed"]))
    return stats


def shape(url=JSON_URL, force=False):
    """Diagnostika: vypise klice obalky a prvnich zaznamu."""
    payload, result = fetch_json(url, force=force,
                                 ext="jsonld" if url.endswith(".jsonld") else "json")
    if payload is None:
        return "Dump se nepodarilo ziskat: %s" % result.error
    lines = ["zdroj: %s (%s)" % (url, result.status)]
    if isinstance(payload, dict):
        lines.append("klice obalky: %s" % list(payload)[:20])
    records = find_container(payload)
    lines.append("nalezeno zaznamu: %d" % len(records))
    for record in records[:2]:
        if isinstance(record, dict):
            lines.append("-" * 60)
            lines.append(json.dumps(record, ensure_ascii=False, indent=2)[:2500])
    return "\n".join(lines)


def lookup(conn, query, limit=20):
    """Vyhledani sluzby podle nazvu - bez ohledu na velka pismena a diakritiku."""
    import db
    like = "%" + db.normalize_text(query.strip()) + "%"
    return conn.execute(
        """SELECT id, code, name, agenda_name, ohlasovatel_name, source_url
             FROM katalog_services
            WHERE norm(name) LIKE ? OR norm(description) LIKE ? OR norm(code) LIKE ?
         ORDER BY length(coalesce(name, '')) LIMIT ?""",
        (like, like, like, limit),
    ).fetchall()
