"""Parser B: stranky "Jak si zaridit" MC Praha 13 (jen HTML, strojove citelna
verze neexistuje).

  Index   https://www.praha13.cz/jak-si-zaridit/
  Sitemap https://www.praha13.cz/sitemap.xml

Stranky drzi standardni ceskou sablonu "zivotni situace" cislovanou po bodech,
takze se parsuje podle cisla bodu; kdyz cislovani chybi, zkusi se jeste
nadpisy podle klicovych slov. Nenalezeny bod = None, nic se nedoplnuje.

POZOR: bod 13 (lhuty) se uklada jen jako deadline_text_raw k RUCNIMU overeni.
Do tabulky steps se odsud automaticky neprepisuje zadna lhuta.
"""

import html
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from parsers.http_cache import fetch

INDEX_URL = "https://www.praha13.cz/jak-si-zaridit/"
SITEMAP_URL = "https://www.praha13.cz/sitemap.xml"
ALLOWED_HOST = "www.praha13.cz"

BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "table", "ul", "ol", "dt", "dd",
}
DROP_TAGS = {"script", "style", "noscript", "svg", "head"}

# Standardni sablona zivotni situace (MV CR). Nazvy slouzi i jako zaloha,
# kdyz na strance chybi cislovani.
POINT_KEYWORDS = {
    4: ("zakladni informace",),
    5: ("kdo je opravnen",),
    6: ("jake jsou podminky a postup",),
    7: ("jakym zpusobem", "zahajit reseni"),
    8: ("na ktere instituci", "na kterem urad"),
    9: ("kde, s kym a kdy", "kde s kym a kdy"),
    10: ("jake doklady",),
    11: ("jake jsou potrebne formulare", "formulare"),
    12: ("jake jsou poplatky", "spravni poplat"),
    13: ("jake jsou lhuty", "lhuty pro vyrizeni"),
    17: ("podle ktereho pravniho predpisu",),
    19: ("opravne prostredky",),
    20: ("jake sankce", "sankce mohou byt uplatneny"),
    25: ("za spravnost popisu odpovida",),
}

POINT_HEADING_RE = re.compile(r"^\s*(\d{1,2})\s*[.)]\s*(.*)$")
OFFICE_HOURS_RE = re.compile(
    r"(pond[eě]l[ií]|[uú]ter[yý]|st[rř]eda|[cč]tvrtek|p[aá]tek|po\s*[,a]|po\s*:|"
    r"[uú][rř]edn[ií]\s+hodiny|[uú][rř]edn[ií]\s+doba)", re.I)


def strip_accents(text):
    import unicodedata
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


class PageText(HTMLParser):
    """HTML -> radky textu + seznam odkazu. Zamerne primitivni a odolne."""

    def __init__(self, base_url=""):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.chunks = []
        self.links = []          # (text, absolutni url)
        self.title = None
        self._skip_depth = 0
        self._in_title = False
        self._in_h1 = False
        self._link_href = None
        self._link_text = []

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag == "a":
            self._link_href = dict(attrs).get("href")
            self._link_text = []
        if tag in BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in DROP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag == "a":
            text = " ".join("".join(self._link_text).split())
            if self._link_href:
                self.links.append((text, urljoin(self.base_url, self._link_href)))
            self._link_href = None
            self._link_text = []
        if tag in BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        self.chunks.append(data)
        if self._link_href is not None:
            self._link_text.append(data)
        if (self._in_title or self._in_h1) and data.strip() and not self.title:
            self.title = " ".join(data.split())
        elif self._in_h1 and data.strip():
            self.title = " ".join(data.split())

    def text(self):
        raw = "".join(self.chunks)
        raw = html.unescape(raw).replace("\xa0", " ")
        lines = [" ".join(line.split()) for line in raw.split("\n")]
        return "\n".join(line for line in lines if line)


def split_points(text):
    """Rozreze text sablony na {cislo bodu: text}. Nezname nadpisy ignoruje."""
    points = {}
    current = None
    buffer = []
    for line in text.split("\n"):
        match = POINT_HEADING_RE.match(line)
        number = int(match.group(1)) if match else None
        is_heading = False
        if number and 1 <= number <= 30:
            rest = strip_accents(match.group(2))
            # "13. Jake jsou lhuty..." je nadpis; "13. 5. 2024" nebo "1. trida" ne
            if number in POINT_KEYWORDS:
                is_heading = any(k in rest for k in POINT_KEYWORDS[number]) or (
                    len(rest) > 10 and not rest[:1].isdigit())
            else:
                is_heading = len(rest) > 10 and not rest[:1].isdigit()
        if is_heading:
            if current is not None:
                points[current] = "\n".join(buffer).strip()
            current = number
            buffer = []
            tail = match.group(2).strip()
            # nadpis bodu ("13. Jake jsou lhuty pro vyrizeni") do obsahu nepatri;
            # kdyz je ale text na stejnem radku za dvojteckou, ten si nechame
            if ":" in tail:
                rest_of_line = tail.split(":", 1)[1].strip()
                if rest_of_line:
                    buffer.append(rest_of_line)
            continue
        if current is not None:
            buffer.append(line)
    if current is not None:
        points[current] = "\n".join(buffer).strip()

    # Zaloha pro stranky bez cislovani: hledame nadpisy podle klicovych slov.
    if len(points) < 3:
        lines = text.split("\n")
        starts = []
        for index, line in enumerate(lines):
            flat = strip_accents(line)
            if len(flat) > 120:
                continue
            for number, keywords in POINT_KEYWORDS.items():
                if any(flat.startswith(k) or flat.lstrip("0123456789.) ").startswith(k)
                       for k in keywords):
                    starts.append((index, number))
                    break
        for position, (index, number) in enumerate(starts):
            end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
            body = "\n".join(lines[index + 1:end]).strip()
            if body and number not in points:
                points[number] = body
    return points


def _point(points, number):
    value = points.get(number)
    return value.strip() if value and value.strip() else None


def _lines(value):
    if not value:
        return []
    out = []
    for line in value.split("\n"):
        line = line.strip(" -•\t")
        if len(line) > 1:
            out.append(line)
    return out


def parse_page(url, raw_html, fetched_at=None):
    """HTML -> radek pro praha13_pages. Chybejici body zustavaji None."""
    parser = PageText(base_url=url)
    try:
        parser.feed(raw_html)
    except Exception:
        pass  # rozbite HTML: bereme, co se stihlo nacist
    text = parser.text()
    points = split_points(text)

    where = _point(points, 9)
    office_hours = None
    if where:
        hours = [line for line in where.split("\n") if OFFICE_HOURS_RE.search(line)]
        office_hours = "\n".join(hours) or None

    form_links = [text_ for text_, href in parser.links
                  if href.lower().endswith((".pdf", ".doc", ".docx", ".rtf", ".odt", ".xlsx"))]
    forms = []
    for item in _lines(_point(points, 11)) + form_links:
        if item and item not in forms:
            forms.append(item)

    title = parser.title
    if title:
        title = re.sub(r"\s*[|–-]\s*(Praha 13|M[ČC] Praha 13).*$", "", title).strip()

    status = "ok" if len(points) >= 5 else ("partial" if points else "failed")
    return {
        "url": url,
        "title": title,
        "department": _point(points, 8),
        "address": where,
        "office_hours": office_hours,
        "documents": json.dumps(_lines(_point(points, 10)), ensure_ascii=False),
        "forms": json.dumps(forms, ensure_ascii=False),
        "fees": _point(points, 12),
        "deadline_text_raw": _point(points, 13),
        "sanctions": _point(points, 20),
        "responsible_department": _point(points, 25),
        "points": json.dumps({str(k): v for k, v in sorted(points.items())}, ensure_ascii=False),
        "status": status,
        "fetched_at": fetched_at or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "parsed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def discover(logger, force=False, max_age=None):
    """Seznam URL podstranek 'jak si zaridit' z indexu a ze sitemap.xml."""
    urls = []
    kwargs = {"force": force}
    if max_age is not None:
        kwargs["max_age"] = max_age

    index = fetch(INDEX_URL, ext="html", logger=logger, **kwargs)
    if index.ok:
        parser = PageText(base_url=INDEX_URL)
        try:
            parser.feed(index.text)
        except Exception:
            pass
        for _, href in parser.links:
            parsed = urlparse(href)
            if parsed.netloc.endswith(ALLOWED_HOST) and "jak-si-zaridit" in parsed.path:
                clean = href.split("#")[0].rstrip("/") + "/"
                if clean.rstrip("/") != INDEX_URL.rstrip("/"):
                    urls.append(clean)
        logger("praha13", INDEX_URL, "ok", "z indexu %d odkazu" % len(urls))
    else:
        logger("praha13", INDEX_URL, "error", index.error or "index se nepodarilo stahnout")

    sitemap = fetch(SITEMAP_URL, ext="xml", logger=logger, **kwargs)
    if sitemap.ok:
        found = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap.text)
        sub = [u.split("#")[0].rstrip("/") + "/" for u in found if "jak-si-zaridit" in u]
        urls.extend(sub)
        logger("praha13", SITEMAP_URL, "ok",
               "sitemap: %d zaznamu, z toho %d k 'jak si zaridit'" % (len(found), len(sub)))
    else:
        logger("praha13", SITEMAP_URL, "warning", sitemap.error or "sitemap nedostupna")

    seen, unique = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def run(conn, logger, limit=None, force=False, max_age=None, urls=None):
    stats = {"found": 0, "ok": 0, "partial": 0, "failed": 0}
    targets = urls if urls is not None else discover(logger, force=force, max_age=max_age)
    stats["found"] = len(targets)
    if limit:
        targets = targets[:limit]

    kwargs = {"force": force}
    if max_age is not None:
        kwargs["max_age"] = max_age

    for url in targets:
        try:
            result = fetch(url, ext="html", logger=None, **kwargs)
            if not result.ok:
                stats["failed"] += 1
                logger("praha13", url, "error", result.error or "nestazeno")
                continue
            row = parse_page(url, result.text)
            conn.execute(
                "INSERT OR REPLACE INTO praha13_pages (%s) VALUES (%s)"
                % (", ".join(row), ", ".join(":" + c for c in row)), row)
            conn.commit()
            stats[row["status"]] = stats.get(row["status"], 0) + 1
            logger("praha13", url, "ok" if row["status"] == "ok" else "warning",
                   "%s | bodu: %d | lhuta v bode 13: %s"
                   % (row["status"], len(json.loads(row["points"])),
                      "ano (k rucnimuovereni)" if row["deadline_text_raw"] else "ne"))
        except Exception as exc:  # jedna rozbita stranka nesmi shodit beh
            stats["failed"] += 1
            logger("praha13", url, "error", "%s: %s" % (type(exc).__name__, exc))
    logger("praha13", INDEX_URL, "ok",
           "hotovo: nalezeno %d, ok %d, castecne %d, chyb %d"
           % (stats["found"], stats["ok"], stats["partial"], stats["failed"]))
    return stats
