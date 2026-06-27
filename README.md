# AI-Powered Car Damage Assessment — Jury Presentation Pack

*A complete guide for your hackathon / university jury presentation: project explanation, speech, and Q&A bank.*

> **How to use this pack:** Sections 1–13 are your reference and slide content. Section 14 is the speech to deliver. Section 15 is your defense — read it twice before you present. Replace **[App Name]** with your final name (e.g. *CrashLogic* or *DentScan*).

---

## Scope at a glance — what we built vs. what comes next

To stay honest in front of a technical jury, we separate two things clearly:

- **MVP (what we demonstrate today):** photo upload → damage detection with bounding boxes → damage-type classification (dent / scratch / crack) → damaged-part identification → online part-price lookup → an *indicative* repair-vs-replace cost range → a generated report.
- **Vision (future work):** damage-severity scoring, video and 3D analysis, VIN-based identification, and direct insurer/repair-shop integrations.

Throughout this document we present the cost output as an **estimated range**, not a guaranteed final price, and we treat the whole system as a **preliminary assistant** — not a replacement for a mechanic, insurer, or official inspection.

---

## 1. Project Introduction

**[App Name]** is an AI-powered car damage assessment application. The user takes or uploads one or more photos of a vehicle after an accident, and the system returns a clear, preliminary assessment: which parts are damaged, what type of damage it is, and an estimated cost range to repair or replace.

The real-world problem is simple and universal. After even a minor accident, drivers are thrown into uncertainty. They can *see* that something is broken, but they cannot easily answer the questions that matter most: *What exactly is damaged? How bad is it? What will it cost?* Today the only way to get those answers is to drive from one repair shop to another, collect inconsistent estimates, and hope someone is being honest.

This matters because cars are expensive, accidents are stressful, and information is unevenly distributed. The repair shop knows the prices; the driver usually does not. Our project closes that gap by giving the driver an instant, transparent starting point — in seconds, from a phone, before any money or trust is committed.

---

## 2. Problem Statement

After an accident, vehicle owners face a chain of related difficulties:

- **They don't know which parts are damaged.** Visible damage and the underlying affected components are not always the same thing, and most drivers can't name parts confidently.
- **They can't judge severity.** A scratch and a crack look different but cost very differently, and an owner has no objective way to tell which they're dealing with.
- **Estimating cost is hard.** Part prices, labor rates, and — in import-heavy markets like Azerbaijan — delivery and customs costs are opaque to the average person.
- **Shops quote different prices.** One garage says one number, another says something far higher, and the driver has no baseline to evaluate either.
- **Manual inspection takes time.** Getting an in-person estimate means travel, waiting, and often several visits.
- **The whole process lacks transparency.** Without an independent reference point, the owner is largely dependent on someone else's subjective judgment.

The result is wasted time, financial uncertainty, and a real risk of overpaying — or, in the insurance context, of disputes and fraud.

---

## 3. Proposed Solution

**[App Name]** replaces that uncertainty with a guided, automated assessment. The flow moves the user from a single photo all the way to a cost range and a report:

1. **The user uploads a photo** (or several) of the damaged vehicle.
2. **The system recognizes the vehicle** — color, and where possible make and model — to anchor the later price search.
3. **It detects the damaged areas** and draws bounding boxes so the user can see what the AI is reacting to.
4. **It identifies the damaged part** — bumper, door, hood, fender, headlight, windshield, trunk, and so on.
5. **It classifies the damage type** — dent, scratch, or crack — with a confidence score for each detection.
6. **It searches online sources** for the price of the relevant part (new, used, aftermarket).
7. **It estimates total cost** by combining part price, estimated labor, and delivery/customs, and produces a **minimum–maximum range** plus a repair-or-replace recommendation.
8. **It generates a report** the user can read, save, or share.

Each step builds on the previous one. The detection tells us *where*, the part model tells us *what component*, the classifier tells us *what kind of damage*, and that combination is exactly what the price module needs to produce a meaningful number.

---

## 4. Complete User Workflow

> **Photo upload → vehicle identification → damage detection → damaged-part identification → damage classification → price search → repair/replacement cost estimation → result & report**

What the user actually sees at each stage:

| Stage | What happens | What the user sees |
|---|---|---|
| **1. Upload** | User selects or captures one+ photos | Simple upload screen, image preview, "Analyze" button |
| **2. Vehicle ID** | System reads color, attempts make/model | "Detected: white Toyota Corolla (confidence 82%)" with an option to correct it |
| **3. Damage detection** | Model locates damaged regions | The photo with colored bounding boxes drawn over damaged areas |
| **4. Part identification** | Each region is mapped to a car part | Labels like "Front bumper," "Left headlight" |
| **5. Damage classification** | Each region is typed | Tags like "Dent (91%)," "Scratch (87%)" |
| **6. Price search** | System queries marketplaces for the part | A short "searching prices…" state |
| **7. Cost estimation** | Part + labor + delivery/customs combined | A clear range, e.g. "Repair: 80–140 AZN · Replace: 220–360 AZN" |
| **8. Report** | Everything is compiled | A downloadable summary with the annotated photo, detected parts, damage types, confidences, prices, and the disclaimer |

The key design principle: **the user is never asked to trust a black box.** They see the boxes, the labels, the confidence scores, and the price reasoning — and they can correct the vehicle identity if it's wrong.

---

## 5. Artificial Intelligence Components

In plain language, here is what the system does and the AI ideas behind each piece.

**Computer vision** is the umbrella: teaching a computer to "see" and interpret the contents of an image. Everything below is a kind of computer vision.

**Object detection** finds *where* things are in an image and draws a box around them. We use it to locate damaged regions on the car.

**Image classification** answers *what* something is. We use it to decide the damage type within a region — dent, scratch, or crack.

**Vehicle make-and-model recognition** is a specialized classifier that tries to name the car. Color is relatively easy; precise make/model/year is genuinely hard, so in the MVP we treat this as a *best guess the user can correct*, and we can optionally let the user simply tell us the model (they know their own car).

**Car-part detection or segmentation** maps a region of the image to a known component (bumper, door, fender). Detection gives a box; segmentation gives an exact outline. The MVP uses detection; segmentation is a future upgrade for cleaner part boundaries.

**Damage-type detection** is the classification step above, applied per detected region.

**Confidence scores** accompany every prediction — a number from 0 to 1 expressing how sure the model is. We show these so the user can weigh the result rather than blindly trust it.

**Vision-language models (VLMs)** are large AI models that can look at an image and describe it in words. They're useful as a flexible fallback — for example, to describe an unusual vehicle or summarize the damage in natural language for the report.

**Online search / price-retrieval** is the non-vision component: once we know the part, year, and model, we query the web and marketplaces for prices.

### The crucial distinction: area vs. part vs. damage type

These three are easy to confuse, and a jury will respect you for separating them cleanly:

- **Damaged *area* detection** answers **"Where on the image is there damage?"** → it outputs a bounding box around the damaged region. It is purely spatial.
- **Car-*part* identification** answers **"What component is in that region?"** → it maps the region to a label like *front bumper*. It is semantic — it names the object.
- **Damage-*type* classification** answers **"What kind of damage is this?"** → *dent / scratch / crack*. It describes the nature of the damage.

A single photo region can carry all three answers at once: *a dent (type) on the front bumper (part), located here (area).* In practice these are often combined into one multi-label detector, but conceptually they are three different questions, and the price estimate depends on getting all three right.

---

## 6. Price Estimation System

Once the system knows the part, it builds a search using everything available:

- **Vehicle brand and model** (e.g. Toyota Corolla)
- **Production year**, when identified or supplied by the user
- **Part name** (e.g. front bumper cover)
- **OEM or part number**, when it can be resolved — this gives the most precise match
- **Part condition options:** new, used, or aftermarket
- **Local and international marketplaces**, which matters a great deal in markets where most parts are imported

From the listings it gathers, the system filters out obvious outliers and computes a robust range rather than a single number. The final estimate can combine:

- **Part price** (or a range across conditions: aftermarket cheapest, OEM most expensive)
- **Estimated labor cost** (rule-based or looked up per part/operation)
- **Delivery cost**
- **Import or customs cost** — significant for imported parts in regions like Azerbaijan
- **A repair-versus-replacement recommendation** (explained below)
- **A minimum and maximum** total

**Repair vs. replace logic:** shallow scratches and small dents are often *repairable*, which is labor-heavy but avoids buying a new part. Cracks, shattered glass, broken lamps, and structural deformation usually require *replacement*. The system uses the detected damage type and part to lean one way or the other, and presents both options so the user decides.

> **Honesty about accuracy:** This is an **indicative price range based on available online data**, not a guaranteed final cost. Prices change, listings vary in quality, and the real number depends on the specific shop, the exact part variant, and hidden damage that a photo cannot reveal. We always present a range and never a single "guaranteed" figure.

---

## 7. Main Advantages

- **Faster initial assessment** — seconds from a phone, instead of driving between shops.
- **Greater price transparency** — an independent reference point the driver controls.
- **Less dependence on subjective estimates** — a baseline to sanity-check any single quote.
- **Convenience for owners** — no appointment needed for a first read on the damage.
- **Support for insurance pre-assessment** — a fast, consistent first-pass triage of claims.
- **Assistance for repair shops** — a quick documentation and quoting aid.
- **Repair-vs-replacement comparison** — helps the owner choose the cheaper sensible option.
- **Reduced inspection time** — automated first assessment shortens the manual process.
- **Digital report generation** — a shareable, savable record of the damage and estimate.
- **Better decision-making** — the owner negotiates and decides from a position of information.
- **Potential reduction of insurance fraud** — consistent, photo-anchored, timestamped assessments are harder to manipulate than verbal claims.
- **Accessibility for non-experts** — drivers with little automotive knowledge get a clear, named result.

---

## 8. Target Users

- **Individual vehicle owners** — the core user: instant clarity and a cost baseline after an accident.
- **Insurance companies** — fast, standardized pre-assessment and claim triage; documentation for low-value claims.
- **Car repair shops** — a quick estimating and customer-documentation tool.
- **Car rental companies** — rapid damage logging at vehicle return (handover/return inspection).
- **Fleet-management companies** — consistent assessment across many vehicles and drivers.
- **Used-car marketplaces** — objective condition reporting to build buyer trust.
- **Vehicle inspection services** — a digital first-pass that speeds up and standardizes their workflow.

---

## 9. Example Scenario

A driver has a minor collision and uploads a photo of the **front of their white Toyota Corolla**.

1. **Vehicle ID:** The app recognizes a white Toyota Corolla (with a confidence score), and offers the driver a chance to confirm or correct the year.
2. **Damage detection:** It draws boxes over two damaged regions on the front of the car.
3. **Part identification:** Both regions are mapped to the **front bumper**.
4. **Damage classification:** One region is tagged **dent (91%)**, the other **scratch (86%)**.
5. **Price search:** Using *Toyota Corolla + front bumper + year*, the system searches marketplaces and collects compatible bumper listings (new, used, aftermarket).
6. **Cost estimation:** It produces two options:
   - **Repair** (smooth the dent, refinish the scratch): an estimated labor-driven range.
   - **Replace** (new/aftermarket bumper + fitting + delivery/customs): a higher range.
7. **Result shown to the user:**
   > *Vehicle: White Toyota Corolla · Damaged part: Front bumper · Damage: Dent + Scratch*
   > *Recommendation: Repair likely sufficient (no crack detected)*
   > *Repair estimate: ~80–140 AZN · Replacement estimate: ~220–360 AZN*
   > *This is a preliminary AI estimate. Final cost should be confirmed by a professional.*
8. **Report:** A one-page summary with the annotated photo, detected parts, damage types, confidences, prices, and the disclaimer — ready to save or share.

In under a minute, the driver moves from "I have no idea what this will cost" to "I have a credible range and a recommendation I can take to a shop."

*(Note: the AZN figures above are illustrative placeholders for the demo, not measured outputs.)*

---

## 10. Innovation and Unique Value

Most academic and open-source projects in this space stop at one step: **"here is the damage."** They detect a scratch or a dent and end there. That's a model, not a product.

Our value is that we connect the **entire decision chain** after an accident into one flow:

**Vehicle identification → damage detection → damaged-part recognition → damage classification → online part-price retrieval → repair-cost estimation → report generation.**

The innovation isn't a single novel model — it's the **integration**. We take the output of computer vision and push it all the way to the question the user actually cares about: *what do I do, and what will it cost?* A damage detector tells you something is wrong. **[App Name]** helps you decide what to do about it. That end-to-end, decision-support framing — combined with region-specific cost reality like import and customs — is what makes it more than a demo of object detection.

---

## 11. Technical Architecture

A simple, high-level view suitable for a slide:

> **Mobile / Web interface → Backend API → AI image-analysis models → Vehicle & part database → Online price-search module → Cost-estimation engine → Report-generation module**

Responsibilities of each component:

- **Mobile / Web interface** — captures or uploads photos, shows annotated results, confidence scores, the cost range, and the report. This is what the user touches.
- **Backend API** — the coordinator. It receives images, calls the models in order, manages the price search, assembles the final result, and returns it to the interface.
- **AI image-analysis models** — the vision core: damage detection (bounding boxes), part identification, damage-type classification, and vehicle recognition. Outputs labels, boxes, and confidence scores.
- **Vehicle & part database** — reference data: how detected parts map to real catalog parts, common part numbers, and labor references that feed the estimate.
- **Online price-search module** — queries marketplaces and the web for current part prices using model/year/part/part-number, and filters the results.
- **Cost-estimation engine** — combines part price + labor + delivery/customs, removes outliers, applies repair-vs-replace logic, and outputs a min–max range.
- **Report-generation module** — packages the annotated image, findings, prices, recommendation, and disclaimer into a clean, shareable report.

The design is **modular**: each block can be improved or swapped independently, which is exactly how we'd evolve from MVP to product.

---

## 12. Challenges and Limitations

We're upfront about the hard parts — and for each, the path forward.

- **Image quality and lighting.** Blurry, dark, or reflective photos hurt detection. → *Guide the user to take clearer photos, validate image quality before analysis, and train on augmented (varied-lighting) data.*
- **Different camera angles.** The same damage looks different from different viewpoints. → *Use multi-angle training data and, in future, fuse multiple photos of the same damage.*
- **Hidden internal damage.** A photo cannot show bent frames or mechanical damage. → *State this limitation clearly; future work can combine photos with other signals (sensor/OBD data, repair history).*
- **Similar-looking vehicle models.** Many cars look alike, so make/model can be wrong. → *Treat it as a correctable best guess and let the user confirm; improve with better recognition models over time.*
- **Regional price differences.** A part costs differently across markets. → *Prioritize local marketplaces and make region a configurable input.*
- **Rapidly changing online prices.** Listings move fast. → *Query at assessment time, present a range, and timestamp the estimate.*
- **Parts availability.** A part may be out of stock or rare. → *Show multiple condition options (new/used/aftermarket) and flag low availability.*
- **Model confidence and false detections.** No model is perfect; it can miss or hallucinate damage. → *Always display confidence scores, set sensible thresholds, and keep the human in the loop.*
- **Visible vs. actual mechanical damage.** What looks minor may be serious underneath (and vice versa). → *Frame every output as preliminary and recommend professional confirmation.*

The honest summary: this is a **decision-support tool with known boundaries**, and we design the UX so the user always understands those boundaries.

---

## 13. Future Improvements

*(All items below are future work, beyond the current MVP.)*

- **Damage-severity estimation** — scoring how serious each damage is, not just its type.
- **Multiple-photo or video analysis** — a full walk-around for more complete coverage.
- **3D vehicle reconstruction** — assembling a 3D view from several photos for better localization.
- **Direct insurance integration** — feeding assessments straight into claim systems.
- **Local repair-shop integration** — real quotes and availability from nearby shops.
- **Automatic appointment booking** — from assessment to a scheduled repair in one tap.
- **More accurate labor-cost estimation** — region- and shop-specific labor models.
- **Historical price tracking** — trends over time for better, more stable estimates.
- **Internal/mechanical damage detection** — using sensor, OBD, or history data alongside photos.
- **Broader coverage** — more vehicle brands, more part categories, more damage types.

---

## 14. Jury Presentation Speech *(≈3–4 minutes)*

> Deliver this naturally. Pause after the problem and after the example. Make eye contact on the disclaimer — juries reward honesty.

Good [morning / afternoon], everyone. Thank you for the chance to present our project.

Let me start with a moment most drivers know too well. You've just had a small accident. No one is hurt — but your car is damaged, and immediately the questions begin. Which parts are actually broken? How serious is it? How much will this cost to fix? You call one repair shop and get one price. You call another and get a completely different one. You feel uncertain, and honestly, a little powerless.

This is the problem our project solves. We built **[App Name]**, an AI-powered car damage assessment application. The idea is simple: take a photo of the damage, and in seconds get a clear, preliminary assessment of what is damaged and what it might cost.

Here is how it works. The user uploads one or more photos of the car after an accident, and our system does several things. First, it recognizes basic information about the vehicle — the color, and where possible the make and model. Second, it detects the damaged areas and draws boxes around them, so you can see exactly what the AI is looking at. Third, it identifies which part is affected — the bumper, the door, the headlight. And fourth, it classifies the type of damage — is it a dent, a scratch, or a crack? Every detection comes with a confidence score, so the user always knows how sure the system is.

Then comes the part that makes us different. Most damage-detection projects stop at "here is the damage." We go one step further. Once we know the part and the type of damage, our system searches online marketplaces for the price of that part — new, used, or aftermarket. It combines that with an estimated labor cost and, importantly for our region, delivery and customs costs. The result is an indicative price range, from a minimum to a maximum, plus a simple recommendation: is this damage better repaired, or is replacement the smarter option? Finally, everything is collected into a clean digital report the user can save or share.

Let me give a quick example. Imagine someone uploads a photo of a Toyota Corolla with a damaged front bumper. Our app recognizes the car, detects a dent and a scratch on the bumper, identifies the part, and searches for compatible bumper prices. It then shows a repair estimate in one range, a replacement estimate in another, and a recommendation. In under a minute, the driver goes from total uncertainty to a clear starting point.

Now, I want to be honest about what this is — and what it is not. Our application gives a *preliminary*, AI-based assessment. It does not replace a professional mechanic, an insurance expert, or an official inspection. A photo cannot show hidden mechanical damage, and online prices change. That's why we present a *range*, not a guaranteed number, and why we always show confidence levels.

But the value is real. Faster initial assessment. Far more price transparency. Less dependence on one shop's subjective estimate. And it's useful not only for individual drivers, but for insurance companies doing pre-assessment, for repair shops, for rental and fleet companies, and for used-car marketplaces.

Looking ahead, we see a clear path: damage-severity scoring, video and multi-angle analysis, VIN-based identification, and direct integration with insurers and local repair shops.

In short, we set out to answer one stressful question — *"what's damaged, and what will it cost?"* — quickly, transparently, and in a way anyone can use. That is what **[App Name]** does.

Thank you. We'd be happy to take your questions.


