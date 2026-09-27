# Is there a paper in Zeeguu's MWE detection?

**Status**: assessment, not a plan
**Date**: 2026-09-27
**Author**: Claude, for Mircea
**Subject**: `zeeguu/core/mwe/`, ADR [0004](../adr/0004-multi-word-expression-detection.md) (lands with PR [#764](https://github.com/zeeguu/api/pull/764))

A research-novelty assessment of the multi-word expression subsystem. The
question asked was whether there is a publishable contribution in it. The
short answer is at the bottom of this section; the rest of the document is the
evidence.

**Verdict in one paragraph.** The *architecture* is good engineering and not a
paper — layered rule/lexicon/LLM MWE pipelines are a described genre, and
Zeeguu's is a competent instance of it, not a novel one. What is publishable is
something nobody went looking for. Across ~102,000 multi-word translation events
in 11 languages, **61.7% of multi-word units were fused by the learner's own
hand** rather than proposed by the detector — and most of those spans are **not
multi-word expressions under any definition in the literature**. `som folk`
("as people"), `forskere siger` ("researchers say"), `dårlige oplevelser` ("bad
experiences") are plainly compositional. Learners are chunking for comprehension,
and idiomaticity is only one of the things that makes a span worth asking about.
That is a finding about the *task definition* rather than about a system's score:
**the unit a reader needs is not the unit the field has spent nine years
annotating for** — and it supplies a mechanism for the one user-study result in
the competing literature, which found learners shrugging at annotation errors.
The data is already on disk, so this costs months rather than years (§6.2). A
second, safer paper also exists: **Danish has no MWE identification corpus at
all**, in PARSEME or anywhere else (§6.1) — a resource contribution with a known
venue, a known format, and near-zero novelty risk, because it claims a gap rather
than an idea.

**Three things to be sceptical about before believing any of it.** The number
61.7% is real but "hand-fused" does **not** mean "missed MWE", and framing it as a
recall failure would be wrong and easily demolished (§7.4). The claim rests on a
labelled sample of those spans that **does not exist yet** and could refute it in
a week (§7.1). And the *idea* that the relevant unit is user-relative is probably
not new — Wray said something close to it in 2002 — even if the measurement is;
that check was still running when this was written (§2.7).

---

## 1. What is definitively already done

### 1.1 MWE identification as a task, and PARSEME

MWE identification is a canonical, well-served NLP task with a dedicated
multilingual shared-task series and a dedicated annual workshop. Nothing about
"detect which tokens form one unit" is open.

- **PARSEME corpus 2.0** (LREC 2026) — Savary et al.
  <https://lrec.elra.info/lrec2026-main-378>, preprint
  <https://gitlab.com/parseme/corpora/-/blob/master/pre-prints/PARSEME_corpus_2.0_pre-print.pdf>.
  17 languages, ~5M tokens, >250k sentences, ~140k MWE annotations. First
  edition to cover **all** syntactic categories (verbal, nominal, adjectival,
  adverbial, functional) under a typology of 18 categories, driven by decision
  diagrams over linguistic tests. Release: <http://hdl.handle.net/11372/LRT-6123>.
- **PARSEME corpus 1.3** (MWE 2023) — <https://aclanthology.org/2023.mwe-1.6/>,
  26 languages, verbal MWEs only. Release
  <http://hdl.handle.net/11372/LRT-5124>. Still the widest language coverage.
- Earlier editions 1.2 (2020) <https://aclanthology.org/2020.mwe-1.14/>,
  1.1 (2018) <https://aclanthology.org/W18-4925/>, 1.0 (2017)
  <http://langsci-press.org/catalog/view/204/1344/1319-1>.
- **PARSEME 2.0 shared task** overview — <https://aclanthology.org/2026.mwe-1.33/>.
  10 systems in the identification subtask, 5 in a new paraphrasing subtask.
- Community hub: <https://gitlab.com/parseme/corpora/-/wikis/home>. The
  per-language repositories were **made private in August–September 2025** to
  avoid LLM contamination ahead of the 2.0 shared task; only the LINDAT
  releases are public.

The ADR's decision to label lexicon sections with PARSEME's verbal categories
is correct and cheap, and the caution about not labelling the non-verbal
sections is also correct: the 2.0 guidelines
(<https://parsemefr.lis-lab.fr/parseme-st-guidelines/2.0/>) do define nominal,
adjectival, adverbial and functional categories, so those labels now exist,
but they are defined by decision diagrams rather than by name, and guessing
them would be worse than leaving the sections descriptive.

### 1.2 Verified: the PARSEME 2.0 language list, and where Danish stands

The task brief asked whether Danish is in PARSEME 2.0. **It is not**, and the
answer is stronger than that: Danish is not in *any* PARSEME edition and has
no language repository in the PARSEME GitLab group at all.

Exact 2.0 list, quoted from the preprint (§1):

> This edition covers 17 languages, including 10 (out of 26) covered
> previously (called veteran languages) – French (fr), Modern Greek (el),
> Hebrew (he), Persian (fa), Polish (pl), Portuguese (pt), Romanian (ro),
> Slovene (sl), Swedish (sv), Serbian (sr) – and 7 new ones – Dutch (nl),
> Egyptian (egy), Georgian (ka), Ancient Greek (grc), Japanese (ja), Latvian
> (lv) and Ukrainian (uk). One language, Marathi (mr), in still in the release
> pipeline and should be published soon.

So the 7 new ones are **nl, egy, ka, grc, ja, lv, uk** — no Nordic language
among them, and Swedish is the only Nordic language in PARSEME at all. The
full PARSEME wiki table lists 33 language repositories (ar, eu, bg, zh, hr,
cs, nl, egy, en, fa, fr, ka, de, el, grc, he, hi, hu, ga, it, ja, lv, lt, mt,
pl, pt, ro, sr, sl, es, sv, tr, uk). Danish, Norwegian, Icelandic, Finnish and
Estonian are all absent.

Cross-tabulating against the 16 languages Zeeguu lets a learner study
(`Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED`: de, es, fr, nl, en, it,
da, pl, sv, ru, no, hu, pt, ro, el, bg):

| Zeeguu language | PARSEME 1.3 (verbal) | PARSEME 2.0 (all types) |
|---|---|---|
| bg, de, en, es, hu, it | yes | no |
| el, fr, pl, pt, ro | yes | yes |
| sv | no (1.2 only) | yes |
| nl | no | yes |
| **da** | **no** | **no** |
| **no** | **no** | **no** |
| **ru** | **no** | **no** |

**Thirteen of Zeeguu's sixteen learnable languages have PARSEME gold data
today. Danish, Norwegian and Russian have none.** Danish is the language the
subsystem was built around: it is the language of the bug in ADR-0004, it has
the only verb lexicon (`DANISH_VERB_MWES`), and its lexicon is roughly twice
the size of any other (~104 entries against 38–51 for de/en/nl/no/sv). The
language Zeeguu has invested most in is the one language for which no
evaluation resource exists anywhere. That asymmetry is the cleanest paper-shaped
fact in this whole assessment.

Two consequences, both actionable:

1. A Danish PARSEME-scheme corpus is a concrete, citable, unclaimed output.
   §6.1 costs it.
2. For the other 13 languages an intrinsic evaluation of Zeeguu's detector can
   be run **today, with no annotation at all**, against the public LINDAT
   releases. Zeeguu currently has no such numbers (§5.6). Somebody should do
   this regardless of whether any paper happens, because right now nobody can
   say whether `GermanicStrategy` is any good.

### 1.3 Verified: Danish MWE resources that *do* exist

Danish is not a blank slate at the *type* level, and this matters because it
removes one candidate contribution.

- **The Danish Idiom Dataset: A collection of 1000 Danish idioms and fixed
  expressions** — Sørensen, Nimb, Mikkelsen & Jensen, NB-REAL 2025 (Tallinn).
  <https://aclanthology.org/2025.nbreal-1.5/>. 1000 idiomatic expressions
  drawn from the multiword units of *Den Danske Ordbog* (DDO), each with a
  correct dictionary definition plus three distractors (a literal
  misinterpretation, a figurative misinterpretation, and a random definition
  from another expression). Published by Det Danske Sprog- og
  Litteraturselskab, funded through sprogteknologi.dk, and publicly available
  there.

  This is a **type-level lexicon built for interpretation benchmarking** — can
  an LLM pick the right meaning of a given idiom — **not a token-level
  identification corpus**. It contains no running text and no annotated
  occurrences, so it cannot be used to measure whether a detector finds
  expressions in context. Two implications:

  - It does **not** preempt a Danish PARSEME-scheme identification corpus.
  - It **does** preempt any claim that curating a Danish MWE lexicon is a
    contribution. It also means Zeeguu should just *use* it: 1000 DDO-sourced
    expressions is a far better seed for `lexicons/da.py` than the current
    hand-picked ~104, and it comes with dictionary definitions. This is a free
    engineering win independent of any paper, and DSL is in Copenhagen.

- **ID10M: Idiom Identification in 10 Languages** — Tedeschi et al.,
  Findings of NAACL 2022. <https://aclanthology.org/2022.findings-naacl.208/>,
  data <https://github.com/Babelscape/ID10M>. Wiktionary-derived idiom
  annotations, occurrences matched from Wikipedia, automatic for 10 languages
  (zh, nl, en, fr, de, it, ja, pl, pt, es), manually curated for 4 (en, de, it,
  es). **No Danish.** The PARSEME 2.0 preprint explicitly criticises it:
  Wiktionary has no shared MWE definition across contributors, it carries no
  MWE type information, and it excludes MWEs with gaps — which is precisely
  the class Zeeguu's `mwe_is_separated` / `mwe_partner_token_i` machinery
  exists to handle.
- **CoAM: Corpus of All-Type Multiword Expressions** — Ide et al., ACL 2025.
  <https://aclanthology.org/2025.acl-long.1311/>. 1.3K sentences, English
  only, MWEs tagged with type to enable fine-grained error analysis; reports a
  fine-tuned LLM beating the previous SOTA on DiMSUM.
- **MultiCoPIE** (MWE 2025) <https://aclanthology.org/2025.mwe-1.8/> and
  **PIE** (MWE 2021) <https://aclanthology.org/2021.mwe-1.5/> — potentially-
  idiomatic-expression corpora; neither covers Danish.

### 1.4 Verified: LLMs do not solve this, which retrospectively vindicates Layer 3 being off

*(The numbers are here; §1.10 covers why LLM-for-MWE is closed as a novelty
claim.)*

The ADR turns the LLM layer off for cost (5–15s/article) and records how to
turn it back on. The PARSEME 2.0 authors ran the experiment Zeeguu did not,
and the result is a reason to leave it off on *quality* grounds too, not just
cost.

Their abstract: *"Results show that generic large language models do not
encode sufficient knowledge to solve the MWE identification task."* Their
baseline used API-based prompting with succinct MWE and task definitions;
best model was **gpt-5-mini**. MWE-based (exact-match) F-scores, Table 6 of
the preprint:

| lang | egy | fa | fr | grc | he | ja | ka | lv | nl | pl | pt | ro | sl | sr | sv | uk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **F (MWE-based)** | 0 | 46.8 | 36.5 | 24.9 | 30.1 | 19.3 | 10.0 | 26.3 | **61.5** | 24.5 | 16.3 | 33.2 | 32.6 | 31.3 | **33.3** | 34.6 |

Token-based F is higher throughout (partial credit), e.g. nl 64.2, fa 62.2,
fr 53.6, sv 45.2. LLaMA3.3 and Qwen3 were "considerably lower". Egyptian
scored zero exact matches.

The two numbers that bear on Zeeguu are **Dutch 61.5** and **Swedish 33.3** —
the two Germanic languages in 2.0, both handled by `GermanicStrategy`. A
zero-shot LLM on the Swedish gold set gets an exact-match F of 33. Note the
precision/recall split the paper flags: precision exceeded recall for fa, fr,
ja, nl, and recall exceeded precision for grc, he, ka, lv, pt, sl, sv, uk.
Zeeguu's design constraint is precision, and a zero-shot LLM is
*recall*-leaning in Swedish, which is the wrong direction for this
application.

Caveat, stated plainly: this is not an apples-to-apples comparison with
Zeeguu. PARSEME asks for all MWEs of all categories in running text; Zeeguu
asks for a much narrower thing (which tokens should fuse under a tap) and is
allowed to return nothing. A low PARSEME F-score does not mean the LLM would
be bad at Zeeguu's job. But it does mean the LLM layer was never going to be
an oracle, and the ADR's framing of it as a quality upgrade deferred for cost
is too generous to it. CoAM's result (fine-tuned LLM beats SOTA) suggests the
gap is closable by fine-tuning, not by prompting — which is a different and
much larger project than flipping `HYBRID_LANGUAGES` back on.

### 1.5 How MWE identification is evaluated — and the one thing nobody has tried

This is the section that decides whether there is a real paper here, so it is
worth being precise about what the field has and has not done.

**The two authoritative evaluation surveys both enumerate the extrinsic options,
and end-user behaviour is not among them.**

- **Multiword Expression Processing: A Survey** — Constant et al., CL 43(4),
  2017. <https://aclanthology.org/J17-4005/>. Extrinsic evaluation of MWE
  *identification* is enumerated as: information retrieval (Doucet &
  Ahonen-Myka 2004), WSD (Finlayson & Kulkarni 2011), parsing, and machine
  translation. For *discovery*: identification, parsing, MT. Clicks, lookups and
  deployed-application telemetry appear nowhere. Two quotable gap statements:

  > "In the case of discovery, evaluation is usually done intrinsically by means
  > of expert judgments, gold standards, and dedicated test sets, but these lack
  > the scale, naturalness, and coverage of possible extrinsic evaluation in
  > downstream applications."

  > "We believe that future research should focus on developing extrinsic
  > evaluation measures, test sets, and guidelines for MWE discovery."

  It also notes, discouragingly for the existing extrinsic tradition, that *"it
  is rare to observe convincing performance gains in downstream tasks."*

- **A Survey of MWE Identification Experiments: The Devil is in the Details** —
  Ramisch, Walsh, Blanchard & Taslimipoor, MWE 2023.
  <https://aclanthology.org/2023.mwe-1.15/>. Surveys 40 identification papers
  built on DiMSUM and PARSEME. This is the single most useful sentence in the
  literature for Zeeguu's purposes:

  > "Currently, most evaluation techniques are automatic. One open issue is
  > whether there is a place in which manual evaluation of detected MWEs should
  > be performed, (e.g. in the context of downstream tasks). New evaluation
  > protocols can be considered in the future."

  The community's own dedicated methodology survey confirms evaluation is
  near-universally automatic F1, and frames new protocols as future work — and
  even then imagines only *manual* evaluation, not behavioural.

**All five PARSEME editions, through 2.0 in 2026, report intrinsic P/R/F1 only**
(1.0 <https://aclanthology.org/W17-1704/>; 2.0 corpus and shared task as cited
in §1.1). There is no drift toward application-grounded metrics.

**Genuine extrinsic MWE evaluations exist, and all of them are machine-internal
proxies with no humans in the loop:**

- **Task-based Evaluation of Multiword Expressions: a Pilot Study in Statistical
  Machine Translation** — Carpuat & Diab, NAACL-HLT 2010.
  <https://aclanthology.org/N10-1029/>. The earliest explicit "task-based
  evaluation of MWEs"; the task is SMT BLEU.
- **Evaluating the Impact of Verbal Multiword Expressions on Machine
  Translation** — Liu, Ghosh & Jiang, ACL 2026.
  <https://aclanthology.org/2026.acl-long.698/>, <https://arxiv.org/abs/2508.17458>.
  The state of the art in extrinsic MWE evaluation as of now: reference-free MT
  metrics. Still no users.

**The MWE workshop's own call for papers asks for exactly the missing thing.**
The MWE 2026 CFP (<https://multiword.org/mwe2026/>) solicits work on *"extending
these attempts to integrate and evaluate MWE technology in end-user
applications."* The resulting 33–34 paper volume contains no answer. The closest
is Alves, Bagdasarov & Teich, *Cognitive Signatures of Multi-Word Expressions:
Reading-Time and Surprisal* — eye-tracking as a **psycholinguistic probe of
human MWE processing**, not as an evaluation signal for an identifier.

**And the one deployed formulaic-language tool with a real user base published no
evaluation of its identifier at all.** Lin, P. (2022), *Developing an
intelligent tool for computer-assisted formulaic language learning from YouTube
videos*, **ReCALL** 34(2), 185–200,
<https://www.cambridge.org/core/product/identifier/S0958344021000252/type/journal_article>.
IdiomsTube auto-identifies English formulaic expressions in YouTube captions
from 53,635 templates and had **8,000+ registered users**; the paper reports
feature description and adoption counts, deferring effectiveness to an
unpublished manuscript. A formulaic-language identifier in front of thousands of
users whose identification quality was never measured from their behaviour.

### 1.6 What *is* partly done — and should be imported rather than reinvented

Framing the following as imported method makes the contribution stronger, not
weaker, and pre-empts the obvious reviewer objections.

- **Behaviour-based evaluation of a token-grouping task already exists — in
  information retrieval.** **An IR-based Evaluation Framework for Web Search
  Query Segmentation** — Saha Roy, Ganguly, Choudhury & Laxman, SIGIR 2012.
  <https://arxiv.org/abs/1111.1497>. Query segmentation is structurally the same
  problem as MWE grouping: decide which adjacent tokens form one unit. Their
  thesis is Zeeguu's thesis, fourteen years early: *"the goodness of a
  segmentation algorithm as judged through evaluation against a handful of human
  annotated segmentations hardly reflects its effectiveness in an IR-based
  setup."* They replace the gold standard with downstream retrieval performance
  and find that **automatic segmenters sometimes beat human segmentations** once
  you measure what matters. This both legitimises the move and shows nobody has
  made it for MWEs. **Cite it as the method being transplanted.**
- **Click data as *supervision* for segmentation** — Li, Hsu, Zhai & Wang,
  *Unsupervised Query Segmentation Using Clickthrough for Information
  Retrieval*, SIGIR 2011.
  <https://dl.acm.org/doi/10.1145/2009916.2009957>. Also Hagen et al. 2011,
  *Query Segmentation Revisited*,
  <https://downloads.webis.de/publications/papers/hagen_2011a.pdf>.
- **The bias correction the reviewers will demand.** *Unbiased Learning-to-Rank
  with Biased Feedback* — Joachims, Swaminathan & Schnabel, WSDM 2017.
  <https://www.cs.cornell.edu/people/tj/publications/joachims_etal_17a.pdf>.
  Somebody will ask "isn't a tap on a highlighted group *caused* by the
  highlight?" — and they will be right. This is the literature on presentation
  and position bias and propensity correction that answers it. Importing it
  properly is itself part of the contribution.
- **Large-scale lookup-log analysis is an established scientific instrument in
  lexicography** — though never used to evaluate an NLP component.
  Müller-Spitzer, Wolfer & Koplenig, *Observing Online Dictionary Users: Studies
  Using Wiktionary Log Files*, *International Journal of Lexicography* 28(1),
  2015, <https://academic.oup.com/ijl/article/28/1/1/1816539>; de Schryver et
  al., a decade of Swahili–English lookups,
  <https://ejournal.ukm.my/gema/article/view/34284>, and EURALEX 2014
  <https://www.euralex.org/elx_proceedings/Euralex2014/euralex_2014_019_p_281.pdf>.
  This is the methodological ancestor for "lookup logs are legitimate evidence."
  ⚠️ **Unverified**: a frequently-repeated statistic that ~80% of the most
  looked-up entries in an online dictionary are multiword expressions could not
  be traced to a source. **Do not cite it until located** — it would be ideal
  motivation and that is exactly why it needs checking.
- **Learner behaviour as a label source for lexical annotation** exists, but for
  single words only: Ehara et al., *Personalized reading support for
  second-language web documents by collective intelligence*, IUI 2010,
  <https://dl.acm.org/doi/10.1145/1719970.1719978>; Gooding et al., *One Size
  Does Not Fit All: The Case for Personalised Word Complexity Models*, 2022,
  <https://arxiv.org/abs/2205.02564>; gaze-based variants EyeLingo (CHI 2025)
  <https://arxiv.org/abs/2502.10378> and GazeReader (CHI EA 2023)
  <https://dl.acm.org/doi/10.1145/3544549.3585790>. All single tokens, all
  lab-scale or test-derived labels. **The grouping decision is what makes MWE
  identification hard, and nobody has a behavioural signal for it.**

### 1.7 Zeeguu's own prior art, which matters two ways

There is **no Zeeguu paper in the ACL Anthology**. The record (verified via
OpenAlex and by reading the CHI paper):

| Work | Venue |
|---|---|
| Lungu, Sethi, Marti & Schwab, *The Zeeguu API – Modeling Learner Progress to Accelerate Vocabulary Acquisition*, 2016 | Zenodo |
| Lungu, *Bootstrapping an Ubiquitous Monitoring Ecosystem for Accelerating Vocabulary Acquisition*, 2016 | ECSAW 2016, <https://dl.acm.org/doi/abs/10.1145/2993412.3003389> |
| Oosterhof, Digkas & Lungu, *Making reading in a second language more enjoyable*, 2016 | Zenodo |
| Lungu, van der Brand, Chirtoaca & Avagyan, *As We May Study: Towards the Web as a Personalized Language Textbook*, 2018 | CHI 2018, <https://mircealungu.com/docs/assets/papers/18-AsWeMayStudy.pdf> |
| Hollenstein & Lungu, *Analyzing user interactions to estimate reading time in web-based L2 reader applications*, 2022 | EUROCALL 2022, doi:10.14705/rpnet.2022.61.1453 |
| Vlachos, Lungu, Shrestha & David, *LLMs for Difficulty Estimation of Foreign Language Content*, 2023 | <https://arxiv.org/abs/2309.05142> |

Three things follow.

1. **Zeeguu's own flagship evaluation is questionnaire-based**, not
   behaviour-based: CHI 2018 used 60 Dutch high-schoolers over one month with a
   pre-survey, a post-usage questionnaire, a teacher interview and descriptive
   statistics, and the paper itself flags that *"the number of students who
   answered our survey was limited."* So a behavioural-evaluation paper does not
   compete with Zeeguu's own record — it extends it.
2. **CHI 2018 already documents that Zeeguu handles multiword translations and
   then discards them.** From the Vocabulary Recommender section: not fit for
   study are *"expressions which are longer than three words"*, and a footnote
   records that the translation providers *"provide context-aware translations
   and multiword translations."* Multiword lookup events have therefore been
   accumulating since 2018 and have never been used to evaluate anything. That
   is a documented "we have data nobody else has" claim, in Zeeguu's own
   published record.
3. **Hollenstein & Lungu 2022 is the methodological stepping stone** — it uses
   tab-switching and word-translation clicks to derive reading-time metrics.
   Interaction data as a *measurement instrument*. The target of measurement is
   different (reading time, not annotation quality), and saying so explicitly is
   the honest framing.

### 1.8 Layered rule + lexicon + statistical pipelines: every layer is taken

This is the finding that kills the architecture-as-contribution idea, and it
should be read before anyone writes an introduction claiming a novel design.
Each of Zeeguu's three layers has a named, cited precedent, and so does the
application setting.

- **Multiword Expression Processing: A Survey** — Constant, Eryiğit, Monti, van
  der Plas, Ramisch, Rosner & Todirascu, *Computational Linguistics* 43(4),
  2017. <https://aclanthology.org/J17-4005/>. §4 ("On the Use of Lexicons")
  treats lexicon + parser + statistical-layer composition as **established
  engineering**, not as an open problem: *"The MWE identification section has
  shown that the use of lexicons increases MWE identification performances.
  Joint rule-based grammar-based MWE-aware parsing generally embodies
  mechanisms to link the grammar to a lexicon."* It also documents, in 2017,
  the exact failure mode that produced the `ud af` bug: naive lemma-based
  forward-maximum-matching *"tends to overgenerate… due to strong
  morphological constraints on some elements or agreement."* And it traces
  rule-constraints-projected-onto-dependency-parses back to Hashimoto, Sato &
  Utsuro (2006). Hybridity is not claimable.
- **Without lexicons, multiword expression identification will never fly: a
  position statement** — Savary, Cordeiro & Ramisch, MWE-WN 2019.
  <https://aclanthology.org/W19-5110/>. The canonical citation for "the
  lexicon layer is not a legacy hack." Cite it; do not re-derive it.
- **Verbal Multiword Expression Identification: Do We Need a Sledgehammer to
  Crack a Nut?** — Pasquer, Savary, Ramisch & Antoine, COLING 2020.
  <https://aclanthology.org/2020.coling-main.296/>. *"A simple
  language-independent system based on a combination of filters competes with
  the best systems from a recent shared task: it obtains the best averaged
  F-score over 11 languages (0.6653)."* The canonical "you do not need neural
  for this" result.
- **MWE as WSD: Solving Multiword Expression Identification with Word Sense
  Disambiguation** — Tanner & Hoffman, Findings of EMNLP 2023.
  <https://aclanthology.org/2023.findings-emnlp.14/>. WordNet-as-lexicon plus
  rule-based candidate extraction, then a learned bi-encoder **filters** the
  candidates, reported to "substantially improve precision". This is Zeeguu's
  architecture with a trained filter where the LLM would go — the strongest
  structural precedent for *generate with rules and lexicon, filter with a
  learned layer, precision improves*.
- **PARSEME shared task 1.2** — Savary, Ramisch et al., MWE-LEX 2020.
  <https://aclanthology.org/2020.mwe-1.14/>. Rule/lexicon hybrids were
  competitive as recently as 2020: **Seen2Seen** (rule-based extraction +
  filtering, closed track, no external resources) placed **second of seven**
  on global MWE-based F1 (≈63.0), beaten only by mBERT-based MTLB-STRUCT.
  FipsCo was rule-based joint parsing plus a VMWE lexicon; HMSid combined
  syntactic patterns with association measures; Seen2Unseen added Wiktionary
  and translation.
- **MorphoFiltered-Gemini at MWE 2026** — Moise & Nisioi.
  <https://aclanthology.org/2026.mwe-1.26/>. Published roughly six months ago:
  an LLM plus a **lightweight UPOS/morphological post-filter to strip false
  positives**, with an explicitly stated precision-over-peak-F1 design —
  *"Rather than optimizing peak performance on individual languages, our
  approach prioritizes cross-lingual stability and precision."* It also reports
  that the filter **hurt** Japanese and Slovene. If Zeeguu ever turns the LLM
  layer on and gates it with POS rules, this paper is the prior art.
- **PMI MWE Scorer at PARSEME 2.0** — Bogdanova & Bucur, MWE 2026 — pointwise
  mutual information over UD trees: Zeeguu's third layer, statistical rather
  than LLM.

### 1.9 The closest prior art is stronger than expected: Linguse is peer-reviewed, and it is Savary's own group

The task brief identified Linguse from a Zenodo record. There is an earlier,
peer-reviewed version, and it matters:

- **Sailing through multiword expression identification with Wiktionary and
  Linguse: A case study of language learning** — Agnieszka Dryjańska, Till
  Überrück-Fries & **Agata Savary**, NLP4CALL 2024 (13th Workshop on NLP for
  Computer-Assisted Language Learning, Rennes).
  <https://aclanthology.org/2024.nlp4call-1.19/>
- **Identification and annotation of multiword expressions in an end-user
  application: The case of teaching/learning French as a foreign language** —
  same authors, 2026, in *Multiword expressions in Natural Language
  Processing: Current trends and challenges*, Language Science Press (PMWE
  vol. 8), pp. 225–254. <https://zenodo.org/records/21277679>,
  doi:10.5281/zenodo.21277679

Their system, **WiktSeen**, deployed in beta with real learners, is layered in
almost exactly Zeeguu's shape: (1) a spaCy pipeline doing tokenization,
POS-tagging, lemmatisation and dependency parsing; (2) lexicon lookup over a
Wiktionary-derived MWE corpus (French Wiktionary via Wiktextract); (3) **seven
trainable rule filters**, including **F6 "components should be syntactically
connected"** — a dependency-subgraph connectedness test — plus a max-gap filter
and a seen-inflection filter, with filter activation tuned as a 7-bit mask on a
Deep-Sequoia dev split.

And they make Zeeguu's precision argument, verbatim: *"Low precision risks
injecting noise and confusion into the learning environment."* They also
decline the neural layer on purpose, and say so: *"While it is tempting to
explore advanced machine-learning algorithms such as transformers for MWE
identification, we consider a gradual approach. Preliminary results and user
feedback indicate that significant real-world benefits can still be obtained
using the existing rule-based system, thus questioning the immediate need for
adding complexity."*

**So: "rule + lexicon MWE identifier deployed in a reading app for language
learners, argued on precision grounds" is taken, twice, by the leader of
PARSEME.** Any paper Zeeguu writes must cite both and differentiate on
something other than the architecture or the motivation. §2 says what is
left.

### 1.10 LLMs on MWE identification: closed as a novelty claim

Do not propose to evaluate LLMs on MWE identification. In the last eighteen
months this became a crowded space with a settled negative answer.

- **Easy as PIE? Identifying Multi-Word Expressions with LLMs** — Hashiloni,
  Hefetz & Bar, **EMNLP 2025 main**.
  <https://aclanthology.org/2025.emnlp-main.1213/>. Zero-shot / few-shot / CoT
  / self-consistency across GPT-4o, GPT-4o-mini, LLaMA-4-Scout, Qwen2.5-72B,
  o3-mini, DeepSeek-R1, on ID10M, MAGPIE and CoAM. Total experiment cost ≈
  **$130**. Collapses on lower-resource languages (best-prompt F1 ≈ 34
  Japanese, ≈ 59 Turkish).
- **Cheese it up: CamemBERT Outperforms Large Language Models for
  Identification of French Multi-word Expressions** — Bagdasarov, Alves &
  Teich, MWE 2026. <https://aclanthology.org/2026.mwe-1.6/>. Fine-tuned
  CamemBERT (F1 = 0.74) beats gpt-oss-20b and Qwen3-32B-AWQ "by large margins
  in precision, recall, and F1", and includes a useful false-positive taxonomy
  (see §1.11).
- **PARSEME 2.0 shared task** — Scholivet, Savary, Ramisch et al., MWE 2026.
  <https://aclanthology.org/2026.mwe-1.33/>. Ten systems: five fine-tuned
  encoders with BIO tagging, one syntax-aware PMI-over-UD, two generative-LLM
  systems, one LLM baseline — and **zero lexicon-based or classic rule+lexicon
  systems**. The organisers' own verdict: *"We emphasize that the best system
  from edition 1.2, MTLB-STRUCT, still gains the upper hand, suggesting that
  little progress is achieved in modern LLMs concerning MWE identification,
  despite their progress in other tasks."* And *"pre-trained encoder models and
  BIO encoding are still competitive."* Note also that MTLB-STRUCT "favours
  precision" while the systems ranked 2–3 favour recall.
- Also: **Prompting Large Language Models for Multiword Expression
  recognition** — Păiș & Mitrofan, 2026, PMWE vol. 8 ch. 7
  <https://zenodo.org/records/21277681>; **Supervision versus
  Demonstration-Based In-Context Learning for MWE Classification** — Karakaş &
  Şimşek, ACL SRW 2026 <https://arxiv.org/abs/2606.07479>; **Semantics of
  Multiword Expressions in Transformer-Based Models: A Survey** — Miletić &
  Schulte im Walde, TACL 12, 2024
  <https://aclanthology.org/2024.tacl-1.33/>; **Rolling the DICE on
  Idiomaticity: How LLMs Fail to Grasp Context** — Mi et al., ACL 2025
  <https://arxiv.org/abs/2410.16069>; **SemEval-2025 Task 1 AdMIRe**
  <https://aclanthology.org/2025.semeval-1.330/>, which ran again as AdMIRe 2
  at MWE 2026.

One thing in this area *is* unoccupied, and it is small: **nobody has published
a serious cost-and-latency treatment of an LLM layer inside an MWE pipeline.**
Easy-as-PIE reports a total dollar figure; PARSEME 2.0 mentions LLM cost only in
a Limitations footnote (*"very large processing costs in subtask 1, especially
in Georgian"*). No per-request latency budget, no caching strategy, no
escalation policy between a cheap deterministic layer and an expensive LLM
layer. Zeeguu has the measurement (5–15s/article) and the decision (turn it
off). That is one paragraph of a paper, not a paper.

### 1.11 Error taxonomies exist — but from corpora, not from deployments

- **Cheese it up** (above) categorises false positives across gpt-oss, Qwen3
  and CamemBERT: partial/boundary matches dominate (70 of 143 shared FPs), with
  LLMs over-extending (*faire confiance à* for *faire confiance*) and
  CamemBERT under-extending (*sur la table* for *être sur la table*); then
  single-token predictions, token-plus-punctuation, noun phrases (terminology,
  institutional names, proper nouns), verb and prepositional phrases,
  adverbial/discourse phrases, and tokenization/metadata artefacts. Their
  conclusion — *"one of the main challenges lies in correctly defining MWE
  boundaries"* — is precisely the `fandt ud af` / `ud af` problem, independently
  arrived at. **This is a corpus finding, not a production finding.**
- **CoAM** makes MWE-typed error analysis a design goal, again on a corpus.
- **MorphoFiltered-Gemini** reports FP classes arising from an LLM layer *and*
  the architectural response *and* where the response backfires. Closest
  published instance of "failure class → architectural response" in MWE, but
  in a shared task, and it is a paragraph rather than a contribution.

**What does not exist**, after seven distinct search phrasings: a published
paper that categorises the failure modes of a *deployed* linguistic-annotation
system observed in production, where the taxonomy plus the architectural
response is the contribution. The adjacent literatures are (a) corpus/benchmark
FP taxonomies as above, and (b) a booming 2025–2026 LLM-ops failure-mode genre
that shares the *form* but none of the *subject*. The nearest deployed-precision
precedent is Grammarly's GECToR line — a positive confidence bias on the KEEP
tag and a sentence-level minimum error-probability threshold, both trading
recall for precision in a user-facing product
(<https://github.com/grammarly/gector>); GECToR itself is Omelianchuk et al.,
BEA 2020, though the specific production-mechanism claims are **unverified**.

### 1.12 Venues, verified

- **Workshop on Multiword Expressions** — 22nd edition, MWE 2026, half-day,
  co-located with **EACL 2026 in Rabat, 28 March 2026**, run by SIGLEX-MWE and
  the UniDive COST Action. <https://multiword.org/mwe2026/>, proceedings
  <https://aclanthology.org/volumes/2026.mwe-1/>. Archival long (8pp) and short
  (4pp), plus non-archival abstracts; ARR submissions accepted. **It has already
  happened** — the next edition is MWE 2027, at whichever *ACL it attaches to.
  Note that UniDive's COST Action funding runs to 2026, so the community's
  organisational momentum after 2026 is an unknown.
- **What MWE 2026 actually accepted** (34 papers): heavily
  **new-language corpora in the PARSEME scheme** (Swedish, Ukrainian, Romanian,
  Marathi, a Turkish idiom benchmark, Sinhala figures of speech), ~15 shared-task
  system papers, domain applications, psycholinguistic/probing work, and
  methodology. **No position papers and no deployed-system experience reports in
  the volume.** The single-language PARSEME corpus paper is unambiguously a
  supported genre; a deployment paper would be an outlier there.
- **The template for a Danish corpus paper already exists**: **Swedish Multiword
  Expression Corpora in PARSEME** — Sara Stymne, Astrid Berntsson Ingelstam &
  Eva Pettersson, MWE 2026. <https://aclanthology.org/2026.mwe-1.3/>. A new
  release plus a historical overview, IAA analysis, Swedish-specific rules for
  **particle verbs** and multiword tokens, and a **comparison with other
  Germanic languages identifying needed revisions to the PARSEME guidelines**.
  A Danish paper would slot directly into that Germanic comparison.
- **EMNLP Industry Track** — <https://2026.emnlp.org/calls/industry_track/> —
  the CFP could have been written for a Zeeguu deployment paper, verbatim:
  *"Submissions are not restricted to industry authors or to proprietary data —
  academic work on genuinely deployed systems is equally welcome, as are
  negative results, lessons learned, and vision papers grounded in deployment
  experience."* Welcomed topics include "Best practices and lessons learned",
  "Case studies, from design to deployment", "Negative results related to
  real-world applications". NAACL/EACL/ACL run parallel industry tracks.
- **Workshop on Insights from Negative Results in NLP** —
  <https://insights-workshop.github.io/> — 6th edition at NAACL 2025
  (<https://aclanthology.org/volumes/2025.insights-1/>), 2026 edition with
  EMNLP. Wants broadly applicable recommendations and "demonstrations that X
  didn't work accompanied by explanation".
- **NoDaLiDa 2027** — 26th Nordic Conference on Computational Linguistics,
  **Copenhagen, 25–28 May 2027**
  (<https://www.aclweb.org/portal/content/workshop-proposals-26th-nordic-conference-computational-linguistics>).
  Mircea's own city. The obvious home for a Danish resource paper, and the
  deadline is plausibly January–February 2027 — **exact date unverified**.
- **LREC** is biennial; LREC 2026 was May 2026 in Palma, so the next is 2028.
  Too far away to plan around. LREC's appetite for a new-language corpus in an
  existing scheme is high but I could not open a current CFP to quote policy;
  treat as **inferred**, though the MWE 2026 volume corroborates it strongly.
- **NLP4CALL** — where the Linguse paper landed; the natural venue for a
  learner-facing evaluation paper, and a friendlier reviewer pool than the MWE
  workshop for anything pedagogical.

## 2. What is genuinely open or unclaimed

Ranked by confidence, and separated from what merely *looks* open. §2.1 changed
substantially once production numbers arrived (§5.10) — read that first if you
read nothing else.

### 2.1 Strongest — the unit a reader needs is not the unit the literature defines

This is the claim the production data actually supports, and it is a different
and better claim than the one I started with.

Across ~102,000 multi-word translation events, **61.7% of multi-word units were
fused by the learner's own hand** rather than proposed by the detector — and
inspection of the most-fused Danish spans shows most are **not MWEs by any
linguistic definition** (`som folk`, `forskere siger`, `dårlige oplevelser`,
`skal være`). Learners are chunking for comprehension, and MWE-hood is only one
contributor to what they chunk (§5.10).

Three things make this a stronger contribution than a straightforward recall
audit:

1. It is a **finding about the task definition**, not about a system's score.
   Nobody has to accept that Zeeguu's detector is good or bad for the result to
   mean something.
2. It supplies a **mechanism** for the one empirical claim in the competing
   literature — Linguse's report that learners tolerate annotation errors (§3).
   If the linguist's unit was never the unit the learner wanted, tolerance is
   explained rather than merely observed.
3. It comes with a **dataset of a kind that does not exist**: ~13,700 positively
   labelled learner-chosen multi-word spans in context since January 2026, ~102k
   since 2017, across 11 languages, where nobody was ever asked to annotate
   anything.

Novelty status: **provisionally open, pending one literature check.** The
adjacent claim — that formulaicity is speaker-relative, so "formulaic for whom?"
is the right question — is Wray's, from 2002, and the phraseology field has a
long-standing split between semantic/idiomaticity-based and frequency-based
definitions of the unit. What I have not yet confirmed is whether anyone has
**measured** the divergence between learner-selected and linguistically-defined
units, at scale, from behaviour. See §2.7 for the honest status of that check.

### 2.2 Strong — Danish as a PARSEME-scheme language

§1.2 and §1.3. No PARSEME repository, no release in five editions, not among the
7 new in 2.0, absent from ID10M and DaNLP. The only Danish resource is a
type-level idiom list built for interpretation benchmarking. Norwegian and
Russian are in the same position; Danish is the one Zeeguu has a reason to care
about.

Open in the weakest sense — because nobody has done the work, not because the
work is hard to conceive. That is exactly what makes it low-risk.

### 2.3 Strong — extrinsic evaluation of MWE identification from real behaviour

§1.5–§1.6. Both evaluation surveys enumerate the extrinsic options and behaviour
is not among them; the MWE 2023 methodology survey calls new evaluation
protocols an open issue and imagines only *manual* evaluation; all five PARSEME
editions are intrinsic F1; the MWE 2026 CFP explicitly asks for
end-user-application evaluation and its own 33-paper volume contains no answer;
the closest competitor evaluated with 12 students and named scaling up as future
work; and a deployed formulaic-language tool with 8,000+ users published no
identifier evaluation at all.

The structural method exists in IR and should be imported rather than reinvented
(Saha Roy et al. 2012 for behaviour-as-evaluation, Li et al. 2011 for
behaviour-as-supervision, Joachims et al. 2017 for the bias correction).
**Novelty is the transfer plus the scale**, not the idea that behaviour can stand
in for a gold standard.

One important downgrade from my first pass: the **rejection** half of this signal
is not viable. `user_mwe_override` holds **130 rows from 46 users** in nine
months (§5.3, §5.10). Explicit negatives are too scarce to carry statistical
weight, exactly as the endpoint's design predicted. The positive half — hand-fused
spans — is three orders of magnitude larger. Build on the positives.

### 2.4 Moderate — whether better detection measurably reduces learner effort

A causal claim, and a rare chance to make one: does improving the detector reduce
the hand-work learners do? A lexicon fix shipped for Danish on 2026-09-27 and
nothing else changed, which makes the Danish hand-fusing rate before and after a
natural experiment, with the other ten languages as concurrent controls (§6.2,
§5.11). I have not found prior work making this specific claim for an NLP
component from product telemetry, though the design itself is standard elsewhere
and would need no methodological defence.

The honest constraint is arithmetic, not novelty: Danish accrues roughly 11
multi-word bookmarks a day, so the post-period needed to detect a modest shift
runs to months, not weeks (§5.11). This is a capstone for a 2027 paper, not a
result available this autumn.

### 2.5 Moderate — a failure taxonomy from a deployed linguistic-annotation system

§1.11. Corpus-based false-positive taxonomies exist and are good — Cheese it up's
boundary-error analysis independently rediscovers the `ud af` problem. A
deployment-based one, organised by *which architectural layer failed* and paired
with the response, I could not find for linguistic annotation. The venue exists
and asks for it. The risk is reviewer fit, not crowding.

### 2.6 Weak — two things that are paragraphs, not papers

- **The "degrade to no-group, never wrong-group" contract.** ADR-0004's core
  constraint is, as far as I found, not stated as a named design rule anywhere in
  the MWE literature, even though the precision preference is widespread
  (WiktSeen's *"low precision risks injecting noise and confusion"*; MTLB-STRUCT
  "favours precision"; MorphoFiltered-Gemini prioritising precision; GECToR's
  KEEP-tag bias). A genuinely useful articulation — and one paragraph. The MWE
  2026 volume contained no position papers and the CFP does not name them as a
  category.
- **Cost and latency of an LLM layer in an MWE pipeline.** §1.10. No published
  per-request latency budget, caching strategy, or escalation policy between a
  cheap deterministic layer and an expensive LLM layer. Zeeguu has the
  measurement (5–15s per article) and the decision (off). A section of a paper.

### 2.7 What I could not settle

- **Whether the learner-chunking divergence in §2.1 is already claimed.** The
  check was still running when this document was finalised; §6.2 states what
  would falsify the novelty claim and §8 Q11 asks for the follow-up. Treat §2.1
  as the most promising item here and the least confirmed. **Do not write an
  abstract around it before the check lands.** The most likely prior-art
  direction is Wray's speaker-relative formulaicity and the phraseology field's
  frequency-vs-idiomaticity split — which would not preempt a measurement, but
  would mean the *idea* is not new and only the evidence is.

### 2.8 Closed — do not pursue

- **Hybrid/layered MWE architecture as a contribution.** §1.8. Every layer has a
  named precedent; the 2017 survey treats the composition as settled engineering.
  A paper led by the three-layer design would be desk-rejected.
- **Rule+lexicon MWE identification in a learner reading app.** §1.9. Taken
  twice by Savary's group, including the precision argument and the
  tap-to-expand interaction.
- **LLMs for MWE identification.** §1.10. EMNLP 2025 main, ACL 2025 main, ACL
  SRW 2026, an MWE 2026 head-to-head, a book chapter, and a whole PARSEME edition
  with an LLM baseline. The organisers' verdict: *"little progress is achieved in
  modern LLMs concerning MWE identification."*
- **Curating a Danish MWE lexicon.** §1.3. DSL published 1000 DDO-sourced
  expressions in 2025. Use theirs.

## 3. Does the Linguse finding threaten Zeeguu's design premise?

The brief flagged this as a contradiction worth taking seriously: Linguse reports
learners "did not perceive [errors] as problematic", which would undercut
ADR-0004's constraint that a wrong grouping is worse than a missing one.

**It does not — and it was never a finding.** Three separate reasons, and the
third one turns the whole thing into an opportunity.

### 3.1 The claim rests on two quotes, and neither is about a wrong grouping

The study (Dryjańska, Überrück-Fries & Savary 2026,
<https://zenodo.org/records/21277679>) recruited **one class of 12** B1 French
learners at the University of Warsaw over four weeks in 2023. **7 of 12**
attended the group feedback session. **4** did the one-on-one interviews and the
pre/postquiz — so the quantitative arm is **two cohorts of two**. The
quantitative instrument was a Vocabulary Knowledge Scale over 10 MWEs. The
authors' own verdict: *"the results are only indicative due to the low number of
participants."* The NLP4CALL version labels the tolerance claim explicitly as a
**hypothesis**: *"We hypothesize that human language learners… can tolerate some
noise in MWE identification without compromising its usefulness."*

The entire "Annotation Quality" category of the qualitative analysis is **two
quotes**:

> "Sometimes the POS tags for words and MWEs were misleading. **That didn't
> hinder my comprehension but is bad for improving my grammar.**"

> "When reading it was most important to understand the bigger picture, small
> annotation errors didn't matter."

The first is itself half-negative and is still counted as tolerance. More
importantly, the five concrete error types the paper analyses are: adverbial-
locution vs adverb POS confusion; MWEs identified but with no definition or
synonym; *ad hoc* unrecognised while *ad* is mis-tagged; *oh* tagged as a verb;
and Wiktionary examples that fail to illustrate the idiosyncrasy. **Not one is a
false-positive grouping** — a fluent, confident translation of something that is
not an expression. The construct ADR-0004 is about was never measured.

Two further caveats weaken the transfer to Zeeguu:

- **WiktSeen ran at P = 0.484 on the class of MWEs that only appear in
  Wiktionary** (R = 0.598, F = 0.535), against P = 0.939 for MWEs attested in
  both Wiktionary and the Sequoia gold standard; overall F = 0.776. So roughly
  **half** the annotations in that class were wrong, learners saw them, and the
  study had no instrument that would have detected it.
- **MWEs were not highlighted by default.** Learners had to hover or click to
  discover them, and several asked for default highlighting (*"I wished all MWEs
  were highlighted by default, instead of me having to hover over all the
  words"*). A learner-initiated click on a word they already suspect they do not
  understand is a different exposure regime from a pre-marked span, which is what
  Zeeguu does.

### 3.2 The broader literature predicts exactly this non-perception — and calls it the harm

This is the reframe that matters, and it is well supported.

- **Fluency Over Adequacy: A Pilot Study in Measuring User Trust in Imperfect
  MT** — Martindale & Carpuat, AMTA 2018.
  <https://aclanthology.org/W18-1803/>. N = 89 across disfluent, control, and
  "misleading" (high fluency, low adequacy) conditions: *"Users responded
  strongly to disfluent translations, but were, surprisingly, much less concerned
  with adequacy."* In the misleading condition every annotator agreed the output
  led readers to a different meaning than the reference — **and trust did not
  drop.**

  A false-positive MWE grouping produces a *fluent* translation. So "learners did
  not perceive errors as problematic" is precisely what this literature predicts,
  and it is **evidence of the danger, not evidence of safety.** Non-detection is
  the harm. This is also exactly ADR-0004's stated reasoning — *"confidently
  wrong in a way the learner cannot detect, because checking it is precisely the
  skill they do not yet have"* — which turns out to have a citable basis.
- **Toward Machine Translation Literacy: How Lay Users Perceive and Rely on
  Imperfect Translations** — Xiao et al., **EMNLP 2025**.
  <https://aclanthology.org/2025.emnlp-main.1725.pdf>,
  <https://arxiv.org/abs/2510.09994>. **N = 452** museum study. High-proficiency
  users detected errors regardless of type; lower-proficiency users failed
  specifically on **adequacy** errors, and *"often relied on it because they
  lacked the skills or strategies to assess its quality."* Proficiency is the
  moderator, which is the boundary condition to state before a reviewer finds it.
- **Misplaced highlighting specifically harms comprehension *and* metacognitive
  accuracy** — the closest analogue to marking a wrong span in a reader:
  - Silvers Gier, Kreiner & Natz-Gonzalez, *Journal of General Psychology*
    136(3), 2009, <https://doi.org/10.3200/genp.136.3.287-302>. **N = 180**,
    three conditions (no / appropriate / inappropriate highlighting).
    Inappropriate highlighting impaired **both comprehension and metacognitive
    accuracy** — readers did not know they had been misled. **Wrong marking was
    worse than no marking.** This is the single strongest analogue for
    ADR-0004's asymmetry claim.
  - Silvers & Kreiner, *Reading Research and Instruction* 36(3), 1997,
    <https://eric.ed.gov/?id=EJ547175>: pre-existing inappropriate highlighting
    impaired comprehension, and **warning readers in advance did not eliminate
    the effect.**
  - **And the mitigation is something Zeeguu already ships.** Gier, Kreiner,
    Hudnell, Montoya & Herring, *Journal of College Reading and Learning* 41(2),
    2011, <https://files.eric.ed.gov/fulltext/EJ926361.pdf>: having readers
    **actively re-highlight** eliminated the negative effect. Letting the learner
    adjust the grouping may neutralise a wrong one — which is what
    `disable_mwe_grouping` does. That is an unexpectedly good argument for the
    ungroup feature, and it is testable from the override data.
- **Learners accept wrong automated feedback, and proficiency predicts how
  much:**
  - Lavolette, Polio & Kahng, *Language Learning & Technology* 19(2), 2015,
    <https://www.lltjournal.org/item/847/>. N = 32, 1,058 coded feedback points
    from Criterion on authentic learner text: 75% correct, 14% miscoded, **11%
    flagged already-correct structures**. Response rates: 73% on correct codes,
    **72% on wrong codes, 56% on false positives** — learners edited correct text
    more than half the time it was falsely flagged, because *"the students were
    not always sure if what they had initially written was correct."*
  - Koltovskaia, *Assessing Writing* 44, 2020,
    <https://doi.org/10.1016/j.asw.2020.100450>. N = 2, but rich process data:
    the low-intermediate writer accepted **100% of Grammarly's suggestions,
    including the 27% that were inaccurate**; the advanced writer over-rejected.
- **The HCI over-reliance literature transfers cleanly and is the strongest part
  of the case**, because it explains *why* a learner cannot protect themselves:
  - Vasconcelos et al., *PACM HCI* 7(CSCW1), 2023,
    <https://doi.org/10.1145/3579605>. N = 731. Over-reliance is rational when
    **verification cost** exceeds benefit. For a learner who lacks the
    target-language knowledge, verification cost is effectively unbounded — the
    framework *predicts* maximal over-reliance and predicts explanations will not
    fix it.
  - Bansal et al., CHI 2021, <https://doi.org/10.1145/3411764.3445717>. >1,500
    participants: *"explanations increased the chance that humans will accept the
    AI's recommendation, regardless of its correctness."* Attaching a gloss or an
    Explain button to a wrong grouping makes it **more** likely to be swallowed —
    directly relevant to Zeeguu's `explain_selection` endpoint.
  - Gaube et al., *npj Digital Medicine* 4:31, 2021,
    <https://doi.org/10.1038/s41746-021-00385-9>. N = 265 physicians: inaccurate
    advice degraded accuracy ~38–40%, and the **lower-expertise** group failed to
    discount it while radiologists did. Same proficiency moderation.
  - Foundations: Parasuraman & Riley, *Human Factors* 39(2), 1997,
    <https://doi.org/10.1518/001872097778543886> (defines both **misuse** and
    **disuse** — false alarms cause abandonment, which is the other half of
    Zeeguu's cost argument); Skitka, Mosier & Burdick, 1999,
    <https://doi.org/10.1006/ijhc.1999.0252> (an imperfect aid made monitoring
    *worse* than no aid); Zhang, Liao & Bellamy, FAT\* 2020,
    <https://doi.org/10.1145/3351095.3372852>; Lai & Tan, FAT\* 2019,
    <https://doi.org/10.1145/3287560.3287590>; Buçinca, Malaya & Gajos, *PACM
    HCI* 5(CSCW1):188, 2021, <https://doi.org/10.1145/3449287>.

**Counterweights to handle honestly**, because they are real and a reviewer will
raise them. Competent learners often *do* filter wrong suggestions: Chodorow,
Gamon & Tetreault, *Language Testing* 27(3), 2010,
<https://doi.org/10.1177/0265532210364391>; Bai & Hu, *Educational Psychology*
37(1), 2017, <https://doi.org/10.1080/01443410.2016.1223275>; Hoang, *JALT CALL
Journal* 18(3), 2022, <https://doi.org/10.29140/jaltcall.v18n3.775> (N = 38, and
the FP rate correlated ρ = .83 with retention of the *correct* form); and John &
Woll, *CALICO Journal* 37(2), 2020, <https://doi.org/10.1558/cj.36523>, who find
grammar checkers fail mostly by **silence** — *"only rarely is the feedback
actively misleading."* The reconciliation is proficiency-dependence, and it
should be stated as a boundary condition rather than discovered in review.

### 3.3 The convention Zeeguu inherited has almost no empirical basis — and that is the opportunity

This is the genuinely surprising result of the search. "Precision matters more
than recall for learner-facing NLP" is a ~23-year-old convention resting on
assertion.

- **The canonical statement is uncited.** *The CoNLL-2014 Shared Task on
  Grammatical Error Correction* — Ng et al., 2014,
  <https://aclanthology.org/W14-1701/>: *"F0.5 emphasizes precision twice as much
  as recall… When a grammar checker is put into actual use, it is important that
  its proposed corrections are highly accurate in order to gain user acceptance.
  **Neglecting to propose a correction is not as bad as proposing an erroneous
  correction.**"* No citation, no data, no learner study.
- **The 90%-precision threshold is a commercial product judgment.** Burstein,
  Chodorow & Leacock, *Criterion™ Online Essay Evaluation*, IAAI 2003,
  <https://cdn.aaai.org/IAAI/2003/IAAI03-001.pdf>: *"we would rather miss an
  error than tell the student that a well-formed construction is ill-formed. A
  minimum threshold of 90% precision was set…"* — accepting recall as low as 40%.
- Escalated to a norm, still uncited: Chodorow, Tetreault & Han, 2007,
  <https://aclanthology.org/W07-1604/> — *"the feedback that students receive…
  should, above all, avoid false positives."* And described as mere convention by
  the authoritative survey: Bryant et al., *Computational Linguistics* 49(3),
  2023, <https://doi.org/10.1162/coli_a_00478> — β = 0.5 is used "because it is
  **generally considered** more important for a GEC system to be precise."
- **Two corrections worth recording**, since both are commonly misattributed:
  the M²/MaxMatch scorer paper (Dahlmeier & Ng, 2012,
  <https://aclanthology.org/N12-1067/>) uses **F1**, not a precision weighting —
  the 2:1 weight was added independently in 2014. And Chodorow, Dickinson,
  Israel & Tetreault, COLING 2012, <https://aclanthology.org/C12-1038/>, argues
  **against** a fixed metric: report raw TP/FP/FN/TN so readers apply their own
  cost weights, since *"no single metric is best for all purposes."*

**And there is exactly one experiment that actually tested it.** *Evaluating
performance of grammatical error detection to maximize learning effect* — Nagata
& Nakatani, COLING 2010 Posters, <https://aclanthology.org/C10-2103/>. Nagata
named the gap in 2010: *"Chodorow and Leacock (2000) and Chodorow et al. (2007)
argue that precision-oriented is better, but **they do not give any concrete
reason.** This means that the recall-precision problem has not yet been solved."*
Then he ran it — four conditions, 22 analysable participants, article and number
errors, sessions needed to halve the error rate:

| Condition | Sessions to halve error rate |
|---|---|
| Human tutor | 16 |
| Precision-oriented (P = .72, R = .25) | 18 |
| **No feedback** | **29** |
| **Recall-oriented** (F-optimal) | **47** |

**Low-precision feedback was worse than no feedback at all**, and the standard
F-measure ranked the recall-oriented system *above* the precision-oriented one —
inverting the actual learning outcome. Caveats are severe and the authors state
them: ~7 per cell, two error types, one L1, 2010 technology, *"not a general but
a limited conclusion."*

So: **an underpowered 2010 poster is carrying essentially the entire empirical
load for a convention the whole field applies — and CoNLL-2014 adopted F0.5 four
years later without citing it.**

### 3.4 Zeeguu's premise is well supported, from a direction the ADR does not cite

The claim ADR-0004 actually needs is not "learners notice bad groupings" but
"learners cannot find expression boundaries themselves, and do not know they are
failing." That has good support:

- **Effect of Frequency and Idiomaticity on Second Language Reading
  Comprehension** — Martinez & Murphy, *TESOL Quarterly* 45(2), 2011,
  <https://onlinelibrary.wiley.com/doi/abs/10.5054/tq.2011.247708>. N = 101, two
  matched texts built **entirely from top-2,000 words**, one arranging them into
  MWEs. Comprehension dropped; **self-rated comprehension was 87.4% against
  actual 60.3%**, and **69% over-estimated on the idiomatic text, four times the
  rate on the non-idiomatic one** (η² = 0.228). *"Students also tended to
  overestimate how much they understood as a function of expressions that either
  went unnoticed or were misunderstood."* Replicated with 124 Korean
  middle-schoolers by Park & Chon, *RELC Journal* 50(2), 2019,
  <https://journals.sagepub.com/doi/10.1177/0033688217748024>. **This is the
  motivating citation ADR-0004 is missing.**
- **Learners do not look up unknown MWEs the way they look up unknown words** —
  and this is the finding Zeeguu can replicate at scale. Bishop, *Noticing
  Formulaic Sequences*, 2004,
  <https://langsci.wisc.edu/wp-content/uploads/sites/1012/2019/01/LSOWP4.1-04-Bishop.pdf>
  (peer-reviewed version as ch. 12 in Schmitt (ed.), *Formulaic Sequences*,
  <https://benjamins.com/catalog/lllt.9.12bis>). N = 44 in a click-for-gloss
  reading interface: unknown single words were clicked **2.22** times against
  **1.43** for unknown formulaic sequences (p = .01), and **colour + underline
  raised formulaic-sequence lookups to 5.00** (p = .0005). *"Learners don't
  notice unknown formulaic sequences as readily as unknown words."* It also
  states Zeeguu's boundary problem: *"A priori, there is no clear way of
  distinguishing between the two types of unknown word string."* Caveat: a
  5-page workshop paper, N = 44, from 2004, whose comprehension gain failed to
  replicate a semester later. It is carrying a lot of weight because there is
  little else.
- Corroborating: Kim, *Language Awareness* 25(1–2), 2016,
  <https://www.tandfonline.com/doi/abs/10.1080/09658416.2015.1122025> — N = 52,
  learners recognised unfamiliar *idioms* as unfamiliar at a significantly lower
  rate than unfamiliar single words. Siyanova-Chanturia, Conklin & Schmitt,
  *Second Language Research* 27(2), 2011,
  <https://journals.sagepub.com/doi/10.1177/0267658310382068> — eye-tracking:
  natives get a formulaic processing advantage, **non-natives do not**.
- **Boundaries are hard even for trained experts, on Savary's own data.** The
  PARSEME 1.0 corpus paper (Savary et al. 2018,
  <https://langsci-press.org/catalog/view/204/1344/1319-1>) reports
  inter-annotator agreement on **unitising** — deciding the span — across 12
  languages at F1_unit **38.3–89.9** and κ_unit **0.319–0.827**, while
  *categorising* an already-agreed span was easy (κ mostly 0.78–1.0). Spans are
  the hard part, and the Linguse co-author's own corpus says so. At the *learner*
  level the entire literature is one qualitative sentence in Bui, Boers &
  Coxhead, *ITL* 171(2), 2019,
  <https://www.jbe-platform.com/content/journals/10.1075/itl.18033.bui>:
  *"the students found it hard to identify the boundaries of expressions."*
  **Nobody has quantified learner boundary accuracy.**
- **Narrow the claim.** Pellicer-Sánchez, *LTR* 21(3), 2017,
  <https://journals.sagepub.com/doi/10.1177/1362168815618428>, and
  Pellicer-Sánchez, Siyanova-Chanturia & Parente, *Applied Psycholinguistics*
  43(3), 2022,
  <https://www.cambridge.org/core/journals/applied-psycholinguistics/article/E29F0A99BDBF82586E2A30C0C5068344>
  show collocational knowledge *is* picked up from unenhanced reading — but both
  used **pseudowords**, which guarantee a novelty signal and therefore cannot
  test the deceptive-transparency case. The defensible framing is: *MWEs composed
  entirely of already-known high-frequency words generate no unknown-item signal,
  are under-attended and under-looked-up, and produce measurable
  over-estimation of comprehension.* Relatedly, Grant & Nation (2006) found only
  ~103 truly opaque "core idioms" in English
  (<https://www.wgtn.ac.nz/lals/resources/paul-nations-resources/paul-nations-publications/publications/documents/2006-Grant-How-many-idioms.pdf>),
  so frame around the semi-transparent middle — Martinez & Schmitt's 505-item
  PHRASE List, *Applied Linguistics* 33(3),
  <https://academic.oup.com/applij/article-abstract/33/3/299/220807> — not core
  idioms.
- **Highlighting has a measured cost, which Zeeguu should know about.** Choi,
  *LTR* 21(3), 2017,
  <https://journals.sagepub.com/doi/10.1177/1362168816653271> — the enhanced
  group learned the collocations but **recalled less of the unenhanced text**;
  Lee, *Language Learning* 57(1), 2007,
  <https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9922.2007.00400.x> —
  N = 259, enhancement aided form learning but **hurt comprehension**; Boers et
  al., *IJAL* 27(2), 2017,
  <https://onlinelibrary.wiley.com/doi/abs/10.1111/ijal.12141> — helps, with
  **zero spillover**; Peters, *Language Learning Journal* 40(1), 2012,
  <https://www.tandfonline.com/doi/abs/10.1080/09571736.2012.658224> — immediate
  gain, gone at two weeks. So marking MWEs is not free even when the marking is
  *right*, which is an argument the ADR does not make and should.

### 3.5 The honest position — and the rhetorical gift

The precision-over-recall asymmetry for learner-facing MWE grouping is
**empirically open**, and more cleanly so than the brief assumed. Both sides rest
on assertion plus tiny samples: Zeeguu's on a design argument in an ADR;
Linguse's on two interview quotes about POS tags; the field's on a 2003
commercial threshold, two uncited assertions, and one 2010 poster with ~7 per
cell.

**And the competing paper hands the question over explicitly.** From the Linguse
Discussion, verbatim:

> "A new research question that has emerged from this study is: **Do false
> positives have a more detrimental effect than false negatives in the context of
> language teaching applications?**"

> "it is needed to establish an optimal balance between recall and precision in
> the context of Foreign Language Teaching… **To the best of our knowledge, no
> such benchmarks exist currently.**"

> "An optimal F-measure might not be the right quality criterion. Weighing
> precision vs. recall, depending on the learners vs. teachers perspectives,
> might be considered instead."

So the correct rhetorical position is **not** "Linguse is wrong" but *"Linguse
asks precisely this question, says no benchmark exists, and cannot answer it at
n=4."*

**And Zeeguu can offer a mechanism they could not.** §5.10 shows that most
multi-word units learners select are not MWEs at all. If the linguist's unit was
never the unit the learner wanted, then "learners tolerate annotation errors"
stops being a puzzle about tolerance and becomes a statement about **relevance** —
they shrugged because the annotations were answering a question they had not
asked. That is a better explanation than tolerance, it is testable from the
labelled sample in §6.2, and offering it turns a contradiction into a
contribution. That is a much stronger and much more collegial framing, and it makes the
work a continuation rather than a rebuttal — which matters, because Savary is a
co-author on both Linguse papers and a likely reviewer.

**Three genuinely unoccupied gaps fall out**, and they are worth stating
separately because they have different costs:

1. **No evaluated reading interface that automatically groups MWEs with the
   grouping's precision manipulated.** The literature has hand-marked items
   (Bishop 2004, so no false positives by construction), a three-page
   research-in-progress report on gaze-contingent collocation highlighting (Jung
   et al., *Language Teaching* 57(4), 2024,
   <https://www.cambridge.org/core/journals/language-teaching/article/abs/103A72069BE04DADC2F525FBEA7C3AA9>),
   and a *writing* assistant (ColloCaid). Requires randomisation — see §5.7.
2. **No quantified measure of learner MWE-boundary identification.** One
   qualitative sentence is the whole literature. **Zeeguu can measure this from
   data it already holds** (§5.2: learner-drawn multi-token spans against the
   system's or a gold grouping). No randomisation, no new instrumentation.
3. **No demonstration that a learner durably internalises a wrong form from
   automated linguistic output.** Acceptance within an episode is measured;
   delayed-post-test acquisition of a miscorrection is not. Zeeguu's exercise and
   scheduling machinery could in principle test this, though §5.8 notes separated
   MWEs are excluded from exercises.

I have written gap 1 up as Proposal D (§6.4). Gap 2 is the cheapest real result
in this document and belongs inside Proposal B. Gap 3 is a further paper and is
not costed here.

## 4. Where Zeeguu's subsystem actually stands

Compactly, so nobody has to infer it from the sections above.

| | Zeeguu | WiktSeen / Linguse | MWEasWSD | PARSEME 2.0 best systems |
|---|---|---|---|---|
| Parser layer | Stanza, per-family rule strategies | spaCy + 7 tuned rule filters | rule-based candidate extraction | — |
| Lexicon layer | hand-curated, ~320 entries over 6 languages | French Wiktionary via Wiktextract | WordNet | **none of the 10 systems** |
| Third layer | LLM, **disabled** | deliberately none | learned gloss/context bi-encoder | fine-tuned encoders (BIO) |
| Languages | 16 learnable, 7 with parser strategies | French | English | 17 |
| Precision stance | explicit: degrade to no-group | explicit: "low precision risks… noise and confusion" | "substantially improve precision" | MTLB-STRUCT "favours precision" |
| Deployed to real learners | **yes, 9 months** | yes, beta | no | no |
| Intrinsic evaluation | **none** | F1 on Deep-Sequoia | DiMSUM, PARSEME 1.1 EN | MWE- and token-based F1 |
| User evaluation | **none published** | 12-student quiz + questionnaire | none | none |
| Learner-chosen multi-word spans on record | **~102k since 2017; ~13.7k since Jan 2026, 11 languages** | clicks not logged | — | — |

Three things fall out of that table.

1. **The architecture is unremarkable.** It is a competent instance of a genre
   with at least three published members. There is nothing to claim in the
   design itself.
2. **The one column Zeeguu wins is deployment**, and specifically the
   combination of deployment with *stored interaction data*. That is the only
   asset no competitor has, and the last row of the table is the whole argument
   of this document: Linguse implements the same tap-to-expand interaction and
   does not log it, so ~102,000 learner-chosen multi-word spans is a corpus that
   exists nowhere else. §5.10 is what is actually in it, and it is not what
   anyone would guess.
3. **The one column Zeeguu loses badly is evaluation.** No intrinsic numbers for
   any language, and §1.2 shows they are obtainable for 13 of 16 without
   annotation. Every proposal below is blocked on this, and it is the cheapest
   thing on the list. If nothing else in this document is acted on, do this.

## 5. What data Zeeguu actually has

Read-only inspection of the models and the endpoint that writes them. **No
database was connected to and nothing was queried.** Everything below is what
the schema and the code permit; how much of it exists in rows is unknown and is
the first open question in §8.

### 5.1 The production window

MWE detection shipped **2026-01-02** ("Add MWE (Multi-Word Expression)
detection for language learning"), with `bookmark.is_mwe` and
`bookmark.mwe_partner_token_i` added by migrations
`tools/migrations/26-01-01--add_is_mwe_to_bookmark.sql` and
`26-01-01-a--add_mwe_partner_token_i_to_bookmark.sql`. The override system
shipped **2026-01-06** (`26-01-05--add_user_mwe_override.sql`). That is roughly
**nine months in production** as of this writing, across 76 MWE-related commits
on `master`, clustered 2026-01 (47), 02 (2), 05 (16), 07 (3), 08 (8).

### 5.2 `Bookmark` — every translation event, with its exact token span

`zeeguu/core/model/bookmark.py`. One row per translation the learner asked for.
The MWE-relevant columns:

| column | what it gives you |
|---|---|
| `sentence_i`, `token_i`, `total_tokens` | the exact token span the learner got translated |
| `is_mwe` | whether this was a **system-proposed** group |
| `mwe_partner_token_i` | partner index for a **separated** MWE (`rufe … an`) |
| `translation_source` | enum `reading` / `exercise` / `article_preview` |
| `reading_session_id`, `browsing_session_id` | which session it happened in |
| `time` | when |
| `user_word_id` → `UserWord` → `Meaning` → two `Phrase` rows | the source string and the gloss shown |

Two distinct signals live in this one table and they are worth separating:

- **`is_mwe = 1`** — the learner tapped a token, the frontend fused the whole
  group, and the learner accepted the result far enough to create a bookmark.
  A weak positive.
- **`is_mwe = 0` and `total_tokens > 1`** — the learner **drew their own
  multi-token span**. The detector proposed nothing there and the learner
  decided the words belonged together anyway. These are candidate **false
  negatives**, self-reported, in context, at whatever scale Zeeguu has. This is
  the most underrated asset in the schema and nothing in the codebase currently
  looks at it.

  **It turned out to be the whole story — and not in the way this paragraph
  assumed.** There are ~13,700 of these since January 2026 and ~102,000 since
  2017, and they are mostly *not* missed MWEs. §5.10 has the numbers and the
  reframing they force. Read it before treating this row class as a
  false-negative log.

### 5.3 `UserMweOverride` — the explicit rejection, and its four holes

`zeeguu/core/model/user_mwe_override.py`, written by
`disable_mwe_grouping` at `zeeguu/api/endpoints/translation.py:756`. Columns:
`user_id`, `article_id`, `sentence_hash` (SHA-256 of the lowercased, stripped
sentence), `mwe_expression` (the lowercased surface string, e.g. `har lavet`),
`disabled`, `created_at`.

The keying is well chosen and the ADR's reasoning holds: hashing the sentence
and storing the expression *text* rather than `sentence_i`/`mwe_group_id` means
an override survives re-tokenization and article re-ordering, and invalidates
itself if the sentence is edited. As a research signal, though, the flow has
four holes, all of which I found by reading the endpoint rather than the model —
and hole 1 turned out to be fatal in practice. **The table holds 130 rows from 46
users in nine months** (§5.10), against ~13,700 hand-fusings in the same window.
The rejection signal is not thin, it is absent. Everything below explains why,
and the fixes are still worth making, but no study should be planned around this
table.

1. **The rejection is conditioned on acceptance.** "Ungroup words" lives in the
   translation menu and the endpoint *requires* a `bookmark_id`. So an override
   can only be recorded by a learner who already tapped the group and got a
   translation. A learner who looks at a wrong grouping, distrusts it, and taps
   around it leaves **no trace whatever**. Any rate computed from this table is
   a rate among learners who already engaged, not among learners exposed.
2. **The bookmark is deleted.** The endpoint does `db_session.delete(bookmark)`.
   The record of *what gloss the learner was shown before rejecting it* is
   destroyed at exactly the moment it becomes interesting. This is the single
   most valuable piece of evidence for the "confidently wrong translation"
   claim in ADR-0004, and the system throws it away. Fixing this is a one-line
   change (soft-delete, or copy the phrase pair into the override row) and is
   the highest-value instrumentation change available.
3. **No language column.** Language has to be reached through
   `article_id` → `Article` → language, so any per-language aggregate needs a
   join and breaks for overrides on deleted articles.
4. **Rows do not aggregate to "this lexicon entry is wrong".** An override is
   per `(user, article, sentence, expression)`. The same bad entry rejected by
   fifty learners is fifty unrelated rows, and because `mwe_expression` is the
   **surface** form, inflected variants of one bad *verb* entry
   (`fandt ud af` / `finder ud af`) will not group together. Grouping by
   lemmatised head would be needed, which means re-running the lemmatiser over
   the stored strings.

### 5.4 `ArticleTokenizationCache` — the denominator, with a version problem

`tokenized_content` holds the full tokenization of an article *including* MWE
groups. This is what makes a proper denominator possible: you can recover every
grouping the system **proposed** to readers, not only the ones that were
tapped, which is the difference between "N rejections" and "N rejections out of
M proposals" — and only the latter is a number.

The blocker the ADR already names: **there is no version column.** The only
invalidation is a seven-day age sweep
(`tools/cleanup_tokenization_cache.py`). So a cached tokenization does not tell
you which detector version produced it, and across nine months and 76 commits
that matters a great deal. Any longitudinal claim ("precision improved after
PR #610") is currently unsupportable from the cache. Adding a version or
content-hash column is cheap and would have to happen before, not after, data
collection for a longitudinal study.

### 5.5 `Meaning.phrase_type` — an already-populated silver label

This is the find I did not expect. `zeeguu/core/model/meaning.py` carries a
`phrase_type` column over an enum: `SINGLE_WORD`, `COLLOCATION`, `IDIOM`,
`EXPRESSION`, `ARBITRARY_MULTI_WORD`. It is populated asynchronously by an LLM
in `zeeguu/core/model/meaning_frequency_classifier.py`, which tracks
`ARBITRARY_MULTI_WORD` separately in its own stats.

That means: **for every multi-word thing a learner has ever translated, Zeeguu
already holds a judgment of whether it is a genuine expression or an arbitrary
span.** As a labelled evaluation set over real learner selections, already
populated, at no annotation cost, that is unusual. There are also
`phrase_type_manually_validated` and `frequency_manually_validated` boolean
columns, so a human-validated subsample has a home already.

Two honest caveats. It is **silver, not gold**: it is an LLM judgment, and §1.4
just established that LLMs are mediocre at MWE identification — though
classifying a *given* span as expression-or-not is an easier task than finding
spans in running text, so the error rate here is probably much lower than
PARSEME's F-scores suggest. And the enum is Zeeguu's own, not PARSEME's; it
maps loosely (`IDIOM`→VID, `COLLOCATION`→roughly LVC/institutionalised) but
not cleanly, and `EXPRESSION` has no PARSEME counterpart.

### 5.6 What there is *no* evaluation of

There is **no intrinsic evaluation of the MWE detector anywhere in the
repository.** `zeeguu/core/test/test_lexicon_mwe.py` (263 lines) and
`test_article_noun_mwe.py` (115 lines) are unit tests that pin specific
inflections and two named regressions (`i dagene`, `nødt`); they are
regression guards, not measurements. `tools/` contains
`extract_mwes_from_ud.py` (a candidate *miner*, from UD's `fixed` relation) and
no evaluation harness. **No precision or recall number exists for any language.**
Nobody can currently say whether `GermanicStrategy` is good, and §1.2 shows
that for 13 of 16 languages this could be measured this week against public
PARSEME releases. Whatever else happens, this should happen.

### 5.7 The natural-experiment temptation, and why to resist it

`UserPreference.SHOW_MWE_HINTS` is a per-user on/off toggle for MWE hints. It
looks like a free A/B test and it is not one: it is **self-selected**, so
hint-off users differ from hint-on users in unknown ways, plausibly including
proficiency and tolerance for tooling. I also grepped for experiment-group,
feature-flag or variant-assignment infrastructure across `zeeguu/` and found
none. **Zeeguu has no randomisation machinery.** Any causal claim needs it
built first, which is a small but non-zero project and carries the ethics
question in §8.

### 5.8 Other things that exist, briefly

- **`UserActivityData`** — a generic event log (`user_id`, `time`, `event`,
  `value`, `extra_data` (4096 chars), `source_id`, `platform`). Deliberately
  schemaless, so the instrumentation gaps in §5.3 and §5.4 can be filled by
  logging new event types with **no migration**. Cheapest available fix.
- **`fit_for_study`** — `zeeguu/core/bookmark_quality/fit_for_study.py`
  excludes separated MWEs from study, because fill-in-the-blank exercises do
  not work with non-adjacent words. Consequence for research: the
  exercise-outcome signal is systematically **absent for the hardest MWE
  class**, so exercise performance cannot be used as a quality proxy there.
- **`lexicons/_review/da_wiktionary_candidates.txt`** — 783 lines of mined,
  unpromoted Danish candidates, plus a README explaining the promotion rule.
  Combined with the DSL dataset (§1.3) this is most of a Danish MWE lexicon
  already.
- **Evidence of prior production failures**, usable as error-taxonomy raw
  material: `tools/migrations/26-05-12--cleanup_greek_determiner_ghost_bookmarks.sql`
  documents a bug class where a tapped Greek determiner got an Azure
  word-aligner multi-word noun-phrase translation, and records that a companion
  Germanic + Romance cleanup of **440 rows** was executed manually on
  2026-05-12. Named PRs across the window: #605 (Stanza DET+NOUN auto-MWE),
  #610 (lexicon overlay), #618/#620 (separated-MWE gating and audit), #628
  (multi-word translation alternatives), #699/#701 (overrides in preview
  summaries), #764 (lemma-headed verb lexicon).

  **But**: that migration cites `docs/history/26-05-12--translation-disambiguation-and-auto-mwe.md`
  and "ADR-019", and **neither exists in the repository** — `docs/adr/` holds
  only 0001–0004. The documented history is thinner than the code comments
  imply. An error taxonomy would have to be reconstructed from git log, PR
  threads and migrations rather than lifted from existing write-ups. That is
  perfectly respectable provenance, but it is real work, not curation.

### 5.9 What is not recorded at all

This list is what decides whether Proposal 2 (§6.2) is feasible:

- **No log of groupings shown but not tapped.** The tokenization cache gives
  you what was proposed per article and reading sessions give you exposure,
  but there is no attention signal. Exposure ≠ seen.
- **No record of which token the learner tapped.** Fusion happens in the
  frontend; only the resulting group span is stored. So you cannot ask whether
  learners tap the head or the particle, which is a genuinely interesting
  question the data almost answers.
- **No positive confirmation.** Acceptance is only ever inferred from the
  absence of a rejection.
- **No detector version on anything** (§5.4).
- **No consent, terms-of-service, or research-use field** in any model. I
  grepped for `consent`, `gdpr`, `privacy_policy`, `research_use` across
  `zeeguu/` and found nothing. See §8.
- ~~Scale is unknown.~~ **Answered after this section was first drafted — see
  §5.10.** It is the one place where the assessment got materially better on
  contact with the database.

### 5.10 The census: production numbers, and the caveat that reframes everything

These figures were measured read-only on production after the sections above were
drafted. They change the strongest available claim, so they are reported in full
rather than summarised.

**Volume.** `is_mwe` landed 2026-01-01, so the detector-versus-hand split is only
meaningful from **2026-01-05**. There are no NULLs — a clean 0/1 split.

| | |
|---|---|
| Multi-word bookmarks since 2026-01-05 | **22,253** |
| …of which **hand-fused** by the learner | **13,725 = 61.7%** |
| Multi-word bookmarks all-time | **~102,000**, earliest **2017-06-09** |
| `user_mwe_override` rows | **130**, from **46 users**, 130 distinct spans, 2026-01-07 → 2026-09-24 |

Two immediate consequences, in opposite directions.

- **The positive signal is abundant.** ~13,700 learner-chosen multi-word spans in
  nine months, ~102,000 over nine years, across 11 languages. Scale is not a
  constraint on anything in this document. This retires the largest open question
  I had.
- **The negative signal is not viable.** 130 override rows from 46 users is three
  orders of magnitude smaller, exactly as the endpoint's design predicts (§5.3):
  ungrouping costs a deliberate menu interaction, while hand-fusing is in-flow.
  **Any proposal resting on learner rejections is dead.** Build on the positives.

**Hand-fused rate by language, against the architecture that serves it:**

| Languages | Hand-fused | Parser strategy | Lexicon |
|---|---|---|---|
| pt 77.1, it 71.2, es 68.9, fr 66.1 | **66–77%** | `AuxOnlyStrategy` | **none** |
| sv 65.6, ro 64.9, de 60.1, da 54.2, el 53.2, nl 52.6 | 53–66% | Germanic / Romanian / Greek | sv, de, da, nl yes; ro, el no |
| **en 36.8** | **37%** | Germanic | yes |

Sample sizes where given: fr n = 11,557 over 301 users; da n = 3,103 over 116
users; en n = 728 over 84 users.

That ordering is suggestive in the right direction — the four languages with no
lexicon and the thinnest parser strategy sit at the top, and the best-served
language sits at the bottom, a 40-point spread. **But it is a cross-section, and
it is badly confounded.** Languages differ in learner populations, proficiency
mixes, article sources, and — crucially — in how often their MWEs are contiguous
and how much morphology the lemmatiser has to get right. English sitting lowest
could be the lexicon working, or it could be that English learners in Zeeguu are
more advanced, or that English multi-word units are more often adjacent. Nothing
in the cross-section separates these. §5.11 is how you separate them.

**And here is the caveat that matters more than any of the above.** Inspection of
the most-frequently hand-fused Danish spans does **not** return a shortlist of
missed expressions. It returns, mostly, compositional phrases:

`at få` · `har fået` · `skal være` · `er ikke` · `et sted` · `som folk` ·
`skal have` · `forskere siger` · `nogle områder` · `dårlige oplevelser` ·
`sine gæster`

`som folk` is "as people". `forskere siger` is "researchers say".
`dårlige oplevelser` is "bad experiences". These are not MWEs under PARSEME's
scheme, under Wiktionary's, or under any definition in the literature surveyed in
§1. (`slå op` is a genuine verb-particle construction the detector is missing,
but it is the exception, not the pattern.)

**So "hand-fused" does not mean "missed MWE", and a claim of "61.7% recall
failure" would be wrong and trivially demolished in review.** Any reviewer would
ask for a sample of the spans, and the sample refutes the framing.

What the learners are doing is fusing for a **comprehension unit** — a span large
enough to ask a useful question about — and MWE-hood is only one of the things
that makes a span worth asking about. Others visible in that list: grammatical
constructions a learner has not internalised (`skal være`, `er ikke`,
`har fået` — auxiliary and tense morphology, precisely what `AuxOnlyStrategy`
exists to catch and what the languages at the top of the table lack a lexicon
for), and ordinary noun phrases where the learner wants the phrase rather than
the head.

This reframing is *better* than the recall-audit framing, for three reasons given
in §2.1, and it is what Proposal B (§6.2) is now built on. It also requires one
thing the raw counts do not provide: **a labelled sample.** A few hundred
hand-fused spans, classified PARSEME-style (LVC / VPC / VID / non-verbal MWE /
grammatical construction / compositional / other), reported per language. That is
roughly a day of annotation and it is the difference between a claim and an
anecdote. It should be done **before** any abstract is written, because it is also
the fastest way to discover that the claim does not hold.

### 5.11 The natural experiment, and an honest power analysis

A Danish lexicon fix shipped **2026-09-27 ~18:00 UTC** (PR #764) that measurably
improved Danish recall, with nothing else changing. The Danish hand-fusing rate
before and after is therefore a natural experiment on the causal question that
matters: **does better detection actually reduce the work learners do by hand?**

The design is sound and needs no methodological defence: a
difference-in-differences with Danish treated and the other ten languages as
concurrent controls, which removes the cross-sectional confounds in §5.10.

**Two threats must be resolved before trusting it, and one is a hard blocker.**

1. **The tokenization cache smears the treatment onset.** ADR-0004 states the
   problem itself: changes are invisible until `ArticleTokenizationCache` turns
   over, there is no version column, and the only invalidation is a seven-day age
   sweep. The ADR instructs running
   `python -m tools.cleanup_tokenization_cache --language da` *after* the API
   picks up the change. **If that flush was not run, the effective treatment date
   is smeared across up to seven days and the early post-period is contaminated
   with old groupings.** This must be checked and recorded. If it was not run, run
   it, and treat the flush timestamp rather than the deploy timestamp as the
   event.
2. **Danish volume is thin for this.** 3,103 multi-word bookmarks over 265 days is
   **11.7 per day**. Bookmarks cluster within 116 users (~27 each), so
   user-clustered inference is mandatory and costs roughly a factor of 2.3 in
   effective sample size at a plausible ICC of 0.05. Combining that with the
   variance cost of a DiD:

| True effect on Danish hand-fusing rate | Post-period needed | Calendar date |
|---|---|---|
| 15 pp | ~9 weeks | late Nov 2026 |
| 10 pp | ~5 months | late Feb 2027 |
| 5 pp | ~20 months | not viable |
| 2 pp | — | hopeless |

(Baseline p = 0.542, α = 0.05 two-sided, 80% power, DiD variance penalty ×2,
cluster design effect ×2.29. The pre-period is already long enough; only the
post-period accrues.)

**So the single-PR natural experiment cannot be the spine of a paper.** One
lexicon fix moving a behavioural rate by 10–15 points would be a large effect,
and if the true effect is 5 points — entirely plausible — this design will never
resolve it. It is a capstone, and the paper must not depend on it.

**There is a much stronger natural experiment sitting in the same data, and it is
already complete.** Before 2026-01-02 **no detector existed**, so every
multi-word bookmark in the ~102,000-row archive back to 2017 was hand-fused by
construction. The detector launch is therefore a single large intervention — and
it did *not* affect all languages. `NoOpStrategy` languages with no lexicon —
**pl, ru, hu, bg** — got nothing from the launch and serve as genuine controls,
while da/de/el/en/es/fr/it/nl/no/pt/ro/sv were treated. That is a
difference-in-differences across a ~102k-observation panel with a clean event
date, years of pre-period, and eight months of post-period **available now**.

Two caveats on it. The per-language figures reported above cover 11 languages and
do not include pl/ru/hu/bg, which suggests those languages may have too few
multi-word bookmarks to serve as controls — **this needs checking and is Q12 in
§8.** And a launch is never a clean single treatment: the frontend fusion
behaviour, the translation path, and the article mix all changed around it, so a
parallel-trends check on the pre-period is essential rather than optional.

## 6. Concrete paper proposals

### 6.1 Proposal A — A Danish MWE corpus in the PARSEME 2.0 scheme

**The claim.** Danish, a language with ~6M speakers, a national language
technology programme and a major dictionary institute, has **no
multiword-expression identification corpus**. This paper provides the first
one, annotated in the PARSEME 2.0 scheme over UD_Danish-DDT, reports IAA and
scheme-applicability findings, and situates Danish in the Germanic comparison
that the Swedish PARSEME paper opened.

**Why it is unclaimed.** §1.2: Danish has no PARSEME repository, no release in
any of the five editions, and is not among the 7 languages new to 2.0. §1.3:
the only Danish MWE resource is a **type-level** idiom list built for LLM
interpretation benchmarking, with no running text and no annotated
occurrences. §1.3 again: ID10M does not cover Danish. DaNLP's dataset registry
lists no Danish MWE resource. Swedish is the only Nordic language in PARSEME at
all.

**Evidence needed.**
- **Substrate**: UD_Danish-DDT — the **only** Danish UD treebank, 5,512
  sentences / 100,733 tokens, CC BY-SA 4.0, genres news/fiction/spoken/
  nonfiction, contributed by Johannsen, Martínez Alonso & Plank
  (<https://universaldependencies.org/treebanks/da_ddt/index.html>). PARSEME
  builds on UD-compatible morphosyntax, so this is the right and only base.
  Zeeguu already mines it: `tools/extract_mwes_from_ud.py`.
- **Seeds to cut annotation cost**: the 1000 DDO expressions from the Danish
  Idiom Dataset; the 783 lines of mined Wiktionary candidates already sitting in
  `lexicons/_review/da_wiktionary_candidates.txt`; the current ~104-entry
  lexicon. PARSEME's own workflow supports exactly this — the 2.0 paper notes
  that where *"candidates (mapped from MWE lexicons, e.g. in Romanian or
  Georgian) are present, those are validated and other missed candidates are
  sought for."*
- **Expected yield**: PARSEME 2.0 averages 1 MWE per 1.8 sentences across the
  corpus, so ~3,000 MWEs from DDT is the order of magnitude. **This is my
  extrapolation, not a measured figure.**
- **IAA**: PARSEME 2.0 measures IAA as MWE-based F between annotators over a
  subset ranging from 100 sentences (Persian) to 5,200 (Hebrew); IAA exceeds 70
  for 9 of 17 languages. Crucially, **three 2.0 languages (Greek, Japanese,
  Egyptian) had a single annotator and used self-agreement after a delay
  instead.** So a single competent annotator plus a self-agreement measurement
  is a precedented, publishable configuration — which is what makes this
  feasible for a small team.
- **Process**: become a PARSEME **Language Leader** for Danish. The route is
  documented (<https://gitlab.com/parseme/corpora/-/wikis/PARSEME-Language-Leader-Guide>):
  recruit and train annotators, adapt the guidelines with Danish examples,
  coordinate annotation, run the CI/CD CUPT validity checks, write the README,
  and co-author the release publication. The core organisers explicitly offer
  support and invite contact. **This is an open door, not a competition.**

**Venue.** MWE 2027 (long paper) is the natural home — §1.12 shows the 2026
volume contained single-language PARSEME corpus papers for Swedish, Ukrainian,
Romanian and Marathi, so the genre is not merely accepted but routine.
**NoDaLiDa 2027** (University of Copenhagen, 25–28 May 2027) is the
higher-value option for a Danish resource: home institution, local audience,
Nordic remit. Workshop proposals there are due **16 November 2026** and
workshop papers **15 March 2027**; the main-conference deadline is not yet
published (**unverified**). A Danish MWE resource could also simply land in a
future PARSEME release with a joint corpus paper, which is lower effort and
lower credit.

**Risk it is already done: low, but not zero.** I verified absence across the
PARSEME wiki (33 language repos), all five release announcements, ID10M, CoAM,
MultiCoPIE, PIE and DaNLP. The residual risks are: (a) the per-language PARSEME
repositories went **private in August 2025**, so a Danish effort could
conceivably be underway invisibly — a single email to the PARSEME core group
resolves this and **must be sent before any work starts**; (b) DSL
(Det Danske Sprog- og Litteraturselskab), who built the idiom dataset and hold
DDO, are the obvious people to do this and may already intend to. That second
risk is better treated as an opportunity: they are in Copenhagen, they are
funded through sprogteknologi.dk for exactly this kind of work, and a joint
ITU–DSL paper is stronger than either alone.

**Honest effort estimate.** The annotation is the whole cost and it is not
small. PARSEME publishes no per-token annotation rate, so any number here is
inference — **treat the following as unverified estimation.** For all-category
2.0 annotation of ~100k tokens, with a decision-diagram guideline the annotator
must first learn, I would budget **3–5 person-months** for one trained
annotator including guideline training and consistency passes, plus **3–4
weeks** of coordination, tooling, CUPT validation and writing. Halve the
annotation scope to verbal MWEs only and it becomes perhaps 6–8 person-weeks,
but then it is a 1.3-scheme corpus rather than a 2.0 one and the contribution
is weaker. This is the right shape for **an MSc thesis or a funded student
assistant**, supervised — it is not a spare-evenings project, and the failure
mode is a half-annotated corpus that cannot be released.

**What Zeeguu gets even if the paper never happens.** A gold Danish evaluation
set, which §5.6 establishes does not exist in any form, for the one language the
subsystem was built around.

### 6.2 Proposal B — What unit does the reader need? A census of learner-chosen multi-word spans

**This is the strongest proposal, and it got stronger and cheaper when the
production numbers arrived.** It was originally drafted as a recall audit —
"learners reject the detector's groupings, here is the extrinsic error rate" —
and the data refuted that framing (§5.10). What replaced it is a better paper.

**The claim.** MWE identification is defined, annotated and evaluated against
spans that linguists mark. In a deployed reader, learners mark their own spans,
and they have now done so ~102,000 times across 11 languages. Three findings:

1. **61.7% of multi-word lookups are learner-drawn**, not system-proposed
   (13,725 of 22,253 since 2026-01-05), and the rate varies from 37% (English:
   Germanic strategy plus lexicon) to 77% (Portuguese: aux-only strategy, no
   lexicon).
2. **Most learner-drawn spans are not MWEs under any definition in the
   literature.** `som folk`, `forskere siger`, `dårlige oplevelser`, `skal være`
   are compositional. Learners fuse for a **comprehension unit** — a span large
   enough to ask a useful question about — and idiomaticity is only one of the
   things that makes a span worth asking about. Grammatical constructions the
   learner has not internalised are visibly another.
3. Therefore **recall against a PARSEME-style gold standard is the wrong target
   for a reading assistant**, and an F-measure over linguist-defined spans cannot
   tell you whether the tool is serving its user. What the reader needs overlaps
   the MWE but is neither a subset nor a superset of it.

**Why this is the right claim rather than the recall claim.** It does not require
anyone to accept that Zeeguu's detector is good or bad. It is a finding about the
task definition, and it is exactly the kind of finding that only a deployment can
produce — which answers the "why should we care about your one system" objection
before it is raised. It also supplies something the literature currently lacks: a
**mechanism** for Linguse's observation that learners tolerate annotation errors
(§3). If the linguist's unit was never the unit the learner wanted, tolerance is
explained rather than merely reported. And it can be stated as a continuation of
the Linguse Discussion rather than a rebuttal of it, which matters when Savary is
a likely reviewer.

**Why it is plausibly unclaimed — with one live caveat.** §1.5–§1.6 establish
that MWE evaluation is intrinsic F1, that the two authoritative surveys do not
list behaviour among the extrinsic options, and that the MWE 2026 CFP asks for
end-user-application evaluation and its own volume does not answer. The
learner-behaviour side of the CALL literature covers single words only.
**However**: the *idea* that the unit is user-relative is not new. Wray's
speaker-relative formulaicity ("formulaic for whom?") and phraseology's
long-standing split between idiomaticity-based and frequency-based definitions
of the unit are the obvious prior art, and a check on whether anyone has
**measured** the learner/linguist divergence was still running when this document
was finalised (§2.7, §8 Q11). **Do not write an abstract before that lands.** The
likely outcome is that the idea is old and the measurement is new, which is a
perfectly good paper — but it changes the framing from "we discovered" to "we
quantified, for the first time, at scale."

**Evidence needed, in dependency order.**

1. **The labelled sample. This is the gating item and it should be done first,
   because it is also the fastest way to find out the claim is wrong.** A few
   hundred hand-fused spans per language, in context, classified into: PARSEME
   verbal categories (LVC / VPC / VID / IRV / MVC), non-verbal MWE, **grammatical
   construction** (`skal være`, `har fået`), **compositional phrase**
   (`dårlige oplevelser`), and other. Report the distribution per language. One
   day per language for a competent annotator, plus half a day to write the
   category guideline. Three languages with contrasting architectures — Danish
   (Germanic + lexicon), French (aux-only, no lexicon), English (best served) —
   is enough for the paper and costs under a week.
   - If the distribution comes back mostly-MWE, the reframing is wrong and this
     becomes a recall audit after all.
   - If it comes back mostly-compositional, as the Danish spot check suggests,
     the claim holds and the per-language distribution *is* the result.
2. **The intrinsic anchor** (§5.6, shared with Proposal C). Measure the detector
   against PARSEME gold for the 13 covered languages. Two numbers the paper
   needs: what fraction of learner-drawn spans a PARSEME-trained system would
   even be *asked* to find, and what fraction of system-proposed groups learners
   accept. Without this the paper has behaviour and no reference frame.
3. **The dose–response.** The per-language table in §5.10, reported *with* its
   confounds stated plainly (learner population, proficiency mix, article source,
   contiguity and morphology all vary with language). Do not present the
   cross-section as causal. It is a motivating pattern.
4. **The causal check** (§5.11). The detector-launch difference-in-differences
   over the ~102k archive — treated languages against `NoOpStrategy` languages
   with no lexicon (pl, ru, hu, bg), event 2026-01-02, years of pre-period and
   eight months of post-period **already banked**. This is much stronger than the
   single-PR Danish experiment and is available now. Gate it on Q12 (do the
   control languages have enough volume?) and on a parallel-trends check.
5. **The Bishop replication, nearly free.** Bishop (2004) found learners click
   unknown single words 2.22 times against 1.43 for unknown formulaic sequences,
   n = 44, in 2004 (§3.4). Zeeguu can test whether multi-word units are
   under-looked-up relative to single words at a scale four orders of magnitude
   larger, from data already held, with no new instrumentation. It is a separate
   small finding that strengthens the motivation and costs a query.
6. **A release plan, if the corpus is to be a contribution.** ~13,700 spans with
   sentence context across 11 languages is a citable resource of a kind that does
   not exist. It also consists of real learners' reading material and lookup
   behaviour, so releasing it needs a consent basis and a de-identification pass
   (§8 Q3). Decide early whether the corpus is a contribution or only an
   instrument — it changes the venue.

**What this proposal no longer needs**, and this is the main practical gain: **no
collection window, no new instrumentation, no randomisation, and no reliance on
the override table.** The main claim is answerable from data already on disk. The
four instrumentation fixes in §5.3–§5.4 remain worth making, but they are no
longer blockers.

**Venue.** **MWE 2027** is the best fit and should be the target. The CFP asks
for end-user-application evaluation; the audience is the people whose annotation
scheme is being relativised, which is both the risk and the point. Frame it as
*complementary units* — the reader's unit and the linguist's unit answer
different questions — not as "PARSEME measures the wrong thing," which is both
less true and less publishable. Secondary options: **LREC 2028** if the corpus
becomes the headline contribution (resource papers are LREC's core business, but
2028 is far away); **NLP4CALL or ReCALL** for the pedagogical framing, friendlier
reviewers, lower prestige, and the venue where Linguse published. A staged plan
is legitimate: the census and labelled sample to NLP4CALL 2027, the full study
with the DiD and the Danish gold set to MWE 2028.

**Risk it is already done: moderate, and concentrated in one place.** Low for the
measurement, moderate for the idea (§2.7). The single most valuable derisking
action remains **emailing Agata Savary**: she co-authored both Linguse papers, her
Discussion poses this exact question, and she will know instantly whether the
learner/linguist divergence has been measured. That email either derisks the
project or converts the likeliest competitor into a co-author.

**Risk it fails for other reasons: low-to-moderate**, and much lower than before
the numbers arrived. The remaining failure modes are: the labelled sample comes
back mostly-MWE and the framing collapses (cheap to discover, item 1); the
control languages turn out too small for the DiD (item 4, Q12); or the consent
basis for the corpus release does not exist (item 6, Q3 — survivable, the corpus
just stays an instrument).

**Honest effort estimate. 2.5–3.5 person-months**, which is a third of my earlier
estimate because the collection window vanished:

| | |
|---|---|
| Category guideline + labelled sample, 3 languages | ~1 week |
| Census analysis, per-language breakdowns, plots | 2–3 weeks |
| Intrinsic PARSEME harness (shared with Proposal C) | 2–3 weeks |
| Difference-in-differences over the archive | 1–2 weeks |
| Bishop replication query | 1–2 days |
| Writing | 3 weeks |

Calendar time is ~4 months from a standing start if nobody waits for the Danish
single-PR experiment — and they should not (§5.11).

### 6.3 Proposal C — A failure taxonomy for MWE grouping in a deployed reader

**The claim.** MWE identification is evaluated in the literature on corpora,
where every error costs the same F1 point. In a deployed reader the errors are
not interchangeable: they have different user-visible consequences, different
frequencies, and different architectural causes — and the layer responsible is
routinely not the one you would guess. This paper gives the taxonomy from nine
months of production, and for each class the architectural response and whether
it worked.

The `fandt ud af` case from ADR-0004 is the worked example and it is a good one
precisely because the culprit was counter-intuitive: the parser was *right*
(Stanza attached `ud --advmod--> fandt`), `GermanicStrategy` *discarded* the
correct analysis because `ADV + advmod` only becomes a group for words in
`NEGATION_WORDS`, and the lexicon then *filled the vacuum* with a span that is
not an expression. The correct entry existed but sat unpromoted in
`lexicons/_review/` and would not have matched anyway because the verb was
inflected. Four layers, three of them behaving as designed, one wrong answer.
That is the kind of finding a corpus evaluation structurally cannot produce.

**Why it is plausibly unclaimed.** §1.11: after seven search phrasings, no
published paper categorises failure modes of a *deployed* linguistic-annotation
system where the taxonomy plus architectural response is the contribution. The
adjacent work is corpus FP taxonomies (Cheese it up, CoAM) and a 2025–2026
LLM-ops failure-mode genre with the same form and a different subject.

**Evidence needed — and this is where it gets uncomfortable.**
- Per-class **frequency on the production distribution**, not on anecdotes. §5.4
  gives the denominator (proposals recoverable from `ArticleTokenizationCache`);
  §5.3 gives one numerator (overrides). Both are usable.
- **Measured precision on production text**, which does not exist today (§5.6).
  For the 13 PARSEME-covered languages this is obtainable without annotation;
  for Danish it needs Proposal A or a small ad-hoc annotation.
- **Traffic volume and time in production**, which an industry-track reviewer
  will ask for first. Both are now in hand: nine months, 22,253 multi-word
  bookmarks across 11 languages, ~102,000 back to 2017 (§5.10). This is no longer
  a blocker for this proposal.
- **The architectural response per class, with before/after.** Here the
  provenance is weaker than the code comments suggest: the migration
  `26-05-12--cleanup_greek_determiner_ghost_bookmarks.sql` cites a
  `docs/history/…` write-up and an "ADR-019" that **do not exist in the
  repository** (§5.8). The taxonomy must be reconstructed from 76 commits, the
  named PRs (#605, #610, #618/#620, #628, #699/#701, #764), the migrations, and
  the one ADR. That is honest provenance but it is archaeology, and some of the
  before/after numbers are simply gone — nobody measured before changing.

**Venue.** **EMNLP Industry Track** is the right home and its CFP is unusually
explicit about wanting this (§1.12), including negative results and lessons
learned from academic authors on deployed systems. Second choice: the
**Insights from Negative Results** workshop. The MWE workshop is a **poor fit** —
its 2026 volume contained no deployment or experience-report papers at all, and
reviewers there will have no template to score it against.

**Risk it is already done: low. Risk it is rejected anyway: high.** This is the
inverse risk profile of Proposal A. Nobody has written this paper, and there is
a reason: it is hard to make a taxonomy from one system look like a contribution
rather than a war story. Reviewers will ask (a) why these classes generalise
beyond Zeeguu, (b) what the numbers are, and (c) what a reader can *do*
differently. Answer (a) is the strongest available: the classes are organised by
**which layer failed and how**, and the layer inventory (parser rules, lexicon,
neural/LLM) is shared with WiktSeen, MWEasWSD and MorphoFiltered-Gemini, so the
taxonomy is about the architecture, not about Zeeguu. Answer (b) requires
§5.6 to be fixed first. Answer (c) is the "degrade to no-group, never to
wrong-group" contract, which is a genuinely transferable design rule and is not
stated as such anywhere I found.

**Honest effort estimate.** **6–10 person-weeks**, most of it in two
unglamorous places: building the intrinsic evaluation that does not exist
(§5.6 — 2–3 weeks for the 13 PARSEME languages, including writing a CUPT
reader and deciding on a precision-oriented metric), and the git/PR archaeology
(2–3 weeks). The writing is 2 weeks. It does **not** require new user data,
new annotation, or ethics approval, which makes it by far the cheapest of the
proposals — and the only one that can start this week.

### 6.4 Proposal D — Does grouping precision actually matter to learners?

Listed because §3 establishes it is the most *interesting* question here, and
because the competing paper poses it in print. Listed last because Zeeguu is
currently the least equipped of the four to answer it.

**The claim.** The precision-over-recall convention in learner-facing NLP is
~23 years old, rests on a commercial 90%-precision product gate (Burstein et al.
2003) and two uncited assertions (Chodorow et al. 2007; Ng et al. 2014), and has
been tested experimentally **once** — Nagata & Nakatani, COLING 2010, with ~7
participants per cell. That one experiment found low-precision feedback **worse
than no feedback at all** (47 sessions to halve the error rate against 29 for no
feedback), and found that F-measure ranked the systems in the *opposite* order to
the learning outcome. This paper tests the convention properly, for MWE grouping,
with randomised assignment in a deployed reader.

**Why it is unclaimed, and unusually cleanly.** §3.5: the Linguse Discussion
states it verbatim — *"Do false positives have a more detrimental effect than
false negatives in the context of language teaching applications?"* — and adds
*"To the best of our knowledge, no such benchmarks exist currently."* §3.5 gap 1:
no evaluated reading interface automatically groups MWEs with the grouping's
precision manipulated. Bishop (2004) hand-marked the items, so there were no
false positives by construction; the gaze-contingent highlighting work is a
three-page progress report; ColloCaid is a writing tool.

**Evidence needed.** Randomised assignment of learners to a
higher-recall/lower-precision detector configuration versus the current one, and a
downstream outcome. Configurations are easy — the architecture already has the
knobs (turn on more `GermanicStrategy` relations, lower the lexicon's match
threshold, enable `HYBRID_LANGUAGES`). The outcome is the hard part: reading
comprehension is not measured in Zeeguu, so the realistic candidates are
behavioural (ungroup rate, tap-and-abandon, translation re-requests, session
abandonment) or learning-proxy (retention of the resulting words through the
scheduler). Given §3.2, a *perception* outcome would be the wrong choice — the
whole point is that learners cannot detect the errors.

**Blockers, and they are real.**
- **No randomisation infrastructure.** §5.7: no experiment-group, feature-flag or
  variant-assignment machinery anywhere in `zeeguu/`. `SHOW_MWE_HINTS` is
  self-selected and cannot substitute. This has to be built.
- **Ethics.** This proposal, uniquely, involves deliberately serving a
  configuration you believe to be worse, to real learners, to find out how much
  worse. That is a standard and answerable A/B ethics question — the harm is small,
  reversible, and of the same kind learners already encounter — but it must be
  answered before, not after, and there is currently no consent field anywhere in
  the models (§8 Q3).
- **Power.** The same arithmetic as §5.11 applies and is worse, because the
  outcome is rarer than a fusion event. A Danish-only arm is hopeless; this needs
  the large languages (fr, de, es, it) and months.

**Venue.** **NLP4CALL, EUROCALL or ReCALL** for the CALL framing — this is a
pedagogy question and those reviewers will judge the design rather than the NLP.
**CHI or CSCW** if framed as over-reliance on imperfect automated annotation,
where §3.2's HCI literature is the home crowd and Zeeguu has form (CHI 2018). The
MWE workshop is a poor fit; it has no template for a randomised learner study.

**Risk it is already done: very low.** §3 searched this directly from several
angles and found one 2010 poster.

**Risk it never happens: high.** It needs infrastructure Zeeguu lacks, an ethics
process that may not exist yet, and a long collection window — and it is the third
thing in a queue behind two cheaper papers.

**Honest effort estimate. 6–9 person-months**, and that is optimistic: 3–4 weeks
to build randomisation, 2–3 weeks to define and validate an outcome measure,
unknown calendar time for ethics approval, 4–6 months of collection, 6 weeks of
analysis and writing. **PhD-project shape.** Do not start it as a side project.

## 7. Recommendation

**There is a paper here. It is Proposal B, it is about four months of work rather
than a year, and the thing that decides whether it exists costs under a week.**

That changed twice while this document was being written. The first draft said the
gating unknown was Zeeguu's traffic volume; the database answered that
decisively — ~102,000 learner-chosen multi-word spans since 2017, ~13,700 since
January 2026 (§5.10). The second draft said the paper was a recall audit; the
same data refuted that framing, because most hand-fused spans are not MWEs. What
is left is a better claim than either: **the unit a reader needs is not the unit
the literature defines**, and Zeeguu is the only system in a position to measure
how far apart they are.

### 7.1 Do this week

**1. The labelled sample. This is the gate on everything.** Take ~300 hand-fused
spans in context from three languages with contrasting architectures — Danish
(Germanic + lexicon), French (aux-only, no lexicon), English (best served) — and
classify them: PARSEME verbal categories, non-verbal MWE, grammatical
construction, compositional phrase, other. Under a week including the guideline.

Do it first because it is the cheapest way to discover the claim is wrong. If the
spans come back mostly-MWE, the reframing collapses and this reverts to a recall
audit, which is a much weaker paper. If they come back mostly-compositional, as
the Danish spot check suggests, the distribution *is* the result and the paper has
a spine.

**2. Check whether the tokenization cache was flushed for Danish after PR #764.**
ADR-0004 is explicit that detection changes are invisible until
`ArticleTokenizationCache` turns over and that the flush must be run *after* the
API picks up the change. If it was not run, the natural experiment's treatment
onset is smeared across up to seven days and the early post-period is
contaminated (§5.11). Five minutes to check, and it is the difference between a
usable event date and a useless one.

**3. Email Agata Savary.** She leads PARSEME, co-authored both Linguse papers,
and her own Discussion asks the question Proposal D poses and states that no
benchmark exists. She will know instantly whether the learner-versus-linguist
divergence in §2.1 has already been measured, which is the one open novelty
question in this document (§2.7). The email either derisks the project or turns
the likeliest competitor into a co-author. The cost — revealing the idea to the
one group that could execute it faster — is real and worth paying, because being
second here is worth nothing.

### 7.2 Do this month

**Build the intrinsic evaluation that does not exist** (§5.6). Download the public
PARSEME 1.3 and 2.0 releases, write a CUPT reader, measure the detector on the 13
of 16 learnable languages with gold data (§1.2). Report precision and recall
separately; choose a precision-weighted summary deliberately rather than
defaulting to F1, since ADR-0004's constraint makes plain F1 the wrong metric.

2–3 weeks. It is shared between Proposals B and C, it is the column Zeeguu most
conspicuously loses (§4), and its value does not depend on any paper. Right now
nobody can say whether `GermanicStrategy` is any good, which is an uncomfortable
thing to be true of code that has been shaping what learners read for nine months.
Expect the recall numbers to look terrible and decide in advance how to report
that — Zeeguu targets a narrow high-precision subset and is allowed to return
nothing, so recall against PARSEME is close to meaningless. Deciding that before
seeing the numbers is the difference between an evaluation and a rationalisation.

**Run the detector-launch difference-in-differences** (§5.11). Before 2026-01-02
no detector existed, so every multi-word bookmark back to 2017 was hand-fused by
construction, and `NoOpStrategy` languages with no lexicon (pl, ru, hu, bg) got
nothing from the launch. That is a ~102k-observation panel with a clean event
date, years of pre-period and eight months of post-period **already banked** —
far stronger than waiting on the single Danish PR. Gate it on Q12 and on a
parallel-trends check.

### 7.3 Then

**Pursue Proposal B (§6.2) as the research contribution.** Target **MWE 2027**,
framed as *complementary units* rather than as a critique of PARSEME. It is the
only proposal with a claim a strong venue would care about, it needs no collection
window, no new instrumentation, no randomisation and no reliance on the override
table, and it supplies a mechanism for the one empirical finding in the competing
literature. ~2.5–3.5 person-months of work, ~4 months calendar.

**Pursue Proposal A (§6.1) if and only if there is a student.** The safest
publishable output here: a verified gap, a venue that routinely accepts the genre,
a documented entry route, a precedent paper to model on. At 3–5 person-months of
annotation it is a good MSc thesis and a bad side project. **NoDaLiDa 2027 in
Copenhagen (25–28 May 2027)** is the target; the workshop-paper deadline of 15
March 2027 is reachable if annotation starts around November 2026. Its
by-product — a gold Danish evaluation set — is worth more to Zeeguu than the paper.

**Fold Proposal C (§6.3) into Proposal B, or hold it as a fallback.** The
`fandt ud af` failure analysis is a genuinely good worked example and belongs in
Proposal B as motivation. As a standalone EMNLP Industry Track paper it remains
viable and uncrowded, but it is now the third-best use of the same effort.

**Do not start Proposal D (§6.4) yet.** It is the most interesting question in
this document and the one Zeeguu is least equipped to answer: no randomisation
infrastructure, no consent basis, no outcome measure, and a long collection
window. It is the paper after the paper.

### 7.4 Do not

- **Do not claim "61.7% recall failure."** This is the most important negative
  recommendation in the document. The number is real and the framing is wrong —
  the top hand-fused Danish spans are `som folk`, `forskere siger`,
  `dårlige oplevelser`. Any reviewer will ask for a sample, and the sample refutes
  the claim. State the census as a divergence finding, not as an error rate.
- **Do not build the paper on the Danish single-PR natural experiment.** §5.11:
  under a realistic difference-in-differences with user-clustered inference, a
  15-point effect is visible by late November, a 10-point effect by late February,
  and a 5-point effect never. One lexicon PR moving a behavioural rate by 10–15
  points would be a large effect. Use it as a capstone; use the launch DiD as the
  spine.
- **Do not plan anything around `user_mwe_override`.** 130 rows, 46 users, nine
  months (§5.10). The rejection signal is absent, not thin.
- **Do not write the architecture paper.** §1.8–§1.9: every layer has a named
  precedent, the 2017 survey treats the composition as settled engineering, and
  Savary's group has published the rule+lexicon-in-a-learner-reading-app paper
  twice, precision argument included.
- **Do not write an LLM-for-MWE paper.** §1.10. Closed in the last eighteen
  months, with the PARSEME organisers' own verdict that modern LLMs make "little
  progress" on this task.

### 7.5 The honest bottom line

ADR-0004 is a better piece of technical writing than most of what is cited above,
in the specific sense that it states its failure contract, records the bug that
motivated it, and measures the thing it decided on. None of that is publishable,
and the temptation to make the architecture the paper should be resisted.

What *is* publishable is the thing nobody thought to look at, and it is not what
anyone expected going in. The interesting finding is not that the detector misses
expressions. It is that **learners are asking a different question than the one
the field has spent nine years annotating for** — and that this may be why the one
user study in the literature found learners shrugging at annotation errors. That
is a real contribution, it is cheap, and the data is already on disk.

Three caveats keep it honest. The idea that the unit is user-relative is probably
not new (Wray, 2002) even if the measurement is — and that check had not landed
when this was written (§2.7). The cross-sectional language comparison is
confounded and must not be presented as causal. And the whole thing rests on a
labelled sample that does not exist yet and could refute it in a week.

If only one thing happens as a result of this document, let it be the labelled
sample. If two, add the evaluation harness.

## 8. Open questions needing Mircea's input

Ordered by how much they change the plan.

**Q1. Is the labelled sample worth a week of your or a student's time, now?**
Everything in Proposal B depends on it and nothing else can substitute. If the
answer is no, the honest conclusion is Proposal A or nothing.

**Q2. Was `tools/cleanup_tokenization_cache.py --language da` run after PR #764
deployed on 2026-09-27?** If not, the natural experiment's event date is the cache
turnover, not the deploy, and the first week of post-period data is mixed. Also:
was it run after the earlier MWE changes (#605, #610, #618)? If not, every
before/after in the history is smeared, which matters for the launch DiD too.

**Q3. What is the consent and ethics basis for publishing analyses of learner
interaction data — and for *releasing* a corpus of learner-chosen spans with
their sentence contexts?** I found no consent, terms-of-service, GDPR or
research-use field anywhere in the models. You have published user studies before
(CHI 2018, EUROCALL 2022), so some pathway exists; I need to know whether it
covers retrospective log analysis and, separately, redistribution. The answer
decides whether the ~13,700-span corpus is a contribution or only an instrument
(§6.2 item 6).

**Q4. Is there a student?** Proposal A is a well-shaped MSc thesis and a poor side
project. If there is one, does ITU's thesis calendar line up with a NoDaLiDa 2027
submission (workshop papers 15 March 2027, main-conference deadline not yet
published)?

**Q5. Do you have a relationship with Agata Savary or the PARSEME core group, and
are you willing to write to them?** This is the single highest-value action
available (§7.1) and it has a real cost. It is your call, not mine.

**Q6. Any contact with Det Danske Sprog- og Litteraturselskab?** They hold DDO,
published the 1000-idiom dataset (§1.3), are funded through sprogteknologi.dk for
exactly this kind of work, and are in Copenhagen. They are the natural co-authors
for Proposal A and the most likely people to preempt it. Do you know whether they
are already planning MWE corpus work?

**Q7. Which is the actual goal — a publication, or better MWE detection?** They
diverge sharply. The fastest route to better detection is adopting DSL's 1000
expressions into `lexicons/da.py` and building the evaluation harness; neither is
a paper. The fastest route to a paper is the labelled sample and the census, which
improves detection not at all. Both are worth doing; knowing which you are
optimising for changes the order.

**Q8. Is the 5–15 second LLM latency figure measured or estimated?** It is
load-bearing for the cost argument in ADR-0004 and §2.6, and I could not find the
measurement in the repository.

**Q9. Do `docs/history/26-05-12--translation-disambiguation-and-auto-mwe.md` and
"ADR-019" exist anywhere?** The Greek cleanup migration cites both; neither is in
the repo (`docs/adr/` holds only 0001–0004). If they are in your vault they would
materially reduce Proposal C's archaeology cost — and they are the kind of
document that should be in the repo.

**Q10. Norwegian.** Zeeguu supports `no`, and Norwegian is absent from PARSEME
exactly as Danish is. Bundle it into Proposal A as a Danish+Norwegian Nordic
contribution, or is that scope creep? My instinct is scope creep — one language
done properly beats two done thinly — but you know the Norwegian user base and I
do not.

**Q11. The one literature check still open.** Whether anyone has *measured* the
divergence between learner-selected and linguistically-defined multi-word units
was still running when this was finalised (§2.7). The likely prior art is Wray's
speaker-relative formulaicity and phraseology's frequency-versus-idiomaticity
split, which would leave the measurement novel but not the idea. **Do not write an
abstract for Proposal B until this is settled**, and Q5 is the fastest way to
settle it.

**Q12. Do pl, ru, hu and bg have enough multi-word bookmarks to serve as DiD
control languages?** The per-language figures in §5.10 cover 11 languages and omit
these four, which may mean they are too small. The launch difference-in-differences
in §5.11 depends on them. One query.

**Q13. Was anything else deployed on 2026-09-27?** The natural experiment assumes
the Danish lexicon fix was the only change. Worth confirming against the deploy
log rather than against memory.
