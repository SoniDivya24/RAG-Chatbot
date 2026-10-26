# Results - Standard mode (standard-on-imac)

Document: `iMac_PER_Oct2024.pdf` (42 chunks, 0 newly embedded). Config: k=5, min score 0.62, temperature 0.7, chat `gemini-3.1-flash-lite`, embeddings `models/gemini-embedding-001`.

**core 3/3, extended 12/14, refusals 4/4; page metrics n/a (this mode stores no pages)**

Answer correctness is an automatic substring check (a convenience); retrieval is the raw top-k before the relevance floor. Regenerate with `PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode standard --pdf samples/iMac_PER_Oct2024.pdf --questions eval/questions/visual.json --label standard-on-imac`.

## By content type

| Content type | n | answers correct | page hit@3 / hit@5 / MRR | evidence in context |
|---|---|---|---|---|
| prose | 2 | 2/2 | n/a | 2/2 |
| table | 5 | 5/5 | n/a | 5/5 |
| call-out | 4 | 4/4 | n/a | 4/4 |
| chart | 2 | 1/2 | n/a | 2/2 |
| footnote | 4 | 3/4 | n/a | 3/4 |
| refusal | 4 | 4/4 | n/a | - |
| ALL | 21 | 19/21 | n/a | 16/17 |

## Per question

| ID | Question | Answer | Pass | Gold rank | Retrieved (page, kind) |
|---|---|---|---|---|---|
| Q1 | How much less energy does iMac use compared to the ENERGY STAR requirement? | iMac uses 58 percent less energy than the requirement for ENERGY STAR. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| Q2 | What is the total carbon footprint of the iMac, and how much of that comes from product use versus manufacturing? | The total carbon footprint depends on the model configuration:  *   **iMac (two ports) 256GB:** 346 kg CO2e *   **iMac (four ports) 512GB:** 391 kg CO2e  For the **iMac (two ports) 256GB** model, the distribution of life cycle emissions is as follows:  *   **Production:** 50% (173 kg CO2e) *   **Product use:** 45% (155.7 kg CO2e) | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| Q3 | What material is the iMac stand made from, and what percentage of it is recycled? | The iMac stand is made from 100 percent recycled aluminum. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| C1 | What was the baseline emissions figure, and how many kilograms did the reductions remove? | The baseline emissions figure is 445 kg CO2e, and the emissions reductions removed 99 kg. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| C2 | Which categories of reductions are shown between baseline and final emissions? | Based on the provided documents, the following categories of reductions are identified as contributing to the difference between baseline emissions and the final product footprint:  *   **Recycled and low-carbon materials:** The use of recycled content (such as 100 percent recycled aluminum in the stand) reduced total product emissions by about 13 percent. *   **Low-carbon electricity for manufacturing:** Transitions by suppliers to low-carbon electricity sources have reduced product emissions by 5 percent. *   **Other reductions:** The report notes a total emissions reduction of 99 kg when comparing the baseline to the final iMac emissions. (Note: The documents also mention that Apple accounts for the emissions necessary to generate low-carbon electricity, such as the manufacturing and maintenance of renewable energy infrastructure like wind and solar farms, within their calculations). | **NO** | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| T1 | What is the power consumption in sleep mode at 115V? | The power consumption for the iMac in sleep mode at 115V is 0.57W. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| T2 | What is the idle (display on) power consumption at 230V? | The power consumption for the iMac in the "Idle—Display On" mode at 230V is 20.9W. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| T3 | What is the power adapter efficiency at 100V? | The power adapter efficiency at 100V is 91.1%. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| T4 | What is the carbon footprint of the four-port 512GB iMac? | The carbon footprint of the iMac (four ports) 512GB configuration is 391 kg CO2e. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| F1 | Is iMac free of PVC and phthalates, and are there exceptions? | The iMac is generally free of PVC and phthalates. However, there are exceptions for AC power cords in India, Thailand (specifically for 2-prong AC power cords), and South Korea, where Apple is still seeking government approval for the replacement of these substances. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| F2 | Does the 100% recycled copper claim apply to every iMac? | No. According to the provided documents, the use of 100 percent recycled copper in thermal module components applies to the iMac (four ports) only. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| F3 | What counts as recycled content in the more-than-15-percent claim? | The documents do not provide a specific breakdown of which materials are included in the "more than 15 percent recycled content" calculation for the iMac. However, the text notes that the company currently quantifies carbon savings from the use of recycled aluminum, titanium, stainless steel, lithium, cobalt, tungsten, and gold in select parts for select products, and mentions that it plans to improve its accounting of recycled content over time. | **NO** | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| F4 | How is Zero Waste to Landfill verified for iMac? | For established iMac final assembly supplier sites, Zero Waste to Landfill is third-party verified by UL LLC according to the UL 2799 Standard. This standard requires at least 90 percent diversion through methods other than waste-to-energy to receive a designation. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| K1 | What percent of the packaging is fiber-based, and how much recycled content does the fiber packaging have? | 100% of the iMac packaging is fiber-based, and the fiber packaging contains 76% recycled content. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| K2 | How much recycled plastic does iMac use, and in how many components? | The iMac uses at least 50 percent recycled plastic in 13 components. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| K3 | What share of total rare earth elements is covered by the recycled rare earths in magnets? | Recycled rare earth elements in magnets represent 99 percent of the total rare earth elements in the device. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| P1 | How long is the assumed use period for macOS devices? | Apple assumes a four-year period for power use by first owners for macOS devices. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] |
| N1 | What is the iMac's battery capacity? | I do not have information about the iMac's battery capacity in the provided documents. | yes | - | - |
| N2 | How much does the iMac weigh? | I do not have the information regarding the total weight of the iMac in the provided documents. | yes | - | - |
| N3 | What is the carbon footprint of the 24-inch M5 iMac? | I do not have information about a 24-inch M5 iMac in the provided documents. The documents only contain carbon footprint data for the iMac (two ports) 256GB (346 kg CO2e) and the iMac (four ports) 512GB (391 kg CO2e). | yes | - | - |
| N4 | Who is the CEO of Apple? | I do not have that information in the documents. | yes | - | - |
