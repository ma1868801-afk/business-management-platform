# Router: Entity and Term Map

- Document ID: RT-07
- Index: router
- Purpose: maps names, spellings and business words that users use to the canonical names and codes used in the data, so routing and sub-questions use exact entities.

## Locations

| Canonical name | Code | Common ways users refer to it |
|---|---|---|
| Riyadh Olaya Flagship | RYD-OLY | Olaya, Olaya Street, Riyadh flagship, main store |
| Jeddah Tahlia Flagship | JED-THL | Tahlia, Tahlia Street, Jeddah flagship |
| Riyadh Malqa Standard | RYD-MLQ | Malqa, north Riyadh store |
| Dammam Faisaliyah Standard | DMM-FSL | Faisaliyah, Dammam store, Dammam branch |
| Al Khobar Corniche Standard | KHB-COR | Khobar, Al Khobar, Alkhobar, Corniche |
| Madinah Quba Standard | MED-QBA | Madinah, Medina, Al Madinah, Quba |
| Jeddah Obhur Express | JED-OBH | Obhur, Abhur, Jeddah express |
| Abha City Express | ABH-CTY | Abha, Abha store |
| Riyadh Distribution Center | RYD-DC | DC, warehouse, distribution centre, central warehouse |

Notes: "Jeddah" alone matches two stores (JED-THL and JED-OBH); "Riyadh" alone matches RYD-OLY and RYD-MLQ (and RYD-DC for stock questions). For revenue by city, sum all matching stores; for a named store ask only if the answer would differ materially. Online, Mobile App and B2B revenue belongs to RYD-DC.

## Regions

Central (Riyadh), Western (Jeddah, Madinah), Eastern (Dammam, Al Khobar), Southern (Abha). "Hijaz" refers to the Western region; "Eastern Province" is the Eastern region.

## Product Lines

| Canonical name | Code | Synonyms |
|---|---|---|
| Consumer Electronics | ELEC | electronics, gadgets, phones and laptops, tech |
| Home Appliances | APPL | appliances, white goods, fans and air conditioners, cooling |
| Fashion and Apparel | FASH | fashion, clothing, apparel, thobes and abayas |
| Grocery and Gourmet | GROC | grocery, food, groceries, dates |
| Beauty and Fragrance | BEAU | beauty, perfume, fragrance, oud, cosmetics |
| Sports and Outdoor | SPRT | sports, outdoor, camping, fitness |
| Kids and School | KIDS | kids, school supplies, toys, baby |
| Home Decor and Furnishing | HOME | home, decor, furniture, furnishing |

"Product line" and "category" mean the same thing.

## Channels and Payment Methods

- Channels: In-Store (stores, walk-in, physical), Online (website), Mobile App (app), B2B (business, corporate, contract customers). "Digital" or "e-commerce" means Online plus Mobile App.
- Payment methods: Mada, Credit Card, Apple Pay, STC Pay, Cash, Cash on Delivery (COD), Buy Now Pay Later (BNPL, installments), Bank Transfer.

## Metric Words

| User says | Canonical meaning |
|---|---|
| sales, revenue, turnover, income | Net revenue: sum of line totals of Completed orders, excluding VAT |
| gross sales | Net revenue plus line discounts |
| profit, margin, gross profit | Net revenue minus cost of goods (line margin) |
| orders, transactions, tickets | Number of distinct orders |
| basket, average basket, AOV, ticket size | Average order value (net revenue divided by orders) |
| units, quantity, volume | Units sold |
| stock, inventory, on hand, quantity | Quantity on hand or available quantity (state which) |
| available stock | Quantity on hand minus reserved |
| demand | Units sold (for forecasting, weekly units) |
| attainment, target achievement | Net revenue divided by monthly target |

## Seasons and Events

| Canonical name | Spellings and aliases |
|---|---|
| Ramadan | Ramadhan, Ramzan, the holy month |
| Eid al-Fitr | Eid ul-Fitr, Id al-Fitr, Eid after Ramadan, small Eid |
| Hajj and Eid al-Adha | Hajj season, Eid ul-Adha, Id al-Adha, big Eid, Arafat |
| White Friday | Black Friday, white friday sale |
| National Day | Saudi National Day, 23 September, Yawm al-Watani |
| Founding Day | Saudi Founding Day, 22 February |
| Back to School | school season, BTS |
| Summer | summer season |
| Winter | winter season, camping season |

## Time Phrases (Reference Date 2026-10-31)

| Phrase | Resolved period |
|---|---|
| today, now, current | 2026-10-31 |
| yesterday | 2026-10-30 |
| last week, past week | 2026-10-25 to 2026-10-31 (last complete Sunday to Saturday week) |
| this week | 2026-11-01 onwards: no data yet; use last week and say so |
| last month | October 2026: 2026-10-01 to 2026-10-31 |
| this month | October 2026 (month to date, full month of data) |
| last 30 days | 2026-10-02 to 2026-10-31 |
| last quarter | Q3 2026: 2026-07-01 to 2026-09-30 |
| this quarter | Q4 2026 to date: 2026-10-01 to 2026-10-31 |
| this year, year to date, YTD | 2026-01-01 to 2026-10-31 |
| last year | 2025-01-01 to 2025-12-31 |
| next week | Week starting 2026-11-01 (forecast) |
| next month | Weeks starting 2026-11-01 (about 4 weeks, forecast) |
| next quarter | 13 weeks starting 2026-11-01 (forecast) |

## Arabic Business Terms (Transliterated)

Arabic questions are translated to English before routing. These common terms show the intended meaning.

| Transliteration | English meaning |
|---|---|
| mabi'at | sales |
| iradat | revenue |
| arbah | profits |
| mukhzun | stock or inventory |
| mawrid, muwarridin | supplier, suppliers |
| fari', furu' | branch, branches |
| 'umala' | customers |
| mustarajaat | returns |
| 'urud | promotions or offers |
| tawaqqu' | forecast |
| siyasa | policy |
| 'aqd | contract |

Eastern Arabic-Indic digits are converted to Western digits (0-9) before routing, and answers use Western digits.

## Product Name Hints

Users usually give the product name without the SKU. Map to the SKU using the catalog in the knowledge base: for example "tower fan" is APPL-0004 (AirWhirl Tower Fan), "khalas dates" is GROC-0001, "4-person tent" is SPRT-0001, "backpack 18-inch" is KIDS-0001. If a name matches several SKUs, the sub-question lists the candidates and asks the subgraph to answer for all of them.
