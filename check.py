"""Kontrola akceptacnich kriterii zadani proti naplnene databazi.

    python check.py

Skonci nenulovym kodem, kdyz nektere kriterium neplati - hodi se pred demem.
"""

import re
import sys

import db

conn = db.connect()
ok = True
def check(name, condition, detail=""):
    global ok
    print(("OK    " if condition else "CHYBA ") + name + ((" :: " + detail) if detail else ""))
    if not condition: ok = False

n = conn.execute("SELECT COUNT(*) FROM situations").fetchone()[0]
check("presne 20 situaci", n == 20, str(n))

bad = conn.execute("""SELECT s.slug, COUNT(st.id) c FROM situations s
                      LEFT JOIN steps st ON st.situation_id = s.id
                      GROUP BY s.id HAVING c < 3""").fetchall()
check("kazda situace ma aspon 3 kroky", not bad, str([r["slug"] for r in bad]))

bad = conn.execute("""SELECT id FROM steps
                      WHERE (source_url IS NULL OR source_url = '')
                        AND deadline_status != 'manual_todo'""").fetchall()
check("kazdy krok ma source_url nebo manual_todo", not bad, str(len(bad)))

bad = conn.execute("""SELECT id FROM steps WHERE deadline_status = 'manual_todo'
                      AND (deadline_text IS NOT NULL OR deadline_days IS NOT NULL
                           OR deadline_source IS NOT NULL)""").fetchall()
check("zadna vymyslena lhuta u manual_todo", not bad, str(len(bad)))

bad = conn.execute("""SELECT id FROM steps WHERE deadline_status = 'verified'
                      AND (deadline_text IS NULL OR deadline_source IS NULL)""").fetchall()
check("kazda overena lhuta ma zdroj", not bad, str(len(bad)))

bad = conn.execute("""SELECT id FROM steps
                      WHERE sanction_text IS NOT NULL AND sanction_source IS NULL""").fetchall()
check("kazda sankce ma zdroj", not bad, str(len(bad)))

# zadne castky v lhutach a sankcich (zadani: zadna vymyslena pokuta ani castka)
money = re.compile(r"\d[\d\s]*(Kč|korun)", re.I)
hits = []
for row in conn.execute("SELECT id, deadline_text, sanction_text FROM steps"):
    for field in ("deadline_text", "sanction_text"):
        if row[field] and money.search(row[field]):
            hits.append((row["id"], field, row[field][:60]))
check("zadne konkretni castky v lhutach/sankcich", not hits, str(hits))

langs = conn.execute("""SELECT COUNT(*) FROM situations
    WHERE slug IN ('prestehovani-do-prahy-13','dite-nastupuje-do-1-tridy','zapis-ditete-do-ms',
                   'narozeni-ditete','prodlouzeni-dlouhodobeho-pobytu',
                   'zmena-zamestnavatele-zamestnanecka-karta','oznameni-zmeny-adresy-oamp',
                   'adaptacne-integracni-kurz','docasna-ochrana-registrace-prodlouzeni',
                   'zdravotni-pojisteni-pro-cizince')
      AND title_uk IS NOT NULL AND title_ru IS NOT NULL""").fetchone()[0]
check("situace 1-4 a 15-20 maji UK i RU nazev", langs == 10, str(langs))

steps_langs = conn.execute("""SELECT COUNT(*) FROM steps st JOIN situations s ON s.id=st.situation_id
    WHERE s.title_uk IS NOT NULL AND (st.title_uk IS NULL OR st.title_ru IS NULL)""").fetchone()[0]
check("kroky prelozenych situaci maji UK i RU nazev", steps_langs == 0, str(steps_langs))

aud = dict(conn.execute("SELECT audience, COUNT(*) FROM situations GROUP BY audience").fetchall())
check("audience vyplnena", set(aud) <= {"all", "citizen", "foreigner"}, str(aud))

docs = conn.execute("SELECT COUNT(*) FROM steps WHERE documents IS NOT NULL AND documents != '[]'").fetchone()[0]
print("\ninfo: kroku se seznamem dokladu:", docs, "/ 83")
print("info:", db.counts(conn))
conn.close()
sys.exit(0 if ok else 1)
