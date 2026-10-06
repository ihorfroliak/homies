# 07 — Product & Growth Doctrine

> **Source:** founder instruction of 2026-09-25 (TASK-010, Part A). Ranks with
> [02-BUSINESS-LOGIC](02-BUSINESS-LOGIC.md) (see [00-AUTHORITY](00-AUTHORITY.md)):
> 02 says *what* Homies does in each phase; this document says *how every
> material product decision is judged*. Mandatory context for any substantial
> task — a Task Contract names the dimensions below that apply to it and how
> the work moves them.

## 1. Market scope

| | |
|---|---|
| Current product market | **Poland** |
| Architecture expansion target | **Europe** |
| Possible first liquidity market | a large Polish city (e.g. Kraków) — an acquisition choice, **not** a data-model boundary |

**Launch locally. Model nationally. Architect internationally.**

No domain design may assume `city == Kraków`, `country == Poland` forever,
`currency == PLN` forever, or that Polish administrative terminology is
universal terminology. Country-specific legal concepts must not contaminate
universal core concepts; they live behind a country seam.

## 2. The ten questions

For every material feature, flow or product/architecture decision, answer the
dimensions relevant to it. A dimension that does not apply is skipped, not
padded.

| # | Dimension | Question | Judged by |
|---|---|---|---|
| A1 | **UX** | Does this make Homies easier, faster and more pleasant to use? | User effort, not implementation elegance: steps, time to outcome, confusion, error recovery, mobile usability, information clarity |
| A2 | **Trust & safety** | Does it improve trust, privacy, reliability or safety? | Trust is designed into the experience. Identity verification is not complete trust; long-term trust combines identity, authority, property verification, freshness, history, behaviour, transaction and incident context |
| A3 | **Automation** | Can Homies remove repetitive manual work? | Both **customer automation** and **Homies internal automation** — alerts, verification, scheduling, applications, moderation, fraud detection, support triage, reference-data import, marketing attribution, AI-assisted workflows |
| A4 | **Efficiency** | Does it reduce steps, time, errors or operating cost? | User and operational efficiency, not only server latency |
| A5 | **Marketplace liquidity** | Does it improve quality supply, demand, matching or successful housing outcomes? | Liquidity is existential: a beautiful marketplace without relevant inventory has failed |
| A6 | **Competitive advantage** | Why choose Homies instead of an established alternative? | Not "competitors have it" |
| A7 | **Beauty & desirability** | Does Homies feel premium, coherent and desirable? | Beauty and UX are requirements, not decoration. The future design system covers typography, spacing, photography, maps, motion, microinteractions, mobile UX, empty/loading/error states, visual hierarchy |
| A8 | **Growth** | Can the value be explained, marketed, measured, used for acquisition or retention? | Product and marketing develop in parallel (§6) |
| A9 | **Scalability** | Does it serve Poland today and Europe later without a core-domain rewrite? | §1 |
| A10 | **Necessity** | If it moves none of the above, why build it? | Avoid feature-count competition |

## 3. Product principles

1. Quality over feature count.
2. User outcome over implementation novelty.
3. Trust is a product feature.
4. Security is designed in, not attached before release.
5. Automation is preferred over repetitive manual workflows.
6. Transparency is a core Homies differentiator.
7. Beauty and usability are requirements, not decoration.
8. Growth is designed alongside the product.
9. Marketplace liquidity is existential.
10. Property persists; Listing is temporary.
11. Country-specific legal concepts must not contaminate universal core concepts.
12. Homies derives product decisions from user needs, evidence, domain
    constraints and measurable outcomes rather than feature imitation
    (D-106; §5).

## 4. Positioning (directional, not final copy)

| | |
|---|---|
| Launch positioning | **Najprzejrzystszy sposób na wynajem mieszkania w Polsce.** |
| Product thesis | Homies makes finding, renting and managing a home more transparent, trustworthy and efficient. |
| Long-term thesis | Homies is a trusted residential-property marketplace and operating system that maintains a persistent digital identity for a home across discovery, rental, sale and management. |

These guide product decisions; marketing copy may change.

## 5. Independent market evidence doctrine

*Founder decision D-106 (2026-10-06) supersedes the earlier "competitive
benchmark doctrine" of this section, which named a standing set of commercial
platforms; the earlier text remains in Git history.*

For every material workflow, the reasoning chain is:

```text
OBSERVED USER / WORKFLOW PROBLEM
              ↓
TRACEABLE EVIDENCE
              ↓
HOMIES INFERENCE OR HYPOTHESIS
              ↓
HOMIES-SPECIFIC PRODUCT RESPONSE
              ↓
MEASURABLE OUTCOME
```

Principles:

* Homies product decisions originate from user needs, evidence, domain
  constraints, safety and business outcomes.
* External commercial products may inform human learning outside the
  repository; they are not repository product authority.
* A feature is never justified solely because another commercial product has
  it.
* Generic market capability categories (property discovery, search and
  filtering, map discovery, inventory aggregation, alerts, communication,
  viewing coordination, renter applications, trust and identity, authority
  verification, landlord workflow, agency operations, tenancy lifecycle) are
  acceptable language; named commercial platforms are not used as product
  authority.
* A factual external claim requires traceable evidence (source rules in
  [`docs/research/`](../research/README.md)); an unsupported claim is labelled
  **HYPOTHESIS** or omitted.
* A product recommendation stands on Homies reasoning alone — users, this
  doctrine, the domain model, safety, business goals, successful housing
  outcomes or operational constraints.

**Independent synthesis — binding rule for committed material.** Current
committed product, market and research material — canon, Task Contracts,
specifications, handoffs, product / growth / frontend documents and
`docs/research/` — is independently written and does not contain: names of
commercial competing marketplaces or platforms; their commercial URLs or
domains; their logos or screenshots; copied marketing copy or UI copy;
proprietary feature names or proprietary taxonomies; page-by-page cloning
instructions or trade-dress recreation; or reasoning whose only basis is
that another company does something. General market patterns are not
claimed as legally unique to Homies. Technical dependencies, protocols,
standards, public registries and providers actually selected or evaluated
are named wherever engineering truth requires it. Immutable evidence and
banner-marked historical documents are not rewritten under this rule.

Market evidence lives in [`docs/research/`](../research/README.md)
(non-normative); it reaches implementation only through a founder/product
decision recorded as a D-entry, a canonical update or an approved Task
Contract.

## 6. Two parallel tracks

| Track | Scope |
|---|---|
| **Product / engineering** | Task Contracts, canon, code |
| **Growth / market** | SEO, Google Ads, paid social, content, brand, referral system, credits, landlord acquisition, agency acquisition, partnerships, remarketing, lifecycle messaging, analytics and attribution, CAC/LTV, regional liquidity strategy |

Neither waits for the other. Engineering tasks name the growth hooks they
enable (e.g. location data that powers SEO landing pages) without building the
growth system inside a product task.

## 7. North Star

| | |
|---|---|
| Long-term North Star | **Successful Housing Outcomes** |
| Phase-1 operating focus | **Successful Rental Outcomes / Move-ins** |

**Measurement gap (2026-09-25):** Homies has no production traffic and no
move-in signal. Phase 1A records contact reveals, conversations and viewings
server-side, but nothing yet observes a completed move-in. Defining that
signal (tenant/owner confirmation, listing marked let, time-to-let) is a
future task; no number is reported until it exists.

## 8. How this document is used

* A Task Contract for substantial work names the applicable dimensions and
  its intended effect on each (one line each is enough).
* A reviewer (ChatGPT, Codex, founder) may reject work that ignores a
  relevant dimension, or that fails A10.
* Changes to this document are founder decisions.
