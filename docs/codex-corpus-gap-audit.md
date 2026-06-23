# CaptureOS Corpus Gap Audit — Knowledge-Driven Cross-Check

Date: 2026-06-22

Method note: This review is primarily knowledge-driven. I only spot-checked specific identifiers that were plausibly stale or easy to misstate. Where a claim could have drifted and I did not fully re-verify it live, I mark it as `verify current eCFR` or `verify current tax-year guidance`.

## Validation of Recommended Targets

The original audit is directionally strong, but it mixes three different things: valid CFR targets, stale identifier claims, and priorities that do not match a small-business-first "get money" MVP.

Confirmed valid targets from knowledge:

- `48 CFR Parts 2, 4, 9, 12, 13, 15, 19, 25, 52` remain sensible FAR-layer collection for small-business contracting.
- `2 CFR Parts 25, 170, 180, 200` remain sensible grants-layer collection.
- `13 CFR Parts 120, 121, 123, 124, 125, 126, 127` remain sensible SBA program and set-aside collection.
- `32 CFR Part 170` is the correct standalone CMMC program rule.
- `48 CFR Part 204` and `48 CFR Part 252` are still the right DFARS parts to pair with CMMC/cyber obligations.
- `29 CFR Parts 4 and 5`, and `41 CFR Parts 60-1 and 60-2`, are valid labor/EEO targets, though they are not the next best "get money" additions.

Spot-checked corrections:

- `48:240` is stale/wrong as a current eCFR target. In the current June 2026 eCFR chapter listing for DFARS, Chapter 2 still shows `48 CFR Part 204` with `Subpart 204.75 Cybersecurity Maturity Model Certification`, and the chapter index does not show a live `Part 240`. Do not carry forward `48:240` without a separate point-in-time verification.
- The original audit's implication that CMMC moved out of DFARS Part 204 should not be accepted as current. The current split is: `32 CFR Part 170` for the DoD CMMC program rule, plus `48 CFR Part 204` for DFARS implementation/prescriptions, plus `48 CFR Part 252` for clause text.
- `2 CFR Part 182 = Governmentwide Requirements for Drug-Free Workplace (Financial Assistance)` is correct. Treat any reference to `2 CFR Part 183` as a different topic, not drug-free workplace.
- The user prompt's example `26 CFR § 1.45S` for WOTC is wrong. `IRC § 45S` is the employer credit for paid family and medical leave, not the Work Opportunity Tax Credit.

Important omission from the original audit:

- There is no standalone eCFR part titled "SBIR" or "STTR" that fills the main SBIR/STTR gap. The controlling materials are mostly outside the CFR: the `Small Business Act, 15 U.S.C. § 638`, the current SBA `SBIR/STTR Policy Directive` PDF, and agency solicitation/program materials.
- `13 CFR Part 121`, which you already have, is the main SBA regulatory hook for SBIR/STTR size eligibility. If you later need appeals workflow depth, `13 CFR Part 134` is the next SBA procedural layer, but that is not a first-pass corpus gap for MVP.

Priority correction:

- The original audit overweights labor compliance and DoD cyber relative to the stated product value proposition. For a small-business-first MVP built around "find and access government money and advantages," the biggest remaining authoritative gaps are `SBIR/STTR` and `targeted tax-credit materials`, not `29 CFR 4/5` or the broader `41 CFR 60` family.

## GET-MONEY Pillar: SBIR/STTR Sources

Authoritative sources to collect now:

- `Small Business Act, 15 U.S.C. § 638`.
  - This is the statutory home of both SBIR and STTR.
  - Confirmed from SBA's SBIR policy page summary.
- `SBIR and STTR Extension Act of 2022`.
  - This is the current reauthorization reference you should anchor to, not older reauthorization summaries.
  - Use it as statutory context, not as the day-to-day operating document.
- `SBA SBIR/STTR Policy Directive` PDF.
  - This is the single most important missing SBIR/STTR artifact.
  - SBA states that it issues one combined directive for both programs and that participating agencies must align their program rules and procedures to it.
  - This is where you get the operative rules for eligibility, phase structure, proposal requirements, award process, data rights, agency reporting, and SBA oversight.
- `SBIR.gov` policy/tutorial/program pages.
  - These are not a substitute for the directive, but they are high-value operational support material for a small business user.
  - The policy landing page is especially useful as a directive index and metadata wrapper.
  - The tutorials and agency-participation pages are useful for retrieval against user questions like "who participates," "what is a Phase I vs Phase II," and "what are current award thresholds."
- Participating-agency solicitation and topic pages.
  - NIH/CDC, NSF, DoD, DOE, NASA, USDA, DOC/NOAA, DHS, DOT, EPA, ED, and HHS program-specific pages matter operationally.
  - These should generally be treated as live or semi-live sources, not static corpus anchors, because topics, deadlines, and application instructions roll over frequently.

What the current corpus already covers for SBIR/STTR:

- `13 CFR Part 121` already gives you the main SBA size-regulation layer.
- That means the missing SBIR/STTR gap is not "find the right CFR part," but "add the non-CFR policy and program authority that users actually need."

Are there eCFR parts for SBIR/STTR?

- No standalone, high-value eCFR part named for SBIR or STTR was confirmed.
- The practical answer is:
  - `13 CFR Part 121` is the existing size/eligibility anchor already in corpus.
  - `13 CFR Part 134` is a possible later add for SBA Office of Hearings and Appeals procedures if you want size/status appeal depth.
  - The real missing authority is the SBA directive PDF, not another CFR title/part.

One caution:

- The current SBIR.gov policy page still contains stale prose about authorization through September 30, 2022. Use the page because it points to the directive PDF and reflects SBA program administration, but use the `SBIR and STTR Extension Act of 2022` as the reauthorization reference rather than relying on that embedded date language.

## GET-MONEY Pillar: Tax Credit Sources

Title 26 should be collected in a targeted way, not bulk-ingested.

Why bulk ingestion of all of Title 26 would be counterproductive:

- `26 CFR Part 1` alone is enormous and only a tiny fraction is relevant to small-business "find money / claim credit" use cases.
- Tax retrieval quality degrades if you dump general income-tax regulations into the same semantic space as a few narrow credit regimes.
- Tax credits are unusually form-driven and tax-year-sensitive. For many user questions, the operative source is a small cluster of regulations plus the current IRS forms/instructions, not the whole title.
- A broad Title 26 ingest would add far more irrelevant noise than useful signal.

Target these specific Title 26 materials first:

1. Research Credit / R&D Credit

- `26 CFR §§ 1.41-0 through 1.41-9`.
  - These are the core research credit regulations and are the highest-value Title 26 addition for a small-business-first MVP.
  - They cover the definitions and computational framework users actually need when asking whether they may qualify.
- `26 CFR § 1.280C-4`.
  - Important adjacency because the research credit interacts with deduction disallowance/election mechanics.
- Operational IRS materials to pair with the CFR:
  - `Form 6765, Credit for Increasing Research Activities` (`verify current tax-year revision`)
  - `Form 8974, Qualified Small Business Payroll Tax Credit for Increasing Research Activities` (`verify current tax-year revision`)
  - `Form 3800, General Business Credit` (`verify current tax-year revision`)
- Product judgment:
  - This is the strongest tax-credit fit for the stated product scope because it is material for startups and technology-oriented small businesses, and it can be tied directly to innovation spend.

2. Work Opportunity Tax Credit

- `IRC § 51` is the controlling statute.
- The current eCFR spot-check surfaced `26 CFR § 1.51-1`, but not a deep modern regulation cluster comparable to the § 1.41 series.
- That means WOTC should be treated as a statute-plus-forms workflow more than a CFR-heavy workflow.
- Operational materials to pair with the statute/reg text:
  - `Form 5884, Work Opportunity Credit` (`verify current tax-year revision`)
  - `Form 3800, General Business Credit` (`verify current tax-year revision`)
  - `Form 8850, Pre-Screening Notice and Certification Request for the Work Opportunity Credit` (`verify current tax-year revision`)
  - `ETA Form 9061` and `ETA Form 9062` (`verify current revision`)
- Explicit correction:
  - Do not model WOTC as `§ 1.45S`. That identifier is for a different credit.

3. FICA Tip Credit

- The controlling statute is `IRC § 45B`.
- This is useful for hospitality and restaurant small businesses, but it is narrower than the research credit and WOTC.
- The operational layer matters more than a broad CFR ingest:
  - `Form 8846, Credit for Employer Social Security and Medicare Taxes Paid on Certain Employee Tips` (`verify current tax-year revision`)
  - `Form 3800, General Business Credit` (`verify current tax-year revision`)
- Current spot-check note:
  - I did not confirm a rich standalone CFR cluster for § 45B in current eCFR. Treat this as a form/guidance-led collection item rather than a CFR-first one.

4. Energy Credits

- Defer these for MVP unless you already know you are serving clean-energy installers, manufacturers, or building owners.
- If you do pursue them later, do not ingest "§ 1.48" generically. Target precise current regulations such as:
  - `26 CFR § 1.48-9`
  - `26 CFR § 1.48-13`
  - `26 CFR § 1.48-14`
  - `26 CFR § 1.48E-1` (`verify current eCFR`)
- Reason to defer:
  - These credits are sector-specific, fact-intensive, and often depend on technical/property attributes that are far less universal than R&D credit or WOTC.

Recommended Title 26 collection decision:

- `NOW`: `26 CFR §§ 1.41-0 through 1.41-9`, `26 CFR § 1.280C-4`, `26 CFR § 1.51-1`, plus the current IRS forms/instructions named above.
- `DEFER`: broader energy-credit clusters and any bulk Title 26 ingestion.

## Capability Gaps Confirmed

`PDF-download adapter` is a genuine need.

What it unlocks immediately:

- `SBA SBIR/STTR Policy Directive` PDF.
- `NIST SP 800-171 Rev. 2` and `NIST SP 800-171 Rev. 3`.
- `NIST SP 800-171A` assessment publication set.
- IRS forms and instructions for `Form 6765`, `Form 8974`, `Form 5884`, `Form 8846`, `Form 3800`, and `Form 8850`.
- DOL WOTC forms such as `ETA 9061` and `ETA 9062`.

Why HTML-only scrape is insufficient:

- The controlling text for SBIR/STTR is the directive PDF, not just the surrounding web page.
- NIST publication content is published as formal publication artifacts with stable identifiers and PDF/HTML versions outside the CFR/FR model.
- Tax-credit claiming is heavily form-driven. A small business user often needs the form/instruction pair as much as the regulation text.

`NIST/publication authority` is also a genuine need.

Why a new authority class matters:

- `NIST SP 800-171` and `800-171A` are authoritative but non-regulatory publications.
- SBA directives and IRS/DOL forms are also authoritative but do not fit cleanly into `ecfr` or `federal_register`.
- Giving them a dedicated authority bucket improves provenance, ranking, and user trust because the system can distinguish "binding regulation," "agency directive," and "official form/publication."

CMMC-specific conclusion:

- If you intend to answer CMMC questions, `32 CFR Part 170` + `48 CFR Part 204` + `48 CFR Part 252` are necessary but not sufficient.
- The real implementation detail lives in:
  - `NIST SP 800-171 Rev. 2`
  - `NIST SP 800-171 Rev. 3`
  - `NIST SP 800-171A` assessment material
- NIST confirms `SP 800-171 Rev. 3` and `SP 800-171A Rev. 3` were published in May 2024, and `SP 800-171 Rev. 3` supersedes `Rev. 2`.
- For a defense-supplier workflow, the NIST publication layer materially changes answer quality; without it, you can cite clauses but not explain control-by-control compliance.

Small-business-first MVP implication:

- The PDF adapter is not just for CMMC. It is also the enabler for the highest-value missing "money" artifacts: the SBA directive and IRS/DOL tax-credit forms.

## MVP Prioritization (NOW vs DEFER)

NOW

- `SBA SBIR/STTR Policy Directive` PDF.
- `SBIR.gov` policy/tutorial/participating-agency pages.
- Targeted `Title 26` tax-credit layer:
  - `26 CFR §§ 1.41-0 through 1.41-9`
  - `26 CFR § 1.280C-4`
  - `26 CFR § 1.51-1`
  - current IRS forms/instructions for `6765`, `8974`, `5884`, `3800`, `8850`
  - DOL `ETA 9061/9062`
- `PDF-download adapter`.
- A generic `publication` authority class, with SBA/NIST/IRS/DOL official publications as first-class corpus objects.

DEFER

- Broad labor/EEO expansion beyond what is already collected:
  - `29 CFR Parts 4 and 5`
  - `41 CFR Part 60` family
- Broad CMMC/DoD cyber package unless defense suppliers are an immediate design-partner segment:
  - `32 CFR Part 170`
  - `48 CFR Part 204`
  - `48 CFR Part 252`
  - `NIST SP 800-171/171A`
- Agency-specific grants overlays such as EDGAR/HHS agency adoption layers.
- Energy-credit regulation clusters in Title 26.
- Bulk Title 26 ingestion of any kind.

Reason for this split:

- The corpus already covers the core federal contracts, grants, SBA loans, set-aside, and FAR-small-business substrate.
- The biggest remaining user-visible "money" gaps are:
  - research commercialization funding via `SBIR/STTR`
  - tax-advantage workflows via targeted credits
- Everything else above is valid, but less aligned to the MVP promise.

## Single Highest-Priority Next Collection

Collect the current `SBA SBIR/STTR Policy Directive` PDF next.

Why this is the single highest-priority next collection:

- It fills the largest remaining "get money" authority gap with one compact artifact.
- It is authoritative for both `SBIR` and `STTR`.
- It directly supports eligibility, proposal, phase, award, and commercialization questions that small businesses actually ask.
- It is more valuable to the stated MVP than another labor/compliance CFR part.
- It also forces the right platform improvement: a PDF-capable collection path for future SBA, NIST, IRS, and DOL documents.
