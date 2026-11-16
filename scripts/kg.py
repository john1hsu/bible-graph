#!/usr/bin/env python3
"""Bible Graph: validator, reasoner, exporter and analytics.

Usage:
  python3 scripts/kg.py check                       # validate articles + SHACL + reasoning (exit 1 on errors)
  python3 scripts/kg.py build                       # check, then regenerate everything in graph/
  python3 scripts/kg.py similar "Candidate title"   # rank existing nodes by similarity to a candidate
  python3 scripts/kg.py new <domain> <slug> <Type>  # scaffold an article with the sections its class needs
  python3 scripts/kg.py query <file.rq | 'SPARQL'>  # run SPARQL over asserted + inferred graph + ontology

Pipeline (see README.md):
  Markdown+YAML articles
    -> structural validation (citations, Scripture references, uniqueness, enums, class-specific rules)
    -> RDF graph (SKOS + PROV-O + schema.org HowTo + before/after examples + per-article named graphs)
    -> OWL 2 RL reasoning (inverse / symmetric / transitive / domain / range)
    -> consistency checks (disjoint classes, domain/range, cycles)
    -> SHACL validation (ontology/shapes.ttl)
    -> exports (N-Triples, TriG, Turtle-star edge evidence, JSON-LD, index, study guide, Scripture index)
    -> analytics (PageRank, betweenness, Louvain, k-core, link prediction,
       frontier ranking with expected types, learning paths, SPARQL competency gaps)

Generated outputs in graph/ are never hand-edited. Set BG_KG_ROOT to run against another tree (tests).
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

try:
    import yaml
    import networkx as nx
    from rdflib import BNode, Graph, Literal, Namespace, URIRef
    from rdflib.collection import Collection
    from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency ({e.name}). Run: pip install -r requirements.txt --break-system-packages")

ROOT = Path(os.environ.get("BG_KG_ROOT") or Path(__file__).resolve().parent.parent)
ARTICLES = ROOT / "articles"
GRAPH_DIR = ROOT / "graph"
ONTOLOGY = ROOT / "ontology" / "ontology.ttl"
SHAPES = ROOT / "ontology" / "shapes.ttl"
SEEDS = ROOT / "topics" / "seeds.yaml"
QUERIES = ROOT / "queries"

REPO = "https://github.com/john1hsu/bible-graph/"
CT = Namespace(REPO + "id/")
CTO = Namespace(REPO + "ontology#")
SCHEMA = Namespace("https://schema.org/")
WD = Namespace("http://www.wikidata.org/entity/")
PREFIXES = {"bg": CT, "bgo": CTO, "skos": SKOS, "prov": PROV, "dcterms": DCTERMS, "schema": SCHEMA,
            "rdf": RDF, "rdfs": RDFS, "owl": OWL, "xsd": XSD, "wd": WD}

ID_RE = re.compile(r"^bg:[a-z0-9]+(?:-[a-z0-9]+)*$")
SAMEAS_RE = re.compile(r"^(wd:Q\d+|https://\S+)$")

SOURCE_TYPES = {
    "scripture",              # the biblical text itself, in a named translation: Bible Gateway, USCCB (NABRE), ESV.org, NET Bible, STEP Bible, Blue Letter Bible, Sefaria (Tanakh)
    "peer-reviewed",          # journals: Journal of Biblical Literature, New Testament Studies, Vetus Testamentum, Tyndale Bulletin, Catholic Biblical Quarterly, BASOR
    "primary",                # ancient texts outside the Bible: Josephus, Philo, the church fathers (CCEL, New Advent), the Dead Sea Scrolls (Leon Levy library), the Mishnah (Sefaria)
    "textbook",               # academic introductions and commentaries from university and seminary presses
    "reference-work",         # Bible dictionaries and encyclopedias: Anchor Yale, Eerdmans, Lexham, ISBE, Oxford Bibliographies, Catholic and Jewish Encyclopedias, Stanford Encyclopedia of Philosophy
    "academic",               # university and seminary pages and courses: Yale Open Courses, Tyndale House, Duke Divinity, Dallas Seminary, Notre Dame
    "museum",                 # British Museum, Israel Museum, the Louvre, the Metropolitan Museum: artifacts and manuscripts
    "government",             # Israel Antiquities Authority, Library of Congress and other official heritage bodies
    "confessional",           # a church's own official teaching: Catechism of the Catholic Church, Westminster Confession, Book of Concord, Thirty-Nine Articles, Orthodox catechisms, creeds
    "institutional",          # Bible societies and established ministries: American Bible Society, United Bible Societies, BibleProject, Biblical Archaeology Society, Ligonier
    "magazine",               # Biblical Archaeology Review, Christianity Today
    "encyclopedia",           # Britannica
    "preprint",               # unreviewed preprints (weak)
    "news",                   # reputable press (weak; events and discoveries only)
    "community",              # blogs, sermons, Q&A sites, podcasts, forums (weak)
}
STRONG = SOURCE_TYPES - {"preprint", "news", "community"}
# "scripture" is deliberately not scholarly: every article pairs the text with scholarship about it.
SCHOLARLY = {"peer-reviewed", "primary", "textbook", "reference-work", "academic", "museum", "government"}
BANNED_DOMAINS = ("wikipedia.org", "wikiwand.com", "wikiquote.org", "rationalwiki.org", "fandom.com", "quora.com",
                  "chatgpt.com", "perplexity.ai", "ezinearticles.com", "wikihow.com",
                  # quotation and "verse of the day" aggregators: Bible "quotes" are often misquoted or not in the Bible at all
                  "brainyquote.com", "goodreads.com", "azquotes.com", "quotefancy.com", "quotemaster.org",
                  "quotes.net", "inspiringquotes.us", "everydaypower.com", "passiton.com")
LEVELS = {"introductory", "intermediate", "advanced"}
BASIS = {"scriptural", "ecumenical", "varies-by-tradition", "consensus", "debated", "misconception", "historical",
         "devotional"}
CONFIDENCE = {"high", "medium", "low"}
REQUIRED = ["id", "type", "title", "domain", "summary", "level", "basis", "sources", "created"]
INTERNAL_PROPS = {"questionFor", "evidence", "example", "howTo"}
NON_ARTICLE_CLASSES = {"Source", "StudyQuestion", "Rewrite", "Entity", "Text"}
STUDY_CLASSES = {"Book", "Passage", "Person", "Event", "Theme", "Covenant", "Doctrine", "Practice", "Method", "Pitfall",
                 "LifeSituation"}
EXAMPLE_CLASSES = {"Practice", "Method", "Pitfall", "Misconception"}
STEP_CLASSES = {"Practice", "Method"}
DEVOTIONAL_CLASSES = {"Practice", "Method", "Pitfall", "LifeSituation"}
# Articles about things outside the text itself may omit Scripture references and a scripture source.
NO_REF_CLASSES = {"Scholar", "Work", "Manuscript", "Translation", "Artifact", "Organization", "Field"}

# Class -> headings it must have (subclasses inherit: a Parable needs the Passage headings).
SECTIONS = {
    "Book": ["## Background", "## Outline", "## Key themes"],
    "Collection": ["## Books included"],
    "Passage": ["## Context", "## Walking through the text", "## Interpretation"],
    "Person": ["## Life and story", "## Legacy in Scripture"],
    "Group": ["## Who they were", "## In the biblical story"],
    "Place": ["## Geography", "## In the biblical story"],
    "Event": ["## What happened", "## Significance"],
    "Period": ["## Timeline", "## Significance"],
    "Theme": ["## Through the Bible"],
    "Covenant": ["## Biblical basis", "## Through the Bible"],
    "Doctrine": ["## Biblical basis", "## Historical development"],
    "Genre": ["## How to read it", "## Common mistakes"],
    "Method": ["## How to apply it", "## Common mistakes"],
    "Practice": ["## How to apply it", "## Common mistakes"],
    "Pitfall": ["## How to spot it", "## How to fix it"],
    "Misconception": ["## Where it comes from", "## What the Bible actually says"],
    "LifeSituation": ["## What Scripture says", "## Pitfalls"],
    "Tradition": ["## Key teachings", "## How it reads Scripture"],
    "Scholar": ["## Life and work", "## Influence"],
    "Work": ["## Background", "## Influence"],
    "Manuscript": ["## Description", "## Significance"],
    "Translation": ["## Translation approach", "## Significance"],
    "Artifact": ["## Description", "## Significance"],
}
BASIS_SECTIONS = {"varies-by-tradition": "## Views across traditions", "debated": "## Scholarly views"}

# Books of the Bible in canonical order (Old Testament, deuterocanonical / apocryphal books, New Testament),
# with chapter counts (the higher count where Hebrew, Greek or Catholic numbering differ) and accepted variants.
BOOKS = [
    ("Genesis", 50), ("Exodus", 40), ("Leviticus", 27), ("Numbers", 36), ("Deuteronomy", 34), ("Joshua", 24),
    ("Judges", 21), ("Ruth", 4), ("1 Samuel", 31), ("2 Samuel", 24), ("1 Kings", 22), ("2 Kings", 25),
    ("1 Chronicles", 29), ("2 Chronicles", 36), ("Ezra", 10), ("Nehemiah", 13), ("Esther", 16), ("Job", 42),
    ("Psalms", 151), ("Proverbs", 31), ("Ecclesiastes", 12), ("Song of Songs", 8), ("Isaiah", 66),
    ("Jeremiah", 52), ("Lamentations", 5), ("Ezekiel", 48), ("Daniel", 14), ("Hosea", 14), ("Joel", 4),
    ("Amos", 9), ("Obadiah", 1), ("Jonah", 4), ("Micah", 7), ("Nahum", 3), ("Habakkuk", 3), ("Zephaniah", 3),
    ("Haggai", 2), ("Zechariah", 14), ("Malachi", 4),
    ("Tobit", 14), ("Judith", 16), ("Wisdom of Solomon", 19), ("Sirach", 51), ("Baruch", 6),
    ("Letter of Jeremiah", 1), ("Prayer of Azariah", 1), ("Susanna", 1), ("Bel and the Dragon", 1),
    ("1 Maccabees", 16), ("2 Maccabees", 15), ("1 Esdras", 9), ("2 Esdras", 16), ("Prayer of Manasseh", 1),
    ("3 Maccabees", 7), ("4 Maccabees", 18),
    ("Matthew", 28), ("Mark", 16), ("Luke", 24), ("John", 21), ("Acts", 28), ("Romans", 16),
    ("1 Corinthians", 16), ("2 Corinthians", 13), ("Galatians", 6), ("Ephesians", 6), ("Philippians", 4),
    ("Colossians", 4), ("1 Thessalonians", 5), ("2 Thessalonians", 3), ("1 Timothy", 6), ("2 Timothy", 4),
    ("Titus", 3), ("Philemon", 1), ("Hebrews", 13), ("James", 5), ("1 Peter", 5), ("2 Peter", 3), ("1 John", 5),
    ("2 John", 1), ("3 John", 1), ("Jude", 1), ("Revelation", 22),
]
BOOK_ALIASES = {"Psalm": "Psalms", "Song of Solomon": "Song of Songs", "Wisdom": "Wisdom of Solomon",
                "Ecclesiasticus": "Sirach", "Acts of the Apostles": "Acts"}
BOOK_INDEX = {b: i for i, (b, _) in enumerate(BOOKS)}
BOOK_CHAPTERS = dict(BOOKS)
_LOC = r"\d+(?::\d+[a-c]?)?(?:[-\u2013]\d+(?::\d+[a-c]?)?)?"
REF_RE = re.compile(rf"^(?P<book>(?:[1-4] )?[A-Z][A-Za-z]*(?: (?:of|and|the|[A-Z][A-Za-z]*))*)"
                    rf"(?: (?P<loc>{_LOC}(?:, ?{_LOC})*))?$")


def parse_ref(ref: str) -> tuple[str | None, str]:
    """('Romans', '') for a valid reference, (None, reason) otherwise. Checks the book and its first chapter."""
    m = REF_RE.match(" ".join(str(ref).split()))
    if not m:
        return None, "use 'Book', 'Book 3', 'Book 3:16' or 'Book 3:16-18' (e.g. 'Romans 8:28-39')"
    book = BOOK_ALIASES.get(m["book"], m["book"])
    if book not in BOOK_INDEX:
        return None, f"unknown book '{m['book']}'"
    if m["loc"] and BOOK_CHAPTERS[book] > 1:
        ch = int(re.match(r"\d+", m["loc"]).group())
        if not 1 <= ch <= BOOK_CHAPTERS[book]:
            return None, f"{book} has {BOOK_CHAPTERS[book]} chapters"
    return book, ""


MIN_WORDS, MAX_WORDS = 400, 1400
SHINGLE_DUP = 0.35      # 5-word shingle Jaccard: copied text
TFIDF_DUP = 0.80        # cosine on TF-IDF of bodies: same topic rewritten
TFIDF_WARN = 0.60
TITLE_DUP = 0.85
STOP = set("the a an of and or in on to for is are be as by with that this it its from at which can not but "
           "if than then so such into their they them these those was were has have had more most when".split())


# ================================================================ ontology ===
@dataclass
class Ontology:
    graph: Graph
    classes: set[str] = field(default_factory=set)
    supers: dict[str, set[str]] = field(default_factory=dict)
    props: set[str] = field(default_factory=set)
    domain: dict[str, set[str]] = field(default_factory=dict)
    range: dict[str, set[str]] = field(default_factory=dict)
    disjoint: list[set[str]] = field(default_factory=list)
    transitive: set[str] = field(default_factory=set)

    def is_a(self, cls: str, allowed: set[str]) -> bool:
        return bool(self.supers.get(cls, {cls}) & allowed)


def local(u) -> str:
    return str(u).split("#", 1)[1] if str(u).startswith(str(CTO)) else ""


def class_set(g: Graph, node) -> set[str]:
    if isinstance(node, BNode):
        members = g.value(node, OWL.unionOf)
        return {local(m) for m in Collection(g, members)} if members else set()
    return {local(node)} if local(node) else set()


def load_ontology() -> Ontology:
    g = Graph().parse(ONTOLOGY)
    o = Ontology(graph=g)
    o.classes = {local(s) for s in g.subjects(RDF.type, OWL.Class) if local(s)}
    parents = defaultdict(set)
    for s, sup in g.subject_objects(RDFS.subClassOf):
        if local(s) and local(sup):
            parents[local(s)].add(local(sup))
    for c in o.classes:
        seen, stack = {c}, [c]
        while stack:
            for p in parents[stack.pop()]:
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        o.supers[c] = seen
    o.props = {local(s) for s in g.subjects(RDF.type, OWL.ObjectProperty) if local(s)}
    o.transitive = {local(s) for s in g.subjects(RDF.type, OWL.TransitiveProperty) if local(s)}
    for p in o.props:
        for d in g.objects(CTO[p], RDFS.domain):
            o.domain[p] = class_set(g, d)
        for r in g.objects(CTO[p], RDFS.range):
            o.range[p] = class_set(g, r)
    for n in g.subjects(RDF.type, OWL.AllDisjointClasses):
        o.disjoint.append({local(m) for m in Collection(g, g.value(n, OWL.members))})
    for a, b in g.subject_objects(OWL.disjointWith):
        o.disjoint.append({local(a), local(b)})
    return o


def load_seeds() -> dict:
    data = yaml.safe_load(SEEDS.read_text()) if SEEDS.exists() else {}
    return (data or {}).get("domains") or {}


# ================================================================= text utils ===
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(w for w in s.split() if w not in STOP)


def stem(w: str) -> str:
    return w[:6] if len(w) > 6 else w.rstrip("s")


def tokens(s: str) -> set[str]:
    return {stem(w) for w in norm(s).split()}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


CHAR_SIM_MIN = 0.92   # whole-label character similarity only counts when near-identical (spelling variants)


def same_token(x: str, y: str) -> bool:
    """Equal stems, or one stem (of 4+ letters) a prefix of the other: aware/awareness, theory/theories."""
    x, y = (t[:-1] + "i" if t.endswith("y") else t for t in (x, y))
    x, y = sorted((x, y), key=len)
    return x == y or (len(x) >= 4 and y.startswith(x))


def label_sim(a: str, b: str, idf: dict[str, float] | None = None) -> float:
    """Similarity of two labels: IDF-weighted token Jaccard, so words shared by many labels
    ("book", "parable") count for little, plus character similarity for near-identical spellings.
    Plain character similarity is not used below CHAR_SIM_MIN: on short labels it scores unrelated
    words around 0.5-0.8 ("Mark" vs "Mary")."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    w = (lambda t: idf.get(t, max(idf.values(), default=1.0))) if idf else (lambda t: 1.0)
    matched = {x for x in ta if any(same_token(x, y) for y in tb)}
    shared = sum(w(x) for x in matched)
    union = shared + sum(w(x) for x in ta - matched) + \
        sum(w(y) for y in tb if not any(same_token(x, y) for x in matched))
    tok = shared / union if union else 0.0
    ch = SequenceMatcher(None, norm(a).replace(" ", ""), norm(b).replace(" ", "")).ratio()
    return max(tok, ch if ch >= CHAR_SIM_MIN else 0.0)


def label_idf(labels: list[str]) -> dict[str, float]:
    df = Counter(t for x in labels for t in tokens(x))
    n = len(labels)
    return {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}


def strip_markup(body: str) -> str:
    body = body.split("\n## Sources", 1)[0]
    return re.sub(r"\[\^s\d+\]", " ", body)


def shingles(text: str, k: int = 5) -> set[str]:
    w = norm(strip_markup(text)).split()
    return {" ".join(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


def tfidf(docs: list[str]) -> list[dict[str, float]]:
    toks = [[stem(w) for w in norm(d).split()] for d in docs]
    df = Counter(t for ts in toks for t in set(ts))
    n = len(docs)
    vecs = []
    for ts in toks:
        tf = Counter(ts)
        v = {t: (c / max(1, len(ts))) * (math.log((1 + n) / (1 + df[t])) + 1) for t, c in tf.items()}
        norm2 = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm2 for t, x in v.items()})
    return vecs


def cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def slug(node_id: str) -> str:
    return node_id.split(":", 1)[1]


def iri(node_id: str) -> URIRef:
    return CT[slug(node_id)]


def short(u) -> str:
    s = str(u)
    for p, ns in PREFIXES.items():
        if s.startswith(str(ns)):
            return f"{p}:{s[len(str(ns)):]}"
    return s


# ================================================================== articles ===
def load_articles() -> tuple[list[dict], list[str]]:
    arts, errors = [], []
    if not ARTICLES.exists():
        return arts, errors
    for path in sorted(ARTICLES.rglob("*.md")):
        rel = path.relative_to(ROOT)
        raw = path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        if not m:
            errors.append(f"{rel}: missing YAML frontmatter")
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            errors.append(f"{rel}: bad YAML: {e}")
            continue
        fm["_path"], fm["_body"] = str(rel), m.group(2)
        arts.append(fm)
    return arts, errors


def typed_edges(a: dict):
    """(predicate-IRI, target-id, relation-dict|None) for every outgoing edge of an article."""
    for b in a.get("broader") or []:
        yield SKOS.broader, b, None
    for r in a.get("related") or []:
        yield SKOS.related, r, None
    for r in a.get("requires") or []:
        yield CTO.requires, r, None
    for r in a.get("relations") or []:
        if isinstance(r, dict) and r.get("predicate") and r.get("object"):
            yield CTO[r["predicate"]], r["object"], r


def required_sections(o: Ontology, cls: str, basis: str | None = None) -> list[str]:
    secs = [h for c, hs in SECTIONS.items() if o.is_a(cls, {c}) for h in hs]
    if basis in BASIS_SECTIONS:
        secs.append(BASIS_SECTIONS[basis])
    return list(dict.fromkeys(secs)) + ["## Connections", "## Sources"]


# ================================================================ validation ===
def validate(arts: list[dict], o: Ontology, seeds: dict) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    article_classes = o.classes - NON_ARTICLE_CLASSES
    usable_props = o.props - INTERNAL_PROPS
    ids: dict[str, str] = {}
    types: dict[str, str] = {}

    for a in arts:
        p = a["_path"]
        for f in REQUIRED:
            if not a.get(f):
                errs.append(f"{p}: missing required field '{f}'")
        aid = str(a.get("id", ""))
        if aid and not ID_RE.match(aid):
            errs.append(f"{p}: id '{aid}' must look like bg:lowercase-slug")
        elif aid:
            if aid in ids:
                errs.append(f"{p}: duplicate id {aid} (also {ids[aid]})")
            ids[aid] = p
            if Path(p).stem != slug(aid):
                errs.append(f"{p}: filename must be {slug(aid)}.md")
        dom = a.get("domain")
        if dom and dom not in seeds:
            errs.append(f"{p}: domain '{dom}' is not a key in topics/seeds.yaml")
        if dom and Path(p).parent.name != dom:
            errs.append(f"{p}: must live in articles/{dom}/")
        cls = a.get("type")
        if cls and cls not in article_classes:
            errs.append(f"{p}: type '{cls}' not an article class in the ontology {sorted(article_classes)}")
        elif cls:
            types[aid] = cls
        if a.get("level") and a["level"] not in LEVELS:
            errs.append(f"{p}: level '{a['level']}' not in {sorted(LEVELS)}")
        ev = a.get("basis")
        if ev and ev not in BASIS:
            errs.append(f"{p}: basis '{ev}' not in {sorted(BASIS)}")
        for k in ("created", "modified"):
            if a.get(k) and not isinstance(a[k], date):
                errs.append(f"{p}: {k} must be a YYYY-MM-DD date")
        if len(str(a.get("summary", ""))) < 40:
            errs.append(f"{p}: summary must be a real 1-2 sentence definition (>= 40 chars)")

        # ---- edges
        for key in ("broader", "related", "requires", "sameAs"):
            if a.get(key) is not None and not isinstance(a.get(key), list):
                errs.append(f"{p}: {key} must be a list")
        for key in ("broader", "related", "requires"):
            for ref in a.get(key) or []:
                if not ID_RE.match(str(ref)):
                    errs.append(f"{p}: {key} ref '{ref}' is not a bg: id")
                elif ref == aid:
                    errs.append(f"{p}: {key} points to itself")
        for x in a.get("sameAs") or []:
            if not SAMEAS_RE.match(str(x)):
                errs.append(f"{p}: sameAs '{x}' must be wd:Q<number> or an https IRI")
        source_ids = {s.get("id") for s in a.get("sources") or [] if isinstance(s, dict)}
        cited_by_edge = set()
        for r in a.get("relations") or []:
            if not isinstance(r, dict) or not {"predicate", "object", "source"} <= set(r) \
                    or set(r) - {"predicate", "object", "source", "confidence"}:
                errs.append(f"{p}: relation {r} needs predicate, object, source (+ optional confidence)")
                continue
            if r["predicate"] not in usable_props:
                errs.append(f"{p}: predicate '{r['predicate']}' not in ontology (add it to ontology.ttl first)")
            if not ID_RE.match(str(r["object"])):
                errs.append(f"{p}: relation object '{r['object']}' is not a bg: id")
            if r["object"] == aid:
                errs.append(f"{p}: relation {r['predicate']} points to itself")
            if r["source"] not in source_ids:
                errs.append(f"{p}: relation {r['predicate']} -> {r['object']} cites unknown source '{r['source']}'")
            cited_by_edge.add(r["source"])
            if r.get("confidence", "medium") not in CONFIDENCE:
                errs.append(f"{p}: relation confidence must be one of {sorted(CONFIDENCE)}")
        n_edges = sum(1 for _ in typed_edges(a))
        if n_edges < 3:
            errs.append(f"{p}: needs at least 3 edges across broader/related/requires/relations (has {n_edges})")
        if not a.get("relations"):
            errs.append(f"{p}: needs at least 1 typed, evidenced relation")

        # ---- class-specific structure
        checks = a.get("studyQuestions") or []
        if not isinstance(checks, list):
            errs.append(f"{p}: studyQuestions must be a list of questions")
            checks = []
        if cls and o.is_a(cls, STUDY_CLASSES) and len(checks) < 2:
            errs.append(f"{p}: a {cls} needs >= 2 studyQuestions questions")
        for q in checks:
            if not isinstance(q, str) or not q.strip().endswith("?"):
                errs.append(f"{p}: studyQuestions item must be a string ending in '?': {q!r}")
        steps = a.get("steps") or []
        if not isinstance(steps, list) or any(not isinstance(s, str) or len(s.strip()) < 10 for s in steps):
            errs.append(f"{p}: steps must be a list of instructions (>= 10 chars each)")
        elif cls and o.is_a(cls, STEP_CLASSES) and len(steps) < 3:
            errs.append(f"{p}: a {cls} needs >= 3 steps")
        ex = a.get("example")
        if cls and o.is_a(cls, EXAMPLE_CLASSES) and not ex:
            errs.append(f"{p}: a {cls} needs a before/after example")
        if ex:
            if not isinstance(ex, dict) or set(ex) != {"situation", "before", "after", "why"} \
                    or not all(isinstance(ex[k], str) and ex[k].strip() for k in ex):
                errs.append(f"{p}: example needs exactly situation, before, after, why (non-empty strings)")
            elif norm(ex["before"]) == norm(ex["after"]):
                errs.append(f"{p}: example before and after are the same")
            elif len(ex["why"]) < 20:
                errs.append(f"{p}: example.why must explain the improvement (>= 20 chars)")
        is_misc = bool(cls) and o.is_a(cls, {"Misconception"})
        if is_misc and not any(
                isinstance(r, dict) and r.get("predicate") == "challengedBy" for r in a.get("relations") or []):
            errs.append(f"{p}: a Misconception needs a challengedBy relation to the passage or source that corrects it")
        if ev and cls and (ev == "misconception") != is_misc:
            errs.append(f"{p}: basis 'misconception' is for (and only for) type Misconception")
        if ev == "devotional" and cls and not o.is_a(cls, DEVOTIONAL_CLASSES):
            errs.append(f"{p}: basis 'devotional' is only for {sorted(DEVOTIONAL_CLASSES)}; a {cls} is a matter of "
                        "Scripture, tradition or history")

        # ---- anchored in Scripture
        refs = a.get("references") or []
        if not isinstance(refs, list):
            errs.append(f"{p}: references must be a list like [John 3:16, Romans 8:28-39]")
            refs = []
        for ref in refs:
            book, why = parse_ref(ref)
            if not book:
                errs.append(f"{p}: bad Scripture reference '{ref}': {why}")
        needs_text = bool(cls) and not o.is_a(cls, NO_REF_CLASSES)
        if needs_text and not refs:
            errs.append(f"{p}: needs at least 1 key Scripture reference in `references`")

        # ---- citations
        srcs = a.get("sources") or []
        urls, strong = set(), 0
        for s in srcs:
            if not isinstance(s, dict):
                errs.append(f"{p}: malformed source entry")
                continue
            for f in ("id", "title", "publisher", "url", "type", "accessed"):
                if not s.get(f):
                    errs.append(f"{p}: source {s.get('id', '?')} missing '{f}'")
            url = str(s.get("url", ""))
            if url and not url.startswith("https://"):
                errs.append(f"{p}: source {s.get('id')} url must be https")
            if any(b in url for b in BANNED_DOMAINS):
                errs.append(f"{p}: source {s.get('id')} uses a banned domain ({url})")
            if url in urls:
                errs.append(f"{p}: duplicate source url {url}")
            urls.add(url)
            if s.get("accessed") and not isinstance(s["accessed"], date):
                errs.append(f"{p}: source {s.get('id')} accessed must be a YYYY-MM-DD date")
            if s.get("type") not in SOURCE_TYPES:
                errs.append(f"{p}: source {s.get('id')} type '{s.get('type')}' not in {sorted(SOURCE_TYPES)}")
            elif s["type"] in STRONG:
                strong += 1
        stypes = {s.get("type") for s in srcs if isinstance(s, dict)}
        if len(srcs) < 3:
            errs.append(f"{p}: needs at least 3 sources (has {len(srcs)})")
        if strong < 2:
            errs.append(f"{p}: needs at least 2 sources of a strong type")
        if not stypes & SCHOLARLY:
            errs.append(f"{p}: needs at least 1 scholarly source {sorted(SCHOLARLY)}")
        if needs_text and "scripture" not in stypes:
            errs.append(f"{p}: needs at least 1 'scripture' source (the passage itself, in a named translation)")

        body = a["_body"]
        cited = set(re.findall(r"\[\^(s\d+)\](?!:)", body))
        defined = set(re.findall(r"^\[\^(s\d+)\]:", body, re.M))
        for sid in source_ids - cited - cited_by_edge:
            errs.append(f"{p}: source {sid} is never cited")
        for sid in cited - source_ids:
            errs.append(f"{p}: body cites [^{sid}] but it is not in frontmatter sources")
        for sid in source_ids - defined:
            errs.append(f"{p}: missing footnote definition [^{sid}]: in ## Sources")
        prose = body.split("\n## Sources", 1)[0]
        for para in re.split(r"\n\s*\n", prose):
            t = para.strip()
            if not t or t.startswith(("#", ">", "|", "```")) or len(t) < 120:
                continue
            if "[^s" not in t:
                errs.append(f"{p}: uncited paragraph: '{t[:70]}...'")
        words = len(re.findall(r"\w+", prose))
        if words < MIN_WORDS:
            errs.append(f"{p}: body is {words} words; minimum {MIN_WORDS}")
        elif words > MAX_WORDS:
            warns.append(f"{p}: body is {words} words; consider splitting (> {MAX_WORDS})")
        if cls in o.classes:
            for sec in required_sections(o, cls, ev):
                if not re.search(rf"^{re.escape(sec)}\s*$", body, re.M):
                    errs.append(f"{p}: missing section '{sec}' required for {cls}")

    # ---- domain / range on edges whose target is written
    for a in arts:
        aid, cls = a.get("id"), a.get("type")
        if aid not in types:
            continue
        for r in a.get("relations") or []:
            if not isinstance(r, dict) or r.get("predicate") not in o.props:
                continue
            pred, obj = r["predicate"], r.get("object")
            if pred in o.domain and o.domain[pred] and not o.is_a(cls, o.domain[pred]):
                errs.append(f"{a['_path']}: {pred} expects subject in {sorted(o.domain[pred])}, not {cls}")
            if obj in types and pred in o.range and o.range[pred] and not o.is_a(types[obj], o.range[pred]):
                errs.append(f"{a['_path']}: {pred} -> {obj} expects object in {sorted(o.range[pred])}, "
                            f"not {types[obj]}")

    # ---- acyclicity of hierarchy and prerequisite edges
    for name, pred in (("broader", SKOS.broader), ("requires", CTO.requires), ("partOf", CTO.partOf),
                      ("precedes", CTO.precedes)):
        g = nx.DiGraph()
        for a in arts:
            for pr, t, _ in typed_edges(a):
                if pr == pred:
                    g.add_edge(a.get("id"), t)
        try:
            cyc = nx.find_cycle(g)
            errs.append(f"cycle in '{name}' edges: " + " -> ".join(u for u, _ in cyc) + f" -> {cyc[0][0]}")
        except nx.NetworkXNoCycle:
            pass

    # ---- uniqueness
    names = [(a["_path"], a.get("title", ""),
              {norm(x) for x in [a.get("title", "")] + list(a.get("aliases") or [])} - {""}) for a in arts]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            (pi, ti, ni), (pj, tj, nj) = names[i], names[j]
            if ni & nj:
                errs.append(f"{pi}: title/alias collides with {pj}: {sorted(ni & nj)}")
            elif jaccard(tokens(ti), tokens(tj)) >= TITLE_DUP:
                errs.append(f"{pi}: title too similar to {pj} ('{ti}' vs '{tj}')")
    sh = [shingles(a["_body"]) for a in arts]
    vec = tfidf([strip_markup(a["_body"]) for a in arts])
    for i in range(len(arts)):
        for j in range(i + 1, len(arts)):
            js, cs = jaccard(sh[i], sh[j]), cosine(vec[i], vec[j])
            if js >= SHINGLE_DUP:
                errs.append(f"{arts[i]['_path']}: copies text from {arts[j]['_path']} (shingle {js:.2f})")
            if cs >= TFIDF_DUP:
                errs.append(f"{arts[i]['_path']}: same topic as {arts[j]['_path']} (tf-idf cosine {cs:.2f})")
            elif cs >= TFIDF_WARN:
                warns.append(f"{arts[i]['_path']}: overlaps {arts[j]['_path']} (tf-idf cosine {cs:.2f})")
    return errs, warns


# ======================================================================== RDF ===
def bind(g: Graph) -> Graph:
    for p, ns in PREFIXES.items():
        g.bind(p, ns)
    return g


def article_graph(a: dict, seeds: dict) -> tuple[Graph, list[str]]:
    """RDF for one article (its named graph) plus Turtle-star lines for edge evidence."""
    g = bind(Graph())
    s = iri(a["id"])
    sl = slug(a["id"])
    g.add((s, RDF.type, CTO[a["type"]]))
    g.add((s, RDFS.label, Literal(a["title"])))
    g.add((s, SKOS.prefLabel, Literal(a["title"])))
    g.add((s, SKOS.definition, Literal(" ".join(str(a["summary"]).split()))))
    for al in a.get("aliases") or []:
        g.add((s, SKOS.altLabel, Literal(al)))
    g.add((s, SKOS.inScheme, CT[f"scheme/{a['domain']}"]))
    g.add((s, DCTERMS.created, Literal(a["created"], datatype=XSD.date)))
    if a.get("modified"):
        g.add((s, DCTERMS.modified, Literal(a["modified"], datatype=XSD.date)))
    g.add((s, CTO.domain, Literal(a["domain"])))
    g.add((s, CTO.level, Literal(a["level"])))
    g.add((s, CTO.basis, Literal(a["basis"])))
    for ref in a.get("references") or []:
        g.add((s, CTO.keyReference, Literal(" ".join(str(ref).split()))))
    g.add((s, CTO.file, Literal(a["_path"])))
    for x in a.get("sameAs") or []:
        g.add((s, SKOS.exactMatch, WD[x[3:]] if x.startswith("wd:") else URIRef(x)))

    src_iri = {}
    for src in a["sources"]:
        u = CT[f"source/{sl}/{src['id']}"]
        src_iri[src["id"]] = u
        g.add((s, PROV.wasDerivedFrom, u))
        g.add((u, RDF.type, CTO.Source))
        g.add((u, DCTERMS.title, Literal(src["title"])))
        g.add((u, DCTERMS.publisher, Literal(src["publisher"])))
        g.add((u, SCHEMA.url, URIRef(src["url"])))
        g.add((u, CTO.sourceType, Literal(src["type"])))
        g.add((u, DCTERMS.date, Literal(src["accessed"], datatype=XSD.date)))

    star = []
    for pred, obj, rel in typed_edges(a):
        g.add((s, pred, iri(obj)))
        if rel:
            star.append(f"<< <{s}> <{pred}> <{iri(obj)}> >> bgo:evidence <{src_iri[rel['source']]}> ; "
                        f"bgo:confidence \"{rel.get('confidence', 'medium')}\" .")

    for i, q in enumerate(a.get("studyQuestions") or [], 1):
        u = CT[f"{sl}/check/{i}"]
        g.add((u, RDF.type, CTO.StudyQuestion))
        g.add((u, RDFS.label, Literal(q.strip())))
        g.add((u, CTO.questionFor, s))

    if a.get("steps"):  # schema.org HowTo, so the procedure is machine-readable
        h = CT[f"{sl}/howto"]
        g.add((s, CTO.howTo, h))
        g.add((h, RDF.type, SCHEMA.HowTo))
        g.add((h, SCHEMA.name, Literal(a["title"])))
        for i, step in enumerate(a["steps"], 1):
            u = CT[f"{sl}/howto/{i}"]
            g.add((h, SCHEMA.step, u))
            g.add((u, RDF.type, SCHEMA.HowToStep))
            g.add((u, SCHEMA.position, Literal(i)))
            g.add((u, SCHEMA.text, Literal(" ".join(step.split()))))

    ex = a.get("example")
    if ex:
        e = CT[f"{sl}/example"]
        g.add((s, CTO.example, e))
        g.add((e, RDF.type, CTO.Rewrite))
        for k in ("situation", "before", "after", "why"):
            g.add((e, CTO[k], Literal(" ".join(str(ex[k]).split()))))
    return g, star


def scheme_graph(seeds: dict) -> Graph:
    g = bind(Graph())
    for dom, spec in seeds.items():
        u = CT[f"scheme/{dom}"]
        g.add((u, RDF.type, SKOS.ConceptScheme))
        g.add((u, SKOS.prefLabel, Literal((spec or {}).get("label") or dom)))
    return g


def reason(asserted: Graph, o: Ontology) -> Graph:
    """OWL 2 RL closure; returns only the *new* triples about bg: nodes that are worth publishing."""
    import owlrl
    full = Graph()
    for t in asserted:
        full.add(t)
    for t in o.graph:
        full.add(t)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(full)
    inferred = bind(Graph())
    keep_ns = (str(CTO), str(SKOS))
    for s, p, ob in full:
        if (s, p, ob) in asserted or not isinstance(s, URIRef) or not str(s).startswith(str(CT)):
            continue
        if isinstance(ob, BNode) or (s == ob):
            continue
        if p == RDF.type and str(ob).startswith(str(CTO)):
            inferred.add((s, p, ob))
        elif str(p).startswith(keep_ns) and isinstance(ob, URIRef) and str(ob).startswith(str(CT)):
            inferred.add((s, p, ob))
    return inferred


def consistency(asserted: Graph, inferred: Graph, o: Ontology) -> list[str]:
    errs = []
    types = defaultdict(set)
    for g in (asserted, inferred):
        for s, ob in g.subject_objects(RDF.type):
            if local(ob):
                types[s].add(local(ob))
    for s, ts in sorted(types.items()):
        for group in o.disjoint:
            clash = ts & group
            if len(clash) > 1:
                errs.append(f"contradiction: {short(s)} is inferred to be both {' and '.join(sorted(clash))} "
                            f"(disjoint classes) - check the edges that point at it")
    return errs


def shacl(asserted: Graph, o: Ontology) -> list[str]:
    from pyshacl import validate as shacl_validate
    shapes = Graph().parse(SHAPES)
    conforms, report, _ = shacl_validate(asserted, shacl_graph=shapes, ont_graph=o.graph, inference="rdfs",
                                         advanced=True, allow_warnings=True)
    if conforms:
        return []
    out = []
    SH = Namespace("http://www.w3.org/ns/shacl#")
    for r in report.subjects(RDF.type, SH.ValidationResult):
        node = report.value(r, SH.focusNode)
        msg = report.value(r, SH.resultMessage)
        path = report.value(r, SH.resultPath)
        out.append(f"SHACL: {short(node)} {short(path) if path is not None else ''}: {msg}")
    return sorted(set(out))


def assemble(arts: list[dict], seeds: dict):
    per_article, star, asserted = {}, [], bind(Graph())
    for a in arts:
        g, st = article_graph(a, seeds)
        per_article[a["id"]] = g
        star += st
        asserted += g
    asserted += scheme_graph(seeds)
    return asserted, per_article, star


# =================================================================== exports ===
def nt_lines(g: Graph) -> list[str]:
    return sorted(set(line for line in g.serialize(format="nt").splitlines() if line.strip()))


def write_exports(arts, seeds, o, asserted, per_article, star, inferred) -> None:
    GRAPH_DIR.mkdir(exist_ok=True)
    (GRAPH_DIR / "triples.nt").write_text("\n".join(nt_lines(asserted)) + "\n")
    (GRAPH_DIR / "inferred.nt").write_text("\n".join(nt_lines(inferred)) + "\n")

    # TriG: one named graph per article (nanopublication-style), provenance about each graph in the default graph
    trig = ["# Per-article named graphs. Default graph holds provenance about each named graph.", ""]
    for a in arts:
        gname = f"<{iri(a['id'])}#graph>"
        trig.append(f"{gname} <{RDF.type}> <{PROV.Entity}> .")
        trig.append(f"{gname} <{DCTERMS.subject}> <{iri(a['id'])}> .")
        trig.append(f"{gname} <{DCTERMS.source}> \"{REPO}blob/main/{a['_path']}\" .")
        for src in a["sources"]:
            trig.append(f"{gname} <{PROV.wasDerivedFrom}> <{CT[f'source/{slug(a['id'])}/{src['id']}']}> .")
    for a in arts:
        trig += ["", f"<{iri(a['id'])}#graph> {{"] + ["  " + x for x in nt_lines(per_article[a["id"]])] + ["}"]
    trig += ["", f"<{CT['inferred']}> {{"] + ["  " + x for x in nt_lines(inferred)] + ["}"]
    (GRAPH_DIR / "graph.trig").write_text("\n".join(trig) + "\n")

    head = [f"@prefix {p}: <{ns}> ." for p, ns in (("bgo", CTO), ("bg", CT))]
    (GRAPH_DIR / "edge-evidence.ttls").write_text(
        "# Turtle-star (RDF 1.2): each typed edge annotated with the source that supports it and a confidence.\n"
        + "\n".join(head) + "\n\n" + "\n".join(sorted(star)) + "\n")

    ctx = {p: str(ns) for p, ns in PREFIXES.items()}
    jsonld = json.loads(asserted.serialize(format="json-ld", context=ctx, auto_compact=True))
    def canon(x):  # rdflib emits sets in hash order; sort every list so builds are byte-for-byte reproducible
        if isinstance(x, dict):
            return {k: canon(v) for k, v in x.items()}
        if isinstance(x, list):
            return sorted((canon(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
        return x
    jsonld = canon(jsonld)
    (GRAPH_DIR / "graph.jsonld").write_text(json.dumps(jsonld, indent=1, ensure_ascii=False, sort_keys=True) + "\n")

    index = []
    for a in arts:
        index.append({
            "id": a["id"], "title": a["title"], "aliases": a.get("aliases") or [], "type": a["type"],
            "domain": a["domain"], "level": a["level"], "basis": a["basis"],
            "file": a["_path"], "created": str(a["created"]), "summary": " ".join(str(a["summary"]).split()),
            "edges": [{"predicate": short(p), "object": t, **({"source": r["source"],
                       "confidence": r.get("confidence", "medium")} if r else {})} for p, t, r in typed_edges(a)],
            "references": [" ".join(str(r).split()) for r in a.get("references") or []],
            "studyQuestions": a.get("studyQuestions") or [], "steps": a.get("steps") or [],
            "example": a.get("example") or None,
            "source_urls": [x["url"] for x in a["sources"]],
        })
    (GRAPH_DIR / "index.json").write_text(json.dumps(sorted(index, key=lambda x: x["id"]), indent=1,
                                                     ensure_ascii=False) + "\n")


def md_cell(s: str) -> str:
    return " ".join(str(s).split()).replace("|", "\\|")


def write_study_guide(arts, o) -> None:
    """A study-ready view: every study question, procedure and before/after reading, grouped by domain."""
    out = ["# Study guide", "", "Every study question, step-by-step practice and before/after reading in the graph, "
           "grouped by domain. Use it for personal study or a small group. Generated by `scripts/kg.py build`.", ""]
    useful = [a for a in arts if a.get("example") or a.get("steps") or a.get("studyQuestions")]
    if not useful:
        out.append("_None yet._")
    for dom in sorted({a["domain"] for a in useful}):
        out += [f"## {dom}", ""]
        for a in sorted((x for x in useful if x["domain"] == dom), key=lambda x: x["title"].lower()):
            out += [f"### [{a['title']}](../{a['_path']}) — {a['type']}", ""]
            if a.get("references"):
                out += ["Read: " + "; ".join(md_cell(r) for r in a["references"]), ""]
            if a.get("steps"):
                out += [f"{i}. {md_cell(st)}" for i, st in enumerate(a["steps"], 1)] + [""]
            ex = a.get("example")
            if ex:
                out += [f"*{md_cell(ex['situation'])}*", "", "| Before | After |", "|---|---|",
                        f"| {md_cell(ex['before'])} | {md_cell(ex['after'])} |", "", f"**Why:** {md_cell(ex['why'])}", ""]
            if a.get("studyQuestions"):
                out += ["Study questions:"] + [f"- {md_cell(q)}" for q in a["studyQuestions"]] + [""]
    (GRAPH_DIR / "study-guide.md").write_text("\n".join(out) + "\n")


def ref_sort_key(ref: str):
    nums = [int(x) for x in re.findall(r"\d+", ref.split(" ", 1)[1] if re.match(r"^[1-4] ", ref) else ref)]
    return nums or [0]


def write_scripture_index(arts) -> None:
    """Every key Scripture reference in the graph, in canonical book order, with the articles that discuss it."""
    by_book = defaultdict(list)
    for a in arts:
        for ref in a.get("references") or []:
            ref = " ".join(str(ref).split())
            book, _ = parse_ref(ref)
            if book:
                by_book[book].append((ref, a))
    out = ["# Scripture index", "", "Every key Scripture reference in the graph, in canonical book order (Old Testament, "
           "deuterocanonical books, New Testament), with the articles that discuss it. Generated by "
           "`scripts/kg.py build`.", ""]
    if not by_book:
        out.append("_None yet._")
    for book in sorted(by_book, key=lambda b: BOOK_INDEX[b]):
        out += [f"## {book}", ""]
        for ref, a in sorted(by_book[book], key=lambda x: (ref_sort_key(x[0]), x[0], x[1]["title"].lower())):
            out.append(f"- **{md_cell(ref)}** — [{a['title']}](../{a['_path']}) ({a['type']})")
        out.append("")
    (GRAPH_DIR / "scripture-index.md").write_text("\n".join(out) + "\n")


# ================================================================= analytics ===
def canon_cell(x) -> str:
    if x is None:
        return ""
    s = short(x)
    return ", ".join(sorted(s.split(", "))) if ", " in s else s  # GROUP_CONCAT order is unspecified


def run_queries(store: Graph) -> list[dict]:
    results = []
    for f in sorted(QUERIES.glob("*.rq")) if QUERIES.exists() else []:
        text = f.read_text()
        meta = dict(re.findall(r"^#\s*(\w+):\s*(.+)$", text, re.M))
        rows = list(store.query(text, initNs=PREFIXES))
        results.append({"file": f.name, "title": meta.get("title", f.stem), "question": meta.get("question", ""),
                        "gap": meta.get("gap", "false").strip() == "true", "vars": [str(v) for v in rows[0].labels]
                        if rows else [], "rows": sorted([[canon_cell(x) for x in r] for r in rows])
                        if "ORDER BY" not in text.upper() else [[canon_cell(x) for x in r] for r in rows]})
    return results


def louvain(ug) -> list[set[str]]:
    """Louvain communities that are identical on every run.

    Louvain iterates over Python sets of nodes, and the order of a set of strings changes with
    PYTHONHASHSEED (randomised per process), so a fixed `seed=` alone is not enough. Integers hash to
    themselves, so we run it on integer labels assigned in sorted order and map the result back.
    """
    if not ug.number_of_edges():
        return []
    names = sorted(ug.nodes)
    ig = nx.Graph()
    ig.add_nodes_from(range(len(names)))
    idx = {n: i for i, n in enumerate(names)}
    ig.add_edges_from(sorted((min(idx[u], idx[v]), max(idx[u], idx[v])) for u, v in ug.edges))
    return [{names[i] for i in c} for c in nx.algorithms.community.louvain_communities(ig, seed=42)]


def write_analytics(arts, o, seeds, asserted, inferred) -> None:
    known = {a["id"] for a in arts}
    byid = {a["id"]: a for a in arts}
    g = nx.DiGraph()
    g.add_nodes_from(known)
    frontier = defaultdict(list)
    for a in arts:
        for p, t, _ in typed_edges(a):
            g.add_edge(a["id"], t, predicate=short(p))
            if t not in known:
                frontier[t].append(a["id"])
    n_edges = sum(1 for a in arts for _ in typed_edges(a))
    pr = nx.pagerank(g) if g.number_of_nodes() else {}
    ug = g.to_undirected()
    btw = nx.betweenness_centrality(ug) if ug.number_of_nodes() > 2 else {}
    comms = louvain(ug)
    core = nx.core_number(nx.Graph(ug)) if ug.number_of_edges() else {}

    # expected type of frontier nodes, from range axioms the reasoner applied
    exp_type = defaultdict(set)
    for s, ob in inferred.subject_objects(RDF.type):
        sid = "bg:" + str(s)[len(str(CT)):]
        if sid in frontier and local(ob) not in {"Entity", "Concept", "Text"}:
            exp_type[sid].add(local(ob))

    def most_specific(ts: set[str]) -> str:
        return ", ".join(sorted(t for t in ts if not any(t != u and t in o.supers.get(u, set()) for u in ts)))

    # frontier: referenced-but-unwritten, ranked by number of referrers weighted by their centrality
    seed_slugs = {s for spec in seeds.values() for s in ((spec or {}).get("seeds") or [])}
    score = {k: len(v) + 10 * sum(pr.get(x, 0) for x in v) + (0.5 if slug(k) in seed_slugs else 0)
             for k, v in frontier.items()}
    lines = ["# Frontier", "", "Nodes that existing articles point to but nobody has written yet. Score = referrers "
             "+ 10 x their PageRank + 0.5 if seeded. *Expected type* is what the OWL reasoner inferred from the "
             "range of the edges pointing at it; use it as the new article's `type`. Generated by `scripts/kg.py build`.", ""]
    if frontier:
        lines += ["| Node | Score | Expected type | Referenced by |", "|---|---|---|---|"]
        for k in sorted(frontier, key=lambda x: (-score[x], x)):
            lines.append(f"| `{k}` | {score[k]:.2f} | {most_specific(exp_type.get(k, set())) or '-'} | "
                         f"{', '.join(f'`{x}`' for x in sorted(set(frontier[k])))} |")
    else:
        lines.append("_Empty._")
    (GRAPH_DIR / "frontier.md").write_text("\n".join(lines) + "\n")

    # link prediction among written nodes (Adamic-Adar on the undirected graph)
    sugg = []
    for u, v, p in nx.adamic_adar_index(ug, [(u, v) for i, u in enumerate(sorted(known))
                                              for v in sorted(known)[i + 1:] if not ug.has_edge(u, v)]):
        if p > 0:
            sugg.append((p, u, v))
    sugg.sort(key=lambda x: (-x[0], x[1], x[2]))
    lines = ["# Suggested links", "", "Pairs of written nodes that share many neighbours but are not yet connected "
             "(Adamic-Adar index). Candidates for a `related` back-link or a typed relation; only add one if a "
             "source supports it. Generated by `scripts/kg.py build`.", ""]
    if sugg:
        lines += ["| Score | Node A | Node B | Shared neighbours |", "|---|---|---|---|"]
        for p, u, v in sugg[:25]:
            shared = sorted(set(ug[u]) & set(ug[v]))
            lines.append(f"| {p:.2f} | `{u}` | `{v}` | {', '.join(f'`{x}`' for x in shared[:5])} |")
    else:
        lines.append("_None yet._")
    (GRAPH_DIR / "suggested-links.md").write_text("\n".join(lines) + "\n")

    # learning path: topological generations of the `requires` DAG
    rg = nx.DiGraph()
    for a in arts:
        rg.add_node(a["id"])
        for r in a.get("requires") or []:
            rg.add_edge(r, a["id"])
    lines = ["# Learning path", "", "Topological layers of the `requires` (prerequisite) graph: learn layer 1 "
             "before layer 2, and so on. Unwritten prerequisites are marked. Generated by `scripts/kg.py build`.", ""]
    if rg.number_of_edges():
        for i, layer in enumerate(nx.topological_generations(rg), 1):
            items = []
            for n in sorted(layer, key=lambda x: (byid.get(x, {}).get("level", "zzz"), x)):
                if n in byid:
                    items.append(f"[{byid[n]['title']}](../{byid[n]['_path']}) ({byid[n]['level']})")
                else:
                    items.append(f"`{n}` (unwritten)")
            lines.append(f"{i}. " + "; ".join(items))
    else:
        lines.append("_No prerequisite edges yet._")
    (GRAPH_DIR / "learning-path.md").write_text("\n".join(lines) + "\n")

    # SPARQL competency questions over asserted + inferred + ontology
    store = bind(Graph())
    for gg in (asserted, inferred, o.graph):
        store += gg
    res = run_queries(store)
    lines = ["# Competency questions", "", "SPARQL queries in `queries/` run over the asserted graph, the OWL-RL "
             "inferences and the ontology. Queries marked *gap* list holes in the graph; gap runs fill them. "
             "Generated by `scripts/kg.py build`.", ""]
    for r in res:
        lines += [f"## {r['title']}{' (gap)' if r['gap'] else ''}", "", f"_{r['question']}_ — `queries/{r['file']}`", ""]
        if r["rows"]:
            lines += ["| " + " | ".join(r["vars"]) + " |", "|" + "---|" * len(r["vars"])]
            lines += ["| " + " | ".join(f"`{c}`" if c.startswith("bg:") else c for c in row) + " |"
                      for row in r["rows"][:30]]
            if len(r["rows"]) > 30:
                lines.append(f"\n…and {len(r['rows']) - 30} more.")
        else:
            lines.append("_No results._")
        lines.append("")
    (GRAPH_DIR / "competency.md").write_text("\n".join(lines) + "\n")

    # stats
    by = lambda k: Counter(a[k] for a in arts)
    out = ["# Graph statistics", "",
           f"- Articles (nodes written): **{len(arts)}**",
           f"- Frontier nodes (referenced, unwritten): **{len(frontier)}**",
           f"- Asserted edges: **{n_edges}** (typed + evidenced: "
           f"**{sum(len(a.get('relations') or []) for a in arts)}**)",
           f"- Asserted triples: **{len(asserted)}**; inferred by OWL-RL: **{len(inferred)}**",
           f"- Citations: **{sum(len(a['sources']) for a in arts)}**",
           f"- Scripture references: **{sum(len(a.get('references') or []) for a in arts)}**; "
           f"study questions: **{sum(len(a.get('studyQuestions') or []) for a in arts)}**; "
           f"procedures: **{sum(1 for a in arts if a.get('steps'))}**; "
           f"before/after examples: **{sum(1 for a in arts if a.get('example'))}**",
           f"- Weakly connected components: **{nx.number_weakly_connected_components(g) if len(g) else 0}**",
           f"- Communities (Louvain): **{len(comms)}**; max k-core: **{max(core.values()) if core else 0}**", ""]
    if pr:
        out += ["## Most central nodes", "", "PageRank = authority; betweenness = bridges between areas.", "",
                "| Node | PageRank | Betweenness | Written |", "|---|---|---|---|"]
        out += [f"| `{n}` | {v:.4f} | {btw.get(n, 0):.4f} | {'yes' if n in known else 'no'} |"
                for n, v in sorted(pr.items(), key=lambda kv: (-kv[1], kv[0]))[:15]]
        out.append("")
    if comms:
        out += ["## Communities", ""]
        for i, c in enumerate(sorted(comms, key=lambda c: (-len(c), sorted(c)[0]))[:10], 1):
            out.append(f"{i}. " + ", ".join(f"`{x}`" for x in sorted(c)[:12]) + (" …" if len(c) > 12 else ""))
        out.append("")
    for title, key in (("By type", "type"), ("By domain", "domain"), ("By level", "level"),
                       ("By basis", "basis")):
        out += [f"## {title}", ""] + [f"- {k}: {v}" for k, v in sorted(by(key).items())] + [""]
    covered = by("domain")
    out += ["## Domain coverage (breadth runs pick the lowest)", ""]
    out += [f"- {d}: {covered.get(d, 0)}" for d in sorted(seeds, key=lambda d: (covered.get(d, 0), d))]
    (GRAPH_DIR / "stats.md").write_text("\n".join(out) + "\n")


# ===================================================================== commands ===
def full_check(build: bool) -> int:
    o = load_ontology()
    seeds = load_seeds()
    arts, errs = load_articles()
    warns: list[str] = []
    if not errs:
        e, warns = validate(arts, o, seeds)
        errs += e
    if not errs:
        asserted, per_article, star = assemble(arts, seeds)
        inferred = reason(asserted, o)
        errs += consistency(asserted, inferred, o)
        errs += shacl(asserted, o)
    for w in warns:
        print("  warning:", w)
    if errs:
        print(f"{len(errs)} problem(s):")
        for e in errs:
            print("  -", e)
        return 1
    print(f"OK: {len(arts)} article(s) valid; {len(asserted)} asserted + {len(inferred)} inferred triples; "
          "SHACL conforms; no contradictions.")
    if build:
        write_exports(arts, seeds, o, asserted, per_article, star, inferred)
        write_study_guide(arts, o)
        write_scripture_index(arts)
        write_analytics(arts, o, seeds, asserted, inferred)
        print("Graph regenerated in graph/.")
    return 0


def similar(query: str) -> int:
    arts, _ = load_articles()
    if not arts:
        print("No articles yet. Topic is unique.")
        return 0
    docs = [" ".join([a.get("title", "")] + list(a.get("aliases") or []) + [str(a.get("summary", ""))])
            for a in arts] + [query]
    vec = tfidf(docs)
    idf = label_idf([x for a in arts for x in [a.get("title", "")] + list(a.get("aliases") or [])])
    scored = []
    for a, v in zip(arts, vec):
        labels = [a.get("title", "")] + list(a.get("aliases") or [])
        lab = 1.0 if norm(query) in {norm(x) for x in labels} else max(label_sim(query, x, idf) for x in labels)
        scored.append((max(lab, cosine(vec[-1], v)), lab, cosine(vec[-1], v), a["id"], a.get("title")))
    print("score  label  tfidf  id  title")
    for s, lab, cs, i, t in sorted(scored, reverse=True)[:10]:
        print(f"{s:.2f}   {lab:.2f}   {cs:.2f}   {i}  {t}")
    return 0


def new(domain: str, sl: str, cls: str) -> int:
    o, seeds = load_ontology(), load_seeds()
    if domain not in seeds or cls not in o.classes - NON_ARTICLE_CLASSES or not ID_RE.match(f"bg:{sl}"):
        print(f"usage: new <domain in {sorted(seeds)}> <lowercase-slug> <Type in {sorted(o.classes - NON_ARTICLE_CLASSES)}>")
        return 2
    path = ARTICLES / domain / f"{sl}.md"
    if path.exists():
        print(f"{path} already exists")
        return 1
    today = date.today().isoformat()
    extra = ""
    if o.is_a(cls, STEP_CLASSES):
        extra += "steps:\n  - TODO first step\n  - TODO second step\n  - TODO third step\n"
    if o.is_a(cls, EXAMPLE_CLASSES):
        extra += "example:\n  situation: TODO\n  before: TODO\n  after: TODO\n  why: TODO\n"
    if o.is_a(cls, STUDY_CLASSES):
        extra += "studyQuestions:\n  - TODO?\n  - TODO?\n"
    refs = "references: []\n" if o.is_a(cls, NO_REF_CLASSES) else "references: [TODO]\n"
    body = "\n\n".join(f"{s}\n" for s in ["## Why it matters"] + required_sections(o, cls)[:-1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"""---
id: bg:{sl}
type: {cls}
title: TODO
aliases: []
domain: {domain}
summary: >-
  TODO
level: introductory
basis: TODO
broader: []
related: []
requires: []
relations: []
{refs}{extra}sameAs: []
sources: []
created: {today}
---

# TODO

{body}
## Sources
""")
    print(f"created {path.relative_to(ROOT)}")
    return 0


def query(q: str) -> int:
    o, seeds = load_ontology(), load_seeds()
    arts, errs = load_articles()
    if errs:
        print("\n".join(errs))
        return 1
    asserted, _, _ = assemble(arts, seeds)
    store = bind(Graph())
    for gg in (asserted, reason(asserted, o), o.graph):
        store += gg
    text = Path(q).read_text() if q.endswith(".rq") and Path(q).exists() else q
    for row in store.query(text, initNs=PREFIXES):
        print("\t".join(short(x) if x is not None else "" for x in row))
    return 0


def main() -> int:
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else "check"), sys.argv[2:]
    if cmd in ("check", "build"):
        return full_check(cmd == "build")
    if cmd == "similar":
        return similar(" ".join(args))
    if cmd == "new" and len(args) == 3:
        return new(*args)
    if cmd == "query" and args:
        return query(" ".join(args))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
