# Results - Standard mode (standard-on-gpo)

Document: `GPO-Anual-report.pdf` (274 chunks, 274 newly embedded). Config: k=5, min score 0.62, temperature 0.7, chat `gemini-3.1-flash-lite`, embeddings `models/gemini-embedding-001`.

**core 3/3, extended 8/8, refusals 4/4; page metrics n/a (this mode stores no pages)**

- context sent to the model: avg 946 est. tokens (max 984)

Answer correctness is an automatic substring check (a convenience); retrieval is the raw top-k before the relevance floor. Regenerate with `PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode standard --pdf samples/GPO-Anual-report.pdf --questions eval/questions/report.json --label standard-on-gpo`.

## Per question

| ID | Question | Answer | Pass | Gold rank | Retrieved (page, kind) | Filter |
|---|---|---|---|---|---|---|
| Q1 | How many depository libraries did GPO staff visit in FY 2018? | In FY 2018, GPO staff visited 166 depository libraries. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| Q2 | What new digital system replaced FDsys, and when was it fully deployed? | The new digital system that replaced FDsys is called **govinfo**. It was moved out of beta in December 2017 and was scheduled to be fully deployed with the retirement of FDsys in December 2018. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| Q3 | How much did GPO procure in printing and information products in FY 2018 on behalf of federal agencies? | In FY 2018, the GPO procured approximately $375.7 million worth of printing and other information products on behalf of federal agencies. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E1 | How many people did GPO employ in FY 2018? | In FY 2018, the GPO employed 1,737 staff. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E2 | What were GPO's FY 2018 revenues? | GPO's revenue for FY 2018 totaled $874.5 million. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E3 | How many passports did GPO produce in FY 2018? | In FY 2018, the GPO produced 15,901,600 passports. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E4 | How many copies of how many titles were distributed to depository libraries? | In FY 2018, the FDLP distributed more than 802,834 tangible copies of 4,211 titles to depository libraries nationwide. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E5 | How many titles did GPO catalog in FY 2018? | In FY 2018, the GPO cataloged a total of 34,367 titles. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E6 | How many titles does govinfo make available online? | As of FY 2018, govinfo makes more than 2.5 million titles available online. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E7 | How many FDLP Academy webinars were held and how many participants attended? | In FY 2018, the FDLP Academy hosted 85 webinars with 10,214 combined registrants. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| E8 | What was GPO's net income in FY 2018? | GPO's net income in FY 2018 was $52.6 million. | yes | - | [(None, 'text'), (None, 'text'), (None, 'text'), (None, 'text'), (None, 'text')] | - |
| N1 | What were GPO's revenues in FY 2020? | I do not have information regarding GPO's revenues in FY 2020 in the provided documents. The documents only contain financial data for fiscal years 2014 through 2018. | yes | - | - | - |
| N2 | Who is the current Public Printer of the United States? | I do not have that information in the provided documents. | yes | - | - | - |
| N3 | What is the capital of France? | I don't have that information in the documents. | yes | - | - | - |
| N4 | How many employees did GPO have in FY 2015? | I do not have the information regarding the number of GPO employees in FY 2015 in the provided documents. The documents include an employment table that lists headcount for the years 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2016, 2017, and 2018. | yes | - | - | - |
