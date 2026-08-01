# Problem Statement: Household Intelligence at Checkout (Blinkit)

Working name: **Blinkit Sense**

Build an AI-native feature that increases the percentage of monthly active customers who purchase from at least one **new category** each month, where a category is a **tile** in Blinkit's taxonomy (defined in section 4).

---

## 1. Context

Blinkit is built end-to-end to help people re-buy what they already buy. "Order again" is a permanent bottom-nav tab, "Frequently bought" sits above the fold, and recommendations come from purchase history and co-occurrence ("People also bought"). Every surface points backwards.

But nobody enters a new category by browsing. Primary research (5 depth interviews, 4 seven-day diaries, 4,000+ reviews across App Store, Play Store, Reddit and YouTube) found every new-category entry was triggered by a situation with a collapsed time window:

- guests arriving → serving bowls
- market-bought diyas broke on Diwali night → diyas, wicks, oil, idols
- moved out of home → bedsheets "to sleep on"
- plans changed, flight next morning → toys and a book as gifts
- brought a cat home → searched "cat essentials"

Two constraints govern that moment:

1. **Blinkit only wins once the window has collapsed.** With lead time, customers go to the market, Amazon or Nykaa. Speed is worth nothing with a buffer and everything without one. Therefore: no lead-time reminders — they hand the sale to a competitor.
2. **Attention is already consumed.** The customer is mid-preparation. They buy the one or two things they recall; the rest of what the situation required never enters their head.

The ceiling is recall under divided attention — not awareness, not trust.

And the one system that could help is structurally unable to: **collaborative filtering recommends from observed purchases, and a customer has zero purchase history in a category never entered.** Worse, when a household sources a category elsewhere (diyas bought in bulk at a market), the co-purchase pattern was never observed on Blinkit at all.

**This is not a RAG system.** There are no documents to retrieve, no vector database, no embeddings, no chunking. It is an **API-wrapper architecture**: structured input → LLM reasoning → structured output → deterministic guardrails. If the generated architecture proposes a vector store, that is wrong.

---

## 2. What you are building

A checkout-time layer that:

1. Reads the cart and delivery address **cold** — no purchase history required
2. Proposes **four candidate situations** that could have produced this cart, plus a free-text option
3. Takes the customer's confirmation in **one tap**
4. Reasons from world knowledge about what that situation requires
5. **Then** consults purchase history — to drop what they already buy and flag which categories are new for them
6. Presents a requirement set grouped by role, sized to the fee threshold, with a refresh

The output must read as a **reasoned requirement set**, not a ranked product grid. If it renders as tiles with prices it is indistinguishable from the existing "People also bought" and the feature has failed. Roles, coverage and quantity reasoning are the differentiation — not styling.

---

## 3. Core mechanism

```
CART CONTENTS + CURRENT DELIVERY LOCATION
        |
[1] SITUATION READER (LLM)  -- reads cold, no history
        |  returns 4 candidate situations + confidence
        v
    non-blocking strip at the cart:
    4 chips + "Tell us" free text + "Just stocking up" + dismiss
        |  customer taps one
        v
[2] NEED PLANNER (LLM)  -- decomposes the confirmed situation
        |  returns needs grouped by role, with quantity reasoning
        v
[3] CATALOGUE RESOLVER (deterministic)
        |  maps each need to a real SKU from catalog.json
        |  filtered to the household's CURRENT delivery location
        |  unmatched needs become honest gaps
        v
[4] HOUSEHOLD FILTER + GUARDRAILS (deterministic)
        |  drops what they already buy
        |  flags tile categories with zero history as new_category
        |  sizes to the fee threshold - caps at 6 - sensitive-category veto
        v
    Composed set  ->  add all / per-item  ->  refresh  ->  dismiss
```

### The architectural rule

**History is an output filter, not a detection input.**

The LLM reads the cart cold. Purchase history is consulted only *after* the customer confirms — to personalise and to flag new categories.

Consequences, all of which must hold in the build:

- **No cold start.** A first-order customer and a five-year customer get identical inference quality. Nothing is suppressed. Light users have the most unentered categories and matter most to the metric, so excluding them would defeat the objective.
- **Incoherent carts work.** Fruit, cat food, cookware and a plug in one basket defeats any anomaly detector, but an LLM can still propose four plausible readings and let the human resolve. Real carts look like this.
- **Clean contrast with collaborative filtering.** CF *is* purchase history. This works without any.

### What raises and lowers confidence

Confidence is computed from the cart itself, never from a customer baseline:

- **Raises:** items with strong situational implications (cat food, baby wipes, dry fruits, bedsheet, cookware); an unfamiliar delivery location; calendar proximity to a major festival; several items pointing at one reading
- **Lowers:** pure staples with no implication (milk, bread, eggs, vegetables); a single low-signal item

Below threshold (0.4), **show nothing**. Forcing a suggestion onto a routine restock is the failure customers reject most.

**Frequency-tuned threshold:** costs are asymmetric. For a daily customer, silence today costs nothing — tomorrow comes. For a once-a-month customer, their single order is the only touchpoint of the month. Lower the threshold as order frequency drops.

### Metric-validity rule — enforce in code

A suggestion counts toward the objective only if its **tile** category has zero purchase history for that household. Suggesting cat litter to a household that already buys cat food is same-category deepening: it raises basket value and does nothing for the metric.

Every resolved item must carry a flag: `new_category` or `deepening`. Demo flows must lead with `new_category` items.

### Confirmation rules

- Non-blocking strip at the cart. **Never a modal** — the customer's hands are busy.
- Fires **once per session**, not per item.
- Always offers: 4 situation chips, "Tell us" free text, "Just stocking up", dismiss.
- Dismissals and "just stocking up" are recorded — bad hypotheses are data.
- Where a single reading is overwhelmingly likely (first-ever cat food in the cart), state the reasoning instead of asking, and let the add-action be the confirmation. Chips appear only where two or more readings are genuinely plausible.

**Free text is a chip inside the strip, not a search feature.** Zomato — same parent company — already ships natural-language search. A semantic search bar on Blinkit is a port, not an intervention.

---

## 4. Data

Blinkit publishes no developer API, but its storefront loads product data from internal JSON endpoints. `scrape_blinkit.py` fetches from those endpoints and writes `catalog.json`. **The app reads from `catalog.json`; it does not fetch during a user interaction.**

**Why stored rather than live-per-query:** a demo that depends on an external endpoint at click time can fail in front of an evaluator through rate limiting, an endpoint change, or an IP block — and adds seconds of latency to every interaction for no benefit to the argument.

**How freshness is proved instead — scheduled refresh via GitHub Actions.** A workflow re-runs the scraper on a schedule, commits the updated catalogue, and can also be triggered manually. The app always reads the committed file, so it is fast and cannot fail; the **commit history and the diffs between runs are the liveness evidence**, and they are verifiable by anyone with the repo link. Stronger proof than a live fetch nobody can inspect, with none of the demo risk.

```yaml
# .github/workflows/refresh-catalogue.yml
on:
  schedule:
    - cron: "45 3 * * 1"      # 09:15 IST every Monday (Actions cron is UTC)
  workflow_dispatch: {}        # manual trigger button in the Actions tab
```

The app also exposes a **"Refresh catalogue" button** in the sidebar that runs the same code path, so behaviour is identical whether triggered by the schedule, the Actions tab, or the UI.

**Raw output is versioned per run.** Each scrape writes to `data/raw/<UTC timestamp>/` with a `manifest.json` recording keywords, locations, counts per keyword, and any failures. `data/catalog.json` is then built from the most recent successful run. Two run folders side by side are the simplest possible proof that the catalogue refreshes.

### `locations.json`

| Location | Coordinates | Role in the demos |
|---|---|---|
| Sarjapur, Bangalore | 12.8575579, 77.7864057 | home base for h1, h3, h4 |
| Whitefield, Bangalore | — | h2's new address, a within-city move |
| Delhi NCR | — | h5's cross-city move, and the deepest assortment |

### `categories.json` — Blinkit's real taxonomy, captured from the live app

**A category is a TILE, not a group.** The brief's own examples require it: *pet supplies* is the Pet Store, *baby products* is the Baby Care tile, *personal care* is Bath & Body / Hair / Skin & Face. None of those is a top-level group.

Four groups containing 28 tiles:
- **Grocery & Kitchen** — Vegetables & Fruits · Atta, Rice & Dal · Oil, Ghee & Masala · Dairy, Bread & Eggs · Bakery & Biscuits · Dry Fruits & Cereals · Chicken, Meat & Fish · Kitchenware & Appliances
- **Snacks & Drinks** — Chips & Namkeen · Sweets & Chocolates · Drinks & Juices · Tea, Coffee & Milk Drinks · Instant Food · Sauces & Spreads · Paan Corner · Ice Creams & More
- **Beauty & Personal Care** — Bath & Body · Hair · Skin & Face · Beauty & Cosmetics · Feminine Hygiene · Baby Care · Health & Pharma · Sexual Wellness
- **Household Essentials** — Home & Lifestyle · Cleaners & Repellents · Electronics · Stationery & Games

Plus dedicated **Stores**, which sit outside the four groups and count as categories in their own right: Pet Store · Spiritual Needs · Toy Store · Book Store · Jewellery Store · E-Gifts Store · Fashion Basics · Sports Store · Hobby Store · Travel Store · Pharma Store · Ice Cream Store.

**Verified cross-boundary pair for the demos:** cat food sits in **Pet Store**; pet-safe floor cleaner sits in **Cleaners & Repellents**. Different construct entirely — the cross-boundary claim holds.

### `catalog.json` — 250 to 400 products

```json
{ "id": "sku_014",
  "name": "Clumping cat litter 5kg",
  "brand": "BearHugs",
  "category": "Pet Store",
  "price": 449,
  "mrp": 499,
  "unit": "5 kg",
  "available_in": ["Sarjapur", "Whitefield", "Delhi NCR"],
  "fetched_at": "2026-07-31T06:18:58Z" }
```

Every product's `category` must be a **tile** from `categories.json`. Availability is **per location**, not global — `available_in` lists the locations that stock it. The resolver checks it against the household's current location, so a need met in Delhi but not Sarjapur produces an honest gap rather than a phantom suggestion.

**Tie-break when a need matches several products:** prefer the product whose name contains the most words from the need, then the lower price. One SKU per need — never two bedsheets. This must be deterministic so the same cart always produces the same result.

**Scrape keywords** (30, across three locations): cat food · cat litter · litter tray · pet bowl · bed sheet · pillow · bath towel · bucket · mug · mop · dustbin · floor cleaner · room freshener · lint roller · diya · agarbatti · roli chawal · pooja thali · gift box · gift wrapping paper · dry fruits · kaju katli · milk · bread · eggs · curd · atta · tomato · onion · potato

**If the scrape fails or is blocked:** generate a representative catalogue with real Indian product names and realistic prices instead, and record in the README which was used. A working demo on generated products beats a broken one on real products.

**Assortment-depth check:** record how many keywords return results per location. If Delhi NCR returns more than Sarjapur, that is first-party evidence for the assortment-depth claim in the deck.

### `households.json` — 5 profiles

The address signal fires when `current_address` is not in `known_addresses`.

```json
{ "id": "h1",
  "name": "Sarjapur household",
  "known_addresses": ["Sarjapur, Bangalore"],
  "current_address": "Sarjapur, Bangalore",
  "orders_per_month": 12,
  "order_history": [{"sku": "sku_001", "orders_per_month": 8}],
  "current_cart": ["sku_022", "sku_005"] }
```

- **h1** — Sarjapur. Routine grocery basket plus dry fruits (ambiguous-cart demo)
- **h2** — known address Sarjapur, **current address Whitefield** (within-city move)
- **h3** — Sarjapur. Second-ever order, cat food in cart (no-history demo — must work identically)
- **h4** — Sarjapur. Pure staples only: milk, bread, eggs (low-signal demo — must show nothing)
- **h5** — known address Sarjapur, **current address Delhi NCR** (cross-city move, wider assortment, fewer honest gaps than h2)

### `scenarios.json` — situations as data, so new ones need no code change

```json
{ "id": "moving_in",
  "chip_label": "Moving in",
  "prompt_context": "The customer has just moved into a new, empty home." }
```

### Fee model (from the live app)

Delivery ₹30 + handling ₹12 + small-cart ₹20, with the small-cart charge waived above ₹99. Used for threshold-aware sizing: if the cart is below ₹99, tell the customer how much more clears the charge.

---

## 5. LLM contracts

Two calls. Both must return **JSON only** — no prose, no markdown fences, no explanation. Parse defensively; on malformed output, fail closed and show nothing.

**Call 1 — situation reader.**
Input: cart item names with their tile categories, current delivery location, whether that location is unfamiliar, today's date.

```json
{ "confidence": 0.82,
  "candidates": [
    { "id": "festival_gifting", "label": "Festival gifting",
      "reasoning": "dry fruits in festival week" },
    { "id": "hosting", "label": "Guests coming",
      "reasoning": "dry fruits often served to visitors" },
    { "id": "health", "label": "Eating better",
      "reasoning": "dry fruits as a snack replacement" },
    { "id": "stocking", "label": "Just stocking up",
      "reasoning": "no situational signal" }
  ] }
```

Chip labels must be under four words. Confidence must be genuinely low for staple-only carts.

**Call 2 — need planner.**
Input: the confirmed situation label and context, plus the list of tile categories.

```json
{ "situation_label": "Setting up a new home",
  "needs": [
    { "role": "Sleep", "need": "bedsheet",
      "why": "nothing to sleep on yet", "quantity_reasoning": "one double bed" },
    { "role": "Bathroom", "need": "bucket and mug",
      "why": "no bathroom basics in an empty flat", "quantity_reasoning": "one set" }
  ],
  "unavailable": [] }
```

**The LLM returns needs, never SKUs or brand names.** It must say "bedsheet", not "Bombay Dyeing double bedsheet". The application maps `need` to `catalog.json`. This makes hallucinated products structurally impossible rather than merely mitigated — the model never names a product, so it cannot invent one.

---

## 6. Guardrails

| Failure mode | Mitigation |
|---|---|
| Wrong situation read | Never act without a tap where readings are ambiguous. Situation label shown back and correctable. |
| Hallucinated products | LLM returns needs; code resolves SKUs. Unmatched needs render as an honest gap: "we don't stock this — you'll need it elsewhere." |
| Over-suggestion | Cap at 6 items. Drop anything in the household's routine basket. Size to the fee threshold, not to maximum cart value. Every item and the whole strip dismissable. |
| Sensitive categories | Hard rules-gate: **Health & Pharma and Baby Care are never auto-composed.** Category-level guidance only. The LLM composes; code vetoes. |
| Low signal | Below the 0.4 confidence threshold, show nothing. Coverage is partial by design. |
| Malformed LLM output | Fail closed. Never render a partial or guessed set. |
| Catalogue refresh fails | Keep serving the committed `catalog.json` and surface the error. Never silently present stale data as freshly fetched. Rate-limit the scraper with a 2-second delay and an identifying user-agent. |

**Demoable guardrail:** a confirmed situation the catalogue cannot cover must return what it has and name what it cannot, rather than padding with popular SKUs.

---

## 7. Evaluation

Two models are compared on the same test set, and the comparison is a deliverable.

- **Primary:** `openai/gpt-oss-120b` on Groq
- **Comparison:** `llama-3.3-70b-versatile` on Groq

`compare_models.py` runs the same five test carts through both and writes `docs/model_comparison.md`.

**What to measure:**

| Dimension | Test |
|---|---|
| Situation-reading accuracy | Does the top candidate match the intended reading for each demo cart? |
| Confidence calibration | Does the staples-only cart score below 0.4, and the dry-fruits cart above 0.6? |
| Need-planning completeness | Does "Moving in" include the non-obvious items — bucket, mop, dustbin — not just bedsheet? |
| World-knowledge depth | Does a Diwali situation return diyas **and** wicks **and** oil? Does a cat situation avoid suggesting phenyl? |
| Format compliance | Rate of valid JSON without markdown fences, across 10 runs |
| Latency | Seconds per call |

---

## 8. File structure

```
blinkit-sense/
  docs/
    problemStatement.md
    architecture.md
    model_comparison.md
  data/
    categories.json
    catalog.json
    households.json
    locations.json
    scenarios.json
  data/raw/
    20260731T061858/   # one folder per scrape run
      manifest.json    # keywords, locations, counts, failures
  .github/workflows/
    refresh-catalogue.yml
  phases/              # one self-contained folder per build phase
    phase_1_scraper/
      __init__.py  config.py  scraper.py  README.md
    phase_2_data/
    phase_3_situation_reader/
    phase_4_confirmation/
    phase_5_need_planner/
    phase_6_resolver/
    phase_7_household_filter/
  llm.py               # both LLM calls, provider read from .env
  engine.py            # resolver, household filter, threshold maths
  app.py               # Streamlit UI
  test_categories.py
  test_situation.py
  test_needs.py
  test_engine.py
  compare_models.py
  requirements.txt
  .env                 # never committed
  .gitignore
  README.md
```

---

## 9. Build phases

Each phase ends with a runnable test. Do not start the next phase until the current one passes.

**Every phase gets its own folder** under `phases/`, self-contained with its own `config.py` and `README.md`, so phases stay independently testable and the build process is legible in the repo.

1. **Scraper** — `phases/phase_1_scraper/`. Find Blinkit's product endpoint, fetch the 30 keywords across 3 locations, write raw output to `data/raw/<UTC timestamp>/` with a `manifest.json`, then build `data/catalog.json` from it. Print counts per keyword and per location. Rate-limit with a 2-second delay and an identifying user-agent.
2. **Data layer** — categories, households, locations, scenarios. **Write this test first:** `test_categories.py` prints, per household, current location and whether it is unfamiliar, tile categories with purchase history, and tile categories with none. Then, for each demo flow, print every resolvable SKU labelled `new_category` or `deepening`. **If a demo produces mostly `deepening`, that demo is invalid** and the household or scenario must change.
3. **Situation reader** — `llm.py`, LLM call 1, JSON parsing, confidence threshold, defensive failure. `test_situation.py` runs all five households.
4. **Confirmation strip** — chips rendered from the LLM response, free text, "just stocking up", dismiss. Non-blocking, once per session.
5. **Need planner** — LLM call 2, JSON parsing. `test_needs.py` covers "Moving in" and "Festival gifting".
6. **Catalogue resolver** — need to SKU by keyword match, filtered to the household's current location, unmatched needs become honest gaps.
7. **Household filter** — drop owned items, flag `new_category` by tile, cap at 6, sensitive-category veto, compute the ₹99 threshold gap. `test_engine.py` runs the full chain for h2 and prints every result labelled.
8. **Output rendering** — roles, quantity reasoning, new-category line, honest-gap line, threshold line, add-all with per-item toggles, refresh, dismiss.
9. **Model comparison** — `compare_models.py`, writes `docs/model_comparison.md`.
10. **Scheduled refresh** — `.github/workflows/refresh-catalogue.yml`: weekly cron plus `workflow_dispatch`, running the same scraper code path and committing the updated catalogue. Trigger it once manually to prove it works and to produce a second run folder.
11. **Polish and deploy** — desktop layout, refresh-catalogue button in the sidebar, GitHub, Streamlit Cloud, incognito test.

---

## 10. Demo flows — all must work end to end

1. **Ambiguous cart** *(hero)* — h1: dry fruits plus routine groceries → four chips → "Festival gifting" → gift boxes, wrapping, roli chawal, diyas with "a few always break — 12 covers a small home" → **Spiritual Needs and E-Gifts Store are new**.
2. **New delivery location** — h2: Whitefield differs from known Sarjapur → four chips → "Moving in" → bedsheet, pillow, towel, bucket, mug, mop → **Home & Lifestyle, Kitchenware & Appliances, Bath & Body and Cleaners & Repellents are new**.
3. **No history at all** — h3: second-ever order, cat food in cart → reading is unambiguous, so the strip states its reasoning rather than asking → litter, tray, scoop, bowl → **Pet Store is new**. Proves the mechanism does not depend on history.
4. **Incoherent cart** — fruit, cat food, cookware and a plug together → anomaly detection has nothing to say, but the LLM proposes four plausible readings and the customer resolves it in one tap. The hardest case and the best demonstration of reasoning.
5. **Honest gap** — a confirmed situation the catalogue cannot fully cover returns what it has and names what it cannot.
6. **Low signal** — h4: milk, bread, eggs → below 0.4 → the strip does not appear. Shows the system declining to act.

**h5 is not a required demo flow.** It exists so the cross-city case can be explored and so the Delhi assortment is exercised, but demo 2 (h2, within-city) is the one that must work.

**Not a demo flow:** semantic or natural-language search.

---

## 11. UI specification

Single Streamlit page, `layout="wide"`, desktop-first — this is evaluated on a laptop.

- **Top:** household selector (dropdown), showing the current delivery location and flagging it if unfamiliar
- **Left column:** the cart as a simple list with prices, then the fee breakdown and total
- **Below the cart:** the suggestion strip, in a tinted box distinct from the cart
  - Before confirmation: a heading stating what was noticed, then the four chips in a row, a "Tell us" text input, "Just stocking up", and "Dismiss"
  - After confirmation: the situation label as a heading, then needs **grouped by role** with quantity reasoning in smaller text beneath each, then a prominent **"Add all N · ₹total"** button with per-item toggles, then the new-category line, the honest-gap line if any, and "Show other options" / "No, I'm done"
- **Sidebar:** a "Refresh catalogue" button that re-runs the scraper, plus the `fetched_at` timestamp
- Spinner while either LLM call is running
- `st.session_state` so clicking a chip does not reset the page
- No emoji. Restrained styling. The roles and the new-category line must be visually prominent — they are the differentiation.

---

## 12. Stack

- **Build:** Cursor (fallbacks: Antigravity, Windsurf). GitHub from the first commit — the portability layer.
- **App:** Streamlit, Python.
- **LLM:** Groq, via the OpenAI-compatible client. Provider, key and model read from `.env` so the model can be switched by editing one line.

```
GROQ_API_KEY=gsk-your-key-here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_MODEL_ALT=llama-3.3-70b-versatile
```

- **Deploy:** Streamlit Community Cloud, with the Groq key in Secrets.
- **Landing page:** Stitch, deployed on Vercel, linking through to the app.
- **Deck wireframes:** drawn mobile-framed, since Blinkit's real surface is mobile, with one honest line: "prototype built desktop-web for demonstration; production surface is in-app mobile."

---

## 13. Out of scope

Voice input · multi-turn conversation · vector databases and document retrieval (there are no documents) · payments · mobile build · user accounts · lead-time reminders (counterproductive — they route the customer to Amazon) · assortment and variety gaps (not solvable by an app feature) · discount mechanics (contradicts management's stated no-discount position) · supply-chain and dark-store optimisation (demand-side scope only).