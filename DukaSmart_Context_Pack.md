# DUKASMART CONTEXT PACK (replaces the guide PDF, draft docx and slides)

Author: Richard Musili Mwendwa, SCT222-0320/2022. BSc Business Computing, JKUAT, School of Computing and Information Technology, Department of Information Technology. Supervisor: Dennis Njagi. Year: 2026.

RULE: The attached CODE and real outputs are the source of truth. Where this pack and the code disagree, follow the code and list the difference in your reply.

---
## PART A. JKUAT IT DEPARTMENT GUIDE (condensed, authoritative)

### Formatting
- Except the title page: Times New Roman 12 pt, 1.5 line spacing.
- APA format for referencing. Each chapter starts on a new page. All figures/tables captioned in APA style.
- Paragraphing consistent: indent OR blank line, never both. No one-sentence paragraphs. Minimum five sentences per paragraph.
- Figures/tables labelled by chapter (Figure 1.1, Table 3.2).

### Title page (all on ONE centred page)
- Title: concise, captures research area and problem domain, no abbreviations, no "A study of / An investigation of". Bold, 16 pt, centred.
- Author full name (no "By", no initials), plus supervisor name.
- Affiliation statement, 14 pt, italic, centred: "A research project submitted to the Department of Information Technology in the School of Computing and Information Technology in partial fulfilment of the requirements for the award of the degree of Bachelor of Science in Business Computing of Jomo Kenyatta University of Agriculture and Technology." Year below it.

### Front matter order
Title page; Declaration (candidate and supervisor, with signature and date lines: "This research project is my original work and has not been presented for a degree in any other University" / "This research project has been submitted for examination with my approval as University Supervisor"); Abstract (max 1 page: problem, research area, proposed solution, methodology, expected outcome); Table of Contents; List of Tables; List of Figures; Acronyms; Definition of terms (non-common terms only).
- Roman-numeral page numbers start at the Declaration page.
- TOC: column headings "CHAPTER" and "PAGE" once at the top; chapter titles CAPS and bold; subheadings title case with dot leaders and page numbers; also lists References and Appendices.

### CHAPTER 1 INTRODUCTION (sections exactly)
1.1 Background: show genesis of the problem; global perspective then local.
1.2 Project Overview: introduce research area formally; global then local; briefly introduce key computational principles.
1.3 Statement of the Problem: exactly what the problem is, why and how it is a problem, with statistics/evidence derived from the background; magnitude and effects; must reflect current technology trends; NOT just "paper to digital"; tied to the title.
1.4 Proposed Solution: what will be developed ("This research seeks to..."), research component explicit, key operations, compare recent models globally and regionally, no outdated technology.
1.5 Objectives: ONE general objective in line with the title; 3 to 4 specific objectives (research, design, implementation, testing), numbered, SMART, simple statements, student-level, measurable within 8 months.
1.6 Research Questions: equal in number to specific objectives, numbered, real questions, broad, not answerable in a few words, about research areas not the client or prototype.
1.7 Justification: why the research, who benefits, why the solution solves the problem, contribution to the research area, relevance now.
1.8 Proposed System Methodologies: outline only; tools and techniques contextualised; justify choices; cover the research life cycle.
1.9 Scope: geographic area/target group, limitations (data, methodology, resources; time is NOT a limitation), what the project is confined to.

### CHAPTER 2 LITERATURE REVIEW
2.1 Introduction (topic and relevance, background of technology in the application area, purpose and objectives of the review).
2.2 Theoretical Review (key concepts, theoretical divisions/schools of thought, advantages and limitations of each).
2.3 Case Study Review (applications of the topic in the domain; key implementations, successes and misses).
2.4 Integration and Architecture (options for integrating the technology into the application; design architectures/frameworks).
2.5 Summary.
2.6 Research Gaps (and how this research resolves them).
References: minimum 10 peer-reviewed; mostly not older than 5 years.

### CHAPTER 3 SYSTEM ANALYSIS AND DESIGN
3.1 Introduction. 3.2 Systems Development Methodology (introduced before implementation). 3.3 Feasibility Study (economic, technical, operational, others).
3.4 Requirements Elicitation / Data Collection: tool, preparation, administration (attached as appendix, approved by supervisor), sampling technique and sample size, data relevant to the objectives and useful for deducing requirements.
3.5 Data Analysis: statistical tools (Excel/SPSS) with pie/bar/line charts.
3.6 System Specification: functional and non-functional requirements.
3.7 Requirements Analysis and Modelling: dependencies, conflicts; low-level DFDs, use case diagrams, conceptual and analysis class diagrams.
3.8 Logical Design: 3.8.1 System Architecture (high-level structure, components, patterns such as client-server/layered; class and component diagrams); 3.8.2 Control Flow and Process Design (flowchart/activity, sequence, state chart, detailed DFDs, pseudocode); 3.8.3 Design for non-functional requirements (security, error and exception handling, efficiency/appeal).
3.9 Physical Design: 3.9.1 Database Design (schema, tables, fields, relationships, DBMS choice, integrity, security, indexing, query optimisation); 3.9.2 User Interface Design (input/output forms, wireframes).

### CHAPTER 4 SYSTEM IMPLEMENTATION AND TESTING, CONCLUSIONS AND RECOMMENDATIONS
4.1 Introduction. 4.2 Environment and Tools (backend, frontend, middle layers). 4.3 System Code Generation (key processes with code snippets).
4.4 Testing: strategy and objectives (build quality, demonstrate working capability, assess progress/suitability); verification (smoke, stress, white box) and validation (usability, black box, acceptance); test scopes: GUI, usability (peers; evidence form), performance, white box (with flowcharts), load, regression, stress, smoke, unit, acceptance, black box, functional, integration (top-down/bottom-up), security, portability/compatibility, conformance. Minimum 20 test cases covering each module: Test case ID, condition tested, input, expected result, actual result, pass/fail. Screenshots of tests at various stages.
4.5 User Guide (set-up and use instructions).
4.6 Conclusions (problem solved and to what extent; accomplishments; limitations; challenges: skills, money, tools; time is NOT a limitation).
4.7 Recommendations (derived from the conclusions; future improvements).
References. Appendices: instruments, letters of introduction, interview transcripts/questionnaires, budget, project schedule, notes on testing.

---
## PART B. PROJECT FACTS FROM THE DRAFT AND SLIDES (verify against code)

**Draft title:** DukaSmart: A Web-Based Demand Forecasting and Inventory Decision Support System for Small Retail Shops in Nairobi County, Kenya. (Slides: "...and Budget-Constrained Inventory Decision Support". Use ONE final title with "Budget-Constrained".)

**Problem:** Small shops must decide what to restock, how much, and what to prioritise when funds are limited. Low stock alone is not enough: a low-stock item may sell slowly while another sells faster; products differ in cost, price and margin. When total replenishment cost exceeds the budget, competing needs must be compared transparently. Gap: record keeping does not tell the owner which product to prioritise.

**General objective:** To design, develop and evaluate an explainable web-based demand forecasting and budget-constrained inventory decision support system that assists small retail shops in Nairobi County to prioritise stock purchases using historical sales, current inventory, product economics and available purchasing budget.

**Specific objectives:** (1) Investigate sales recording, stock monitoring and purchasing practices of selected small shops in Nairobi County and identify information challenges affecting replenishment. (2) Determine an appropriate, interpretable short-term product-level forecasting approach. (3) Design and implement an explainable budget-constrained replenishment model combining stockout risk, forecast demand, expected gross profit and affordability into a prioritised purchase plan. (4) Evaluate the system for forecast accuracy, functional correctness, usability and recommendation consistency under different budget scenarios.

**Research questions (4, matching the objectives):** practices and constraints affecting replenishment; which interpretable forecasting approach suits the available data; how to combine forecast demand, stock, safety stock, cost, price, gross profit and budget into an explainable priority; what evaluation criteria suit forecast accuracy, functional correctness, usability and recommendation consistency.

**Methodology:** design science; mixed methods (questionnaires and short interviews, where feasible); Agile iterative development; time-ordered holdout forecast validation (MAE and RMSE); functional, integration, forecast, usability, security and budget-scenario testing.

**Scope:** selected small general-retail/FMCG shops in Nairobi County; single-shop prototype; product-level sales history. Out of scope: payments/M-Pesa, payroll, tax, HR, full accounting, multi-branch, supplier negotiation, autonomous procurement, full ERP, dynamic pricing, deep learning. Assumptions: product-level history available or constructed; cost and price known; records accurate; budget entered represents purchasing money; operator makes the final decision. Simulated or anonymised data may be used where real records cannot be disclosed.

**Workflow:** historical sales, demand forecast, expected demand, compare with stock, replenishment quantity, purchase cost, expected gross profit, budget check, prioritised list, user action (accept, change, skip).

**Formulas (verify in code):**
- Required replenishment = max(0, projected need - current stock). Projected need = forecast demand + safety stock (default 20%; the draft's wording "plus lead-time demand" must be checked against code).
- Estimated purchase cost = required replenishment x unit cost. Gross profit per unit = selling price - unit cost. Expected gross profit = forecast quantity x gross profit per unit.
- Stockout risk = shortage / projected need, bounded 0 to 1.
- Priority score = 0.40 R + 0.30 D + 0.20 G + 0.10 A, weights sum to 1.0. R used directly; D, G, A min-max normalised across candidates; affordability = 1/(1 + required cost) then normalised.
- Budget allocation: go down the ranked list; allocate as much of the remaining budget as possible; partial fills allowed; no automatic ordering.
- Forecast data rule: at least 10 non-zero observations and 28 days of history, else "insufficient data". 14-day time-ordered holdout, no shuffling. MAE and RMSE.
- Methods: draft and slides name moving average (baseline) and exponential smoothing (primary, statsmodels). The author's evaluate_system.py compares THREE methods: weighted_moving_average, simple_exponential_smoothing, gradient_boosting, and records which one the system selects. Use the code's truth.

**Recommendation record:** stores full reason and short priority reason; user can accept, change quantity, or skip; retained for review.

**Functional requirements (draft, 17):** FR01 secure sign-in; FR02 owner and staff roles; FR03 maintain products; FR04 record sales; FR05 record purchases; FR06 inventory movements as source of stock changes; FR07 current stock derived from movements; FR08 store cost and price; FR09 owner enters purchasing budget; FR10 short-term forecasts; FR11 identify products needing replenishment; FR12 expected gross profit; FR13 four-factor priority score; FR14 budget-constrained purchase plan; FR15 explanation per recommendation; FR16 accept/change/skip; FR17 retain recommendations.

**Non-functional (draft):** usability, performance, security (hashed passwords, bearer tokens), reliability (stock derived from movements), maintainability (routes/schemas/models/services), scalability (SQLite to PostgreSQL path), explainability, data integrity (foreign keys, validation).

**Database (draft entities):** User, Product, Supplier, Sale, SaleItem, Purchase, PurchaseItem, InventoryMovement (stock source of truth; source types sale/purchase/adjustment; adjustments need a reason), Forecast, Budget, Recommendation. Verify against models.py.

**Security (draft):** bcrypt hashing; password minimum 8 characters and bcrypt input limit; JWT HS256, 12-hour expiry; HTTPBearer; owner-only routes for budgets and recommendations; SQLite foreign keys ON and WAL journaling.

**Stack (verify in requirements.txt/package.json):** Python 3.x, FastAPI, Uvicorn, Pydantic 2.9 and pydantic-settings, SQLite, SQLAlchemy 2.0, PyJWT, bcrypt, pandas, NumPy, statsmodels, scikit-learn (draft says optional; gradient boosting suggests it is used), React 18.3, Vite 6 (the author's dev server shows Vite 6.4.3), Tailwind CSS 4, React Router, Recharts, TanStack Query (in the draft, not on slides, verify), pytest, httpx, Git. Backend served by Uvicorn on port 8000, frontend on port 5173.

**Real UI (from the author's screenshot, 30 Sept 2026):** Sidebar: Home, Record a sale, Record delivery, Stock, What to buy, Sales outlook, Products, Suppliers, Sales & deliveries, Reports. Dashboard greeting "Habari, Amina". Cards: Sales, last 7 days (KES 1,860, down 13.9% on the week before); Products running low (2, checked against the next 14 days); Shelves empty (0); Products tracked (16, 4 suppliers). Charts: "Money coming in" (daily sales, last 30 days) and "Best sellers" (units, last 7 days). Button: "Record a sale". Terminology map for the report: Record delivery = purchase; What to buy = recommendations; Sales outlook = forecasts. Known bug: the Y-axis of "Money coming in" shows "2k" twice (tick formatting).

**Project folder:** backend (app, tests, dukasmart.db, seed.py, migrate_profitability script, pytest.ini, requirements.txt, evaluate_system.py), frontend (src, dist, package.json, vite.config.js), docs, logs, README.md. The 16 products and 4 suppliers suggest seeded (simulated) data; state this openly.

**Draft test cases TC01-TC20:** register valid user; sign in valid; sign in invalid; create product; record purchase (movement recorded); record sale (movement recorded); view stock = sum of movements; adjustment without reason rejected; forecast with sufficient history; forecast with insufficient history gives insufficient-data; enter budget; generate recommendation; accept; change quantity; skip; budget below total need ranks and allocates within budget; partial funding; dashboard/reports; staff denied owner-only function; expired/invalid token rejected. Replace expected with real actual results and pass/fail from pytest output.

**Budget scenarios:** S1 budget covers all needs; S2 budget covers part; S3 high-margin low-volume vs low-margin high-volume; S4 one expensive vs several cheap products; S5 insufficient history; S6 stock already covers need (zero replenishment). Use real results from evaluate_system.py.

**Draft references (9, verify each DOI and keep only the real ones; add more to reach at least 12):**
1. Fildes, R., Ma, S., & Kolassa, S. (2022). Retail forecasting: Research and practice. International Journal of Forecasting, 38(4), 1283-1318.
2. Fildes, R., Kolassa, S., & Ma, S. (2022). Post-script, Retail forecasting: Research and practice. International Journal of Forecasting, 38(4), 1319-1324.
3. Karamshetty, V., De Vries, H., Van Wassenhove, L. N., Dewilde, S., Minnaard, W., Ongarora, D., Abuga, K., & Yadav, P. (2022). Inventory management practices in private healthcare facilities in Nairobi County. Production and Operations Management, 31(2), 828-846. (Healthcare, not retail; describe it accurately.)
4. Kogei, G. J., & Gachengo, L. (2025). The effect of inventory management on performance of selected Naivas supermarkets in Nairobi City County, Kenya. Journal of Procurement & Supply Chain, 5(2), 33-42.
5. Purnamasari, D. I., Permadi, V. A., Saepudin, A., & Agusdin, R. P. (2023). Demand forecasting for improved inventory management in small and medium-sized businesses. Jurnal Nasional Pendidikan Teknik Informatika, 12(1), 56-66.
6. Teerasoponpong, S., & Sopadang, A. (2022). Decision support system for adaptive sourcing and inventory management in small- and medium-sized enterprises. Robotics and Computer-Integrated Manufacturing, 73, 102226.
7. Torres, J., & Carpio, D. (2024). Model to predict inventory demand in retail SMEs using CRISP-DM and machine learning. 2024 IEEE INTERCON.
8. Ulrich, M., Jahnke, H., Langrock, R., Pesch, R., & Senge, R. (2022). Classification-based model selection in retail demand forecasting. International Journal of Forecasting, 38(1), 209-223.
9. van der Haar, J. F., Wellens, A. P., Boute, R. N., & Basten, R. J. I. (2024). Supervised learning for integrated forecasting and inventory control. European Journal of Operational Research, 319(2), 573-586.
The draft also cites "Ma et al. / related 2024" with no reference entry: fix or remove.

**Slides issues to fix later:** no literature review, architecture, ER, UI screenshot, results or recommendations slides; slides 8 and 11 must be updated for the three forecasting methods.

**Honesty rules:** No questionnaire or usability data was collected. NEVER invent respondents, scores, quotes or statistics. Write method, instruments and analysis plan fully and leave yellow placeholders [INSERT: ...] where only real data can go. State that sales data are seeded/simulated if so. Never describe a feature that is not in the code.
