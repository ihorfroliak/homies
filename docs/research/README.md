# Research — non-normative evidence

| Field | Value |
|---|---|
| Status | **NON-NORMATIVE** — registered in [00-AUTHORITY](../canonical/00-AUTHORITY.md) outside the precedence ladder |
| Decision | D-106 (repository system of record and independent research governance) |
| Doctrine | [07 §5 — independent market evidence doctrine](../canonical/07-PRODUCT-GROWTH-DOCTRINE.md) |
| Documents | none yet. MARKET-001 (residential rental market and workflow) is a separate future research task |

Research documents in this folder are **Homies-authored syntheses**. They may
explain why a decision was taken; they never take it.

## 1. Authority path

```text
RESEARCH / EVIDENCE
        ↓
HOMIES HYPOTHESIS
        ↓
FOUNDER / PRODUCT DECISION
        ↓
D-xxx / CANON / APPROVED TASK CONTRACT
        ↓
IMPLEMENTATION
```

Research never authorises implementation, never overrides canon, a
D-decision or an approved Task Contract, and is not cited by code or a Task
Contract as authority — they cite the decision. A research finding that
suggests new backend or frontend features, payments, insurance, contracts,
identity systems, agency tooling, short-stay functionality or AI features
remains a hypothesis until normal Homies governance adopts it.

## 2. Evidence classes (preferred, in order)

1. law and regulation;
2. public administration;
3. official statistics;
4. public registries and datasets;
5. standards;
6. open-access peer-reviewed academic research;
7. established non-commercial research institutions;
8. Homies first-party empirical evidence (labelled as in
   [METRICS-v1](../growth/METRICS-v1.md): exact, proxy or not yet measurable).

Committed market research does not depend on a commercial competing platform
as factual product authority. A publication by a commercial competing
platform cannot be cited without naming that platform, which
[07 §5](../canonical/07-PRODUCT-GROWTH-DOCTRINE.md) forbids in committed
material; such a source is therefore not used — the claim is sourced from an
evidence class above, labelled **HYPOTHESIS**, or omitted. Any exception
needs a founder decision.

## 3. Citations

Every external factual claim records, where applicable:

| Field | Example of what goes here |
|---|---|
| Title | the document's own title |
| Author / institution | the publishing body or authors |
| Publication date | as stated by the source |
| Retrieval date | when Homies read it |
| DOI / public identifier | DOI, official journal reference, dataset id |
| Geographic scope | e.g. Poland, a voivodeship, the EU |
| Limitations | sample, period, definitions, what it does not show |

A claim without traceable evidence is labelled **HYPOTHESIS** or omitted.
Citations are never fabricated, reconstructed from memory or inferred from
what a source "probably" says; an unverifiable source is not cited.

Each statement in a research document is marked as one of:
**OBSERVED PROBLEM** · **EVIDENCE** · **INFERENCE** · **HOMIES HYPOTHESIS** ·
**ACCEPTED DECISION** (with its D-xxx).

## 4. Independent synthesis

The binding rule is [07 §5 — independent synthesis](../canonical/07-PRODUCT-GROWTH-DOCTRINE.md)
(canon, D-106); it applies to all committed product, market and research
material, not only to this folder. Restated here for authors of research:
committed material is independently written and does not contain:

* names of commercial competing marketplaces or platforms;
* their commercial URLs or domains, logos or screenshots;
* copied marketing copy or UI copy;
* proprietary feature names or proprietary taxonomies;
* page-by-page cloning instructions or trade-dress recreation;
* reasoning whose only basis is that another company does something.

Market observations are expressed as generic capability categories — for
example property discovery, search and filtering, map discovery, inventory
aggregation, alerts, communication, viewing coordination, renter
applications, trust and identity, authority verification, landlord workflow,
agency operations, tenancy lifecycle.

General market patterns are not claimed as legally unique to Homies, and no
claim of exclusivity or legal ownership is made for them. Wording used
instead: *Homies-authored synthesis*, *Homies product hypothesis*,
*project-derived product principle*, *independent product reasoning*.

Market-price data are not scraped from third-party platforms (D-42: own data
or licensed sources only); public datasets and registries are used under
their published access terms.

**Scope of this rule.** It covers market, competitive and product-reasoning
material. Technical dependencies, protocols, standards, public registries and
providers actually selected or evaluated are named wherever engineering truth
requires it (for example in ADRs, the canon's stack, production
documentation).

## 5. Historical material

Earlier market and benchmark notes predate D-106. Immutable evidence in
`docs/reviews/` stays byte-for-byte; editable benchmark notes there carry a
banner and were sanitised mechanically where meaning survived; superseded
strategy and business documents are banner-marked historical and are not
product authority. None of them is a template for new research.
