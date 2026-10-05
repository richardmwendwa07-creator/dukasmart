<!--
FORMAT NOTES FOR FINAL WORD/PDF VERSION: Times New Roman 12 pt, 1.5 line spacing (except title page). Each chapter starts on a new page.
Items marked [VERIFY-STAT] are statistics to check. Items marked [VERIFY] are NEW references to check. Items marked [INSERT: ...] need your real data.
-->

<div align="center">

<br><br>

# **DUKASMART: A WEB-BASED DEMAND FORECASTING AND BUDGET-CONSTRAINED INVENTORY DECISION SUPPORT SYSTEM FOR SMALL RETAIL SHOPS IN NAIROBI COUNTY, KENYA**

<br>

**Richard Musili Mwendwa**

**SCT222-0320/2022**

<br>

**Supervisor: Dennis Njagi**

<br><br>

*A research project submitted to the Department of Information Technology in the School of Computing and Information Technology in partial fulfilment of the requirements for the award of the degree of Bachelor of Science in Business Computing of Jomo Kenyatta University of Agriculture and Technology.*

<br>

**2026**

</div>

<div style="page-break-after: always;"></div>

## DECLARATION

**Candidate's Declaration**

This research project is my original work and has not been presented for a degree in any other University.

Signature: ______________________________  Date: ____________________

Richard Musili Mwendwa (SCT222-0320/2022)

**Supervisor's Declaration**

This research project has been submitted for examination with my approval as University Supervisor.

Signature: ______________________________  Date: ____________________

Dennis Njagi

Department of Information Technology, School of Computing and Information Technology, Jomo Kenyatta University of Agriculture and Technology

<div style="page-break-after: always;"></div>

## ABSTRACT

Small retail shops in Nairobi County must decide every week what to restock, how much to buy and which items to buy first when money is limited. Most shops keep sales and stock records on paper or in simple tools, but these records only show what has happened and do not tell the owner which product deserves the next shilling. A product that is low in stock may sell slowly, while another product with more stock may sell fast and earn more profit. When the cost of all needed stock is higher than the cash available, the owner has to compare many competing needs without a clear and fair method. This research is in the area of demand forecasting and inventory decision support for small retail businesses.

This project proposes DukaSmart, an explainable web-based system that forecasts short-term product demand and turns the forecast into a prioritised, budget-constrained purchase plan. For each product, the system compares three forecasting methods, namely weighted moving average, simple exponential smoothing and gradient boosting, and uses the one selected for that product. The forecast is then combined with current stock, safety stock, unit cost, selling price and expected gross profit to calculate stockout risk and a priority score. The ranked list is funded from the owner's budget, from the highest priority downwards, and every recommendation carries a plain-language reason that the owner can accept, change or skip. The research follows a design science approach with mixed methods and Agile development, and the forecasts are checked using a time-ordered 14-day holdout with mean absolute error and root mean square error.

The system is built with a Python FastAPI backend, a SQLite database and a React frontend. It is evaluated for forecast accuracy, functional correctness, usability and consistency of recommendations under different budget scenarios. Sales data in the prototype are seeded or simulated where real shop records cannot be shared, and this is stated openly. The expected outcome is a working prototype that shows small shop owners which products to buy first, in what quantity and why, together with evidence on which forecasting method suits small-shop data. [INSERT: one sentence on the main evaluation results once testing is complete.]

<div style="page-break-after: always;"></div>

## ACRONYMS

| Acronym | Meaning |
|---|---|
| API | Application Programming Interface |
| APA | American Psychological Association |
| DSS | Decision Support System |
| ERP | Enterprise Resource Planning |
| FMCG | Fast-Moving Consumer Goods |
| JKUAT | Jomo Kenyatta University of Agriculture and Technology |
| JWT | JSON Web Token |
| KES | Kenya Shillings |
| KNBS | Kenya National Bureau of Statistics |
| MAE | Mean Absolute Error |
| MSME | Micro, Small and Medium Enterprise |
| RMSE | Root Mean Square Error |
| SES | Simple Exponential Smoothing |
| SME | Small and Medium-Sized Enterprise |
| UI | User Interface |
| WMA | Weighted Moving Average |

<div style="page-break-after: always;"></div>

## DEFINITION OF TERMS

**Affordability:** How easily a shop can pay for the stock a product needs, measured in this project as one divided by one plus the required purchase cost, so that cheaper purchases score higher.

**Budget-constrained replenishment:** The process of choosing which products to restock, and in what quantity, when the money available for buying stock is less than the money needed for all products.

**Demand forecast:** An estimate of how many units of a product customers are likely to buy over a coming period, calculated from past sales.

**Explainable recommendation:** A suggestion that is shown together with a plain-language reason, so that the shop owner can understand why the system made it.

**Expected gross profit:** The forecast quantity of a product multiplied by the profit earned on each unit, where profit per unit is the selling price minus the unit cost.

**Gradient boosting:** A machine learning method that builds many small decision trees one after another, where each new tree tries to correct the mistakes of the earlier ones.

**Holdout validation:** A way of testing a forecast by hiding the most recent days of sales, forecasting them, and comparing the forecast with what really happened.

**Inventory movement:** A record of one change in stock, such as a sale, a purchase (delivery) or an adjustment, from which the current stock level is calculated.

**Priority score:** A number between 0 and 1 that combines stockout risk, forecast demand, expected gross profit and affordability to rank products for purchase.

**Safety stock:** Extra stock kept above the forecast demand to protect the shop against sales that are higher than expected.

**Simple exponential smoothing:** A forecasting method that gives the newest sales the most weight and older sales smaller and smaller weight.

**Stockout:** A situation where a product has run out of stock and a customer who wants it cannot buy it.

**Stockout risk:** The share of the projected need that current stock cannot cover, shown as a value between 0 and 1.

**Weighted moving average:** A forecasting method that averages recent sales but gives larger weights to the more recent days.

<div style="page-break-after: always;"></div>

# CHAPTER 1: INTRODUCTION

## 1.1 Background

Retail shops all over the world depend on one simple cycle: they buy stock, sell it to customers, and buy again. The difficult part of this cycle is knowing how much to buy and when. If a shop buys too little, shelves become empty and customers go elsewhere. If it buys too much, money is locked in goods that sell slowly and may expire or become outdated. Researchers who have reviewed the field describe retail forecasting as a hard problem because shops handle many products whose sales change from day to day (Fildes et al., 2022b).

Large retailers have responded by investing in forecasting software, data teams and automated replenishment tools. Over the last decade, the research on retail forecasting has moved from classical statistical methods towards machine learning methods that learn patterns across many products. Large public forecasting competitions have also shown that carefully built machine learning models can match or beat traditional methods on retail sales data (Makridakis et al., 2022). However, these tools are usually designed for big chains with large data, trained staff and large budgets. They are often too complex, too costly and too hard to explain for a small shop owner who just wants to know what to buy this week.

The problem began when shops moved from keeping stock in the owner's head to keeping records in books and, later, in digital tools. Record keeping gave owners a history of sales and deliveries, but history alone does not make a decision. A record can say that sugar sold 30 packets last week, yet it cannot say whether sugar should be bought before cooking oil when the cash is not enough for both. The real gap, therefore, is between recording what happened and deciding what to do next. This gap is the starting point of this research.

In Kenya, small shops, kiosks and mini-supermarkets are a daily source of food and household goods for many families, and Nairobi County has a very large number of them. Most of these shops are run by an owner and one or two helpers, and the owner usually carries the decision to restock alone. Studies of inventory practice in Nairobi show that inventory management matters for performance, whether in supermarkets (Kogei & Gachengo, 2025) or in private healthcare facilities (Karamshetty et al., 2022). The healthcare study is not about retail, but it shows how stock decisions are managed in a Nairobi setting with limited resources. Small retail shops in the county, however, still have few simple tools that turn their own sales history into a clear purchase plan.

## 1.2 Project Overview

This research is in the area of demand forecasting and inventory decision support for small retail businesses. Demand forecasting is the practice of using past sales to estimate future sales, while inventory decision support is the use of a computer system to help a manager decide how much stock to hold and buy. Together they form a decision chain that begins with sales history and ends with a purchase list. Globally, this area has grown quickly, with recent work on selecting the best forecasting model for each product (Ulrich et al., 2022) and on joining forecasting and inventory control in one learning process (van der Haar et al., 2024). Work on small and medium-sized businesses shows the same interest, including demand forecasting for inventory management (Purnamasari et al., 2023) and decision support for sourcing and inventory (Teerasoponpong & Sopadang, 2022).

Locally, the need is clearest in small shops in Nairobi County, where owners must buy stock with limited cash and cannot afford to be wrong often. A shop owner in this setting does not only ask what is running low. The owner also asks which product sells fastest, which gives the most profit, and which can be paid for with the money at hand. These questions combine forecasting with business economics, which is why the project is described as a decision support system and not only a forecasting tool.

The project uses a few key computational principles that are explained in simple terms here and in more detail later. The first is time series forecasting, where the sales of each product over past days are used to predict the coming days. The second is model comparison, where three methods, namely weighted moving average, simple exponential smoothing and gradient boosting, are tested on a hidden part of the history and the system uses the one selected for each product. The third is multi-factor scoring, where stockout risk, forecast demand, expected gross profit and affordability are scaled to a common range and combined into one priority score. The fourth is budget allocation, where the ranked products are funded one by one from the available budget, and partial funding is allowed when the money runs short.

## 1.3 Statement of the Problem

Running out of stock is a costly and well-measured problem in retail. A worldwide study of retail out-of-stocks found that, on average, about 8% of items that customers wanted were not available on the shelf (Gruen et al., 2002). Most of these empty shelves were found to come from store-level ordering and replenishment decisions, and not from problems at the factory or the warehouse. This means that the decision about what to reorder is itself a main cause of lost sales. For a small shop with few products and thin margins, each lost sale is a larger share of income than it is for a large chain.

Small businesses carry a very large part of Kenya's economy, so the problem affects many households. The national survey of micro, small and medium enterprises by the Kenya National Bureau of Statistics reported about 7.4 million MSMEs in 2016 and credited the sector with roughly 28% of national output (Kenya National Bureau of Statistics [KNBS], 2016). Retail and trade shops are among the most common types of these enterprises, and Nairobi County hosts a very large number of them. These figures are from 2016 and are used only to show the size of the sector, so more recent figures should be checked before the final submission. Even so, they show that a tool which improves the stock decisions of small shops can touch a large number of livelihoods.

The specific problem is that small shop owners must decide what to restock, how much to buy and what to buy first when funds are limited, and they have no simple, transparent method for doing so. Low stock alone is not enough to guide the decision. A product that is low in stock may sell slowly, while another product that still has some stock may sell quickly. Products also differ in cost, selling price and profit margin, so the same amount of money can earn very different returns depending on what is bought. When the total cost of all needed stock is higher than the budget, the owner is forced to compare competing needs by memory and feeling.

The effects of this problem are lost sales, money tied up in slow stock, and decisions that cannot be explained or repeated. Existing record keeping, whether in books or in simple digital tools, tells the owner what was sold and what is in stock, but it does not tell the owner which product to prioritise. Large retail forecasting systems do answer such questions, but they are built for chains and are not designed around a small owner's weekly cash limit (Fildes et al., 2022b). Recent research shows strong forecasting and inventory methods, yet most of it does not combine forecast demand, profit and a fixed budget into an explanation that a shop owner can read and trust. This project is therefore concerned with the lack of an explainable, budget-aware forecasting and decision support system for small retail shops in Nairobi County, which is exactly what the title of this report describes.

## 1.4 Proposed Solution

This research seeks to design, develop and evaluate DukaSmart, a web-based system that forecasts short-term product demand and produces a prioritised, budget-constrained purchase plan for small retail shops. The research component is the investigation of which interpretable forecasting approach suits the sales data of small shops and how forecast demand, stock, profit and budget can be combined into an explainable priority. The development component is the working prototype that applies these findings. The system follows a clear workflow: it starts from historical sales, forecasts demand, compares the expected demand with current stock, calculates the replenishment quantity and its cost, estimates the expected gross profit, checks the budget, and then shows a prioritised list on which the owner can act. The owner stays in control, because every recommendation can be accepted, changed or skipped and nothing is ordered automatically.

The key operations of the system are forecasting, replenishment calculation, priority scoring and budget allocation. For forecasting, the system compares weighted moving average, simple exponential smoothing and gradient boosting for each product on a 14-day time-ordered holdout and records which method it selects for that product. [INSERT: confirm the selection rule used in evaluate_system.py, for example the method with the lowest holdout error.] Required replenishment is the larger of zero and the projected need minus current stock, where the projected need is the forecast demand plus a safety stock set by default at 20%. Stockout risk is the shortage divided by the projected need, kept between 0 and 1, and the priority score is 0.40 times stockout risk plus 0.30 times demand plus 0.20 times gross profit plus 0.10 times affordability. Demand, gross profit and affordability are scaled with min-max normalisation across the candidate products, and the budget is then allocated down the ranked list with partial funding allowed.

Recent models in the literature show what is possible and where this solution sits. Globally, work on retail sales forecasting with meta-learning shows that the best method can differ between products and can be chosen using the features of each series (Ma & Fildes, 2021), and classification-based model selection reaches a similar idea from another direction (Ulrich et al., 2022). Studies on joining forecasting and stock control show that learning directly from data can support ordering decisions (van der Haar et al., 2024), and work on tree-based methods explains why boosted trees perform well in forecasting (Januschowski et al., 2022). Regionally, the Kenyan studies reviewed here focus on how inventory practice relates to performance (Kogei & Gachengo, 2025; Karamshetty et al., 2022), and they do not offer a forecasting-driven purchase plan for a small shop. DukaSmart avoids outdated tools and deep learning, uses methods that can be explained to a shop owner, and adds the missing step of ranking purchases under a fixed budget.

## 1.5 Objectives

**General objective**

To design, develop and evaluate an explainable web-based demand forecasting and budget-constrained inventory decision support system that assists small retail shops in Nairobi County to prioritise stock purchases using historical sales, current inventory, product economics and available purchasing budget.

**Specific objectives**

1. Investigate sales recording, stock monitoring and purchasing practices of selected small shops in Nairobi County and identify information challenges affecting replenishment.
2. Determine an appropriate, interpretable short-term product-level forecasting approach.
3. Design and implement an explainable budget-constrained replenishment model combining stockout risk, forecast demand, expected gross profit and affordability into a prioritised purchase plan.
4. Evaluate the system for forecast accuracy, functional correctness, usability and recommendation consistency under different budget scenarios.

## 1.6 Research Questions

1. What sales recording, stock monitoring and purchasing practices and constraints affect replenishment decisions in small retail shops in Nairobi County?
2. Which interpretable short-term forecasting approach best suits the product-level sales data available in small retail shops?
3. How can forecast demand, current stock, safety stock, unit cost, selling price, expected gross profit and available budget be combined into an explainable priority for replenishment?
4. What evaluation criteria are suitable for judging forecast accuracy, functional correctness, usability and recommendation consistency of a budget-constrained inventory decision support system?

## 1.7 Justification

This research is needed because small shops make daily stock decisions that directly decide whether they earn or lose money, yet they have almost no tools made for their size. Out-of-stock losses are common in retail and are strongly linked to ordering decisions (Gruen et al., 2002), so even a modest improvement in those decisions can matter. The research is also timely because forecasting methods have improved greatly in recent years, and many of them can now run on a normal computer without special hardware (Makridakis et al., 2022). What is still missing is a way to bring these methods to small shops in a form that is simple, affordable and explained in plain language. This project responds to that gap by joining proven forecasting methods with a clear budget rule.

The main beneficiaries are small shop owners and their staff in Nairobi County, who gain a clear list of what to buy, how much, and why. A second group of beneficiaries is suppliers and customers, because better stock decisions lead to fewer empty shelves and steadier orders. Researchers and students gain a documented example of how forecasting, product economics and budget limits can be joined in one explainable model. The university benefits from a practical project that applies business computing to a local problem. Policy makers interested in supporting small businesses also gain evidence of what low-cost digital tools can offer.

The solution fits the problem because it moves from recording to deciding. Instead of showing only stock levels, it shows which product to buy first and explains the reason using stockout risk, expected demand, profit and cost. Using more than one forecasting method, and keeping the one that performs better on hidden recent data, guards against relying on a method that does not suit a given product (Ma & Fildes, 2021). The owner remains the decision maker, which builds trust and keeps responsibility where it belongs. The contribution to the research area is an evaluated, explainable approach to budget-constrained replenishment that uses small-shop data and is described openly enough to be repeated or improved by others.

## 1.8 Proposed System Methodologies

This section gives only an outline, and the full detail is in Chapter 3. The research follows a design science approach, in which a useful artefact is built to solve a real problem and then evaluated (Hevner et al., 2004). The research life cycle follows the common design science stages of problem identification, definition of objectives, design and development, demonstration, evaluation and communication (Peffers et al., 2007). This approach was chosen because the project must both produce a working system and produce knowledge about which forecasting approach and priority model suit small shops. It also fits well with the four specific objectives, which move from investigation to design, implementation and evaluation.

Data collection will use mixed methods. Questionnaires and short interviews with selected small shop owners and staff in Nairobi County will be used, where feasible, to understand current recording, stock monitoring and purchasing practices and to collect usability feedback. [INSERT: sampling technique, sample size, instruments and ethics approval once confirmed.] Product-level sales history is needed to build and test the forecasts. Where real shop records cannot be shared, simulated or anonymised data will be used, and the prototype data are seeded and are stated openly to be so. No questionnaire or usability results are reported in this chapter, because they can only be written after real data are collected.

The system will be built with Agile iterative development, so that small working versions are produced, shown and improved. The backend will use Python with FastAPI, Uvicorn, SQLAlchemy and SQLite, with pandas, NumPy, statsmodels and scikit-learn for forecasting. The frontend will use React with Vite, Tailwind CSS, React Router and Recharts, and the code will be managed with Git. These tools were chosen because they are free, well documented, popular among developers and suitable for a small system that can later move from SQLite to a larger database. [INSERT: confirm TanStack Query and the exact library versions from requirements.txt and package.json.]

Evaluation will be done in two parts. Forecasts will be checked with a time-ordered 14-day holdout, with no shuffling, using mean absolute error and root mean square error (Hyndman & Koehler, 2006). A product needs at least 10 non-zero sales observations and 28 days of history to be forecast, and otherwise the system reports insufficient data instead of guessing. The system will also be tested for functional correctness, integration, security, usability and budget-scenario behaviour using automated tests and user feedback. The budget scenarios will cover cases where the budget covers all needs, only part of the needs, a trade-off between high-margin low-volume and low-margin high-volume products, one expensive product against several cheap ones, insufficient history, and stock that already covers the need.

## 1.9 Scope

The project is confined to selected small general-retail and fast-moving consumer goods shops in Nairobi County, Kenya. The prototype serves a single shop at a time and works with product-level sales history. It covers recording of sales and deliveries, stock tracking from inventory movements, short-term demand forecasting, the priority score, budget allocation and the owner's decision to accept, change or skip each recommendation. The target users are shop owners, who can set budgets and act on recommendations, and shop staff, who have limited access. The project does not claim to serve other types of businesses or other counties.

Some functions are outside the scope of this project. These are payments and M-Pesa integration, payroll, tax, human resources, full accounting, multi-branch management, supplier negotiation, automatic ordering without the owner's approval, a full enterprise resource planning system, dynamic pricing and deep learning methods. These items are left out so that the project can focus on its central question of how to prioritise purchases under a budget. They are not weaknesses of the research, and some of them are suggested for future work. The reader should therefore not expect the system to handle them.

The project has limitations related to data, methodology and resources. On the data side, real shop records may not be disclosed, so simulated or anonymised data may be used, and results from such data may not match real shops exactly. On the methodology side, only three forecasting methods are compared, a short holdout of 14 days is used, and the priority weights are fixed rather than learned. On the resource side, the work is done with limited funds, free tools and a small number of participating shops. Time is not treated as a limitation of this project.

The project rests on several assumptions. Product-level sales history is assumed to be available or can be constructed from the shop's records. The cost and selling price of each product are assumed to be known, and records are assumed to be accurate. The budget entered into the system is assumed to represent the money the owner can really spend on stock. Finally, the operator is assumed to make the final decision, and the system only advises.

<div style="page-break-after: always;"></div>

# CHAPTER 2: LITERATURE REVIEW

## 2.1 Introduction

This chapter reviews the work that is related to demand forecasting and inventory decision support for small retail shops. The topic is relevant because stock decisions decide whether a shop has the right goods at the right time, and these decisions rely on estimates of future demand. Retail forecasting has been studied for many years, and recent reviews show both strong progress and many practical difficulties (Fildes et al., 2022b). A short follow-up note to that review adds further comments on the state of research and practice (Fildes et al., 2022a). Understanding this background helps to choose methods that are accurate enough and still simple enough for a small shop.

The use of technology for stock control has moved through several stages. Shops first used handwritten books, then spreadsheets and point-of-sale tools, and later forecasting software that estimates demand. In large retail, machine learning is now common, and competitions on retail sales data have compared many methods on the same problem (Makridakis et al., 2022). In small businesses, studies have tried demand forecasting and decision support tools in settings with less data and fewer resources (Purnamasari et al., 2023; Teerasoponpong & Sopadang, 2022). In Kenya, the literature on small retail still concentrates more on inventory practice than on forecasting tools.

The purpose of this review is to find out what is already known and what is still missing, so that this project is placed correctly in its field. The review has four aims that match the objectives of the project. The first is to describe the key concepts and the main approaches to forecasting and to stock prioritisation. The second is to examine related studies and judge their successes and misses. The third is to compare options for building such a system. The fourth is to identify the research gaps that this project addresses. These aims are served by the sections that follow, which cover theory, case studies, integration and architecture, a summary and the research gaps.

## 2.2 Theoretical Review

Demand forecasting rests on the idea that past sales contain patterns that help to predict future sales. A time series is a list of values recorded over time, such as the number of units of a product sold each day. Forecasting methods try to separate the level of sales, the trend, repeating weekly patterns and random noise. Accuracy is judged by comparing forecasts with actual sales that were not used to build the forecast, and common measures are mean absolute error and root mean square error (Hyndman & Koehler, 2006). Because small shops sell few units per day and many days have zero sales, the data are often short and irregular, which makes forecasting harder.

Forecasting approaches can be grouped into statistical methods and machine learning methods, and each group has its own advantages and limits. Statistical methods such as moving averages and exponential smoothing are simple, fast, need little data and are easy to explain, but they cannot use extra information such as the day of the week unless they are extended. Machine learning methods such as gradient boosting learn complex patterns from many features and can be very accurate, but they need more data, more tuning and are harder to explain (Friedman, 2001; Januschowski et al., 2022). Large forecasting studies show that no single method wins everywhere and that results depend on the data (Petropoulos et al., 2022). This is why the project compares three methods and does not assume that one is always best. Table 2.1 summarises the three approaches used in this research.

**Table 2.1**

*Forecasting Approaches Considered for DukaSmart*

| Approach | How it works | Strengths | Limitations | Fit for small-shop data |
|---|---|---|---|---|
| Weighted moving average (WMA) | Averages recent daily sales and gives larger weights to newer days | Very simple, fast and easy to explain; needs little history | Reacts slowly to sudden change; does not model trend or weekly pattern by itself | Good baseline for short or stable series |
| Simple exponential smoothing (SES) | Updates the forecast each day by mixing the newest sale with the previous forecast, so older days fade away | Easy to explain; adapts to level changes; widely used as a benchmark (Petropoulos et al., 2022) | Gives a flat forecast and does not model trend or weekly pattern | Good for products with steady sales and few records |
| Gradient boosting | Builds many small decision trees in sequence, each correcting the errors of the earlier ones (Friedman, 2001) | Can learn complex patterns and use extra features; strong results in forecasting studies (Januschowski et al., 2022; Makridakis et al., 2022) | Needs more data and tuning; harder to explain; may overfit short series | Useful for products with longer and richer history |

*Note.* Descriptions are summarised from the cited sources and from the design of the DukaSmart prototype.

Beyond forecasting, the theory of inventory control explains how a forecast becomes a purchase decision. A basic idea is that the stock a shop needs is the expected demand plus a buffer, called safety stock, which protects against sales that are higher than expected. The quantity to buy is then the need minus the stock already on hand, and it cannot be below zero. Research that joins forecasting and inventory control argues that these two steps should be considered together and not in isolation (van der Haar et al., 2024). In a small shop, the budget adds a third limit, because the owner cannot always buy the full quantity for every product.

When money is limited, products must be ranked, and this is a multi-criteria decision problem. A product can be urgent because stockout risk is high, valuable because it earns a high gross profit, popular because demand is high, or easy to afford because its cost is low. These criteria are measured in different units, so they are often scaled to a common range and combined with weights. A simple weighted score is easy to explain, which matters because decision support is more useful when the user can see why a recommendation was made. The weights in DukaSmart are fixed and visible, and the final decision always stays with the owner.

The research approach itself also has a theory, which is design science. Design science holds that a researcher can create a useful artefact, such as a software system, and produce knowledge by building and evaluating it (Hevner et al., 2004). A standard process model describes the steps from problem identification through design, demonstration and evaluation (Peffers et al., 2007). This approach suits the present project because the aim is both to build a system and to learn which methods work. It also encourages the researcher to test the artefact against clear criteria, which this project does through forecast error measures, functional tests and user feedback.

## 2.3 Case Study Review

Several studies show how forecasting and inventory ideas have been applied, and their results help to place this project. Table 2.2 lists the related studies that are reviewed in this section, with their context, approach and the gap each leaves for this research.

**Table 2.2**

*Summary of Related Studies*

| Author(s) and year | Context | Approach or focus | Contribution | Gap relative to this project |
|---|---|---|---|---|
| Fildes et al. (2022b) | Retail forecasting in research and practice | Review of retail forecasting literature and practice | Maps the main challenges and methods in retail forecasting | Not a system; not aimed at small shops with a fixed budget |
| Fildes et al. (2022a) | Follow-up to the retail forecasting review | Post-script commentary | Adds further views on the review | Not a system or a decision model |
| Ma & Fildes (2021) | Retail sales forecasting | Meta-learning to choose forecasting methods | Shows that method choice can be learned from series features | Large-retail focus; no budget-based purchase plan |
| Ulrich et al. (2022) | Retail demand forecasting | Classification-based model selection | Shows that choosing a model per series can improve accuracy | Does not turn forecasts into a budget-limited plan |
| van der Haar et al. (2024) | Forecasting and inventory control | Supervised learning for integrated forecasting and stock control | Shows that learning can support ordering decisions directly | Not designed for small shops or owner-explained priorities |
| Makridakis et al. (2022) | Large retail sales forecasting competition | Comparison of many methods on retail data | Reports results and lessons from a large retail forecasting competition | Competition setting; not a shop-level decision tool |
| Purnamasari et al. (2023) | Small and medium-sized businesses | Demand forecasting for inventory management | Applies forecasting to support stock decisions in small and medium businesses | Does not rank purchases under a budget |
| Teerasoponpong & Sopadang (2022) | Small and medium-sized enterprises | Decision support for adaptive sourcing and inventory | Presents a decision support system for sourcing and stock | Not focused on small retail shops or on budget-ranked replenishment |
| Torres & Carpio (2024) | Retail SMEs | CRISP-DM process with machine learning to predict inventory demand | Shows a data-mining process for predicting demand in retail SMEs | Prediction focus; no explainable budget-constrained plan |
| Kogei & Gachengo (2025) | Naivas supermarkets, Nairobi City County | Effect of inventory management on performance | Links inventory management to performance in Kenyan supermarkets | Practice study; no forecasting or decision tool |
| Karamshetty et al. (2022) | Private healthcare facilities, Nairobi County | Inventory management practices | Describes stock practice in a Nairobi healthcare setting | Healthcare, not retail; no forecasting tool |

*Note.* Entries summarise the focus of each cited work in the author's own words.

The global studies show strong progress in methods but little attention to small owners. The review by Fildes et al. (2022b) gives a broad picture of retail forecasting and shows how many practical issues remain between research and daily use. The work of Ma and Fildes (2021) and of Ulrich et al. (2022) shows that choosing the right method for each series can improve results, which supports the idea of comparing several methods per product. The work of van der Haar et al. (2024) goes further by linking forecasting with the ordering decision itself. A common limit in these studies is that they target large retailers, so a small shop with little data and a tight cash limit is rarely the main user.

The studies on small and medium-sized businesses are closer to this project but still leave a gap. Purnamasari et al. (2023) show that demand forecasting can support inventory management in small and medium-sized businesses. Teerasoponpong and Sopadang (2022) present a decision support system for sourcing and inventory in small and medium-sized enterprises, which shows the value of decision support in such settings. Torres and Carpio (2024) apply a structured data-mining process and machine learning to predict inventory demand in retail SMEs. These studies show success in predicting or supporting decisions, but they do not combine forecast demand, profit and a fixed purchase budget into one explained ranking.

The Kenyan studies show that inventory management matters but do not provide forecasting tools. Kogei and Gachengo (2025) examine the effect of inventory management on performance in selected Naivas supermarkets in Nairobi City County, which gives local evidence of its importance. Karamshetty et al. (2022) study inventory management practices in private healthcare facilities in Nairobi County, and although this is not retail, it shows the working conditions of stock managers in the county. Both studies describe practice and performance and do not build or test a forecasting-based purchase planning tool. The Kenyan literature reviewed here therefore leaves room for a practical system designed for small shops.

Large competitions give useful lessons about method choice. The M5 competition on retail sales data compared many methods and reported what worked best on a large retail dataset (Makridakis et al., 2022), and studies of tree-based forecasting help to explain why boosted trees did well (Januschowski et al., 2022). These findings support including gradient boosting in this project. At the same time, the competition data came from a large retailer with many products and long histories, which is different from a single small shop. This is why simple methods are kept in the comparison, since they may do as well on short and noisy shop data.

## 2.4 Integration and Architecture

There are several ways to bring forecasting into a small shop's daily work. The simplest is a spreadsheet with formulas, which is cheap and familiar but hard to keep consistent and hard to extend with several forecasting methods. A second option is a standalone desktop or mobile app, which works offline but is harder to update and to share between owner and staff. A third option is a web-based application with a backend that stores data and runs the forecasting, and a frontend that the owner uses in a browser. A fourth option is to use a large cloud machine learning platform, which is powerful but costly and complex for a small shop.

This project chooses the web-based option because it balances cost, ease of use and room to grow. A web application can be used on a phone, tablet or computer without installing heavy software, and updates are made once on the server. It also allows owner and staff to have different roles with different permissions. The forecasting libraries needed, such as pandas, statsmodels and scikit-learn, are free and run well in a Python backend. This option also keeps the system explainable, because the calculations are written in clear steps and are not hidden inside a closed platform.

The architecture follows a layered client-server design. The frontend, built with React, shows the user interface, such as the dashboard and the screens for recording sales, recording deliveries, viewing stock, seeing what to buy and viewing the sales outlook. The backend, built with FastAPI, is organised into routes, schemas, models and services, which keeps the code easier to maintain. The database stores users, products, suppliers, sales, purchases, inventory movements, forecasts, budgets and recommendations, and the movements table is the source of truth for stock. SQLite is used in the prototype, with a clear path to a larger database such as PostgreSQL if the system grows.

The design also follows several quality principles that the literature on decision support supports. Security uses hashed passwords, token-based sign-in and owner-only access to budgets and recommendations. Reliability comes from deriving current stock from recorded movements, so stock cannot be changed without a record. Explainability comes from storing a full reason and a short priority reason for every recommendation. Data integrity comes from foreign keys and input validation. [INSERT: confirm each of these features against the final code before submission.]

## 2.5 Summary

The literature shows that retail forecasting is a mature but difficult field in which no single method is best for every product. Statistical methods are simple and easy to explain, and machine learning methods can be more accurate when there is enough data. Work on model selection suggests that the best method may differ between products, and work on integrated forecasting and stock control shows the value of linking forecasts to ordering decisions. Studies of small and medium-sized businesses show that forecasting and decision support can help, but they differ in context and method.

The Kenyan studies reviewed here show that inventory management matters for performance in Nairobi, in supermarkets and in healthcare facilities. They do not, however, offer a forecasting-driven tool that helps a small retail shop decide what to buy first when money is limited. A web-based layered architecture is a practical way to deliver such a tool at low cost. The review also supports comparing several forecasting methods per product, keeping the methods explainable, and checking them on time-ordered hidden data. These findings guide the design and methods used in the next chapters.

## 2.6 Research Gaps

The first gap is that most advanced retail forecasting research is aimed at large retailers with rich data and technical teams (Fildes et al., 2022b; Makridakis et al., 2022). Small shops have short, noisy sales records and limited technical skill, so the methods and tools used for chains do not transfer directly. This research resolves the gap by testing three methods, from very simple to more advanced, on small-shop data and by recording which method is selected for each product. It also sets a minimum data rule, so that the system says "insufficient data" instead of giving a weak forecast. In this way the project studies what works under small-shop conditions.

The second gap is that forecasting studies usually stop at a forecast or at an order quantity and do not rank purchases under a fixed budget. The studies by Ma and Fildes (2021), Ulrich et al. (2022) and van der Haar et al. (2024) improve forecasting or ordering, but none of them is built around an owner who cannot afford to buy everything. In a small shop, the real question is which product to fund first. This research resolves the gap with a priority score that combines stockout risk, demand, expected gross profit and affordability, and with a budget allocation that funds the ranked list from the top. The approach is simple enough to explain and to repeat.

The third gap is that the Kenyan literature reviewed describes inventory practice and performance but does not provide or evaluate a forecasting-based decision tool for small retail shops (Kogei & Gachengo, 2025; Karamshetty et al., 2022). This leaves Nairobi shop owners with advice but without a working tool. This research resolves the gap by investigating local practices and building and evaluating a prototype for small shops in Nairobi County. It also reports openly where data are simulated and where real data have not yet been collected. The result is a documented local example that others can test further.

The fourth gap is that many decision tools give an answer without a reason, which makes owners less likely to trust or use them. Explainable output is especially important for small shop owners who make the final decision with their own money. This research resolves the gap by storing a full reason and a short priority reason for every recommendation and by letting the owner accept, change or skip it. The recommendations are kept for later review, so the owner can see what was suggested and what was done. The evaluation then checks usability and the consistency of recommendations under different budget scenarios, so that the trust claim is tested and not only assumed.

<div style="page-break-after: always;"></div>

# REFERENCES

Fildes, R., Kolassa, S., & Ma, S. (2022a). Post-script, Retail forecasting: Research and practice. *International Journal of Forecasting, 38*(4), 1319–1324.

Fildes, R., Ma, S., & Kolassa, S. (2022b). Retail forecasting: Research and practice. *International Journal of Forecasting, 38*(4), 1283–1318.

Friedman, J. H. (2001). Greedy function approximation: A gradient boosting machine. *The Annals of Statistics, 29*(5), 1189–1232.https://www.jstor.org/stable/2699986

Gruen, T. W., Corsten, D. S., & Bharadwaj, S. (2002). *Retail out-of-stocks: A worldwide examination of extent, causes, and consumer responses.* Grocery Manufacturers of America. (Industry report, not peer-reviewed.)

Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design science in information systems research. *MIS Quarterly, 28*(1), 75–105.https://doi.org/10.2307/25148625

Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting, 22*(4), 679–688.https://doi.org/10.1016/j.ijforecast.2006.03.001

Januschowski, T., Wang, Y., Torkkola, K., Erkkilä, T., Hasson, H., & Gasthaus, J. (2022). Forecasting with trees. *International Journal of Forecasting, 38*(4), 1473–1481. https://doi.org/10.1016/j.ijforecast.2021.10.004

Karamshetty, V., De Vries, H., Van Wassenhove, L. N., Dewilde, S., Minnaard, W., Ongarora, D., Abuga, K., & Yadav, P. (2022). Inventory management practices in private healthcare facilities in Nairobi County. *Production and Operations Management, 31*(2), 828–846.

Kenya National Bureau of Statistics. (2016). *2016 national micro, small and medium establishments (MSME) survey: Basic report.* Kenya National Bureau of Statistics. (Government report, not peer-reviewed.)

Kogei, G. J., & Gachengo, L. (2025). The effect of inventory management on performance of selected Naivas supermarkets in Nairobi City County, Kenya. *Journal of Procurement & Supply Chain, 5*(2), 33–42.

Ma, S., & Fildes, R. (2021). Retail sales forecasting with meta-learning. *European Journal of Operational Research, 288*(1), 111–128. https://doi.org/10.1016/j.ejor.2020.05.038

Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022). M5 accuracy competition: Results, findings, and conclusions. *International Journal of Forecasting, 38*(4), 1346–1364. https://doi.org/10.1016/j.ijforecast.2021.11.013

Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. (2007). A design science research methodology for information systems research. *Journal of Management Information Systems, 24*(3), 45–77. https://doi.org/10.2753/MIS0742-1222240302

Petropoulos, F., Apiletti, D., Assimakopoulos, V., Babai, M. Z., Barrow, D. K., Ben Taieb, S., Bergmeir, C., Bessa, R. J., Bijak, J., Boylan, J. E., Browell, J., Carnevale, C., Castle, J. L., Cirillo, P., Clements, M. P., Cordeiro, C., Cyrino Oliveira, F. L., De Baets, S., Dokumentov, A., ... Ziel, F. (2022). Forecasting: Theory and practice. *International Journal of Forecasting, 38*(3), 705–871. https://doi.org/10.1016/j.ijforecast.2021.11.001

Purnamasari, D. I., Permadi, V. A., Saepudin, A., & Agusdin, R. P. (2023). Demand forecasting for improved inventory management in small and medium-sized businesses. *Jurnal Nasional Pendidikan Teknik Informatika, 12*(1), 56–66.

Teerasoponpong, S., & Sopadang, A. (2022). Decision support system for adaptive sourcing and inventory management in small- and medium-sized enterprises. *Robotics and Computer-Integrated Manufacturing, 73*, Article 102226.

Torres, J., & Carpio, D. (2024). Model to predict inventory demand in retail SMEs using CRISP-DM and machine learning. In *2024 IEEE INTERCON*. IEEE.

Ulrich, M., Jahnke, H., Langrock, R., Pesch, R., & Senge, R. (2022). Classification-based model selection in retail demand forecasting. *International Journal of Forecasting, 38*(1), 209–223.

van der Haar, J. F., Wellens, A. P., Boute, R. N., & Basten, R. J. I. (2024). Supervised learning for integrated forecasting and inventory control. *European Journal of Operational Research, 319*(2), 573–586.
