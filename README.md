# Bible Graph

A growing, citation-backed guide to the Bible for Christians who want to know it better: how the Bible is put together, every book of the Old and New Testaments, key passages and parables, the people, places, events and periods of the biblical story, the life and teachings of Jesus, the great themes, covenants and doctrines, how to read and study Scripture well, its historical and cultural background, how the text was preserved and translated, and what it says to everyday life. A scheduled run researches one new topic, checks every verse against the text, writes it as a study-ready node with evidenced, typed edges, and only commits it if the validator, the OWL reasoner and the SHACL shapes all agree it is sound.

It is written for Christians of every tradition: where Catholic, Orthodox and Protestant Christians agree it says so, where they differ it sets out each view fairly from that tradition's own sources, and where scholars debate authorship, dating or history it gives the traditional and scholarly views side by side.

**Read it online: https://john1hsu.github.io/bible-graph/** (rebuilt automatically on every new article by `.github/workflows/pages.yml` from `site/build.py`).

Start with **[`graph/scripture-index.md`](graph/scripture-index.md)** (every passage covered, Genesis to Revelation) and **[`graph/study-guide.md`](graph/study-guide.md)** (every study question, practice and before/after reading, ready for personal or small-group study).

## Architecture

```
articles/<domain>/<slug>.md          Markdown + YAML frontmatter (one node each)
        │  scripts/kg.py
        ▼
 1. structural validation      Scripture references (book + chapter), citations, uniqueness (shingles + TF-IDF), study rules, acyclicity
 2. RDF assembly               SKOS + PROV-O + schema.org HowTo + before/after readings, one named graph per article
 3. OWL 2 RL reasoning         inverse / symmetric / transitive properties, domain & range typing
 4. consistency checking       disjoint-class contradictions, domain/range violations
 5. SHACL validation           ontology/shapes.ttl (semantic contract on the exported RDF)
 6. exports + analytics        graph/  (regenerated on every commit; CI fails if stale)
```

| Layer | What | Where |
|---|---|---|
| Ontology | OWL 2 RL classes (Book, Collection, Passage, Parable, Person, Group, Place, Event, Period, Theme, Covenant, Doctrine, Genre, Method, Practice, Pitfall, Misconception, LifeSituation, Tradition, Manuscript, Translation, Artifact, …) and typed relations (`partOf`, `features`, `teaches`, `quotes`, `fulfills`, `prefigures`, `parallels`, `parentOf`, `occurredAt`, `precedes`, `heldBy`, `addresses`, `speaksTo`, `corroboratedBy`, …) with inverses, symmetry, transitivity, domains, ranges and disjointness; aligned with SKOS, PROV-O and schema.org | `ontology/ontology.ttl` |
| Shapes | SHACL: every node defined, sourced, levelled and given a basis; content articles anchored in Scripture references; practices and methods carry ≥ 3 steps and a before/after example; pitfalls and misconceptions carry a correction; books, passages, people, events, themes, doctrines and practices carry study questions | `ontology/shapes.ttl` |
| Nodes | One Markdown article per entity: id, class, hierarchy, prerequisites, evidenced typed edges, Scripture references, steps, before/after example, study questions, basis, entity links and sources | `articles/<domain>/` |
| Scripture index | Every key reference in canonical order with the articles that discuss it | `graph/scripture-index.md` |
| Study guide | All study questions, procedures and before/after readings in one place | `graph/study-guide.md` |
| Linked data | N-Triples (asserted and OWL-RL inferred), TriG with per-article named graphs and provenance, Turtle-star edge evidence (RDF 1.2), JSON-LD, JSON index | `graph/triples.nt`, `graph/inferred.nt`, `graph/graph.trig`, `graph/edge-evidence.ttls`, `graph/graph.jsonld`, `graph/index.json` |
| Analytics | PageRank, betweenness, Louvain communities, k-core, coverage by type/domain/level/basis | `graph/stats.md` |
| Frontier | Unwritten nodes ranked by referrers weighted by their centrality, with the **type the reasoner expects** | `graph/frontier.md` |
| Link prediction | Adamic-Adar scores for written nodes that should probably be connected | `graph/suggested-links.md` |
| Competency questions | SPARQL over asserted + inferred triples: themes traced across Scripture, who appears where, promise and fulfilment, family trees, views by tradition, misconceptions; *gap* queries (pitfalls with no remedy, books with no key passage, life situations with no Scripture, people and events not tied to a text, events with no place in the timeline, orphans) drive gap-filling runs | `queries/*.rq` → `graph/competency.md` |
| Learning path | Topological layers of the `requires` prerequisite DAG | `graph/learning-path.md` |

## What makes it more than a link list

- **Anchored in the text.** Every article about the Bible's content lists the passages it rests on, checked for a real book and chapter, cites the passage itself, and links to it on the site — so readers go back to Scripture, not just to a summary.
- **Study-ready.** Study questions mix comprehension and reflection for personal or small-group use; practices have ordered steps (published as schema.org `HowTo`); pitfalls and misconceptions show a careless reading next to a careful one.
- **Fair to every tradition, honest about scholarship.** Every node has a `basis` (scriptural, ecumenical, varies-by-tradition, consensus, debated, misconception, historical, devotional), so what the text says, what Christians share, where traditions differ and what scholars debate are never confused.
- **Every typed edge is evidenced.** Each relation cites the source that supports it and carries a confidence, published as RDF-star annotations on the edge.
- **Reasoning, not just storage.** Writers state one direction (`Abraham parentOf Isaac`, `Parable of the Sower partOf Gospel of Mark`); the OWL-RL reasoner materialises `childOf`, `hasPart`, symmetric relations like `spouseOf` and `parallels`, and types unwritten nodes from property ranges. Contradictory typing and timeline loops fail the build.
- **Self-directing growth.** Runs rotate between depth (frontier), breadth (least-covered domain) and gap (SPARQL competency gaps).
- **Reproducible.** Outputs are byte-for-byte deterministic; CI re-runs tests and the build and fails if `graph/` is stale.

## Usage

```bash
pip install -r requirements.txt
python3 scripts/kg.py check                          # validate + reason + SHACL
python3 scripts/kg.py build                          # ...and regenerate graph/
python3 scripts/kg.py similar "Abram"                # duplicate check for a candidate topic
python3 scripts/kg.py new key-passages psalm-23 Passage   # scaffold
python3 scripts/kg.py query queries/04-themes-across-scripture.rq   # or an inline SPARQL string
python3 -m pytest -q tests                           # end-to-end tests on fixture articles
```

Steer what gets written by editing `topics/seeds.yaml`. The run playbook is `CLAUDE.md`; the article format is `SCHEMA.md`. Change which translation the site links to in `site/site.yaml` (`bible_version`). The `.nt`, `.trig` and `.jsonld` exports load into Apache Jena/Fuseki, GraphDB, Oxigraph, rdflib, or Neo4j via n10s; `.ttls` needs an RDF 1.2 / RDF-star aware store.
