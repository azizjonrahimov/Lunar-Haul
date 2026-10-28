# Writing the Lunar ATC papers: style guide, section template and referee checklist (current to 2026-10-27)

This note is for the three papers planned from the Lunar ATC simulation study (decentralized learned bidding, cross-owner team lifts, a safety layer, operation without Earth contact). It has five parts:

1. What the writing literature agrees on, reduced to rules we can check.
2. How to report a simulation study: ODD, STRESS-DES, and the V&V sources.
3. How to report statistics from a common-random-number design.
4. The features that make text read as machine-written, and how to remove them.
5. A section-by-section template with word budgets for a 25–40 page paper, then a referee checklist.

It builds on what the earlier rounds taught us. The two referee reports on v3 (`paper/v3/REVIEW_round1.md`, `REVIEW_round2.md`) and the round-1 report on r1 (`paper/r1/REVIEW_round1.md`) found no em-dashes and no filler vocabulary, so we no longer make the vocabulary mistakes. The criticisms that remained were structural: counted openers ("Three things matter"), verdict one-liners ("Distance is what costs."), "X, not Y" constructions (39 in v3), a Discussion that repeated the Results, slogans opening paragraphs, project code words in the prose (`any_part`, "Phase-2 mix", "v3"), abstracts carrying 30 numbers, and claims that went past the data (slopes evaluated at u = 0, "never", "no amount of DAgger helps"). The same reports singled out some passages to keep: the pilot that reversed sign, the documented browser divergence, "the check tests the implementation, not the model", and the honest Limitations. Those passages are the model for the new papers.

---

## 1. Principles, with sources

### 1.1 Gopen and Swan, "The Science of Scientific Writing" (American Scientist 78(6), 1990, pp. 550–558)

Readers have fixed expectations about where information appears in a sentence. Meet those expectations and the reader spends attention on the content, not on decoding the prose.

- **Subject and verb together.** Put the verb right after the grammatical subject. "The auction, which runs on every vehicle and uses the bids of the previous round together with the link state, converges in 4 rounds" makes the reader hold the subject for 18 words. Better: "The auction converges in 4 rounds. It runs on every vehicle and uses..."
- **Stress position.** The end of a sentence is where readers look for emphasis. Put the new or important item there: "Under perfect communication the decentralized assignment matched the centralized optimum in all 1,000 instances", not "In all 1,000 instances, the decentralized assignment matched the centralized optimum under perfect communication."
- **Topic position.** The start of a sentence should hold old information that links back to the previous sentence, and should name whose story the sentence tells.
- **Actions belong in verbs.** "We performed an evaluation of" becomes "we evaluated". Pinker calls nominalizations "zombie nouns".
- **Context before new material.** Give the condition before the result: "With one owner, pooling changes nothing", not "Pooling changes nothing, with one owner."

### 1.2 Mensh and Kording, "Ten simple rules for structuring papers" (PLOS Computational Biology 13(9): e1005619, 2017)

1. Focus on one central contribution, and put it in the title.
2. Write for readers who do not know your work. Define every term the first time it appears, and use no internal shorthand.
3. Use context–content–conclusion (C-C-C) at every scale: the paper, each section, each paragraph.
4. Avoid zig-zag. Mention each subject in one place, and use parallel structure for parallel items.
5. Make the abstract tell the whole story: context, gap, approach, the main results with numbers, and what they mean.
6. In the introduction, say why the paper matters. Narrow from the field to the gap.
7. Present results as a chain of claims, each backed by a figure or table, that adds up to the central contribution.
8. In the discussion, say how the gap was filled, state the limitations, and say what the work means for the field.
9. Spend your time on the title, abstract, figures and outline. Most readers see nothing else.
10. Get feedback and cut. Ask a reader outside the project to summarize the paper; if the summary is wrong, the paper is unclear.

Two rules matter most for us. Rule 1: three papers means three central contributions. Do not let all of them leak into every paper. Rule 3: the C-C-C paragraph is the fix for the "slogan opener" criticism. Open with context, give the evidence, and close on the consequence. Do not close on a restatement.

### 1.3 Whitesides, "Writing a Paper" (Advanced Materials 16(15), 2004, pp. 1375–1377)

- A paper is a tool for organizing the research, not a log of it. Write the outline early, ideally before the last experiments, and let the outline show which experiments are still missing.
- Outline in this order: the conclusions you hope to support, then the figures and tables that would support them, then the text. Rewrite the outline as the data come in.
- A paper is not the history of the work. Report the design that worked, and give the failures that teach something in their own short subsection, not in chronological order.
- Most of the information is in the figures and tables. The text explains them.

### 1.4 Strunk and White, *The Elements of Style* (4th ed., 2000), and Pinker, *The Sense of Style* (Viking, 2014)

From Strunk and White: omit needless words; use the active voice; put statements in positive form; use definite, specific, concrete language; keep related words together; express parallel ideas in parallel form; place the emphatic words at the end.

From Pinker:
- **Classic style.** The writer shows the reader something in the world, as in a conversation between equals. Avoid metadiscourse ("In this section we will discuss"), hedges used as defense rather than information, and talk about concepts when you could talk about things. "The auction" is a thing. "The coordination paradigm" is not.
- **The curse of knowledge.** We know the code. The reader does not. Every abbreviation, every scenario label and every metric name is a tax on the reader. Name things by what they are: "the four-vehicle fleet at reference demand", not "P2-4".
- **Coherence.** Readers follow the given-then-new order, consistent naming (one term per concept, used every time), and explicit connectives that state the real logical relation (because, but, so, for example). Use them where the relation exists. Do not use them as decoration.
- **Hedging.** Hedge once, where the uncertainty actually is, and say what the uncertainty is ("within the 2028–2031 calendar only"). Do not stack hedges ("may potentially suggest").

### 1.5 What venues ask for

Check each item against the venue's current page before submission. Where this note could not confirm a value from the primary page, it says so.

| Venue | Length | Abstract | Other requirements |
|---|---|---|---|
| IEEE Transactions on Robotics (regular paper) | First submission ≤ 18 pages. Final ≤ 20 pages in Transactions format, counting figures, references and biographies. $175 per page beyond 12. | ≤ 200 words | Optional multimedia (≤ 50 MB zip with ReadMe.txt and Summary.txt). The paper must stand alone: T-RO reviews only the paper. Confirmed on ieee-ras.org, Oct 2026. |
| Journal of Spacecraft and Rockets (AIAA) | AIAA guideline about 10,000–12,000 words for a regular article, figures and tables counted as word equivalents (about 1,400 words per printed page). | 100–200 words, one paragraph, no acronyms or reference numbers | Title ≤ 12 words with no acronyms. Confirmed on aiaa.org author pages; the JSR-specific page was not retrieved. |
| Acta Astronautica (Elsevier) | No fixed limit found. | Elsevier norm is ≤ 250 words | Elsevier norm: 3–5 highlights of ≤ 85 characters each, up to about 6 keywords, a data-availability statement and a declaration of generative-AI use. The journal's guide returned 403 here; confirm on the Elsevier page. |
| Autonomous Robots (Springer) | No fixed limit. | Springer norm is 150–250 words | 4–6 keywords. Confirm. |
| AAMAS (main track) | 8 pages plus references in ACM format, typically. | Short | Double-blind. Check the year's call for papers. Suited to the auction and learned-bidding paper; a full journal version can follow. |

Every target venue now asks authors to disclose any use of generative AI in preparing the manuscript, in the acknowledgements or in a separate declaration. AI tools cannot be listed as authors. Plan the disclosure from the start.

### 1.6 Suggested fit of the three papers

This is a working assumption to be revised once the outlines exist.

- Coordination paper (decentralized learned bidding and team lifts): AAMAS, then Autonomous Robots.
- Safety and Earth-independent operation paper: T-RO. It needs formal statements and proofs or model-checking results, plus the zero-violation statistics.
- Operations paper (what the network buys a lunar base in delay, tonnage and cost): Acta Astronautica or JSR.

Each paper cites the other two for anything outside its own contribution. Mensh and Kording's rule 1 applies to each paper separately.

---

## 2. Reporting a simulation study

### 2.1 ODD protocol for the model description

The ODD protocol (Overview, Design concepts, Details) is the standard description format for agent-based models: Grimm et al. 2006, Ecological Modelling 198:115–126; updated 2010, Ecological Modelling 221:2760–2768; and 2020, JASSS 23(2):7. A model with learned agents bidding in an auction is agent-based, and ODD gives referees from multi-agent systems a familiar map. It has seven elements:

1. **Purpose and patterns.** What the model is for, and which observed or published patterns it must reproduce (for example the JSC teleoperation speeds, the M/G/1 wait, Horizons Earth elevations).
2. **Entities, state variables and scales.** Vehicles, owners, cargo items, sites, links and the safety monitor. Give every state variable with its unit. State the time step (none: event-driven) and the spatial extent and resolution (the 5 m LOLA tile).
3. **Process overview and scheduling.** The event list, and the order of actions within an event: arrival, bidding rounds, award, safety check, motion, link updates.
4. **Design concepts.** Cover the eleven concepts that apply: basic principles, emergence, adaptation, objectives, learning, prediction, sensing, interaction, stochasticity, collectives, observation. For us, learning (how the bidding policy was trained), sensing (what each vehicle knows, and when), interaction (messages and their range), stochasticity (which streams, which seeds) and observation (what is logged) carry most of the content.
5. **Initialization.**
6. **Input data.**
7. **Submodels.** One subsection each for dispatch and auction, radio and visibility, safety layer, traffic, energy, and learned policy.

Keep the full ODD in an appendix. Use the ODD headings as the skeleton of the model section in the body. Grimm et al. 2014 (Ecological Modelling 280:129–139) add TRACE, a structured record of model development, testing and analysis. Our `.team/reports.md` plus the V&V appendix already covers most of it; a short TRACE table in the supplement makes that visible.

### 2.2 STRESS-DES checklist

Monks, Currie, Onggo, Robinson, Kunc and Taylor, "Strengthening the reporting of empirical simulation studies: Introducing the STRESS guidelines", Journal of Simulation 13(1):55–67, 2019. STRESS-DES has 20 items in six groups. Fill it in and publish it as a supplementary table. Referees in operations research look for it.

| Group | Items, with where they go in our papers |
|---|---|
| 1. Objectives | 1.1 purpose of the model; 1.2 model outputs (the primary and secondary metrics); 1.3 aims of the experiments (the preregistered hypotheses) |
| 2. Logic | 2.1 base-model overview diagram; 2.2 base-model logic; 2.3 scenario logic (what each factor changes); 2.4 algorithms (auction, CBBA variant, safety rules, learned policy); 2.5 components: entities, activities, resources, queues, entry and exit points |
| 3. Data | 3.1 data sources (LOLA, SPICE, Horizons, JSC trials, NASA manifests); 3.2 pre-processing; 3.3 input parameters (the table with provenance flags); 3.4 assumptions |
| 4. Experimentation | 4.1 initialization (warm-up, or why none is needed); 4.2 run length; 4.3 estimation approach (replications, CRN, intervals) |
| 5. Implementation | 5.1 software and language versions; 5.2 random sampling (generator, streams, seeding); 5.3 model execution (event scheduling, tie-breaking); 5.4 system specification (CPU, RAM, run times) |
| 6. Code access | 6.1 sharing statement (repository, tag, DOI, licence) |

### 2.3 Provenance flags

Our earlier papers tag each parameter as Measured, Spec, Modelled or Assumed. Referees praised this. Keep it, but per the r1 review W7 put the flags in tables and at the first use of a parameter in the Methods. Do not put them in the Introduction or the Abstract.

### 2.4 V&V vocabulary and sources

Use these terms exactly. Referees notice when "validation" is used for "verification".

- **Verification:** the code implements the conceptual model correctly. **Validation:** the model is accurate enough for its intended use. Sources: Sargent, "Verification and validation of simulation models", Journal of Simulation 7(1):12–24, 2013; Law, *Simulation Modeling and Analysis*, 5th ed., McGraw-Hill, 2015, ch. 5. In Oberkampf and Roy (*Verification and Validation in Scientific Computing*, Cambridge, 2010), verification splits further into code verification and solution verification.
- **Sargent's techniques:** animation, comparison to other models, degenerate tests, event validity, extreme-condition tests, face validity, historical data validation, internal validity, multistage validation, operational graphics, parameter variability and sensitivity analysis, predictive validation, traces, Turing tests. Name the technique when you report a check.
- **Balci:** about 75 VV&T techniques in four classes: informal, static, dynamic and formal (Balci, "Verification, validation, and testing", in Banks (ed.), *Handbook of Simulation*, Wiley, 1998, ch. 10). Assertion checking and model checking fall under the dynamic and formal classes.
- **Kleijnen:** statistical techniques for validation, including the warning that a model can fit data it was calibrated on without being valid (Kleijnen, "Verification and validation of simulation models", European Journal of Operational Research 82(1):145–162, 1995).
- **NASA-STD-7009A** (2016; superseded by 7009B in 2024) asks for a credibility assessment of any model whose results feed a decision, scored factor by factor. The 2008 standard's eight factors were verification, validation, input pedigree, results uncertainty, results robustness, use history, M&S management and people qualifications. 7009A and its handbook (NASA-HDBK-7009A) refine these: NASA applications under 7009A score data pedigree, input pedigree, code verification, solution verification, conceptual validation, referent validation, results uncertainty and results robustness on a 0–4 scale (e.g. NTRS 20230000585). Take the exact list from NTRS 20160011121 before citing it.
- **ASME V&V 40-2018.** Scale the evidence to the risk. Model risk is the combination of model influence (how much the decision rests on the model) and decision consequence. For us, the safety paper makes high-consequence claims and needs the strongest evidence; the throughput and cost claims need less.

The verification plan (`verification_plan.md`, in this folder) maps each proposed check onto these terms.

---

## 3. Statistics reporting

### 3.1 Rules for a common-random-number design

1. **Name the primary comparisons before the final runs.** Preregister them: a dated file in the repository, committed and tagged before the production runs (Nosek et al., "The preregistration revolution", PNAS 115(11):2600–2606, 2018). The file lists, per paper:
   - the hypotheses;
   - the primary metric;
   - the comparison;
   - the effect size of interest or the equivalence margin;
   - the replication rule;
   - the multiplicity correction.

   The r1 review (S16) asked for exactly this after 810 effects had been reported. Everything not in the file is exploratory, and the paper says so.
2. **Report effect sizes with intervals, not p-values alone.** Give the paired difference (or ratio) with its 95% interval, the number of replications, and the units. Use "significant" only in the statistical sense, and say which test. See Wasserstein and Lazar, "The ASA statement on p-values", The American Statistician 70(2):129–133, 2016.
3. **Pair the analysis to match the design.** Under common random numbers, the effect is the mean of the per-seed differences, with a paired t-interval or a paired bootstrap. Comparing two independent intervals for overlap wastes the variance reduction and misleads (v3 review C6). Report the correlation between paired outputs, or the variance-reduction factor, once, to show that CRN worked (Law 2015, ch. 11).
4. **Heavy tails.** For delays and p90s, use paired log-ratios (geometric-mean ratio with a t-interval on the log scale) or a Wilcoxon signed-rank or sign test. Report medians beside means (r1 S2). Bootstrap intervals need at least 2,000 resamples, preferably 10,000, with BCa or percentile intervals; never silently drop non-finite resamples (r1 S4).
5. **"No difference" claims need an equivalence test.** Use TOST with a margin stated in advance (Schuirmann, Journal of Pharmacokinetics and Biopharmaceutics 15(6):657–680, 1987; Lakens, Social Psychological and Personality Science 8(4):355–362, 2017). "Statistically indistinguishable" from a non-significant test is not evidence of equivalence. This matters for claims such as "the learned bidder matches its teacher" and "decentralized equals centralized".
6. **Multiplicity.** Control the family-wise error with Holm for the few primary comparisons. Use Benjamini–Hochberg false-discovery control for screening tables. Say plainly that secondary intervals are per comparison and unadjusted.
7. **Blocks.** If seeds are crossed with calendar start years, the years are a block, not noise (r1 S3). Analyse by block, or state that the intervals include calendar variation over the years used.
8. **Replication and run length.** State the rule. For example: "replications were added until the 95% half-width of the mean urgent delay was within 5% of the mean, with a minimum of 30" (Law 2015, sequential procedure, ch. 9). Report the warm-up method (MSER-5, or Welch's graphical method), or the reason none is needed (terminating simulation from an empty start).
9. **Censoring.** If an item is still waiting at the horizon, its delay is censored. Report the completion share beside every delay statistic, or use a censored estimator (r1 S1).
10. **Zero-event results** (safety violations). Report the exposure: encounters, vehicle-hours, number of runs. Give the 95% upper bound on the rate: about 3/n for zero events in n independent trials (Hanley and Lippman-Hand, JAMA 249(13):1743–1745, 1983); the exact value is 1 − 0.05^(1/n). State what counts as independent. Encounters within one run are correlated, so the conservative n is the number of runs.
11. **Extrapolation.** Report fitted slopes inside the range of the data. Centre covariates at their mean, or evaluate at the reference cell (v3 C3).
12. **Do not quote a number twice with different rounding.** Generate every number in the text from one values file (as `paper/r1/values.json` does). The v3 review found every slip in places where numbers had been typed by hand.

### 3.2 Phrases that the statistics allow

| Write | Only if |
|---|---|
| "X reduced the p90 delay by 6.1 h (95% CI 4.0 to 8.3 h, paired, 30 seeds)" | always the preferred form |
| "X and Y are equivalent within ±5%" | TOST passed at the preregistered margin |
| "we found no difference (−0.4 h, 95% CI −1.9 to 1.1)" | give the interval so the reader sees how small an effect is excluded |
| "X always / never ..." | true in every cell run, and the text says "in every cell we ran" |
| "significantly" | a named test at a stated α, after the stated correction |
| "zero violations in 1.2 million encounters over 900 runs (95% upper bound 3.3 × 10⁻³ per run)" | exposure and bound reported |

---

## 4. Text that reads as machine-written, and how to fix it

These features are not wrong one at a time. They become a signature through frequency and co-occurrence, and referees now look for them. Most of them are also simply bad writing: each spends the reader's attention without adding information. The fix is almost always to replace a pattern with a specific fact.

### 4.1 Vocabulary

Words that appear far more often in machine-generated text than in human scientific prose:

- **Verbs:** delve, underscore, showcase, leverage (as a verb), harness, unlock, foster, navigate (figuratively), streamline, bolster, elevate, embark, spearhead, garner, illuminate.
- **Adjectives:** crucial, pivotal, vital, paramount, robust (outside its statistical meaning), seamless, intricate, multifaceted, holistic, comprehensive, cutting-edge, groundbreaking, nuanced, meticulous, invaluable, transformative.
- **Nouns:** landscape, realm, tapestry, paradigm, synergy, interplay, testament, cornerstone, game-changer, journey.
- **Adverbs and connectives:** notably, importantly, crucially, furthermore, moreover, additionally, ultimately, overall, in summary, in essence, essentially.
- **Stock phrases:** "plays a crucial/vital/key role", "a wide range of", "it is worth noting that", "it is important to note", "paves the way", "in today's ...", "sheds light on", "opens new avenues", "a growing body of", "serves as a", "stands as a", "in the realm of", "at the intersection of".

Fix: delete the word, or replace it with the number or the mechanism it stands in for. "The safety layer plays a crucial role" becomes "The safety layer rejected 4.1% of awarded routes." "Robust" is allowed only with a stated perturbation and result.

### 4.2 Sentence-level patterns

- **Uniform rhythm.** Runs of sentences of similar length (18–25 words) with the same subject-verb-object shape. Human technical prose mixes 6-word sentences with 35-word ones, because the length follows the content. Check by reading aloud. A run of five sentences within a few words of each other in length, all opening with "The", is a flag.
- **Tricolons.** Groups of three adjectives, three nouns or three clauses ("scalable, resilient and efficient"), especially when the third item adds nothing. Real lists have the number of items the facts have: two, four, seven.
- **"Not only X but also Y", and its cousin "X, not Y".** Allowed when a reader would plausibly expect X alone. v3 had 39 instances of ", not ", which is too many. Keep it for the one or two real contrasts in the paper.
- **The reveal.** "The result? ...", "The answer is simple: ...", "Here's the thing", and the colon used for drama. Delete the set-up and state the result.
- **Rhetorical questions** as openers. State the question as a research question once, in the Introduction.
- **Em-dash pairs** used for asides. Use commas or parentheses, or split the sentence. Our papers have had none since v3; keep it that way.
- **Stacked hedges.** "may potentially", "could possibly suggest", "appears to somewhat". Hedge once, where the uncertainty is, and quantify it.
- **Vague attribution.** "Studies have shown", "experts agree", "it is widely recognized". Cite, or delete.
- **Adjective in place of a number.** "a significant improvement", "substantially faster", "goes a long way", "comes close to" (r1 W3). Give the number.
- **Participial tails.** "..., highlighting the importance of X", "..., underscoring the need for Y", "..., demonstrating its effectiveness". These tack an evaluation onto a factual sentence. Delete the tail, or make it a separate claim with evidence.

### 4.3 Paragraph-level and document-level patterns

- **The summary closer.** A paragraph that ends by restating itself ("Overall, these results highlight the value of decentralized coordination."). End on the last piece of evidence or on its consequence for the next step. Test: delete the last sentence of each paragraph. If nothing is lost, leave it deleted.
- **The slogan opener** (r1 W2). "Autonomy and relays are substitutes, and rovers are not." Open with the finding and its condition instead: "In this layout, one site that never sees Earth accounts for 90% of the lost tonnage."
- **Counted openers** (v3 V1). "Three things matter", "Four checks compare". Keep at most three in a paper. Elsewhere start with the first item.
- **Verdict one-liners** (v3 V2). "Distance is what costs." "The reason is structural." Fold them into the sentence that carries the evidence.
- **Signposting.** "In this section, we ...", "As discussed above", "The remainder of this paper is organized as follows" (v3 V9). Headings already do this.
- **Symmetric structure.** Every subsection the same length, every list three to five bullets with bold lead-ins, every paragraph four sentences. Let the content set the length. Bulleted lists belong in tables, checklists and contributions, not in arguments.
- **Generic claims** that would fit any paper: "Multi-robot coordination is an important problem with many applications." Replace them with a claim only this paper could make: "NASA's 2026 architecture guide names a lunar logistics marketplace as a goal but does not say what one would do."
- **The Discussion that repeats the Results** with the same intervals (v3 V3). The Discussion interprets. It cites tables instead of re-quoting them.
- **Perfect balance.** Machine text presents "both sides" evenly and resolves nothing. Take a position the data support, and give the condition under which it would be wrong.

### 4.4 Positive techniques

1. **Write from the data file outward.** Draft each Results paragraph with the table open, and quote cells directly. Specific numbers, file names and conditions are the strongest signal of human authorship, because they are expensive to invent.
2. **Say what went wrong and what you changed.** The v3 referee singled these passages out: the pilot that reversed sign, the staging rule changed after the first results, the browser divergence. Each failure needs a date or a commit, a number and a consequence.
3. **Name the actor.** "We ran", "the auction awards", "the safety layer rejects". The first-person plural is standard in engineering journals for things the authors did.
4. **One term per concept.** Keep a glossary file. If it is "the safety layer" in Section 3, it is not "the shield", "the guard" or "the safety monitor" in Section 6.
5. **No project vocabulary in prose** (r1 W4). Scenario keys, code identifiers, MD5 digests and version labels go in tables, the Availability section or the supplement.
6. **Vary sentence length on purpose, but for content.** A short sentence for a result that matters; a long sentence for a condition with several parts. Do not vary length mechanically.
7. **Prefer the concrete example.** One worked example (a single team lift traced through bids, award, safety check and motion) teaches more than a page of description, and reads as written by someone who looked at the trace.
8. **Read the paper aloud**, or have someone outside the project read it. Mark every sentence where the reader's attention drops.
9. **Run a mechanical scan before every internal review.** A suitable starting pattern:

   ```
   grep -noiE "delve|crucial|pivotal|landscape|tapestry|realm|underscore|showcase|leverag|harness|seamless|intricate|multifaceted|holistic|paramount|notably|importantly|furthermore|moreover|additionally|overall,|in summary|it is worth noting|plays a (crucial|vital|key) role|not only|—" paper/<new>/*.html
   ```

   Count ", not " and "which is why" separately, and count paragraph-final sentences that start with "Overall", "Together", "Taken together", "These results" or "This".
   Target: no hits for the vocabulary list, and no more than one or two instances per paper for the structural devices.

### 4.5 Before and after, from our own drafts and reviews

| Before | After | Why |
|---|---|---|
| "Three things about the version-2 engine matter." | "The demand and operations streams are separate, so ..." | counted opener, project label |
| "Distance is what costs." | "The keep-out's measurable cost is driving: in the Phase-3 fleet it adds 41 km a year." (illustrative figure) | verdict one-liner folded into evidence |
| "A little relay coverage goes a long way for throughput." | "Relay coverage of 10% restores 84% of the tonnage lost under direct-to-Earth operation." (illustrative figure) | slogan, vague quantity |
| "The decentralized auction demonstrates robust performance across a wide range of conditions, highlighting its potential for future lunar operations." | "Across the 48 cells, the decentralized auction's p90 urgent delay was within 0.6 h of the centralized optimum (paired, 30 seeds); the largest gap, 2.1 h, came with three of nine links down." (illustrative figures) | vocabulary, participial tail, no numbers |
| "It is important to note that the safety layer may potentially reduce throughput." | "The safety layer cut delivered tonnage by 1.3% (95% CI 0.9 to 1.7%)." (illustrative figure) | stacked hedge, metadiscourse |
| "We are explicit about what we do not claim." | "We do not predict plume ejecta trajectories." | metadiscourse (v3 V5) |
| "That looked like a bug, and it is not." | "The 6 h gap is the return drive." | reveal device (v3 V4) |

The numbers in the "after" column of rows 2–5 are placeholders that show the form. They are not results.

---

## 5. Section-by-section template for a 25–40 page simulation paper

Assumptions: single-column preprint, 11 pt, about 450 words per page of plain text, and about 350 words per page once figures and tables are mixed in. That gives 9,000–13,000 words of main text, 8–12 figures, 6–10 tables, 60–120 references, and appendices. For T-RO, compress to 12 two-column pages (about 9,000 words including figure equivalents) or accept page charges up to 20. For JSR, stay within about 10,000–12,000 word equivalents.

| Section | Words | Pages | Contents | Do not |
|---|---|---|---|---|
| Title | ≤ 12–15 | | The central contribution as a claim or a question, with no acronyms (AIAA) | use a colon plus a buzzword subtitle |
| Abstract | 150–250 (≤ 200 for T-RO and AIAA) | | Context (1 sentence), gap (1), approach (2), 3–4 results with one number each, implication (1) | carry more than about 8 numbers (r1 W1), cite, use acronyms |
| Highlights (Elsevier) | 3–5 × ≤ 85 characters | | One finding each, with a number | repeat the title |
| 1 Introduction | 900–1,400 | 2–3 | The problem and its stakes, with NASA's numbers and dates; what is known; the gap in one sentence a referee can quote; what we did; the main findings in one paragraph with conditions; 3–4 contributions | add a roadmap paragraph, flag every number, open with a generic claim |
| 2 Background and related work | 1,200–2,000 | 3–4 | Grouped by tradition: multi-robot task allocation (Gerkey and Matarić 2004 taxonomy; auctions and CBBA); safe multi-agent motion (control barrier functions, shielding, reservation-based traffic management); lunar surface operations and communications; learned coordination. Each group ends with what it lacks for our question. A feature-by-work comparison table. | review works that are not compared |
| 3 Model | 3,000–4,500 | 7–10 | ODD skeleton: purpose and patterns; entities and scales; scheduling; relevant design concepts; initialization and inputs; one subsection per submodel. Parameter table with flags (full table in an appendix). One worked example traced through the system. Formal statements of the safety rules and auction properties, with proofs or proof sketches (full proofs in an appendix). | narrate development history in the body |
| 4 Verification and validation | 1,200–2,000 | 3–5 | Approach in Sargent's terms; summary table (check, reference, tolerance, result); the hardest checks in prose; what cannot be validated and why; cross-implementation agreement; credibility statement in the 7009A or V&V 40 sense | claim validation from checks that reproduce calibration data |
| 5 Experimental design and analysis | 900–1,500 | 2–3 | Research questions and preregistered hypotheses; factors and levels table; replication rule; CRN and stream design; warm-up and horizon; primary and secondary metrics; statistical procedures; multiplicity plan; compute and run times | hide choices made after seeing results (state them, as v3 C9 asked) |
| 6 Results | 3,000–4,500 | 7–10 | One subsection per research question. Each opens with the answer and its condition, then the evidence (figure or table), then the boundary of the claim. Negative results get their own short subsection. | open with "Figure 5 shows"; repeat numbers between text and tables except the headline |
| 7 Discussion | 1,000–1,800 | 2–4 | Mechanisms (why the result happens, tested where possible); what it means for an operator, an agency or a standards body; comparison with prior published numbers; what did not help, and why | re-quote Section 6's intervals (v3 V3), open paragraphs with slogans |
| 8 Limitations | 500–900 | 1–2 | Ordered by how much each could change the conclusions; for each, its direction and size where known; choices made after seeing data | list generic limitations ("more data needed") |
| 9 Conclusions | 200–400 | 0.5 | What follows for decisions; one or two next steps tied to the limitations | introduce new numbers, re-summarize every result |
| Availability | 100–250 | | Repository, tag, DOI, data, seeds, the command that reproduces each table, the browser verification page | leave placeholders (v3 S3) |
| AI-use and author contributions | 50–150 | | As the venue requires | |
| References | 60–120 entries | 4–6 | Primary sources; NTRS numbers for NASA reports; DOIs | cite secondary summaries of NASA documents |
| Appendices | as needed | 5–10 | Full ODD; parameter table with flags; full V&V table; STRESS-DES table; proofs; extra results; items the research could not verify | put a result needed for a main claim only in an appendix |

### 5.1 Paragraph template (C-C-C)

1. **Context:** one sentence linking to the previous paragraph, using old information in topic position.
2. **Content:** the claim, then the evidence with numbers and the figure or table reference, then the condition or boundary.
3. **Conclusion:** the consequence for the next step of the argument. Not a recap.

### 5.2 Results subsection template

> **6.k Does decentralized bidding lose anything against a central optimizer when links are perfect?**
> Answer sentence with the effect and interval and its condition. → Figure/table reference with what to look at in it. → The cell where the effect is largest and smallest, and why (mechanism, with a test if one was run). → Boundary: what this does not show. → A link to the next question.

### 5.3 Figure and table rules

- Every figure has a caption that says what is plotted, the units, n, what the error bars are (paired 95% CI, bootstrap, ±SE), and the one thing to see.
- Error bars on log axes come from log-scale intervals (r1 W11).
- Show paired differences when the claim is a difference.
- Every figure file exists, and every caption matches its panels (v3 S1–S2). Check this in the build script.
- Tables give units in headers and the same precision throughout. Numbers come from the values file, never typed by hand.

---

## 6. Referee checklist

Use it for internal review before submission. Each item is yes or no. Note the section and line for every "no". Severity follows our earlier reviews: **M** (must fix), **S** (should fix), **C** (could fix).

### A. Contribution and claims

1. [M] One central contribution, stated in the title and in one quotable sentence in the Introduction.
2. [M] Every claim in the Abstract appears in the Results with the same number, interval and condition.
3. [M] No claim goes beyond the range of the data: no slopes at u = 0 when u spans 0.02–0.08, and no "never" or "always" beyond the cells run.
4. [M] Results that follow directly from the model's rules are presented as properties of the model, not as findings (v3 C1).
5. [S] Generalizations from one class, one expert or one site are qualified.
6. [S] Negative results and design choices made after seeing results are reported in the text and in Limitations.

### B. Model description

7. [M] ODD elements are all present (body plus appendix). Every state variable has a unit.
8. [M] Every parameter has a value, unit, provenance flag and source. Assumed parameters that drive results are swept.
9. [M] The auction, CBBA variant, safety rules and learned-policy architecture are specified well enough to reimplement: pseudocode or equations, tie-breaking and message formats.
10. [M] Formal claims (safety invariance, convergence bound, optimality ratio) state their assumptions: synchronous rounds, static connected network, diminishing marginal gain. The text says what happens when the assumptions fail.
11. [S] One worked example traces an event through the system.
12. [S] Learned components: training data, held-out split, teacher, training budget and failures are all reported.

### C. Verification and validation

13. [M] Each check names its reference, tolerance, result and Sargent technique. The full table is in an appendix.
14. [M] Checks that reproduce calibration data are labelled as calibration, not validation (Kleijnen 1995).
15. [M] Stochastic checks report n and their interval.
16. [M] The safety claim reports exposure and an upper bound (rule of three, or exact), with the independence unit stated.
17. [S] Cross-implementation agreement (Python and browser) is reported, including divergences.
18. [S] There is a credibility statement covering what the model is and is not fit for (7009A or V&V 40 terms).
19. [S] The regression identity holds: new code with the new features off reproduces the previous paper's digests.

### D. Experimental design and statistics

20. [M] Hypotheses, primary metrics and primary comparisons are preregistered (file, date, commit), or the paper says they were not.
21. [M] The replication rule, warm-up, horizon and seeds are stated. The CRN design is stated and its effect reported.
22. [M] Effects are paired differences or ratios with 95% CIs. "No difference" claims use equivalence tests with stated margins.
23. [M] Multiplicity is handled for the primary family, and secondary intervals are labelled unadjusted.
24. [M] Censored delays are handled, or the completion share is shown beside them.
25. [S] Heavy-tailed metrics use log-ratios or rank tests. Medians are given.
26. [S] Blocks (calendar years, sites) are analysed as blocks.
27. [S] Bootstrap uses at least 2,000 resamples, with no silent drops.
28. [S] Sensitivity of the headline results to the top Assumed parameters is shown.

### E. Results, figures and tables

29. [M] Every number in the text matches the released tables at the printed precision.
30. [M] Every figure file exists, and captions match panels. No placeholders (DOI, "TBD") remain.
31. [S] Each Results subsection opens with its answer and condition.
32. [S] Error bars are defined. Log-axis bars come from log-scale intervals.
33. [S] Paired-difference panels are shown where the claim is a difference.
34. [C] Figures are readable in greyscale, and colours are distinguishable for colour-blind readers.

### F. Writing

35. [M] No project code words, scenario keys or version labels in the prose.
36. [M] All terms are defined at first use for both audiences: operations research and planetary operations (r1 W9–W10).
37. [S] No hits on the vocabulary scan in Section 4.9. At most one or two of each structural device (counted openers, ", not ", verdict one-liners, summary closers).
38. [S] The Discussion does not repeat the Results' intervals.
39. [S] No roadmap paragraph and no promissory sentences ("in preparation").
40. [S] The Abstract is within the venue limit and carries about 8 numbers or fewer.
41. [C] Sentences over 40 words are split unless the content needs the length.

### G. Reproducibility and compliance

42. [M] Repository tag, DOI, licence, seeds, and a command per table and figure are given.
43. [M] The STRESS-DES table is filled in.
44. [M] AI-use disclosure is made as the venue requires.
45. [S] The paper meets the venue's length, abstract, keyword, highlight and title rules.
46. [S] Run times and memory are reported (STRESS 5.4).

---

## Sources

Writing:
- G. D. Gopen and J. A. Swan, "The Science of Scientific Writing", American Scientist 78(6):550–558, 1990.
- B. Mensh and K. Kording, "Ten simple rules for structuring papers", PLOS Computational Biology 13(9):e1005619, 2017.
- G. M. Whitesides, "Whitesides' Group: Writing a Paper", Advanced Materials 16(15):1375–1377, 2004.
- W. Strunk Jr. and E. B. White, *The Elements of Style*, 4th ed., Longman, 2000.
- S. Pinker, *The Sense of Style*, Viking, 2014.

Simulation reporting:
- V. Grimm et al., ODD protocol: Ecological Modelling 198:115–126 (2006); 221:2760–2768 (2010); JASSS 23(2):7 (2020).
- V. Grimm et al., TRACE: Ecological Modelling 280:129–139, 2014.
- T. Monks et al., STRESS guidelines, Journal of Simulation 13(1):55–67, 2019.
- A. M. Law, *Simulation Modeling and Analysis*, 5th ed., McGraw-Hill, 2015.
- R. G. Sargent, Journal of Simulation 7(1):12–24, 2013.
- O. Balci, in J. Banks (ed.), *Handbook of Simulation*, Wiley, 1998, ch. 10.
- J. P. C. Kleijnen, EJOR 82(1):145–162, 1995.
- W. L. Oberkampf and C. J. Roy, *Verification and Validation in Scientific Computing*, Cambridge University Press, 2010.
- NASA-STD-7009A (2016), NTRS 20160011121, and NASA-HDBK-7009A.
- ASME V&V 40-2018.

Statistics:
- R. L. Wasserstein and N. A. Lazar, The American Statistician 70(2):129–133, 2016.
- B. A. Nosek et al., PNAS 115(11):2600–2606, 2018.
- D. J. Schuirmann, J. Pharmacokinetics and Biopharmaceutics 15(6):657–680, 1987.
- D. Lakens, Social Psychological and Personality Science 8(4):355–362, 2017.
- J. A. Hanley and A. Lippman-Hand, JAMA 249(13):1743–1745, 1983.

Venues:
- [T-RO Information for Authors](https://www.ieee-ras.org/publications/t-ro/t-ro-information-for-authors/)
- [AIAA Journal Author pages](https://aiaa.org/publications/journals/journal-author/)
- [AIAA page limits and word count guidelines (2024)](https://aiaa.org/wp-content/uploads/2024/12/journalpagelimitsandwordcountguidelines_Sept_2024.pdf)
- Elsevier's Acta Astronautica guide for authors (not retrievable here; confirm limits directly).

Internal: `paper/v3/REVIEW_round1.md`, `paper/v3/REVIEW_round2.md`, `paper/r1/REVIEW_round1.md`, `paper/r1/REVIEW_round2_internal.md`.

## 7. Owner's sources (28 Oct 2026): the IMRaD checklist as journals apply it
From four posts the owner sent (TheRealPublishing channel, drawing on Justin Paul 2024, "Publishing in premier
journals with high impact factor and Q1 journals: Dos and Don'ts", Int. J. Consumer Studies 48(3): e13049,
doi:10.1111/ijcs.13049). Where they differ from §5, these are the stricter rule and win.
- **Title**: at most 20 words, specific, matches the result; write or re-check it last.
- **Abstract**: 250-300 words (journal-dependent; never under 200). Four parts in order: purpose; how it was done
  and with what methods; the results and how important they are; what they may change. The abstract is what
  decides whether anyone reads on.
- **Keywords**: 4-6 precise field terms (some journals allow up to 12). Not a list of everything in the paper.
- **Introduction** must answer, in one place, "what is new here compared with earlier work?". A paper is refused
  when that answer is missing, when the aim is vague, or when the title is too long or too narrow.
- **Methodology** justifies the choices (why this method, this sample size, this data source), not only describes
  them, and runs the checks the design needs (for us: V&V, CRN, pre-registration, seed hygiene).
- **Results** are reported in a fixed order: design recap, primary outcome, secondary outcomes, sensitivity; they
  must actually support the conclusions drawn (a frequent refusal reason).
- **Discussion** is a separate section and does not repeat Results. It compares with earlier studies and states:
  theoretical contribution; practical significance; limitations; future work.
- **Conclusion** is a separate section: purpose, method, main results, significance, in 150-250 words.
- **References**: numbered; at least 15; aim for most from the last five years (the post says 80 %; our field's
  foundations are older, so report the share honestly rather than pad); keep self-citation low and cite the
  journal's own recent papers where relevant.
- **Editing**: short sentences; several passes; a reader outside the project before submission; check for
  plagiarism and disclose AI assistance where the journal requires it (most now do).
- **Reviews**: answer every point separately, show each change, never argue without evidence.
- **Journal fit**: a good paper sent to the wrong journal is refused at the desk; read Aims & Scope.
- **Missing data** (their post is about surveys): state how much is missing, why, and how it was handled; never
  fill blanks with zero or the mean without a reason. Our analogue is censoring: undelivered items are not
  "zero wait"; report censored means and delivered-only means separately and say which is which.
- Their tool list (AnswerThis, Paperpal, Overleaf, Zotero, ...) is optional for us: our build scripts do the number
  checks, and the HTML-to-PDF pipeline replaces LaTeX. Their warning holds: no citation, DOI or statistic from
  an AI tool enters a paper unverified against the source.
