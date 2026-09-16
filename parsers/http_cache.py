"""Stahovani s diskovou cache a logovanim. Pouze standardni knihovna.

Pravidla:
  * kazde URL se uklada do data/cache/<sha1>.<ext> + .meta.json,
  * opakovany beh nestahuje znovu, dokud je cache mladsi nez max_age,
  * kdyz je sit nedostupna, pouzije se stara cache (demo musi fungovat offline),
  * nic z toho nesmi shodit cely beh - chyba se zaloguje a jde se dal.
"""

import gzip
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request

from db import CACHE_DIR

USER_AGENT = (
    "Praha13-ZivotniSituace-Prototype/0.1 (ideathon prototype; kontakt: urad MC Praha 13)"
)
DEFAULT_MAX_AGE = 7 * 24 * 3600  # tyden


class FetchResult:
    def __init__(self, url, path, text, from_cache, status, error=None):
        self.url = url
        self.path = path
        self.text = text
        self.from_cache = from_cache
        self.status = status  # downloaded | cache_fresh | cache_stale | not_modified | failed
        self.error = error

    @property
    def ok(self):
        return self.text is not None

    def __repr__(self):
        return "<FetchResult %s %s>" % (self.status, self.url)


def cache_key(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _paths(url, ext):
    key = cache_key(url)
    os.makedirs(CACHE_DIR, exist_ok=True)
    return (
        os.path.join(CACHE_DIR, "%s.%s" % (key, ext.lstrip("."))),
        os.path.join(CACHE_DIR, "%s.meta.json" % key),
    )


def _read_meta(meta_path):
    try:
        with open(meta_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _read_body(body_path):
    try:
        with open(body_path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def fetch(url, ext="html", max_age=DEFAULT_MAX_AGE, force=False, timeout=60, logger=None):
    """Vrati FetchResult. Nikdy nevyhodi vyjimku ven."""
    body_path, meta_path = _paths(url, ext)
    meta = _read_meta(meta_path)
    now = time.time()
    have_cache = os.path.exists(body_path)
    age = now - os.path.getmtime(body_path) if have_cache else None

    if have_cache and not force and age is not None and age < max_age:
        if logger:
            logger("cache", url, "skipped", "cache je cerstva (%d s)" % int(age))
        return FetchResult(url, body_path, _read_body(body_path), True, "cache_fresh")

    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
        "Accept-Language": "cs,en;q=0.5",
    })
    if have_cache and meta.get("etag"):
        request.add_header("If-None-Match", meta["etag"])
    if have_cache and meta.get("last_modified"):
        request.add_header("If-Modified-Since", meta["last_modified"])

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            with open(body_path, "w", encoding="utf-8") as fh:
                fh.write(text)
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump({
                    "url": url,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "content_type": response.headers.get("Content-Type"),
                    "bytes": len(raw),
                }, fh, ensure_ascii=False, indent=2)
            if logger:
                logger("cache", url, "ok", "stazeno %d B" % len(raw))
            return FetchResult(url, body_path, text, False, "downloaded")
    except urllib.error.HTTPError as exc:
        if exc.code == 304 and have_cache:
            os.utime(body_path, None)  # obsah je platny, jen prodluzujeme cerstvost
            if logger:
                logger("cache", url, "ok", "304 Not Modified, pouzita cache")
            return FetchResult(url, body_path, _read_body(body_path), True, "not_modified")
        error = "HTTP %s %s" % (exc.code, exc.reason)
    except Exception as exc:  # sit, DNS, TLS, timeout - demo nesmi spadnout
        error = "%s: %s" % (type(exc).__name__, exc)

    if have_cache:
        if logger:
            logger("cache", url, "warning", "%s - pouzita starsi cache" % error)
        return FetchResult(url, body_path, _read_body(body_path), True, "cache_stale", error)
    if logger:
        logger("cache", url, "error", error)
    return FetchResult(url, None, None, False, "failed", error)


def fetch_json(url, ext="json", **kwargs):
    """Stahne a rozparsuje JSON. Vraci (data, FetchResult); data je None pri chybe."""
    result = fetch(url, ext=ext, **kwargs)
    if not result.ok:
        return None, result
    try:
        return json.loads(result.text), result
    except ValueError as exc:
        result.status = "failed"
        result.error = "neplatny JSON: %s" % exc
        return None, result
