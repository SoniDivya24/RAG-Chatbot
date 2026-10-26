# Results - Report mode

Document: `GPO-Anual-report.pdf` (263 chunks, 0 newly embedded). Config: k=5, min score 0.68, temperature 0.0, chat `gemini-3.1-flash-lite`, embeddings `models/gemini-embedding-001`.

**core 3/3, extended 8/8, refusals 4/4; hit@3 0.82, hit@5 0.91, MRR 0.84**

Answer correctness is an automatic substring check (a convenience); retrieval is the raw top-k before the relevance floor. Regenerate with `PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode report`.

## Per question

| ID | Question | Answer | Pass | Gold rank | Retrieved (page, kind) |
|---|---|---|---|---|---|
| Q1 | How many depository libraries did GPO staff visit in FY 2018? | GPO staff visited 166 depository libraries in FY 2018 (p. 5, p. 21). | yes | 1 | [(21, 'text'), (5, 'text'), (21, 'text'), (19, 'text'), (19, 'text')] |
| Q2 | What new digital system replaced FDsys, and when was it fully deployed? | The new digital system that replaced FDsys is govinfo (p. 10, 22). It was scheduled to be completely retired and replaced by govinfo in December 2018 (p. 22). | yes | 1 | [(22, 'text'), (10, 'text'), (39, 'text'), (22, 'text'), (46, 'text')] |
| Q3 | How much did GPO procure in printing and information products in FY 2018 on behalf of federal agencies? | GPO procured more than $375 million worth of printing and other information products in FY 2018 (p. 5). The value of this work was approximately $375.7 million (p. 14, p. 15, p. 17). | yes | 1 | [(5, 'text'), (14, 'text'), (15, 'text'), (17, 'text'), (25, 'text')] |
| E1 | How many people did GPO employ in FY 2018? | GPO employed 1,737 staff in FY 2018 (p. 7, 12, 14, 15). | yes | 1 | [(14, 'text'), (15, 'text'), (12, 'text'), (7, 'text'), (6, 'text')] |
| E2 | What were GPO's FY 2018 revenues? | GPO's revenues for FY 2018 totaled $874.5 million (p. 6, p. 43). | yes | - | [(6, 'text'), (27, 'text'), (43, 'text'), (27, 'text'), (25, 'text')] |
| E3 | How many passports did GPO produce in FY 2018? | GPO produced 15,901,600 passports in FY 2018 (p. 14, 15). | yes | 4 | [(6, 'text'), (18, 'text'), (6, 'text'), (14, 'text'), (15, 'text')] |
| E4 | How many copies of how many titles were distributed to depository libraries? | In FY 2018, GPO distributed 802,834 copies of 4,211 titles to depository libraries (p. 5, p. 19). | yes | 1 | [(19, 'text'), (19, 'text'), (19, 'text'), (39, 'text'), (5, 'text')] |
| E5 | How many titles did GPO catalog in FY 2018? | GPO cataloged a total of 34,367 titles in FY 2018 (p. 5, 15). | yes | 1 | [(19, 'text'), (5, 'text'), (15, 'text'), (23, 'text'), (19, 'text')] |
| E6 | How many titles does govinfo make available online? | govinfo makes more than 2.5 million Federal titles available (p. 8, 22). | yes | 1 | [(22, 'text'), (22, 'text'), (8, 'text'), (22, 'text'), (19, 'text')] |
| E7 | How many FDLP Academy webinars were held and how many participants attended? | In FY 2018, the FDLP Academy hosted 85 webinars with 10,214 combined registrants (p. 20). | yes | 1 | [(5, 'text'), (20, 'text'), (20, 'text'), (21, 'text'), (21, 'text')] |
| E8 | What was GPO's net income in FY 2018? | GPO had a net income of $52,624,000 in fiscal 2018 (p. 44). | yes | 1 | [(44, 'text'), (27, 'text'), (27, 'text'), (26, 'text'), (6, 'text')] |
| N1 | What were GPO's revenues in FY 2020? | I could not find this in the document. | yes | - | - |
| N2 | Who is the current Public Printer of the United States? | I could not find this in the document. | yes | - | - |
| N3 | What is the capital of France? | I could not find this in the document. | yes | - | - |
| N4 | How many employees did GPO have in FY 2015? | I could not find this in the document. | yes | - | - |
