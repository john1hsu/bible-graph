"""End-to-end tests for scripts/kg.py against a throwaway tree of fixture articles.

Fixtures use example.org URLs and synthetic prose: they exercise the validator,
reasoner, SHACL shapes and exports, and are never part of the real graph.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
KG = REPO / "scripts" / "kg.py"
NS = "https://github.com/john1hsu/bible-graph/"
TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"


def body(slug: str, sections: list[str]) -> str:
    def para(i: int) -> str:
        words = " ".join(f"{slug.replace('-', '')}{i}w{j}" for j in range(150))
        return f"Synthetic fixture prose for {slug} paragraph {i}: {words}.[^s1][^s2][^s3]"
    out = [f"# {slug}", "", para(0), "", para(1), ""]
    for k, s in enumerate(sections, 2):
        out += [s, "", para(k), ""]
    out += ["## Connections", "", para(99), "", "## Sources", "",
            "[^s1]: Fixture one. https://example.org/1", "[^s2]: Fixture two. https://example.org/2",
            "[^s3]: Fixture three. https://example.org/3"]
    return "\n".join(out) + "\n"


SOURCES = """sources:
  - {id: s1, title: Fixture one, publisher: Example, url: "https://example.org/SLUG/1", type: scripture, accessed: 2026-11-15}
  - {id: s2, title: Fixture two, publisher: Example, url: "https://example.org/SLUG/2", type: reference-work, accessed: 2026-11-15}
  - {id: s3, title: Fixture three, publisher: Example, url: "https://example.org/SLUG/3", type: textbook, accessed: 2026-11-15}
created: 2026-11-15
"""

ARTICLES = {
    ("new-testament-books", "gospel-of-mark"): ("""id: bg:gospel-of-mark
type: Book
title: Gospel of Mark
aliases: [Mark]
domain: new-testament-books
summary: The shortest of the four Gospels, a fast-moving account of the ministry, death and resurrection of Jesus.
level: introductory
basis: scriptural
broader: [bg:gospels]
related: [bg:gospel-of-matthew]
relations:
  - {predicate: attributedTo, object: bg:mark-the-evangelist, source: s2, confidence: medium}
  - {predicate: hasGenre, object: bg:gospel-genre, source: s3}
  - {predicate: teaches, object: bg:kingdom-of-god, source: s1, confidence: high}
references: [Mark 1:1, Mark 1:14-15, Mark 8:27-30]
studyQuestions:
  - How does Mark open his Gospel in Mark 1:1?
  - Why might Mark move so quickly from scene to scene?
""", ["## Background", "## Outline", "## Key themes"]),
    ("key-passages", "parable-of-the-sower"): ("""id: bg:parable-of-the-sower
type: Parable
title: Parable of the Sower
aliases: [parable of the soils]
domain: key-passages
summary: Jesus's parable of seed falling on four kinds of ground, which he explains as four ways people receive the word.
level: introductory
basis: scriptural
broader: [bg:parables-of-jesus]
relations:
  - {predicate: partOf, object: bg:gospel-of-mark, source: s1, confidence: high}
  - {predicate: parallels, object: bg:matthew-13, source: s2}
  - {predicate: teaches, object: bg:kingdom-of-god, source: s3}
references: [Mark 4:1-20]
studyQuestions:
  - What four kinds of ground does the seed fall on?
  - Which kind of ground best describes how I receive God's word this week?
""", ["## Context", "## Walking through the text", "## Interpretation"]),
    ("study-practices", "inductive-bible-study"): ("""id: bg:inductive-bible-study
type: Practice
title: Inductive Bible study
domain: study-practices
summary: A method of studying a passage in three stages, observation, interpretation and application, drawing conclusions from the text itself.
level: introductory
basis: devotional
broader: [bg:bible-study-methods]
requires: [bg:reading-in-context]
relations:
  - {predicate: addresses, object: bg:proof-texting, source: s2, confidence: high}
  - {predicate: usedFor, object: bg:gospel-of-mark, source: s3}
  - {predicate: confusedWith, object: bg:devotional-reading, source: s3, confidence: low}
references: [Acts 17:11, 2 Timothy 2:15]
steps:
  - Read the whole passage slowly and note who, what, where and when.
  - Ask what the passage meant to its first readers before deciding what it means now.
  - Write down one concrete way to put the passage into practice this week.
example:
  situation: Reading Philippians 4:13 before a big exam.
  before: "This verse promises I will ace any exam if I believe hard enough."
  after: "In context Paul is content in hunger and plenty; Christ strengthens me to be faithful whatever the result."
  why: Observing the surrounding verses first keeps the reader from turning a promise of contentment into a guarantee of success.
studyQuestions:
  - Did I observe what the text says before deciding what it means?
  - What did this passage mean to its first readers?
""", ["## How to apply it", "## Common mistakes"]),
    ("interpretation", "proof-texting"): ("""id: bg:proof-texting
type: Pitfall
title: Proof-texting
domain: interpretation
summary: Pulling a verse out of its context to support a conclusion already reached, rather than letting the passage speak.
level: introductory
basis: devotional
broader: [bg:interpretive-pitfalls]
related: [bg:eisegesis]
relations:
  - {predicate: causes, object: bg:misapplied-promises, source: s2, confidence: medium}
references: [Jeremiah 29:11]
example:
  situation: Someone quotes Jeremiah 29:11 as a promise of a smooth career.
  before: "God promises me prosperity and no hardship this year."
  after: "God promised exiles in Babylon a future after seventy years; it speaks of his faithfulness through hardship."
  why: Reading the letter to the exiles in Jeremiah 29 restores the original setting and keeps the promise's real shape.
studyQuestions:
  - Have I read the chapter around this verse?
  - Who was this promise first spoken to?
""", ["## How to spot it", "## How to fix it"]),
    ("old-testament-people", "abraham"): ("""id: bg:abraham
type: Person
title: Abraham
aliases: [Abram]
domain: old-testament-people
summary: The patriarch whom God called from Ur and promised land, descendants and blessing for all nations.
level: introductory
basis: scriptural
broader: [bg:patriarchs]
relations:
  - {predicate: parentOf, object: bg:isaac, source: s1, confidence: high}
  - {predicate: spouseOf, object: bg:sarah, source: s1, confidence: high}
  - {predicate: illustrates, object: bg:faith, source: s3}
references: [Genesis 12:1-3, Hebrews 11:8-12]
studyQuestions:
  - What three things does God promise Abram in Genesis 12:1-3?
  - How does Hebrews 11 describe Abraham's faith?
""", ["## Life and story", "## Legacy in Scripture"]),
    ("interpretation", "god-helps-those-who-help-themselves"): ("""id: bg:god-helps-those-who-help-themselves
type: Misconception
title: God helps those who help themselves
domain: interpretation
summary: A popular proverb often taken for a Bible verse; it does not appear in Scripture, which stresses God's help for the helpless.
level: introductory
basis: misconception
broader: [bg:sayings-not-in-the-bible]
relations:
  - {predicate: challengedBy, object: bg:romans-5, source: s1, confidence: high}
  - {predicate: confusedWith, object: bg:proverbs-6-6-11, source: s2, confidence: low}
references: [Romans 5:6-8]
example:
  situation: A friend says the Bible teaches that God helps those who help themselves.
  before: "It's in the Bible, so God only helps people who have earned it."
  after: "The saying is not in Scripture; Romans 5:6 says Christ died for us while we were still helpless."
  why: Checking the text shows the saying reverses the Bible's emphasis on grace to the undeserving.
""", ["## Where it comes from", "## What the Bible actually says"]),
    ("themes-and-theology", "baptism"): ("""id: bg:baptism
type: Doctrine
title: Baptism
domain: themes-and-theology
summary: The rite of washing with water in the name of the Father, Son and Holy Spirit by which people are joined to the church.
level: intermediate
basis: varies-by-tradition
broader: [bg:sacraments-and-ordinances]
relations:
  - {predicate: heldBy, object: bg:catholic-tradition, source: s2}
  - {predicate: heldBy, object: bg:baptist-tradition, source: s3}
references: [Matthew 28:19, Romans 6:3-4]
studyQuestions:
  - What does Paul connect baptism with in Romans 6:3-4?
  - Where do Christian traditions agree about baptism, and where do they differ?
""", ["## Biblical basis", "## Historical development", "## Views across traditions"]),
    ("manuscripts-translations-and-archaeology", "dead-sea-scrolls"): ("""id: bg:dead-sea-scrolls
type: Manuscript
title: Dead Sea Scrolls
aliases: [Qumran scrolls]
domain: manuscripts-translations-and-archaeology
summary: About 900 manuscripts found in caves near Qumran from 1947, including the oldest known copies of Hebrew Bible books.
level: introductory
basis: consensus
broader: [bg:biblical-manuscripts]
relations:
  - {predicate: discoveredAt, object: bg:qumran, source: s2, confidence: high}
  - {predicate: studiedIn, object: bg:textual-criticism, source: s3}
""", ["## Description", "## Significance"]),
}


def make_tree(tmp: Path, articles=ARTICLES) -> Path:
    for d in ("ontology", "topics", "queries"):
        shutil.copytree(REPO / d, tmp / d)
    for (dom, slug), (fm, secs) in articles.items():
        p = tmp / "articles" / dom / f"{slug}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\n{fm}{SOURCES.replace('SLUG', slug)}---\n{body(slug, secs)}")
    return tmp


def run(tmp: Path, *args: str, hashseed: str = "random") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(KG), *args], cwd=tmp,
                          env={"PYTHONHASHSEED": hashseed, "BG_KG_ROOT": str(tmp), "PATH": ""},
                          capture_output=True, text=True)


def test_valid_tree_builds(tmp_path):
    t = make_tree(tmp_path)
    r = run(t, "build")
    assert r.returncode == 0, r.stdout + r.stderr
    g = t / "graph"
    inferred = (g / "inferred.nt").read_text()
    o, i = f"{NS}ontology#", f"{NS}id/"
    # inverse properties materialised by the reasoner
    assert f"proof-texting> <{o}addressedBy> <{i}inductive-bible-study>" in inferred
    assert f"kingdom-of-god> <{o}taughtIn> <{i}gospel-of-mark>" in inferred
    assert f"isaac> <{o}childOf> <{i}abraham>" in inferred
    assert f"gospel-of-mark> <{o}hasPart> <{i}parable-of-the-sower>" in inferred
    assert f"catholic-tradition> <{o}holds> <{i}baptism>" in inferred
    # symmetric properties materialised
    assert f"sarah> <{o}spouseOf> <{i}abraham>" in inferred
    assert f"matthew-13> <{o}parallels> <{i}parable-of-the-sower>" in inferred
    # range axioms type unwritten frontier nodes
    assert f"isaac> {TYPE} <{o}Person>" in inferred
    assert f"qumran> {TYPE} <{o}Place>" in inferred
    assert f"matthew-13> {TYPE} <{o}Text>" in inferred
    frontier = (g / "frontier.md").read_text()
    assert "`bg:mark-the-evangelist`" in frontier and "Person" in frontier
    assert "<< <" in (g / "edge-evidence.ttls").read_text()
    guide = (g / "study-guide.md").read_text()
    assert "| Before | After |" in guide and "1. Read the whole passage" in guide and "Study questions:" in guide
    assert "Read: Mark 4:1-20" in guide
    idx_md = (g / "scripture-index.md").read_text()
    assert idx_md.index("## Genesis") < idx_md.index("## Jeremiah") < idx_md.index("## Matthew") \
        < idx_md.index("## Mark") < idx_md.index("## Romans") < idx_md.index("## 2 Timothy")
    mark = idx_md[idx_md.index("## Mark"):idx_md.index("## Acts")]
    assert mark.index("Mark 1:1**") < mark.index("Mark 1:14-15") < mark.index("Mark 4:1-20") < mark.index("Mark 8:27-30")
    triples = (g / "triples.nt").read_text()
    assert "HowToStep" in triples and f"<{o}keyReference> \"Genesis 12:1-3\"" in triples
    idx = json.loads((g / "index.json").read_text())
    assert {x["id"] for x in idx} == {"bg:gospel-of-mark", "bg:parable-of-the-sower", "bg:inductive-bible-study",
                                      "bg:proof-texting", "bg:abraham", "bg:god-helps-those-who-help-themselves",
                                      "bg:baptism", "bg:dead-sea-scrolls"}
    assert next(x for x in idx if x["id"] == "bg:abraham")["references"] == ["Genesis 12:1-3", "Hebrews 11:8-12"]
    comp = (g / "competency.md").read_text()
    gaps = comp.split("## People, places and events not tied to the text (gap)")[1].split("\n## ")[0]
    assert "bg:abraham" in gaps                       # not yet linked to a text it appears in
    assert "Pitfalls with no remedy (gap)" in comp
    pit = comp.split("## Pitfalls with no remedy (gap)")[1].split("\n## ")[0]
    assert "_No results._" in pit                     # proof-texting is addressed by inductive study
    path = (g / "learning-path.md").read_text()
    assert path.index("reading-in-context") < path.index("Inductive Bible study")
    stats = (g / "stats.md").read_text()
    assert "## By basis" in stats and "Scripture references: **12**" in stats
    # deterministic: rebuilding under different hash seeds (as CI and scheduled runs do) is byte-identical
    before = {p.name: p.read_text() for p in g.iterdir()}
    for seed in ("1", "2", "3", "4"):
        assert run(t, "build", hashseed=seed).returncode == 0
        assert before == {p.name: p.read_text() for p in g.iterdir()}, f"output changed with PYTHONHASHSEED={seed}"


def mutate(key, old, new):
    arts = dict(ARTICLES)
    fm, secs = arts[key]
    assert old in fm
    arts[key] = (fm.replace(old, new), secs)
    return arts


PRACTICE = ("study-practices", "inductive-bible-study")
PITFALL = ("interpretation", "proof-texting")
PERSON = ("old-testament-people", "abraham")
BOOK = ("new-testament-books", "gospel-of-mark")
MISC = ("interpretation", "god-helps-those-who-help-themselves")


@pytest.mark.parametrize("key,old,new,expect", [
    (PRACTICE, "type: Practice", "type: Misconception\n", "addresses expects subject"),
    (BOOK, "source: s3}", "source: s9}", "unknown source"),
    (MISC, "  - {predicate: challengedBy, object: bg:romans-5, source: s1, confidence: high}\n", "",
     "needs a challengedBy"),
    (PERSON, "basis: scriptural", "basis: misconception", "basis 'misconception' is for"),
    (PERSON, "basis: scriptural", "basis: devotional", "'devotional' is only for"),
    (PRACTICE, "  - Read the whole passage slowly and note who, what, where and when.\n", "", ">= 3 steps"),
    (PITFALL, "  - Who was this promise first spoken to?\n", "", ">= 2 studyQuestions"),
    (PITFALL, "after: \"God promised exiles in Babylon a future after seventy years; it speaks of his faithfulness through hardship.\"",
     "after: \"God promises me prosperity and no hardship this year.\"", "before and after are the same"),
    (PRACTICE, "title: Inductive Bible study", "title: Inductive Bible study\naliases: [Mark]", "collides"),
    (BOOK, "hasGenre, object: bg:gospel-genre", "hasGenre, object: bg:isaac", "contradiction"),
    (PERSON, "parentOf, object: bg:isaac", "parentOf, object: bg:gospel-of-mark", "expects object in ['Person']"),
    (PERSON, "references: [Genesis 12:1-3, Hebrews 11:8-12]", "references: [Genesis 51:1]", "Genesis has 50 chapters"),
    (PERSON, "references: [Genesis 12:1-3, Hebrews 11:8-12]", "references: [Hezekiah 3:1]", "unknown book 'Hezekiah'"),
    (PERSON, "references: [Genesis 12:1-3, Hebrews 11:8-12]", "references: [Genesis 12.1]", "bad Scripture reference"),
    (PERSON, "references: [Genesis 12:1-3, Hebrews 11:8-12]\n", "", "needs at least 1 key Scripture reference"),
])
def test_rejections(tmp_path, key, old, new, expect):
    t = make_tree(tmp_path, mutate(key, old, new))
    r = run(t, "check")
    assert r.returncode == 1 and expect in r.stdout, r.stdout


def test_reference_formats(tmp_path):
    refs = ("references: [Psalm 23, Song of Solomon 2:1, 1 Corinthians 13:4-7, Jude 3, \"John 3:16, 18\", "
            "Isaiah 52:13–53:12, Sirach 1:1, Bel and the Dragon 1:3, Obadiah]")
    arts = mutate(PERSON, "references: [Genesis 12:1-3, Hebrews 11:8-12]", refs)
    r = run(make_tree(tmp_path, arts), "build")
    assert r.returncode == 0, r.stdout
    idx_md = (tmp_path / "graph" / "scripture-index.md").read_text()
    assert "## Psalms" in idx_md and "## Song of Songs" in idx_md and "## Sirach" in idx_md
    assert idx_md.index("## Obadiah") < idx_md.index("## Sirach") < idx_md.index("## Matthew")


def test_needs_scripture_source(tmp_path):
    t = make_tree(tmp_path)
    p = t / "articles" / "old-testament-people" / "abraham.md"
    p.write_text(p.read_text().replace("type: scripture", "type: textbook"))
    r = run(t, "check")
    assert r.returncode == 1 and "needs at least 1 'scripture' source" in r.stdout, r.stdout
    # a manuscript article is about the history of the text, so it needs neither
    m = t / "articles" / "manuscripts-translations-and-archaeology" / "dead-sea-scrolls.md"
    assert "references" not in m.read_text()


def test_scripture_is_not_scholarship(tmp_path):
    t = make_tree(tmp_path)
    p = t / "articles" / "old-testament-people" / "abraham.md"
    p.write_text(p.read_text().replace("type: reference-work", "type: confessional").replace("type: textbook", "type: magazine"))
    r = run(t, "check")
    assert r.returncode == 1 and "needs at least 1 scholarly source" in r.stdout, r.stdout


def test_views_across_traditions_section(tmp_path):
    t = make_tree(tmp_path)
    p = t / "articles" / "themes-and-theology" / "baptism.md"
    p.write_text(p.read_text().replace("## Views across traditions", "## Other notes"))
    r = run(t, "check")
    assert r.returncode == 1 and "Views across traditions" in r.stdout, r.stdout


def test_debated_needs_scholarly_views(tmp_path):
    arts = mutate(BOOK, "basis: scriptural", "basis: debated")
    r = run(make_tree(tmp_path, arts), "check")
    assert r.returncode == 1 and "## Scholarly views" in r.stdout, r.stdout


def test_passage_sections_inherited_by_parable(tmp_path):
    t = make_tree(tmp_path)
    p = t / "articles" / "key-passages" / "parable-of-the-sower.md"
    p.write_text(p.read_text().replace("## Walking through the text", "## Notes"))
    r = run(t, "check")
    assert r.returncode == 1 and "Walking through the text" in r.stdout, r.stdout


def test_precedes_cycle(tmp_path):
    arts = dict(ARTICLES)
    for slug, nxt in (("the-exodus", "bg:giving-of-the-law"), ("giving-of-the-law", "bg:the-exodus")):
        arts[("events-and-timeline", slug)] = (f"""id: bg:{slug}
type: Event
title: {slug.replace('-', ' ').capitalize()}
domain: events-and-timeline
summary: A fixture event used to check that the biblical timeline cannot loop back on itself.
level: introductory
basis: scriptural
broader: [bg:events]
relations:
  - {{predicate: precedes, object: {nxt}, source: s1}}
  - {{predicate: occurredAt, object: bg:egypt, source: s2}}
references: [Exodus 12:31-42]
studyQuestions:
  - What happened here?
  - Why does it matter?
""", ["## What happened", "## Significance"])
    r = run(make_tree(tmp_path, arts), "check")
    assert r.returncode == 1 and "cycle in 'precedes'" in r.stdout, r.stdout


def test_requires_cycle(tmp_path):
    arts = mutate(PITFALL, "related: [bg:eisegesis]", "related: [bg:eisegesis]\nrequires: [bg:inductive-bible-study]")
    arts = {**arts, PRACTICE: (arts[PRACTICE][0].replace("requires: [bg:reading-in-context]",
                                                         "requires: [bg:proof-texting]"), arts[PRACTICE][1])}
    r = run(make_tree(tmp_path, arts), "check")
    assert r.returncode == 1 and "cycle in 'requires'" in r.stdout


def test_banned_source(tmp_path):
    t = make_tree(tmp_path)
    p = t / "articles" / "interpretation" / "proof-texting.md"
    p.write_text(p.read_text().replace("https://example.org/proof-texting/1", "https://www.brainyquote.com/X"))
    r = run(t, "check")
    assert r.returncode == 1 and "banned domain" in r.stdout


def test_similar_and_new(tmp_path):
    t = make_tree(tmp_path)
    r = run(t, "similar", "Abram")
    assert r.returncode == 0 and r.stdout.splitlines()[1].split()[3] == "bg:abraham"
    r = run(t, "new", "study-practices", "lectio-divina", "Practice")
    assert r.returncode == 0
    text = (t / "articles" / "study-practices" / "lectio-divina.md").read_text()
    assert "steps:" in text and "example:" in text and "studyQuestions:" in text and "## Common mistakes" in text
    assert "references: [TODO]" in text
    r = run(t, "new", "old-testament-books", "genesis", "Book")
    assert r.returncode == 0
    text = (t / "articles" / "old-testament-books" / "genesis.md").read_text()
    assert "## Outline" in text and "studyQuestions:" in text
    r = run(t, "new", "key-passages", "parable-of-the-good-samaritan", "Parable")
    assert r.returncode == 0
    assert "## Walking through the text" in (t / "articles" / "key-passages" / "parable-of-the-good-samaritan.md").read_text()
    r = run(t, "new", "manuscripts-translations-and-archaeology", "codex-sinaiticus", "Manuscript")
    assert r.returncode == 0
    assert "references: []" in (t / "articles" / "manuscripts-translations-and-archaeology" / "codex-sinaiticus.md").read_text()


def test_similar_label_score(tmp_path):
    """Short or loosely related labels must not hit the 0.5 duplicate threshold; real variants still must."""
    t = make_tree(tmp_path)

    def top(q):
        line = run(t, "similar", q).stdout.splitlines()[1].split()
        return float(line[1]), line[3]   # label score, id

    assert top("Gospel of Luke")[0] < 0.5                # one common word only
    assert top("Parable of the talents")[0] < 0.5        # shares only "parable"
    score, node = top("Sower parable")
    assert node == "bg:parable-of-the-sower" and score >= 0.5
    assert top("Inductive Bible studies")[0] >= 0.5      # inflection variant
    assert top("Abraham") == (1.0, "bg:abraham")         # exact title


def test_empty_tree(tmp_path):
    t = make_tree(tmp_path, {})
    r = run(t, "build")
    assert r.returncode == 0, r.stdout
