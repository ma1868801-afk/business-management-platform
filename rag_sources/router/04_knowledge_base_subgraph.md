# Router: Knowledge Base Subgraph Description

- Document ID: RT-04
- Index: router
- Subgraph name: `knowledge_base`

## Purpose

The Knowledge Base subgraph answers questions from the official company documents. It rewrites and expands the question, retrieves passages from the company index, re-ranks them and answers only from the retrieved text. If the passages do not contain the answer it says so.

## What the Knowledge Base Contains (77 Documents)

| Category | Documents | Content |
|---|---|---|
| Company policies | 22 | Overview, mission and values, organization, branch network, sales channels, pricing and discounts, promotions calendar, Nakhla Rewards loyalty programme, returns and refunds, shipping, payments and VAT, B2B sales, inventory policy, procurement, warehouse operations, data privacy, data governance, HR, code of conduct, health and safety, customer service, sales targets. |
| Branch profiles | 9 | One profile per location: address area, size, staff, manager, opening hours, role in the network. |
| Contracts | 28 | 16 supplier contracts (SUP-01 to SUP-16) and 12 contract business customer agreements (CUST-B001 to CUST-B012). |
| Employee records | 10 | Rosters by function with titles, hire dates, reporting lines and compensation for named employees. |
| Product catalogs | 8 | One catalog per product line listing the 15 SKUs with list price, brand, supplier, shelf life and lifecycle status. |

## Choose Knowledge Base When the Question Is About

- A rule or procedure: return window, delivery fee, discount approval, leave policy, safety rules.
- Loyalty programme rules and tier thresholds.
- Contract terms: lead time, minimum order quantity, payment terms, penalties, renewal, credit limit, discount of a business customer.
- Facts about a named product: list price, brand, supplier, shelf life, launch date, lifecycle status.
- Facts about a branch: manager, opening hours, size, staff.
- Facts about a named employee: title, department, reporting line, hire date.
- Definitions used by the company: how revenue, margin or stock status is defined.

## Routing Hints

None. The Knowledge Base subgraph needs only the sub-question.

## Typical Questions

- What is the return window for defective items?
- Who manages the Jeddah Tahlia branch?
- What are the payment terms in the contract with SUP-08?
- What spend is needed to reach Gold tier?
- What is the list price of the AirWhirl Tower Fan?
- What is the credit limit of Red Sea Resorts and Spa?
- How are leave days calculated for new employees?

## Do Not Choose Knowledge Base For

- Questions that need a number computed from transactions (Data Analysis).
- Current stock or purchase order status (Inventory).
- Lists, rankings or averages of employee compensation (reject: restricted data).
