# CaptureOS: Self-Hosted Open-Source Models vs Frontier APIs

**Break-even (24/7 self-hosting vs Claude Haiku 4.5, midpoint filing size): about 18,400 filings/month on a single RunPod L4.**

**Headline recommendation:** Do not replace frontier models across CaptureOS by default. Use open-source locally for document parsing/OCR and possibly narrow extraction helpers, but keep high-stakes compliance reasoning on Claude Sonnet/Opus unless a client explicitly requires isolated deployment or your volume is already in the tens of thousands of filings per month.

**Single biggest premature risk:** You would take on infra and quality-regression risk before you have the workload volume to justify it, in a product where one missed requirement can erase far more value than the token savings.

## 1. COST MODEL

### Repo-grounded starting point

The current code already has the right abstraction seams for this decision:

- `apps/api/captureos/providers/llm.py` selects Gemini, Anthropic, or Mock behind one `LLMProvider`.
- `apps/api/captureos/providers/docparse.py` is a separate seam for parsing, but the local parser today is only `pypdf` / `python-docx` text extraction. It does not do OCR, layout parsing, or table extraction.
- `apps/api/captureos/agents/requirements.py`, `matching.py`, `narrative.py`, `recommendation.py`, `company_brain.py`, `opportunity.py`, and `grant.py` are all currently `ModelTier.pro`.
- Only `apps/api/captureos/agents/calendar.py` is currently `ModelTier.flash`.

That matters because the real immediate cost lever is not "replace all frontier APIs." It is "move the right work to the right seam."

### Assumptions used for break-even

- Filing size estimate: 8 to 15 pages.
- Input tokens per filing: 6,000 to 10,000.
- Output tokens per filing: 1,000 to 2,000.
- Midpoint filing used for primary break-even number: 8,000 input + 1,500 output.
- 24/7 GPU uptime assumption: 730 hours/month.
- Break-even table below uses GPU rental only, which is favorable to self-hosting. Real all-in cost is higher once you add storage, monitoring, networking, incident time, and on-call burden.

### Current API pricing used

- Claude Haiku 4.5: $1 / 1M input tokens, $5 / 1M output tokens.
- Claude Sonnet 4.6: $3 / 1M input tokens, $15 / 1M output tokens.
- Claude Opus 4.8: $5 / 1M input tokens, $25 / 1M output tokens.
- Gemini 2.0 Flash: $0.10 / 1M input tokens, $0.40 / 1M output tokens.

Important correction: Gemini 2.0 Flash is not a live strategic option anymore. Google's pricing page says it was shut down on **June 1, 2026**. It is valid as a historical cost reference only, not as a new deployment target.

### Per-filing API cost estimate

| Model | Low filing | Mid filing | High filing |
| --- | ---: | ---: | ---: |
| Claude Haiku 4.5 | $0.0110 | $0.0155 | $0.0200 |
| Claude Sonnet 4.6 | $0.0330 | $0.0465 | $0.0600 |
| Claude Opus 4.8 | $0.0550 | $0.0775 | $0.1000 |
| Gemini 2.0 Flash | $0.0010 | $0.0014 | $0.0018 |

### GPU rental cost table

| GPU class | Market example | Hourly | $/mo @ 24/7 | Break-even filings/mo vs Haiku 4.5 (midpoint filing) |
| --- | --- | ---: | ---: | ---: |
| L4 24 GB | RunPod | $0.39/hr | $284.70 | 18,368 |
| A10 24 GB | Lambda | $1.29/hr | $941.70 | 60,755 |
| A100 80 GB | RunPod PCIe | $1.39/hr | $1,014.70 | 65,465 |
| A100 40 GB | Lambda PCIe | $1.99/hr | $1,452.70 | 93,723 |
| H100 80 GB | RunPod PCIe | $2.89/hr | $2,109.70 | 136,110 |
| H100 80 GB | Lambda PCIe | $3.29/hr | $2,401.70 | 154,948 |

### Break-even range vs Haiku 4.5

- RunPod L4 breaks even at roughly 14,235 to 25,882 filings/month depending on whether your average filing is "high" or "low" token volume.
- Lambda A10 breaks even at roughly 47,085 to 85,609 filings/month.
- A100/H100 class hardware only makes economic sense if you are at much larger monthly volume or you have a quality/security reason that dominates cost.

### Direct answer to "is near 0 cost true?"

No. That claim is overstated.

- Best-case 24/7 self-host cost is not near zero; it is roughly $285/month on the cheapest viable single-GPU setup before ops overhead.
- If you need a larger model that actually competes with Sonnet-class reasoning, you are no longer in the "$285/month" world. You are in the $1,000 to $2,400+/month world just for the GPU.
- If you use RunPod or Lambda, the documents are not "in-house." They are on third-party infrastructure. You reduce dependence on Anthropic or Google, but you do not eliminate third-party exposure.
- At CaptureOS's likely early volume, per-call Haiku is usually cheaper than keeping even one GPU warm all month.

### Scale threshold: when each wins

- Under about **18k filings/month**, frontier API usage is usually cheaper than a 24/7 RunPod L4 even before counting self-hosting labor.
- Roughly **18k to 60k filings/month**, a single cheap GPU can beat Haiku on raw inference spend for narrow extraction work, but only if the task quality is acceptable and uptime utilization is real.
- Above **60k filings/month**, self-hosting narrow extraction models starts to look economically credible on more than one vendor/hardware choice.
- For Sonnet/Opus-class reasoning, the economic case for self-hosting is weaker than the founder is assuming, because the local model that narrows the quality gap usually requires A100/H100-class infrastructure and still tends to underperform frontier reasoning.

## 2. TASK SEGMENTATION

The founder is directionally right about one thing and wrong about another:

- Right: open-source can be very strong for document extraction.
- Wrong: that does not imply open-source is the right default for compliance reasoning and narrative generation.

### A. DOCUMENT EXTRACTION

This bucket includes OCR, layout parsing, form region detection, table extraction, and PDF-to-structured-text conversion.

The current local docparse path in CaptureOS is materially weaker than what open-source document stacks can do, because it is plain text extraction only. That is the seam with the highest immediate ROI.

#### Candidate tools

- `Surya`: strong OCR/layout/table stack; repo claims 650M params, 90+ languages, layout analysis, reading order, and table recognition. Good fit for a new local `DOCPARSE_PROVIDER`.
- `docTR`: solid OCR library with a KIE pipeline and lighter operational footprint; useful if you want a Python-native stack with simpler integration.
- `PaddleOCR`: broad language support, structured extraction tooling, strong community adoption, good fit for scanned PDFs and forms.
- Small doc-VLMs such as `Qwen2-VL-7B` and `GOT-OCR2_0`: useful for messy visual understanding and format reconstruction, but they are slower, harder to evaluate, and less deterministic than classical OCR/layout pipelines.

#### Cost, latency, quality trade-offs

- Deterministic parse for born-digital PDFs: cheapest and fastest. Often no LLM needed at all.
- OCR/layout stacks like Surya or PaddleOCR: usually the best cost/quality choice for scanned documents and forms. They are cheaper than frontier LLMs and can beat naive cloud OCR on certain document types once tuned.
- Small doc-VLMs: better when the document is visually complex and rule-based extraction fails, but slower and less predictable than OCR + rules.

Estimated latency bands for an 8 to 15 page document:

- Born-digital PDF text extraction: sub-second to a few seconds.
- OCR/layout stack on L4/A10: low single digits to low tens of seconds, depending on scan quality and tables.
- 7B doc-VLM pass: often tens of seconds once you include image preprocessing and generation.

#### Is open-source genuinely better here?

Yes, for this seam, often yes.

- It is clearly better than CaptureOS's current local parser.
- It can be cost-effective and privacy-friendly.
- It is more controllable for field extraction and client-specific rules.

But there are two caveats:

- Open-source OCR is not automatically better than managed document AI on ugly scans, handwriting, or complex tables. You need evaluation data.
- Surya's code is Apache-2.0, but its model weights have commercial licensing conditions outside startups under certain thresholds. That licensing detail matters before productization.

### B. HIGH-STAKES LLM REASONING

This bucket includes requirement interpretation, bid/no-bid scoring, narrative generation, compliance gap analysis, and "what does this clause actually require?" judgments.

This is where the founder's reasoning is weakest.

#### Why the quality gap matters

In CaptureOS, these tasks are not generic summarization. They are decision support for compliance workflows.

- `RequirementExtractionAgent` affects recall of must-satisfy requirements.
- `EvidenceMappingAgent` affects matched vs partial vs missing classification.
- `FitRecommendationAgent` affects pursue/do-not-pursue outcomes.
- `NarrativeGenerationAgent` produces customer-visible content that must stay citation-grounded.

Human gating reduces final submission risk, but it does not eliminate business risk:

- bad extraction increases analyst review time
- bad mapping creates false confidence
- bad recommendation burns capture effort
- bad narratives erode trust immediately

#### Frontier vs self-hosted reasoning models

- Claude Sonnet/Opus remain stronger on instruction following, conservative reasoning, long-context synthesis, schema reliability, and ambiguity handling.
- Self-hosted models such as Llama-3.1-70B or Mistral Large can be useful, but to get close enough on these tasks you usually need expensive hardware and a rigorous eval harness.
- A single A100/H100 running a 70B model is not a "near-zero-cost" substitute for Sonnet. It is an operationally heavier, quality-riskier system that still usually loses on the hardest reasoning cases.

#### Where self-hosting is a false economy

It is a false economy when:

- the task involves ambiguous policy interpretation
- the cost of one missed mandatory requirement is high
- the output is customer-facing and citation-sensitive
- the real cost driver is human review time, not tokens

For CaptureOS, that means reasoning-heavy agents should stay frontier by default.

### Where open wins vs where frontier wins

| Work type | Open-source/self-hosted wins when | Frontier wins when |
| --- | --- | --- |
| OCR and layout parsing | You need cheap, private, repeatable parsing of PDFs, tables, and forms | The scans are unusually messy, handwriting-heavy, or you want managed SLA over tuning |
| Field extraction from known forms | You have stable schemas, deterministic rules, and client-specific mapping | The form varies heavily and requires semantic interpretation every time |
| Requirement extraction from clean text | The task is narrow, repetitive, and evaluated against a gold set | The text is ambiguous, fragmented, contradictory, or legalistic |
| Evidence matching and compliance reasoning | Rarely; only after strong offline evals prove recall and false-negative rates are acceptable | Default choice, because conservative interpretation matters more than token savings |
| Bid/no-bid and fit recommendations | Usually no; business impact of bad judgment is too high | Yes, especially when ambiguity and sparse evidence are common |
| Narrative generation with citations | Usually no; customer-visible quality and hallucination control dominate | Yes; Sonnet/Opus are materially safer here |

## 3. TIERED ROUTING DESIGN

### What the current seam can and cannot do

CaptureOS can support this with no call-site architecture rewrite, but not literally with zero implementation work.

What works cleanly:

- add a new `LocalLLM` or `RouterLLM` provider in `apps/api/captureos/providers/llm.py`
- add one new `LLMProviderName` enum value
- keep using `get_llm()` and `ModelTier`
- add a new local `DOCPARSE_PROVIDER`

What does not work "for free":

- the current `LLM_PROVIDER` is global
- mixed local-plus-Claude routing requires either a router provider or per-deployment config
- `requirement_extraction` is currently `ModelTier.pro`, so it will not route to a local `flash` backend unless you re-tier that agent or add a third tier

That is not an architecture problem. It is a small implementation and routing-policy problem.

### Recommended routing table

| Task | Provider | ModelTier / Config | Rationale |
| --- | --- | --- | --- |
| Born-digital PDF text extraction | No LLM | `DOCPARSE_PROVIDER=local` or deterministic parser | Cheapest, fastest, and most reliable when text is already embedded in the PDF |
| Scanned PDF OCR + layout + table extraction | Self-hosted docparse | New `DOCPARSE_PROVIDER=surya` or `paddleocr` | This is the strongest open-source win and the cleanest seam in the repo |
| Deterministic PDF field fill / known-form mapping | No LLM | Rule-based form mapper | LLM adds cost and nondeterminism with little upside |
| Requirement extraction from parsed solicitation text | Frontier first, local later | Near-term: Claude `flash`; later: local `flash` only after eval and likely after changing this agent from `pro` to `flash` | Recall matters; this task is narrower than narrative generation but still too risky to move blind |
| Evidence retrieval / candidate narrowing | No LLM or local helper | pgvector + reranker; optional local small model | Most of the value is retrieval and scoring, not generation |
| Evidence mapping (`matched` / `partial` / `missing`) | Frontier | Claude `flash` or `pro` depending evals | False negatives and false positives directly affect compliance decisions |
| Company profile synthesis | Frontier | Claude `pro` | Cross-document synthesis with conservative grounding |
| Opportunity research / fit scoring / grant fit | Frontier | Claude `pro` | Ambiguous reasoning with real business consequences |
| Bid/no-bid recommendation | Frontier | Claude `pro` | High-stakes summary judgment; wrong answer wastes human pursuit time |
| Narrative generation with citations | Frontier | Claude `pro` | Customer-visible output; citation discipline and tone matter |
| Compliance calendar from known certs | No LLM preferred | Deterministic rules; current `flash` agent can be retired later | This logic is already close to rule-based and should not require a model long-term |

### Practical rollout that fits the current codebase

1. Upgrade `DOCPARSE_PROVIDER` first with a local OCR/layout backend.
2. Keep reasoning agents on Anthropic.
3. Add a `RouterLLM` only if you want one deployment to mix local and frontier models.
4. Re-tier only the narrow agents after offline eval proves quality.

## 4. PRIVACY ANALYSIS

The privacy case for self-hosting is real, but the founder is mixing together several different regimes that do not have the same answer.

### Core pushback

- Self-hosting on RunPod or Lambda is not "in-house." It is still third-party cloud.
- Self-hosting does not make you FedRAMP compliant by itself.
- CUI and ITAR do not automatically require self-hosting. They require the right deployment boundary, access controls, contractual terms, and customer authorization path.
- Some contracts really do require no third-party AI. In those cases, self-hosting may be required, but usually inside the client's environment or a dedicated compliant enclave, not on a generic startup GPU vendor.

### Decision matrix

| Data class | Self-host required? | Frontier alternative |
| --- | --- | --- |
| Ordinary commercial proposal data | No | Anthropic API with commercial terms, or Bedrock / Vertex enterprise deployment |
| Sensitive but non-regulated client documents | Usually no | Anthropic commercial terms, ZDR where needed, Bedrock, or Vertex with logging controls |
| CUI | Not automatically, but often requires government-authorized cloud boundary and customer approval | Claude on Bedrock or Vertex in FedRAMP/IL environments, with agency ATO and documented controls |
| ITAR / export-controlled research data | Sometimes; depends on customer boundary and who must control the environment | AWS GovCloud (US) with U.S.-person and export-control controls; potentially Bedrock/partner deployment if contractually approved |
| FedRAMP High / DoD IL5 workloads | Usually not self-host by default; must live in an authorized environment | Anthropic says Claude is available on AWS and Google Cloud with authorizations up to FedRAMP High and IL5 |
| Contract clause explicitly banning third-party AI services | Often yes | None if the clause is absolute; likely requires self-hosting inside customer-controlled infrastructure |
| Client demands tenant-dedicated or on-prem inference | Yes | Frontier API usually fails the policy requirement, even if technically secure |

### Specific implications

#### CUI

For CUI, self-hosting is not automatically required. The real question is whether the workload is deployed in an authorized environment with the right inherited controls, access restrictions, audit trail, and customer acceptance. Bedrock or Vertex in the proper government/compliant boundary can satisfy this better than a startup GPU host.

#### ITAR / export-controlled research

AWS states that if you store and process ITAR-regulated data in AWS GovCloud (US), you must meet U.S.-person, DDTC, and export-control program requirements yourself. That means the cloud can support the compliance posture, but it does not outsource it for you. "We self-hosted on RunPod" is not an ITAR answer.

#### FedRAMP

Anthropic's government page says Claude is available on AWS and Google Cloud with authorizations up to FedRAMP High and IL5. AWS also states GovCloud (US) has a FedRAMP High authorization boundary. So if the client needs FedRAMP, a compliant managed frontier deployment may be the shortest path. A startup-operated vLLM stack on non-authorized GPU hosts does not help here.

#### No-third-party-AI clauses

This is the cleanest case for self-hosting. If the contract says "no third-party AI services" or requires model execution only inside the customer's enclave, frontier APIs may be disallowed regardless of their security posture. In that case, the right answer is premium isolated deployment, not a universal default.

#### Zero-retention and enterprise options

- Anthropic commercial terms say they do not train on customer prompts/code under commercial usage by default, and Anthropic offers zero data retention for qualified accounts. ZDR is not standard and requires enablement.
- Amazon Bedrock states customer content is not used to improve base models and is not shared with model providers.
- Google documents that it will not use customer data to train or fine-tune AI/ML models without permission on Gemini Enterprise Agent Platform, and it documents how to reach zero data retention with specific configuration constraints.

### Privacy recommendation

Yes: fully self-hosted should be a **premium tier**, not the default for everyone.

Reason:

- it solves a real problem for a minority of high-security customers
- it creates substantial cost and ops burden for everyone else
- it is not necessary to satisfy most early-stage commercial or even many government workflows if you use the right enterprise deployment mode

## 5. TIMING

### Engineering cost estimate

#### API-only path

- 0.5 to 1.5 person-weeks to harden prompts, schemas, token budgets, retry behavior, and observability around current API providers.

#### Self-hosted docparse upgrade

- 1 to 3 person-weeks to add a local OCR/layout provider behind `DOCPARSE_PROVIDER`, benchmark it on real client docs, and wire structured outputs into ingestion.

This is the highest-ROI self-hosted investment.

#### Full self-hosted vLLM stack for LLM inference

- 4 to 8 person-weeks for a credible first production deployment if you keep scope narrow.
- 8 to 12+ person-weeks if you include autoscaling, GPU failover, secure networking, model rollout procedures, eval harnesses, prompt/version governance, tenant isolation, and production monitoring.

That estimate is for a serious system, not a demo.

### When it makes financial sense

Self-hosting makes financial sense when at least one of these is true:

- you are consistently above roughly **18k filings/month** and the workload is narrow enough to run on an L4-class box
- you have premium customers willing to pay for isolated deployment
- you are losing deals because of data-boundary objections, not because of product immaturity

It does **not** make financial sense just because API pricing feels psychologically expensive. At low volume, the labor and quality risk dominate the token bill.

### What CaptureOS should do right now

Do now:

1. Keep high-stakes reasoning on Claude.
2. Improve the docparse seam first by adding a serious local OCR/layout provider.
3. Add offline evaluation sets for requirement extraction, evidence mapping, and narrative citation correctness.
4. Add a `RouterLLM` only if you need mixed routing in one deployment.
5. Treat client-specific personalization primarily as retrieval, rules, and templates, not tenant fine-tuning.

Defer to Phase 2+:

1. Self-hosted local LLM for narrow extraction agents.
2. Any 70B-class self-hosted reasoning deployment.
3. Per-client fine-tunes, unless a premium customer is funding them and you already have an eval harness.

### Bottom line on timing

For CaptureOS today, self-hosting is an optimization, not the main product bottleneck.

The repo's current architecture already makes the correct next move obvious: strengthen `DOCPARSE_PROVIDER` now, keep reasoning on frontier models, and reserve fully self-hosted inference for premium security tiers or materially higher volume.

## Sources

1. Anthropic pricing: https://platform.claude.com/docs/en/about-claude/pricing
2. Google Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
3. RunPod pricing: https://www.runpod.io/pricing
4. Lambda pricing: https://lambda.ai/pricing
5. Anthropic data usage: https://code.claude.com/docs/en/data-usage
6. Anthropic zero data retention: https://code.claude.com/docs/en/zero-data-retention
7. Anthropic government availability: https://claude.com/solutions/government
8. AWS GovCloud ITAR guidance: https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-itar.html
9. AWS FedRAMP: https://aws.amazon.com/compliance/fedramp/
10. Amazon Bedrock FAQ: https://aws.amazon.com/bedrock/faqs/
11. Google Cloud FedRAMP: https://cloud.google.com/security/compliance/fedramp
12. Gemini Enterprise Agent Platform zero data retention: https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention
13. Surya repo: https://github.com/datalab-to/surya
14. docTR repo: https://github.com/mindee/doctr
15. PaddleOCR repo: https://github.com/PaddlePaddle/PaddleOCR
16. Qwen2-VL-7B-Instruct: https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct
17. GOT-OCR2_0: https://huggingface.co/stepfun-ai/GOT-OCR2_0
