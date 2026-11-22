# Data Governance

- Document ID: KB-POL-17
- Category: Company policy
- Owner: Omar Bakr, Chief Technology and Data Officer (EMP-0005)
- Effective date: 2025-04-01
- Version: 1.5
- Last reviewed: 2026-09-30
- Applies to: Technology, data owners and report users
- Classification: Internal

## 1. Purpose

Data governance makes sure that reports from different teams agree. It defines the owners of data, the standard definitions of measures and the checks that keep the reporting database reliable.

## 2. Roles

| Role | Holder | Responsibility |
|---|---|---|
| Executive sponsor | Omar Bakr, Chief Technology and Data Officer | Owns the data strategy and approves changes to definitions |
| Business Intelligence Lead | Joud Al-Khaldi | Maintains the standard measures and the reporting views |
| Database Administrator | Nawaf Al-Rowaili | Runs the reporting database, access roles and backups |
| Information Security Officer | Ghada Al-Subhi | Approves access and monitors compliance |
| Data owners | Heads of Commercial, Finance, Supply Chain, HR and Customer Service | Answer for the content and quality of their data |

## 3. Standard Definitions

| Measure | Definition |
|---|---|
| Net revenue | Sum of line totals of orders with status Completed, after line discounts, excluding VAT and delivery fees |
| Order count | Number of distinct Completed orders |
| Average order value | Net revenue divided by the number of Completed orders |
| Gross margin | Net revenue minus the cost of the goods sold, divided by net revenue |
| Return rate | Value of returned items divided by net revenue |
| Sales target attainment | Net revenue of a location in a month divided by its target |
| Store ranking | Stores only; the Distribution Center is excluded because it carries Online, Mobile App and B2B sales |
| Retail week | Sunday to Saturday; the weekend is Friday and Saturday |

## 4. Data Quality Rules

- Keys are unique and every foreign key is valid.
- Order totals equal the sum of their lines, VAT is 15 percent of the subtotal and the total equals subtotal plus VAT plus delivery fee.
- Discounts never exceed the line cap in the pricing policy.
- About 8 percent of in-store orders are anonymous and have no customer; all other orders have a customer.
- Quality checks run after every nightly load and failures are reported to the Database Administrator.

## 5. Reference Date and Refresh

The reporting database is loaded nightly. For analysis the reference date is 2026-10-31. Orders of the last three days of the period may still have the status Processing and are not part of revenue.

## 6. Change Control

A change to a definition, a view or a reference table needs a written request, approval by the Chief Technology and Data Officer and a note in the data dictionary. Historic figures are restated only with the approval of the Chief Financial Officer.

## 7. Access to Data

Access is given by role and approved by the data owner and the Information Security Officer (see KB-POL-16). Reporting access is read-only.
