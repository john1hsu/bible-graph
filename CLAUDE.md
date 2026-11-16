# Bible Graph — run playbook

This repo is a citation-backed, reasoner-checked knowledge graph that helps **Christians know the Bible better**: how the Bible is put together, every book of the Old and New Testaments, key passages and parables, the people, places, events and periods of the biblical story, the life and teachings of Jesus, the great themes, covenants and doctrines, how to read and interpret Scripture well (and the common mistakes and misconceptions), practices for studying it, its historical and cultural background, how the text was preserved and translated, and what Scripture says to everyday life. A scheduled run adds **exactly one new, unique article** per run. Every article must send the reader back to the text itself and leave them understanding it a little better. Follow these steps in order. Read `SCHEMA.md` before writing.

## Audience and voice
- Write for a Christian reader who takes the Bible as Scripture and wants to understand it: clear, warm, reverent and accurate. Explain; don't preach, and don't adopt a sceptical or dismissive posture either.
- **Ecumenical and fair.** Readers may be Catholic, Orthodox or Protestant (of many kinds). Where traditions agree, say so plainly (`basis: ecumenical`). Where they differ — canon, baptism, the Lord's Supper, church authority, the end times, Mary — describe each view in its own terms with its own sources (ideally the tradition's confessional documents), use `basis: varies-by-tradition` with a `## Views across traditions` section, and never declare a winner.
- **Honest about scholarship.** For authorship, dating and historical questions, give the traditional view and the main scholarly views fairly, with sources (`basis: debated` + `## Scholarly views`), without either mocking tradition or ignoring scholarship.
- **Respectful of Judaism.** The Hebrew Bible is also Jewish Scripture: describe Jewish readings respectfully, and avoid stereotypes (e.g. Pharisees as stock villains) — say what historians actually know.
- Name deuterocanonical books as such and note which traditions include them.

## 1. Sync and orient
```bash
pip install -r requirements.txt --break-system-packages -q
git pull --rebase origin main
python3 scripts/kg.py build      # must print OK; fix the repo first if it doesn't
```
Read `graph/stats.md`, `graph/frontier.md`, `graph/competency.md` and `topics/seeds.yaml`. `graph/index.json` lists every node (ids, titles, aliases, edges, references, steps, examples, source URLs); `graph/scripture-index.md` lists every passage already covered.

## 2. Pick the topic (graph-driven)
Use the current UTC hour modulo 3:
- **0 → depth.** Take the top node in `graph/frontier.md` that fits a domain, **skipping any node that would belong to the domain with the most articles** ("Domain coverage" in `graph/stats.md`; on a tie for most, skip all tied domains), so one domain's dense cross-links can't snowball into a lopsided graph. Use its *Expected type* (inferred by the reasoner) as the article's `type` unless it is clearly wrong.
- **1 → breadth.** Take the domain at the top of "Domain coverage" in `graph/stats.md` (fewest articles; skip the domain of the most recent commit on ties) and pick an unwritten seed or another important topic in it. Prefer foundational topics (major books, central figures, core passages) before obscure ones.
- **2 → gap.** Take the first row of the first non-empty *(gap)* section in `graph/competency.md` and write the article that closes it (a method that guards against an unaddressed pitfall, a key passage for a book that has none, Scripture for a life situation, the book or event a person or place appears in, the period an event belongs to).
- If the chosen mode yields nothing (as on the first runs, when the frontier is empty), fall back to breadth.

Then prove it is unique:
```bash
python3 scripts/kg.py similar "<candidate title>"
```
If any score ≥ 0.5, or an existing title/alias names the same thing, pick a different topic. Never write a second article on an existing subject — not a rename, a sub-angle that restates it, a different name for the same person (Abram/Abraham, Saul/Paul, Simon/Peter/Cephas), a variant book title (Song of Songs/Song of Solomon, Qoheleth/Ecclesiastes) or a translation of a term (Torah/Law, agape/love). Record alternate names and Hebrew/Greek terms as `aliases`. A book and a key passage inside it are different subjects; so are a person and an event they take part in.

Sibling graphs cover neighbouring ground: the psychology and philosophy of wisdom and the world's wisdom traditions belong to `john1hsu/wisdom-graph`, fallacies and argument evaluation to `john1hsu/critical-thinking-graph`, and listening and conversation skills to `john1hsu/communication-graph`. Write here when the topic is about the Bible (e.g. the Book of Proverbs, wisdom literature as a genre, how Jesus taught), and link the sibling article with `sameAs` (its `https://github.com/john1hsu/<repo>/id/<slug>` IRI) when it is the same concept.

## 3. Research
- Run several web searches and read the actual pages (WebFetch). Don't rely on snippets or memory.
- **Open the passages themselves.** Read every passage in `references` in at least one translation (Bible Gateway, USCCB, ESV.org, NET Bible, STEP Bible, Blue Letter Bible; Sefaria for the Hebrew Bible) and cite at least one as a `scripture` source. Check every chapter-and-verse reference in the article against the opened text — never cite a verse from memory. If a reference can't be confirmed, drop it.
- Collect 3–6 credible sources: ≥ 1 `scripture`, ≥ 1 scholarly and ≥ 2 strong (see `SCHEMA.md`). Prefer Bible dictionaries and encyclopedias (Anchor Yale, Eerdmans, Lexham, ISBE, Oxford Bibliographies), academic introductions and commentaries from university and seminary presses, peer-reviewed journals (*JBL*, *NTS*, *Vetus Testamentum*, *Tyndale Bulletin*, *CBQ*), university and seminary pages (Yale Open Courses, Tyndale House), museums and antiquities authorities for artifacts, and primary ancient sources (Josephus, the church fathers on CCEL or New Advent, the Dead Sea Scrolls digital library). For what a church teaches, cite its own official documents (`confessional`). **Never cite Wikipedia, Wikiquote, wikiHow or quotation and "verse of the day" aggregators** (BrainyQuote, Goodreads quotes, AZ Quotes…) or the other banned sources. Sermons, blogs and Q&A sites are `community` (weak) and never the sole support for a claim.
- Every URL you cite must be one you opened this run. Never invent a URL, DOI or Wikidata id. Only add `sameAs: [wd:Q…]` if you opened that Wikidata page and it is the same concept.
- **Quoting Scripture.** Quote from public-domain translations (World English Bible, KJV, ASV) and name the translation; keep quotations from copyrighted translations (NIV, ESV, NRSV, NABRE…) to a short phrase. Prefer giving the reference and paraphrasing.
- **Misquotes and misconceptions.** Many sayings attributed to the Bible are not in it ("God helps those who help themselves", "God won't give you more than you can handle", "cleanliness is next to godliness"), and many popular details are not in the text (three wise men, an apple in Eden, Mary Magdalene as a prostitute). Check the text before repeating a popular claim; these make good `Misconception` articles, corrected with a `challengedBy` edge to the passage or source.
- Set `basis` honestly (see `SCHEMA.md`): what the text says (`scriptural`), what Christians broadly hold (`ecumenical`), where traditions differ (`varies-by-tradition`), what scholars agree on (`consensus`) or dispute (`debated`).
- Paraphrase sources. No quotation from a source longer than 15 words; at most one quote per source.

## 4. Write the node
```bash
python3 scripts/kg.py new <domain> <slug> <Type>   # scaffold with the fields and sections the class requires
```
- 400–1,000 words, for a thoughtful lay reader in a church small group: what it is, where it is in the Bible, its background, what it means, why it matters for Christian faith and life, common misreadings, and **Connections**. Where relevant, show how the topic runs from the Old Testament into the New.
- `references` list the key passages (book, chapter, verse, e.g. `Romans 8:28-39`); quote any reference containing a comma. `studyQuestions` mix comprehension ("What does God promise Abram in Genesis 12:1-3?") with reflection a reader or small group could discuss. `steps` are concrete and imperative. `example` shows a careless reading or habit (or the popular claim) and a careful one (or what the text says), with a short "why".
- Every substantive paragraph carries footnote citations `[^sN]`; list every source in `## Sources`.
- Edges: 1–3 `broader`, `related` as needed, `requires` for genuine prerequisites, and ≥ 1 (ideally 2–5) typed `relations`, **each citing the source that supports it** and a confidence. Tie passages to their book (`partOf`), people and events to where they appear (`features` from the text or event) and when (`occurredDuring`, `precedes`), texts to the themes they teach (`teaches`), family ties (`parentOf`, `spouseOf`), New Testament use of the Old (`quotes`, `fulfills`, `prefigures`), and views to the traditions that hold them (`heldBy`). Link to existing ids wherever they fit (`graph/index.json`); new target ids are fine and join the frontier. Match each predicate's domain and range (`SCHEMA.md`). Never write inverses — the reasoner adds them.
- If a needed class or predicate is missing, add it to `ontology/ontology.ttl` (label, domain/range, inverse/characteristics) in the same commit. Keep the ontology small; reuse first.
- Back-links: if `graph/suggested-links.md` or the new node shows an existing article should point to it, you may add the id to that article's `related` (or a sourced typed relation). Don't otherwise rewrite existing articles.

## 5. Validate, build, commit, push
```bash
python3 scripts/kg.py build    # fix every problem (structure, citations, references, reasoning contradictions, SHACL) and re-run until OK
git add -A
git commit -m "Add <Title> (<domain>, <mode> run)"
git pull --rebase origin main && python3 scripts/kg.py build && git push origin main
```
If the push is rejected, pull --rebase, rebuild, and push again (once). Commit regenerated `graph/` files with the article; CI fails if they are stale.

## Don'ts
- Don't add more than one article per run, delete articles, or rewrite history.
- Don't commit if validation fails; leave the repo clean.
- Don't cite a source or a verse you didn't open, attach a source to an edge it doesn't support, or repeat a "Bible quote" you couldn't find in the text.
- Don't hand-edit anything in `graph/`.
- Don't take sides between Christian traditions, disparage any tradition or other religion, or present one denomination's reading as the only Christian one.
- Don't give medical, psychiatric, legal or crisis advice, or stand in for a pastor. Articles on suffering, grief, anxiety, abuse or doubt stay general and pastoral in tone, and say plainly that persistent distress is a reason to talk with a pastor, a counsellor or a doctor, or to contact crisis support.
- Don't connect Scripture to current partisan politics or name current political figures; use neutral everyday or church-life scenarios in examples.
