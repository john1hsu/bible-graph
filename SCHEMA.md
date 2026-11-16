# Article schema

Each article is one **node**: `articles/<domain>/<slug>.md`, where the filename equals the id's slug and `<domain>` is a key in `topics/seeds.yaml`. Scaffold one with `python3 scripts/kg.py new <domain> <slug> <Type>`, which pre-fills the fields and sections its class needs.

```markdown
---
id: bg:parable-of-the-prodigal-son       # bg: + lowercase-hyphen slug; never changes
type: Parable                            # most specific class from ontology/ontology.ttl
title: Parable of the Prodigal Son
aliases: [parable of the lost son, parable of the two sons]
domain: key-passages                     # key in topics/seeds.yaml (becomes a SKOS ConceptScheme)
summary: >-                              # 1–2 sentence definition (skos:definition)
  Jesus's story of a younger son who squanders his inheritance and is welcomed home by his father, and an elder brother who resents it.
level: introductory                      # introductory | intermediate | advanced
basis: scriptural                        # see table below
broader: [bg:parables-of-jesus]          # skos:broader, 1–3; must stay acyclic
related: [bg:parable-of-the-lost-sheep]  # skos:related (symmetric)
requires: [bg:parables-of-jesus]         # learning prerequisites (transitive, acyclic) -> graph/learning-path.md
relations:                               # typed edges: EVERY one cites a source id below
  - {predicate: partOf, object: bg:gospel-of-luke, source: s1, confidence: high}
  - {predicate: teaches, object: bg:grace, source: s2}                         # confidence defaults to medium
  - {predicate: speaksTo, object: bg:forgiveness-in-the-bible, source: s3}
references: [Luke 15:11-32, Luke 15:1-2]  # key Scripture: Book, Book 3, Book 3:16 or Book 3:16-18; quote any with a comma
studyQuestions:                          # >= 2 for books, passages, people, events, themes, covenants, doctrines,
  - Who is Jesus speaking to in Luke 15:1-2, and why does that matter for the story?   #   practices, methods, pitfalls, life situations
  - Which son do I most resemble, and what does the father say to him?
sameAs: []                               # optional entity links: Wikidata QIDs or https IRIs (incl. sibling graphs) -> skos:exactMatch
sources:                                 # >= 3; >= 1 scripture; >= 2 strong; >= 1 scholarly
  - id: s1
    title: Luke 15 (World English Bible)
    publisher: Bible Gateway
    url: https://www.biblegateway.com/passage/?search=Luke+15&version=WEB
    type: scripture
    accessed: 2026-11-15
created: 2026-11-15
modified: 2026-11-20                     # optional; set when an article is revised
---

# Parable of the Prodigal Son

Prose with footnote citations after each claim.[^s1]

## Why it matters          (expected for every article)
...class-specific sections (table below)...
## Views across traditions (when basis: varies-by-tradition)
## Scholarly views         (when basis: debated)
## Connections             (always: explain each edge in prose, with citations)
## Sources                 (always)
[^s1]: "Luke 15", *World English Bible*, Bible Gateway. https://... (accessed 2026-11-15)
```

Practices and methods also carry `steps` (≥ 3) and an `example`; pitfalls and misconceptions carry an `example`:

```yaml
steps:
  - Read the whole chapter around the verse before deciding what it means.
  - ...
example:
  situation: Someone quotes Jeremiah 29:11 as a promise of a smooth career.
  before: "God promises me prosperity and no hardship this year."          # careless reading / popular claim / old habit
  after: "God promised exiles in Babylon a future after seventy years."    # careful reading / what the text says / better habit
  why: Reading the letter to the exiles restores the promise's original setting.
```

Class-specific headings are enforced (subclasses inherit them):

| Class | Required headings |
|---|---|
| `Book` | `## Background` (author, date, audience), `## Outline`, `## Key themes` |
| `Collection` | `## Books included` |
| `Passage`, `Parable` | `## Context`, `## Walking through the text`, `## Interpretation` |
| `Person` | `## Life and story`, `## Legacy in Scripture` |
| `Group` | `## Who they were`, `## In the biblical story` |
| `Place` | `## Geography`, `## In the biblical story` |
| `Event` | `## What happened`, `## Significance` |
| `Period` | `## Timeline`, `## Significance` |
| `Theme` | `## Through the Bible` |
| `Covenant` | `## Biblical basis`, `## Through the Bible` |
| `Doctrine` | `## Biblical basis`, `## Historical development` |
| `Genre` | `## How to read it`, `## Common mistakes` |
| `Method`, `Practice` | `## How to apply it`, `## Common mistakes` |
| `Pitfall` | `## How to spot it`, `## How to fix it` |
| `Misconception` | `## Where it comes from`, `## What the Bible actually says` |
| `LifeSituation` | `## What Scripture says`, `## Pitfalls` |
| `Tradition` | `## Key teachings`, `## How it reads Scripture` |
| `Scholar`, `Work` | `## Life and work` / `## Background`, `## Influence` |
| `Manuscript`, `Artifact` | `## Description`, `## Significance` |
| `Translation` | `## Translation approach`, `## Significance` |

## Classes (`type`)

| Class | Use for |
|---|---|
| `Concept` | general ideas about the Bible: the canon, inspiration, the Old and New Testaments, the deuterocanonical books, chapters and verses |
| `Book` | one book: Genesis, Ruth, Psalms, Isaiah, Mark, Romans, Revelation; deuterocanonical books (Tobit, Sirach, 1 Maccabees) labelled as such |
| `Collection` | groupings of books: the Pentateuch, the Historical Books, the Wisdom Books, the Major Prophets, the Twelve, the Gospels, the Pauline epistles |
| `Passage` | key passages: the creation account, the Ten Commandments, the Shema, Psalm 23, Isaiah 53, the Sermon on the Mount, Romans 8, 1 Corinthians 13 |
| `Parable` | parables of Jesus (a kind of `Passage`) |
| `Person` | biblical figures: Abraham, Sarah, Moses, Ruth, David, Elijah, Mary, Peter, Paul, Lydia |
| `Group` | peoples and groups: the Israelites, the Philistines, the Pharisees, the Samaritans, the Twelve |
| `Place` | Jerusalem, the Temple, Bethlehem, Galilee, Mount Sinai, Babylon, Corinth, Rome |
| `Event` | the Flood, the Exodus, the exile, the baptism of Jesus, the crucifixion, the resurrection, Pentecost |
| `Period` | the patriarchs, the judges, the united monarchy, the divided kingdom, the exile, the Second Temple period |
| `Theme` | themes traced across Scripture: the kingdom of God, holiness, exile and return, redemption, grace, the image of God |
| `Covenant` | the Noahic, Abrahamic, Mosaic, Davidic and New covenants |
| `Doctrine` | the Trinity, the incarnation, the atonement, justification, the resurrection of the body, baptism, the Lord's Supper |
| `Genre` | narrative, law, poetry, wisdom literature, prophecy, gospel, epistle, apocalyptic |
| `Method` | interpretive principles: reading in context, reading by genre, Scripture interprets Scripture, typology, the four senses of Scripture |
| `Practice` | study and devotional practices with steps: inductive Bible study, lectio divina, Scripture memorisation, a reading plan, a word study |
| `Pitfall` | reading mistakes: proof-texting, eisegesis, word-study fallacies, anachronism, reading narrative as command |
| `Misconception` | popular beliefs the text doesn't support: "God helps those who help themselves", the three wise men, the apple in Eden |
| `LifeSituation` | situations Christians bring to Scripture: suffering, grief, anxiety, doubt, forgiveness, work, money, marriage |
| `Tradition` | traditions of reading Scripture: Catholic, Eastern Orthodox, Lutheran, Reformed, Anglican, Wesleyan, Anabaptist, Pentecostal, rabbinic Judaism |
| `Field` | biblical archaeology, textual criticism, biblical theology, Second Temple studies |
| `Scholar` | post-biblical interpreters and translators: Josephus, Origen, Jerome, Augustine, Aquinas, Luther, Calvin, Tyndale, Wesley |
| `Work` | non-biblical writings: the Nicene Creed, the Mishnah, Josephus's *Antiquities*, a catechism or confession |
| `Manuscript` | the Dead Sea Scrolls, the Great Isaiah Scroll, Codex Sinaiticus, the Aleppo and Leningrad Codices, Papyrus 52 |
| `Translation` | the Septuagint, the Vulgate, the Peshitta, Luther's Bible, Tyndale, the King James Version, modern versions |
| `Artifact` | the Merneptah Stele, the Tel Dan Stele, the Mesha Stele, the Siloam inscription, the Cyrus Cylinder, the Pilate Stone |
| `Organization` | Bible societies, translation committees, research institutes |

Disjointness is declared (problems — `Pitfall`, `Misconception` — vs. remedies — `Method`, `Practice`; books vs. collections vs. passages; concepts vs. texts vs. people, groups, places, events, periods, interpreters, works, manuscripts, translations, artifacts). The reasoner types unwritten nodes from edge ranges; two edges that imply incompatible types fail the build.

## Predicates (`relations[].predicate`)

| Predicate | Meaning | Constraint | Inferred inverse |
|---|---|---|---|
| `partOf` | passage in a book, book in a collection | transitive, acyclic | `hasPart` |
| `requires`* | learning prerequisite | transitive, acyclic | `prerequisiteOf` |
| `instanceOf` | a kind of | | `hasInstance` |
| `contrastsWith`, `confusedWith`, `alternativeTo`, `complements` | comparisons | symmetric | itself |
| `attributedTo` | written by / traditionally attributed to | Text → Person | `attributedAuthorOf` |
| `hasGenre` | genre of a text | Text → Genre | `genreOf` |
| `features` | a person, group, place or event in a text or event | Text/Event → Person/Group/Place/Event | `featuredIn` |
| `teaches` | a text develops a theme, covenant or doctrine | Text → Theme/Covenant/Doctrine | `taughtIn` |
| `illustrates` | a person, group, place or event illustrates one | → Theme/Covenant/Doctrine | `illustratedBy` |
| `quotes`, `alludesTo` | Scripture quoting or echoing Scripture | Text → Text | `quotedIn`, `alludedToIn` |
| `parallels` | parallel account (Synoptic Gospels, Kings/Chronicles) | Text ↔ Text, symmetric | itself |
| `fulfills` | presented (usually in the New Testament) as fulfilling a promise or prophecy | → Text | `fulfilledIn` |
| `prefigures` | a type: a person or event read as foreshadowing another | → Person/Event/Doctrine/Theme | `prefiguredBy` |
| `occurredAt` | where an event happened | Event → Place | `siteOf` |
| `occurredDuring` | when | → Period | `periodOf` |
| `precedes` | timeline order | Event/Period, transitive, acyclic | `follows` |
| `causes` | leads to | | `causedBy` |
| `parentOf`, `spouseOf`, `siblingOf`, `successorOf` | family and succession | Person → Person (spouse, sibling symmetric) | `childOf`, itself, itself, `succeededBy` |
| `memberOf` | person in a group | Person → Group | `hasMember` |
| `addresses` | guards against / corrects | Method/Practice → Pitfall/Misconception | `addressedBy` |
| `usedFor` | method or practice especially suited to a genre or text | Method/Practice → Genre/Text | `readWith` |
| `speaksTo` | Scripture or teaching for a life situation | → LifeSituation | `drawsOn` |
| `heldBy` | taught or emphasised by a tradition | → Tradition | `holds` |
| `explainedBy` | background that sheds light on it | | `explains` |
| `supportedBy`, `challengedBy` | evidence for / correction, critique, myth-busting | | `supports`, `challenges` |
| `corroboratedBy` | attested outside the Bible | → Artifact/Manuscript/Work | `corroborates` |
| `preservedIn` | text preserved in a manuscript or rendered in a translation | Text → Manuscript/Translation | `preserves` |
| `discoveredAt` | find spot | Artifact/Manuscript → Place | `findSpotOf` |
| `introducedBy`, `introducedIn` | championed by an interpreter / set out in a work | → Scholar / → Work | `introduced`, `introduces` |
| `authoredBy` | author or translator of a work or translation | Work/Translation → Scholar | `authored` |
| `influencedBy` | intellectual influence | | `influenced` |
| `studiedIn` | studied in a discipline | → Field | |

\* `requires` is written as its own list, not under `relations`. Never write inverses yourself; the reasoner materialises them in `graph/inferred.nt`. If you need a new predicate or class, add it to `ontology/ontology.ttl` with a label, any domain/range, and its inverse/characteristics in the same commit.

## Basis

| value | meaning | rule |
|---|---|---|
| `scriptural` | what the biblical text itself says or narrates (a book's content, a passage, a person's story, a theme traced through texts) | |
| `ecumenical` | a teaching held across Catholic, Orthodox and Protestant traditions (the Trinity, the resurrection, the creeds) | |
| `varies-by-tradition` | Christian traditions understand it differently (canon, baptism, the Lord's Supper, the millennium) | needs `## Views across traditions` |
| `consensus` | broad scholarly agreement on a historical, textual or background question | |
| `debated` | scholars disagree (the authorship of Hebrews, the date of the Exodus) | needs `## Scholarly views` |
| `misconception` | a popular belief the text or evidence doesn't support | only and always for `Misconception`; needs a `challengedBy` relation |
| `historical` | history of interpretation, translation, manuscripts and people after the Bible | |
| `devotional` | a study or devotional practice, method or piece of practical guidance | only for `Practice`, `Method`, `Pitfall`, `LifeSituation` |

## Scripture references

`references` lists the key passages an article rests on, as `Book`, `Book 3`, `Book 3:16`, `Book 3:16-18` or `Book 3:16–4:2`. Books use their common English names (`1 Samuel`, `Song of Songs`, `Sirach`, `Revelation`; `Psalm`, `Song of Solomon`, `Wisdom` and `Ecclesiasticus` are accepted). The validator checks the book and its chapter number. Every article needs at least one, except `Scholar`, `Work`, `Manuscript`, `Translation`, `Artifact`, `Organization` and `Field`, which are about things outside the text. References feed `graph/scripture-index.md` and link to the passage on the website.

## Source types

| type | strong | scholarly | examples |
|---|---|---|---|
| `scripture` | yes | no | the passage itself in a named translation: Bible Gateway, USCCB (NABRE), ESV.org, NET Bible, STEP Bible, Blue Letter Bible, Sefaria |
| `peer-reviewed` | yes | yes | *Journal of Biblical Literature*, *New Testament Studies*, *Vetus Testamentum*, *Tyndale Bulletin*, *Catholic Biblical Quarterly* (DOI page) |
| `primary` | yes | yes | ancient texts outside the Bible: Josephus, Philo, the church fathers (CCEL, New Advent), the Dead Sea Scrolls, the Mishnah |
| `textbook` | yes | yes | academic introductions and commentaries from university and seminary presses |
| `reference-work` | yes | yes | Anchor Yale, Eerdmans and Lexham Bible dictionaries, ISBE, Oxford Bibliographies, the Catholic and Jewish Encyclopedias |
| `academic` | yes | yes | university and seminary pages and courses: Yale Open Courses, Tyndale House, Duke Divinity |
| `museum` | yes | yes | British Museum, Israel Museum, Louvre, Metropolitan Museum |
| `government` | yes | yes | Israel Antiquities Authority, Library of Congress |
| `confessional` | yes | no | a church's official teaching: Catechism of the Catholic Church, Westminster Confession, Book of Concord, Thirty-Nine Articles, Orthodox catechisms |
| `institutional` | yes | no | American Bible Society, United Bible Societies, BibleProject, Biblical Archaeology Society |
| `magazine` | yes | no | *Biblical Archaeology Review*, *Christianity Today* |
| `encyclopedia` | yes | no | Britannica |
| `preprint`, `news`, `community` | no | no | context only (sermons, blogs, Q&A sites, podcasts), never the sole support for a claim |

**Banned:** Wikipedia (and mirrors), Wikiquote, wikiHow, Quora, Fandom, quotation aggregators (BrainyQuote, Goodreads quotes, AZ Quotes, Quotefancy…), content farms, SEO listicles and AI-generated pages.

## Enforcement summary (`scripts/kg.py check`)

1. **Structure:** required fields, enums, id/filename/folder agreement, known domain, dates.
2. **Scripture:** valid references (known book, real chapter); ≥ 1 reference and ≥ 1 `scripture` source for articles about the Bible's content.
3. **Citations:** ≥ 3 sources, ≥ 2 strong, ≥ 1 scholarly, https only, no banned or duplicate URLs, every source cited, every substantive paragraph cited, every typed edge cites a source.
4. **Study rules:** class-specific sections; `## Views across traditions` / `## Scholarly views` by basis; ≥ 3 steps for practices and methods; before/after examples for practices, methods, pitfalls and misconceptions (before ≠ after, with a reason); ≥ 2 study questions where required; `challengedBy` for misconceptions; `devotional` and `misconception` only on the classes they fit.
5. **Graph rules:** ≥ 3 edges and ≥ 1 typed relation per node, domain/range on written targets, no cycles in `broader` / `requires` / `partOf` / `precedes`.
6. **Uniqueness:** no shared ids, titles or aliases; no near-identical titles; no copied text (5-gram shingles); no same-topic rewrite (TF-IDF cosine ≥ 0.80; ≥ 0.60 warns).
7. **Reasoning:** OWL 2 RL closure; any node inferred into two disjoint classes fails.
8. **SHACL:** `ontology/shapes.ttl` over the exported RDF with RDFS inference.
