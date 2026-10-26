# Results - Visual document mode

Document: `iMac_PER_Oct2024.pdf` (89 chunks, 0 newly embedded). Config: k=5, min score 0.68, temperature 0.0, chat `gemini-3.1-flash-lite`, embeddings `models/gemini-embedding-001`.

**core 3/3, extended 14/14, refusals 4/4; hit@3 1.00, hit@5 1.00, MRR 0.93**

Answer correctness is an automatic substring check (a convenience); retrieval is the raw top-k before the relevance floor. Regenerate with `PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode visual`.

## By content type

| Content type | n | answers correct | page hit@3 / hit@5 / MRR | evidence in context |
|---|---|---|---|---|
| prose | 2 | 2/2 | 2/2 / 2/2 / 1.00 | 2/2 |
| table | 5 | 5/5 | 5/5 / 5/5 / 1.00 | 5/5 |
| call-out | 4 | 4/4 | 4/4 / 4/4 / 1.00 | 4/4 |
| chart | 2 | 2/2 | 2/2 / 2/2 / 0.75 | 2/2 |
| footnote | 4 | 4/4 | 4/4 / 4/4 / 0.83 | 4/4 |
| refusal | 4 | 4/4 | n/a | - |
| ALL | 21 | 21/21 | 17/17 / 17/17 / 0.93 | 17/17 |

## Per question

| ID | Question | Answer | Pass | Gold rank | Retrieved (page, kind) |
|---|---|---|---|---|---|
| Q1 | How much less energy does iMac use compared to the ENERGY STAR requirement? | iMac uses 58 percent less energy than the requirement for ENERGY STAR (p. 7). | yes | 1 | [(7, 'prose'), (7, 'prose'), (7, 'footnoted claim'), (7, 'footnoted claim'), (12, 'endnote')] |
| Q2 | What is the total carbon footprint of the iMac, and how much of that comes from product use versus manufacturing? | The total product footprint of the iMac (two ports) 256GB is 346 kg CO2e (p. 10).  Regarding the distribution of life cycle product emissions (scope 3): *   Production accounts for 50% (p. 10). *   Product use accounts for 45% (p. 10).  Computed from these figures, the emissions are 173 kg CO2e for production and 155.7 kg CO2e for product use (p. 10).  *Note: Greenhouse gas emissions were calculated using a life cycle assessment methodology in accordance with ISO 14040, 14044, and 14067 standards and based on iMac (two ports) with 512GB storage configuration (p. 2, p. 11).* | yes | 1 | [(10, 'table'), (11, 'endnote'), (2, 'footnoted claim'), (10, 'prose'), (2, 'chart')] |
| Q3 | What material is the iMac stand made from, and what percentage of it is recycled? | The iMac stand is made from aluminum, which is 100 percent recycled (p. 1, p. 4). | yes | 1 | [(1, 'call-out'), (4, 'footnoted claim'), (4, 'call-out'), (4, 'prose'), (2, 'prose')] |
| C1 | What was the baseline emissions figure, and how many kilograms did the reductions remove? | The baseline emissions figure was "445 kg" and the reductions removed "99 kg" (p. 2). | yes | 2 | [(10, 'footnoted claim'), (2, 'chart'), (2, 'footnoted claim'), (11, 'endnote'), (2, 'footnoted claim')] |
| C2 | Which categories of reductions are shown between baseline and final emissions? | The categories of reductions shown are "Recycled and low-carbon materials," "Low-carbon electricity," and "Non-air shipping" (p. 2). | yes | 1 | [(2, 'chart'), (10, 'footnoted claim'), (2, 'footnoted claim'), (2, 'footnoted claim'), (11, 'endnote')] |
| T1 | What is the power consumption in sleep mode at 115V? | The power consumption in sleep mode at 115V is 0.57W (p. 12). | yes | 1 | [(12, 'table'), (12, 'endnote'), (7, 'footnoted claim'), (7, 'footnoted claim'), (7, 'prose')] |
| T2 | What is the idle (display on) power consumption at 230V? | The idle (display on) power consumption at 230V is 20.9W (p. 12). | yes | 1 | [(12, 'table'), (12, 'endnote'), (7, 'footnoted claim'), (7, 'footnoted claim'), (7, 'prose')] |
| T3 | What is the power adapter efficiency at 100V? | The power adapter efficiency at 100V is 91.1% (p. 12). | yes | 1 | [(12, 'table'), (12, 'endnote'), (7, 'footnoted claim'), (7, 'footnoted claim'), (7, 'prose')] |
| T4 | What is the carbon footprint of the four-port 512GB iMac? | The carbon footprint of the iMac (four ports) 512GB is 391 kg CO2e (p. 10). | yes | 1 | [(10, 'table'), (11, 'endnote'), (2, 'footnoted claim'), (10, 'table'), (10, 'prose')] |
| F1 | Is iMac free of PVC and phthalates, and are there exceptions? | iMac is free of PVC and phthalates, except for AC power cords in India, Thailand (for 2-prong AC power cords), and South Korea (p. 4, 11). | yes | 1 | [(4, 'footnoted claim'), (4, 'prose'), (11, 'endnote'), (1, 'call-out'), (6, 'footnoted claim')] |
| F2 | Does the 100% recycled copper claim apply to every iMac? | No. The 100 percent recycled copper in the thermal module applies to iMac (four ports) only (p. 4, p. 11). | yes | 1 | [(4, 'call-out'), (11, 'endnote'), (4, 'footnoted claim'), (1, 'call-out'), (1, 'call-out')] |
| F3 | What counts as recycled content in the more-than-15-percent claim? | Product recycled or renewable content is the mass of certified recycled material relative to the overall mass of the device, not including packaging or in-box accessories (p. 4). | yes | 3 | [(4, 'footnoted claim'), (2, 'footnoted claim'), (11, 'endnote'), (4, 'call-out'), (6, 'call-out')] |
| F4 | How is Zero Waste to Landfill verified for iMac? | Established final assembly supplier sites for iMac are third-party verified as Zero Waste by UL LLC (UL 2799 Standard) (p. 5, p. 11).  [^16]: UL requires at least 90 percent. | yes | 1 | [(5, 'call-out'), (11, 'endnote'), (4, 'footnoted claim'), (1, 'footnoted claim'), (2, 'footnoted claim')] |
| K1 | What percent of the packaging is fiber-based, and how much recycled content does the fiber packaging have? | The packaging is 100 percent fiber-based (p. 6), and the fiber packaging contains 76% recycled content (p. 6). | yes | 1 | [(6, 'call-out'), (1, 'call-out'), (6, 'call-out'), (6, 'prose'), (6, 'footnoted claim')] |
| K2 | How much recycled plastic does iMac use, and in how many components? | iMac uses at least 50 percent recycled plastic in 13 components (p. 4). | yes | 1 | [(4, 'footnoted claim'), (4, 'prose'), (1, 'call-out'), (1, 'call-out'), (4, 'call-out')] |
| K3 | What share of total rare earth elements is covered by the recycled rare earths in magnets? | Recycled rare earth elements in magnets represent 99 percent of the total rare earth elements in the device (p. 4). | yes | 1 | [(4, 'call-out'), (4, 'prose'), (4, 'footnoted claim'), (2, 'footnoted claim'), (11, 'endnote')] |
| P1 | How long is the assumed use period for macOS devices? | The assumed use period for macOS devices is four years (p. 9). | yes | 1 | [(9, 'prose'), (7, 'prose'), (1, 'call-out'), (2, 'footnoted claim'), (7, 'prose')] |
| N1 | What is the iMac's battery capacity? | I could not find this in the document. | yes | - | - |
| N2 | How much does the iMac weigh? | I could not find this in the document. | yes | - | - |
| N3 | What is the carbon footprint of the 24-inch M5 iMac? | I could not find this in the document. | yes | - | - |
| N4 | Who is the CEO of Apple? | I could not find this in the document. | yes | - | - |
