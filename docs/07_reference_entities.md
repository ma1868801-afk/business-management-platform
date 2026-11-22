# 07. Reference Entities Registry

This document is the single source of truth for every named entity and fixed parameter of the fictional company **Nakhla Retail Group**. The knowledge base documents, the RAG schema references, the evaluation scenarios and the Phase 2 data generator all read from the same values, so they cannot disagree. All people, companies and figures are fictional.

Rules for using this registry:

- A value that appears here must appear identically everywhere else (for example a supplier lead time in a contract, in `suppliers.lead_time_days` and in an evaluation scenario).
- Dates before 2026-11-01 are facts. The reference date for all analysis is 2026-10-31 (assumption A-03).
- Weights, ranges and caps in sections 3 to 5 are generator inputs for Phase 2. They are not statements about the final data, which is checked by the guarantees G-01 to G-38 in `03_database_design.md`.

## 1. Company Constants

| Item | Value |
|---|---|
| Company | Nakhla Retail Group (Saudi multi-category retailer) |
| Locations | 9: eight retail stores and one Distribution Center |
| Product lines | 8 lines, 120 SKUs (15 per line) |
| Suppliers | 16 contracted suppliers (2 per product line) |
| Contract business customers | 12 accounts with contracts |
| Loyalty programme | Nakhla Rewards (None, Silver, Gold, Platinum) |
| Currency | SAR (Saudi riyal) |
| VAT | 15 percent; prices and revenue in the database exclude VAT |
| Time zone | Asia/Riyadh (UTC+3); timestamps stored as local time |
| Retail week | Sunday to Saturday; weekend is Friday and Saturday |
| Data period | 2024-01-01 to 2026-10-31 (1,035 days) |
| Reference date | 2026-10-31 (Saturday) |
| First forecast week | 2026-11-01 (Sunday); maximum horizon 13 weeks |

## 2. Locations

Store base weights are the relative in-store demand used by the Phase 2 generator. The Distribution Center has no in-store demand; it carries all Online, Mobile App and B2B orders.

| Code | Name | City | Region | Type | Opened | Area (sqm) | Staff | Manager | Opening hours | Base weight |
|---|---|---|---|---|---|---|---|---|---|---|
| RYD-OLY | Riyadh Olaya Flagship | Riyadh | Central | Flagship Store | 2016-03-15 | 4,200 | 78 | Faisal Al-Harbi | 10:00-23:00 | 100 |
| JED-THL | Jeddah Tahlia Flagship | Jeddah | Western | Flagship Store | 2017-09-20 | 3,800 | 70 | Nasser Al-Ghamdi | 10:00-23:00 | 82 |
| RYD-MLQ | Riyadh Malqa Standard | Riyadh | Central | Standard Store | 2019-05-12 | 2,600 | 46 | Huda Al-Otaibi | 10:00-23:00 | 58 |
| DMM-FSL | Dammam Faisaliyah Standard | Dammam | Eastern | Standard Store | 2018-11-08 | 2,400 | 42 | Abdullah Al-Dossary | 10:00-23:00 | 50 |
| KHB-COR | Al Khobar Corniche Standard | Al Khobar | Eastern | Standard Store | 2020-02-27 | 2,300 | 40 | Reem Al-Qahtani | 10:00-23:00 | 46 |
| MED-QBA | Madinah Quba Standard | Madinah | Western | Standard Store | 2019-10-03 | 2,100 | 38 | Yousef Al-Juhani | 10:00-23:00 | 36 |
| JED-OBH | Jeddah Obhur Express | Jeddah | Western | Express Store | 2021-06-17 | 1,100 | 20 | Salma Al-Zahrani | 11:00-23:00 | 24 |
| ABH-CTY | Abha City Express | Abha | Southern | Express Store | 2022-04-21 | 950 | 17 | Mohammed Al-Asmari | 11:00-23:00 | 18 |
| RYD-DC | Riyadh Distribution Center | Riyadh | Central | Distribution Center | 2015-08-01 | 18,000 | 95 | Khalid Al-Mutairi | 24/7 | n/a |

Expected 2025 store ranking by net revenue (RYD-DC excluded): RYD-OLY, JED-THL, RYD-MLQ, DMM-FSL, KHB-COR, MED-QBA, JED-OBH, ABH-CTY.

## 3. Product Lines

| ID | Code | Line | Department | Target margin % | Peak season | Price range (SAR) | Discount cap % |
|---|---|---|---|---|---|---|---|
| 1 | ELEC | Consumer Electronics | Technology | 14.0 | White Friday | 100 to 4,200 | 25 |
| 2 | APPL | Home Appliances | Technology | 22.0 | Summer | 90 to 3,200 | 25 |
| 3 | FASH | Fashion and Apparel | Lifestyle | 46.0 | Eid al-Fitr | 40 to 650 | 50 |
| 4 | GROC | Grocery and Gourmet | Consumables | 24.0 | Ramadan | 6 to 180 | 20 |
| 5 | BEAU | Beauty and Fragrance | Lifestyle | 55.0 | Eid al-Fitr and National Day | 25 to 900 | 30 |
| 6 | SPRT | Sports and Outdoor | Family and Leisure | 34.0 | Winter | 35 to 1,800 | 40 |
| 7 | KIDS | Kids and School | Family and Leisure | 38.0 | Back to School | 8 to 420 | 35 |
| 8 | HOME | Home Decor and Furnishing | Lifestyle | 44.0 | Ramadan and White Friday | 30 to 1,500 | 40 |

Margin expectations: Beauty and Fragrance has the highest target margin and Consumer Electronics the lowest. Consumer Electronics is the highest-revenue line; Grocery and Gourmet is the highest-volume line.

## 4. Suppliers

Each contract has an initial term of 36 months and renews automatically for 12 months at a time. The end date shown is the end of the current term on 2026-10-31. The on-time delivery rate is the measured rate over the trailing 24 months. Two suppliers are below 85 percent (SUP-04, SUP-08) and four are below 90 percent (those two plus SUP-06 and SUP-12).

| Code | Supplier | Country | City | Line | Lead time (days) | Min order qty | Payment terms (days) | On-time % | Quality | Billing currency | Contract | Start | Current term end |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SUP-01 | Gulf Digital Trading Co. | Saudi Arabia | Riyadh | ELEC | 7 | 40 | 45 | 96.5 | 4.6 | SAR | SC-2023-001 | 2023-02-01 | 2027-01-31 |
| SUP-02 | Shenzhen Nova Electronics Ltd. | China | Shenzhen | ELEC | 42 | 200 | 60 | 91.0 | 4.2 | USD | SC-2022-002 | 2022-09-01 | 2027-08-31 |
| SUP-03 | Al Jazeera Home Appliances Co. | Saudi Arabia | Jeddah | APPL | 6 | 25 | 45 | 94.0 | 4.4 | SAR | SC-2023-003 | 2023-04-01 | 2027-03-31 |
| SUP-04 | Istanbul Cooling Systems A.S. | Turkey | Istanbul | APPL | 21 | 60 | 60 | 84.0 | 4.0 | EUR | SC-2023-004 | 2023-06-01 | 2027-05-31 |
| SUP-05 | Levant Fashion House | Jordan | Amman | FASH | 14 | 120 | 45 | 93.0 | 4.3 | USD | SC-2023-005 | 2023-01-15 | 2027-01-14 |
| SUP-06 | Bosphorus Textile Group | Turkey | Istanbul | FASH | 24 | 150 | 60 | 87.5 | 4.1 | EUR | SC-2024-006 | 2024-01-10 | 2027-01-09 |
| SUP-07 | Al Qassim Dates Cooperative | Saudi Arabia | Buraydah | GROC | 4 | 300 | 30 | 97.5 | 4.7 | SAR | SC-2022-007 | 2022-11-01 | 2027-10-31 |
| SUP-08 | Mediterranean Gourmet Imports | United Arab Emirates | Dubai | GROC | 9 | 250 | 30 | 82.5 | 3.9 | AED | SC-2024-008 | 2024-03-01 | 2027-02-28 |
| SUP-09 | Dubai Oud and Perfumes FZE | United Arab Emirates | Dubai | BEAU | 8 | 80 | 30 | 95.0 | 4.8 | AED | SC-2023-009 | 2023-05-01 | 2027-04-30 |
| SUP-10 | Paris Beaute Distribution SARL | France | Paris | BEAU | 30 | 100 | 60 | 91.0 | 4.5 | EUR | SC-2023-010 | 2023-09-01 | 2027-08-31 |
| SUP-11 | Tabuk Outdoor Gear Co. | Saudi Arabia | Tabuk | SPRT | 7 | 50 | 45 | 92.5 | 4.2 | SAR | SC-2024-011 | 2024-02-01 | 2027-01-31 |
| SUP-12 | Munich Sport Systems GmbH | Germany | Munich | SPRT | 35 | 80 | 60 | 89.0 | 4.6 | EUR | SC-2022-012 | 2022-10-01 | 2027-09-30 |
| SUP-13 | Cairo Educational Supplies | Egypt | Cairo | KIDS | 18 | 200 | 45 | 90.5 | 4.0 | USD | SC-2024-013 | 2024-05-01 | 2027-04-30 |
| SUP-14 | Bright Minds Toys Ltd. | China | Guangzhou | KIDS | 45 | 250 | 60 | 91.5 | 4.1 | USD | SC-2023-014 | 2023-03-01 | 2027-02-28 |
| SUP-15 | Jeddah Home Interiors Co. | Saudi Arabia | Jeddah | HOME | 5 | 30 | 30 | 98.0 | 4.5 | SAR | SC-2023-015 | 2023-07-01 | 2027-06-30 |
| SUP-16 | Milan Casa Design S.r.l. | Italy | Milan | HOME | 33 | 40 | 60 | 93.5 | 4.7 | EUR | SC-2025-016 | 2025-01-15 | 2028-01-14 |

## 5. Contract Business Customers

Customer codes follow the pattern CUST-B001 to CUST-B012 (`customer_type` = Business). The discount is applied as the line discount on B2B orders. Terms are renewed automatically for 12 months after the initial term.

| Code | Customer | Industry | City | Region | Contract | Start | Initial term (months) | Current term end | B2B discount % | Credit limit (SAR) | Payment terms (days) | Account manager |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CUST-B001 | Al Rawabi Hospitality Group | Hospitality | Riyadh | Central | CC-2023-001 | 2023-03-01 | 24 | 2027-02-28 | 8.0 | 900,000 | 45 | Bandar Al-Rasheed |
| CUST-B002 | Eastern Province Medical Center | Healthcare | Dammam | Eastern | CC-2023-002 | 2023-09-01 | 24 | 2027-08-31 | 6.0 | 450,000 | 30 | Turki Al-Harthi |
| CUST-B003 | Najd Business Schools | Education | Riyadh | Central | CC-2024-003 | 2024-01-01 | 12 | 2026-12-31 | 10.0 | 300,000 | 30 | Bandar Al-Rasheed |
| CUST-B004 | Red Sea Resorts and Spa | Hospitality | Jeddah | Western | CC-2023-004 | 2023-06-01 | 24 | 2027-05-31 | 9.0 | 1,200,000 | 60 | Lina Al-Najjar |
| CUST-B005 | Khobar Business Park Management | Facilities Management | Al Khobar | Eastern | CC-2024-005 | 2024-04-01 | 12 | 2027-03-31 | 5.0 | 200,000 | 30 | Turki Al-Harthi |
| CUST-B006 | Tuwaiq Engineering Contractors | Construction | Riyadh | Central | CC-2023-006 | 2023-11-01 | 24 | 2027-10-31 | 7.0 | 600,000 | 45 | Bandar Al-Rasheed |
| CUST-B007 | Madinah Pilgrim Services Co. | Pilgrim Services | Madinah | Western | CC-2024-007 | 2024-02-01 | 12 | 2027-01-31 | 11.0 | 750,000 | 45 | Lina Al-Najjar |
| CUST-B008 | Asir Tourism Development Co. | Tourism | Abha | Southern | CC-2024-008 | 2024-06-01 | 12 | 2027-05-31 | 8.5 | 350,000 | 30 | Lina Al-Najjar |
| CUST-B009 | Gulf Catering Services | Catering | Dammam | Eastern | CC-2023-009 | 2023-08-01 | 24 | 2027-07-31 | 12.0 | 500,000 | 30 | Turki Al-Harthi |
| CUST-B010 | Hijaz University Staff Fund | Education | Jeddah | Western | CC-2025-010 | 2025-01-01 | 12 | 2026-12-31 | 6.5 | 250,000 | 30 | Lina Al-Najjar |
| CUST-B011 | Riyadh Corporate Gifting Co. | Corporate Gifting | Riyadh | Central | CC-2024-011 | 2024-09-01 | 12 | 2027-08-31 | 10.5 | 800,000 | 60 | Bandar Al-Rasheed |
| CUST-B012 | Al Manara Telecom Staff Association | Telecommunications | Riyadh | Central | CC-2025-012 | 2025-03-01 | 12 | 2027-02-28 | 7.5 | 150,000 | 30 | Bandar Al-Rasheed |

Main product focus per account: CUST-B001: Home Appliances, Home Decor and Furnishing, Grocery and Gourmet; CUST-B002: Consumer Electronics, Home Appliances; CUST-B003: Kids and School, Consumer Electronics; CUST-B004: Home Decor and Furnishing, Beauty and Fragrance, Grocery and Gourmet; CUST-B005: Home Appliances, Consumer Electronics; CUST-B006: Consumer Electronics, Sports and Outdoor; CUST-B007: Grocery and Gourmet, Home Appliances, Fashion and Apparel; CUST-B008: Sports and Outdoor, Home Decor and Furnishing; CUST-B009: Grocery and Gourmet, Home Appliances; CUST-B010: Consumer Electronics, Kids and School; CUST-B011: Beauty and Fragrance, Grocery and Gourmet, Fashion and Apparel; CUST-B012: Consumer Electronics, Sports and Outdoor.

## 6. SKU Master (120 SKUs)

Prices are list prices in SAR excluding VAT. Status values: New (launched in 2026), Active, Declining, Discontinued. Six SKUs are dead stock on the reference date (stock on hand and no completed sale from 2026-08-03 to 2026-10-31): the four Discontinued SKUs and FASH-0013 and HOME-0013.

| SKU | Product | Subcategory | Brand | Price (SAR) | Supplier | Unit | Shelf life (days) | Peak season | Status | Launch | Discontinued |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ELEC-0001 | Zenix Pro 15 Smartphone 256GB | Smartphones | Zenix | 3,199.00 | SUP-02 | Each |  |  | Active | 2022-06-08 |  |
| ELEC-0002 | Zenix Lite 12 Smartphone 128GB | Smartphones | Zenix | 1,299.00 | SUP-02 | Each |  |  | Active | 2020-11-15 |  |
| ELEC-0003 | Novabook Pro 16 Laptop | Laptops and Tablets | Novabook | 4,199.00 | SUP-02 | Each |  |  | Active | 2023-04-22 |  |
| ELEC-0004 | Novabook Student 15 Laptop | Laptops and Tablets | Novabook | 2,199.00 | SUP-02 | Each |  |  | Active | 2021-09-02 |  |
| ELEC-0005 | Tabletek Slate 11 Tablet | Laptops and Tablets | Tabletek | 1,599.00 | SUP-02 | Each |  |  | Active | 2019-02-09 |  |
| ELEC-0006 | SoundArc Wireless Earbuds | Audio | SoundArc | 349.00 | SUP-01 | Each |  |  | Active | 2022-07-16 |  |
| ELEC-0007 | SoundArc Studio Over-Ear Headphones | Audio | SoundArc | 699.00 | SUP-01 | Each |  |  | Active | 2020-12-23 |  |
| ELEC-0008 | PulseFit Smartwatch S2 | Wearables | PulseFit | 899.00 | SUP-01 | Each |  |  | Active | 2023-05-03 |  |
| ELEC-0009 | PulseFit Fitness Band 5 | Wearables | PulseFit | 249.00 | SUP-01 | Each |  |  | Active | 2021-10-10 |  |
| ELEC-0010 | HomeSense Smart Speaker | Smart Home | HomeSense | 279.00 | SUP-01 | Each |  |  | Active | 2019-03-17 |  |
| ELEC-0011 | HomeSense Smart Plug 4-Pack | Smart Home | HomeSense | 159.00 | SUP-01 | Pack |  |  | Active | 2022-08-24 |  |
| ELEC-0012 | PixelView 55-inch 4K Smart TV | TV and Display | PixelView | 2,599.00 | SUP-02 | Each |  |  | Declining | 2020-01-04 |  |
| ELEC-0013 | PixelView 43-inch HD TV (previous generation) | TV and Display | PixelView | 1,099.00 | SUP-02 | Each |  |  | Discontinued | 2021-06-11 | 2026-03-31 |
| ELEC-0014 | Nexa Portable Power Bank 20000mAh | Accessories | Nexa | 189.00 | SUP-01 | Each |  |  | Active | 2021-11-18 |  |
| ELEC-0015 | HomeSense Smart Hub Gen 2 | Smart Home | HomeSense | 449.00 | SUP-01 | Each |  |  | New | 2026-05-17 |  |
| APPL-0001 | BreezeMax Split AC 18000 BTU | Cooling and Fans | BreezeMax | 2,699.00 | SUP-04 | Each |  | Summer | Active | 2023-07-08 |  |
| APPL-0002 | BreezeMax Split AC 24000 BTU | Cooling and Fans | BreezeMax | 3,199.00 | SUP-04 | Each |  | Summer | Active | 2021-12-15 |  |
| APPL-0003 | BreezeMax Portable AC 12000 BTU | Cooling and Fans | BreezeMax | 1,899.00 | SUP-04 | Each |  | Summer | Active | 2019-05-22 |  |
| APPL-0004 | AirWhirl Tower Fan | Cooling and Fans | AirWhirl | 249.00 | SUP-03 | Each |  | Summer | Active | 2022-10-02 |  |
| APPL-0005 | AirWhirl Pedestal Fan 18-inch | Cooling and Fans | AirWhirl | 169.00 | SUP-03 | Each |  | Summer | Active | 2020-03-09 |  |
| APPL-0006 | AquaChill Water Cooler Dispenser | Cooling and Fans | AquaChill | 899.00 | SUP-03 | Each |  | Summer | Active | 2023-08-16 |  |
| APPL-0007 | ChefMate Air Fryer 6L | Kitchen Appliances | ChefMate | 449.00 | SUP-03 | Each |  |  | Active | 2021-01-23 |  |
| APPL-0008 | ChefMate Microwave Oven 30L | Kitchen Appliances | ChefMate | 699.00 | SUP-03 | Each |  |  | Active | 2019-06-03 |  |
| APPL-0009 | ChefMate Espresso Machine | Kitchen Appliances | ChefMate | 1,299.00 | SUP-04 | Each |  |  | Active | 2022-11-10 |  |
| APPL-0010 | FreshKeep French Door Refrigerator | Large Appliances | FreshKeep | 3,199.00 | SUP-04 | Each |  |  | Active | 2020-04-17 |  |
| APPL-0011 | FreshKeep Top-Load Washing Machine 9kg | Large Appliances | FreshKeep | 1,599.00 | SUP-04 | Each |  |  | Active | 2023-09-24 |  |
| APPL-0012 | CleanWave Robot Vacuum | Cleaning | CleanWave | 1,399.00 | SUP-03 | Each |  |  | Active | 2021-02-04 |  |
| APPL-0013 | CleanWave Cordless Stick Vacuum | Cleaning | CleanWave | 899.00 | SUP-03 | Each |  |  | Active | 2019-07-11 |  |
| APPL-0014 | WarmGlow Oil Heater | Heating | WarmGlow | 329.00 | SUP-03 | Each |  | Winter | Declining | 2022-12-18 |  |
| APPL-0015 | ChefMate Smart Blender Pro | Kitchen Appliances | ChefMate | 389.00 | SUP-03 | Each |  |  | New | 2026-06-07 |  |
| FASH-0001 | Al Noor Classic White Thobe | Mens Traditional Wear | Al Noor | 189.00 | SUP-05 | Each |  | Eid al-Fitr | Active | 2019-08-08 |  |
| FASH-0002 | Al Noor Premium Winter Thobe | Mens Traditional Wear | Al Noor | 249.00 | SUP-05 | Each |  | Winter | Active | 2022-01-15 |  |
| FASH-0003 | Layali Embroidered Abaya | Womens Traditional Wear | Layali | 389.00 | SUP-05 | Each |  | Eid al-Fitr | Active | 2020-06-22 |  |
| FASH-0004 | Layali Everyday Black Abaya | Womens Traditional Wear | Layali | 229.00 | SUP-05 | Each |  |  | Active | 2023-11-02 |  |
| FASH-0005 | UrbanLine Slim Jeans | Casual Wear | UrbanLine | 149.00 | SUP-06 | Each |  |  | Active | 2021-04-09 |  |
| FASH-0006 | UrbanLine Cotton Polo Shirt | Casual Wear | UrbanLine | 89.00 | SUP-06 | Each |  |  | Active | 2019-09-16 |  |
| FASH-0007 | UrbanLine Hooded Sweatshirt | Casual Wear | UrbanLine | 129.00 | SUP-06 | Each |  | Winter | Active | 2022-02-23 |  |
| FASH-0008 | StridePro Running Shoes | Footwear | StridePro | 349.00 | SUP-06 | Each |  |  | Active | 2020-07-03 |  |
| FASH-0009 | StridePro Leather Loafers | Footwear | StridePro | 299.00 | SUP-06 | Each |  |  | Active | 2023-12-10 |  |
| FASH-0010 | Layali Silk Scarf | Accessories | Layali | 119.00 | SUP-05 | Each |  |  | Active | 2021-05-17 |  |
| FASH-0011 | Marasim Leather Handbag | Bags | Marasim | 599.00 | SUP-05 | Each |  |  | Active | 2019-10-24 |  |
| FASH-0012 | Marasim Weekend Travel Bag | Bags | Marasim | 249.00 | SUP-05 | Each |  |  | Active | 2022-03-04 |  |
| FASH-0013 | UrbanLine Denim Jacket (old collection) | Casual Wear | UrbanLine | 199.00 | SUP-06 | Each |  |  | Declining | 2020-08-11 |  |
| FASH-0014 | Marasim Evening Clutch (limited 2024 edition) | Bags | Marasim | 159.00 | SUP-05 | Each |  |  | Discontinued | 2021-01-18 | 2026-05-31 |
| FASH-0015 | Layali Linen Kaftan | Womens Traditional Wear | Layali | 329.00 | SUP-05 | Each |  |  | Active | 2024-04-01 |  |
| GROC-0001 | Qassim Gold Khalas Dates 1kg | Dates | Qassim Gold | 45.00 | SUP-07 | Each | 365 | Ramadan | Active | 2020-09-08 |  |
| GROC-0002 | Qassim Gold Sukkari Dates Gift Box 2kg | Dates | Qassim Gold | 129.00 | SUP-07 | Box | 365 | Ramadan | Active | 2023-02-15 |  |
| GROC-0003 | Nakhla Select Ramadan Essentials Basket | Gift Baskets | Nakhla Select | 179.00 | SUP-07 | Each | 180 | Ramadan | Active | 2021-07-22 |  |
| GROC-0004 | Qahwa House Arabic Coffee with Cardamom 500g | Coffee and Tea | Qahwa House | 62.00 | SUP-07 | Each | 270 |  | Active | 2019-12-02 |  |
| GROC-0005 | GoldenGrain Premium Basmati Rice 5kg | Pantry Staples | GoldenGrain | 48.00 | SUP-08 | Each | 540 |  | Active | 2022-05-09 |  |
| GROC-0006 | Olivia Extra Virgin Olive Oil 1L | Pantry Staples | Olivia | 54.00 | SUP-08 | Each | 540 |  | Active | 2020-10-16 |  |
| GROC-0007 | PureFarm Long Life Milk 1L (12 pack) | Dairy and Beverages | PureFarm | 42.00 | SUP-08 | Pack | 120 |  | Active | 2023-03-23 |  |
| GROC-0008 | AquaPure Sparkling Water 330ml (24 pack) | Dairy and Beverages | AquaPure | 28.00 | SUP-08 | Pack | 365 |  | Active | 2021-08-03 |  |
| GROC-0009 | NutHouse Mixed Nuts Tin 800g | Snacks | NutHouse | 68.00 | SUP-08 | Each | 240 |  | Active | 2019-01-10 |  |
| GROC-0010 | Chocolat Royal Belgian Chocolate Selection Box | Confectionery | Chocolat Royal | 89.00 | SUP-08 | Box | 300 | Eid al-Fitr | Active | 2022-06-17 |  |
| GROC-0011 | Zafran Co Saffron Threads 5g | Spices | Zafran Co | 76.00 | SUP-08 | Each | 720 |  | Active | 2020-11-24 |  |
| GROC-0012 | Qamar Al-Din Apricot Drink 1L | Dairy and Beverages | Qamar Al-Din | 12.00 | SUP-07 | Each | 365 | Ramadan | Active | 2023-04-04 |  |
| GROC-0013 | Bellini Pasta 500g (12 pack) | Pantry Staples | Bellini | 56.00 | SUP-08 | Pack | 720 |  | Active | 2021-09-11 |  |
| GROC-0014 | Nakhla Select Frozen Samosa Ramadan Pack 60 pcs | Frozen Food | Nakhla Select | 38.00 | SUP-07 | Pack | 180 | Ramadan | Declining | 2019-02-18 |  |
| GROC-0015 | BeeBlessed Organic Honey 500g | Pantry Staples | BeeBlessed | 85.00 | SUP-07 | Each | 720 |  | Active | 2025-03-10 |  |
| BEAU-0001 | Oud Royale Eau de Parfum 100ml | Fragrance | Oud Royale | 489.00 | SUP-09 | Each |  | Eid al-Fitr | Active | 2021-10-08 |  |
| BEAU-0002 | Oud Royale Deluxe Gift Set | Fragrance | Oud Royale | 899.00 | SUP-09 | Set |  | Eid al-Fitr | Active | 2019-03-15 |  |
| BEAU-0003 | Bakhoor Incense Burner Gift Set | Fragrance | Oud Royale | 249.00 | SUP-09 | Set |  | National Day | Active | 2022-08-22 |  |
| BEAU-0004 | Musk Attar Oil 12ml | Fragrance | Oud Royale | 129.00 | SUP-09 | Each |  |  | Active | 2020-01-02 |  |
| BEAU-0005 | Rose Garden Eau de Toilette 100ml | Fragrance | Rose Garden | 329.00 | SUP-10 | Each |  |  | Active | 2023-06-09 |  |
| BEAU-0006 | Lumiere Day Moisturizer SPF50 | Skincare | Lumiere | 119.00 | SUP-10 | Each | 730 |  | Active | 2021-11-16 |  |
| BEAU-0007 | Lumiere Night Repair Serum | Skincare | Lumiere | 219.00 | SUP-10 | Each | 730 |  | Active | 2019-04-23 |  |
| BEAU-0008 | Lumiere Hydrating Face Mask 5-Pack | Skincare | Lumiere | 59.00 | SUP-10 | Pack | 540 |  | Active | 2022-09-03 |  |
| BEAU-0009 | SilkLine Shampoo 400ml | Hair Care | SilkLine | 35.00 | SUP-10 | Each | 900 |  | Active | 2020-02-10 |  |
| BEAU-0010 | SilkLine Argan Hair Oil 100ml | Hair Care | SilkLine | 69.00 | SUP-10 | Each | 900 |  | Active | 2023-07-17 |  |
| BEAU-0011 | ColorPop Matte Lipstick | Makeup | ColorPop | 79.00 | SUP-10 | Each | 900 |  | Active | 2021-12-24 |  |
| BEAU-0012 | ColorPop Stay-Matte Foundation | Makeup | ColorPop | 119.00 | SUP-10 | Each | 900 |  | Active | 2019-05-04 |  |
| BEAU-0013 | Barber and Co Beard Care Kit | Mens Grooming | Barber and Co | 159.00 | SUP-09 | Set |  |  | Active | 2022-10-11 |  |
| BEAU-0014 | Barber and Co Electric Trimmer | Mens Grooming | Barber and Co | 249.00 | SUP-09 | Each |  |  | Declining | 2020-03-18 |  |
| BEAU-0015 | Lumiere Vitamin C Serum | Skincare | Lumiere | 189.00 | SUP-10 | Each | 730 |  | New | 2026-06-21 |  |
| SPRT-0001 | TrailNest 4-Person Camping Tent | Camping Gear | TrailNest | 799.00 | SUP-11 | Each |  | Winter | Active | 2022-11-08 |  |
| SPRT-0002 | TrailNest 2-Person Camping Tent | Camping Gear | TrailNest | 449.00 | SUP-11 | Each |  | Winter | Active | 2020-04-15 |  |
| SPRT-0003 | TrailNest Sleeping Bag (-5C) | Camping Gear | TrailNest | 279.00 | SUP-11 | Each |  | Winter | Active | 2023-09-22 |  |
| SPRT-0004 | TrailNest Portable Camping Stove | Camping Gear | TrailNest | 189.00 | SUP-11 | Each |  | Winter | Active | 2021-02-02 |  |
| SPRT-0005 | Summit 65L Trekking Backpack | Hiking | Summit | 459.00 | SUP-12 | Pack |  |  | Active | 2019-07-09 |  |
| SPRT-0006 | IronCore Adjustable Dumbbell Set 24kg | Fitness Equipment | IronCore | 649.00 | SUP-12 | Set |  |  | Active | 2022-12-16 |  |
| SPRT-0007 | IronCore Treadmill T500 | Fitness Equipment | IronCore | 1,799.00 | SUP-12 | Each |  |  | Active | 2020-05-23 |  |
| SPRT-0008 | FlexFit Yoga Mat | Fitness Equipment | FlexFit | 79.00 | SUP-12 | Each |  |  | Active | 2023-10-03 |  |
| SPRT-0009 | FlexFit Resistance Bands Set | Fitness Equipment | FlexFit | 59.00 | SUP-12 | Set |  |  | Active | 2021-03-10 |  |
| SPRT-0010 | VeloCity Road Bike 21-Speed | Cycling | VeloCity | 1,499.00 | SUP-12 | Each |  |  | Active | 2019-08-17 |  |
| SPRT-0011 | VeloCity Cycling Helmet | Cycling | VeloCity | 159.00 | SUP-12 | Each |  |  | Active | 2022-01-24 |  |
| SPRT-0012 | AquaGlide Swim Goggles | Water Sports | AquaGlide | 49.00 | SUP-11 | Each |  |  | Active | 2020-06-04 |  |
| SPRT-0013 | PlayZone Football Size 5 | Team Sports | PlayZone | 89.00 | SUP-11 | Each |  |  | Declining | 2023-11-11 |  |
| SPRT-0014 | PlayZone Classic Tennis Racket | Team Sports | PlayZone | 329.00 | SUP-11 | Each |  |  | Discontinued | 2021-04-18 | 2026-06-30 |
| SPRT-0015 | Hydro Insulated Bottle 1L | Accessories | Hydro | 85.00 | SUP-11 | Each |  |  | Active | 2024-09-15 |  |
| KIDS-0001 | SchoolPro Backpack 18-inch | School Bags | SchoolPro | 129.00 | SUP-13 | Pack |  | Back to School | Active | 2023-12-08 |  |
| KIDS-0002 | SchoolPro Rolling Backpack | School Bags | SchoolPro | 219.00 | SUP-13 | Pack |  | Back to School | Active | 2021-05-15 |  |
| KIDS-0003 | SchoolPro Lunch Box Set | School Bags | SchoolPro | 49.00 | SUP-13 | Set |  | Back to School | Active | 2019-10-22 |  |
| KIDS-0004 | WriteWell Notebook Set 10-Pack | Stationery | WriteWell | 36.00 | SUP-13 | Set |  | Back to School | Active | 2022-03-02 |  |
| KIDS-0005 | WriteWell Pencil Case and Pens Kit | Stationery | WriteWell | 29.00 | SUP-13 | Set |  | Back to School | Active | 2020-08-09 |  |
| KIDS-0006 | ArtBox Colouring Set 72 pcs | Arts and Crafts | ArtBox | 55.00 | SUP-13 | Set |  |  | Active | 2023-01-16 |  |
| KIDS-0007 | BrickWorld Building Blocks 500 pcs | Toys | BrickWorld | 149.00 | SUP-14 | Each |  |  | Active | 2021-06-23 |  |
| KIDS-0008 | BrickWorld Remote Control Car | Toys | BrickWorld | 199.00 | SUP-14 | Each |  |  | Active | 2019-11-03 |  |
| KIDS-0009 | LittleLearners Educational Tablet | Learning Products | LittleLearners | 329.00 | SUP-14 | Each |  |  | Active | 2022-04-10 |  |
| KIDS-0010 | LittleLearners Arabic Alphabet Puzzle | Learning Products | LittleLearners | 39.00 | SUP-14 | Each |  |  | Active | 2020-09-17 |  |
| KIDS-0011 | Cuddle Plush Camel Toy | Toys | Cuddle | 59.00 | SUP-14 | Each |  |  | Active | 2023-02-24 |  |
| KIDS-0012 | TinyTots Baby Stroller Lite | Baby Gear | TinyTots | 419.00 | SUP-14 | Each |  |  | Active | 2021-07-04 |  |
| KIDS-0013 | TinyTots Baby Bottle Set | Baby Gear | TinyTots | 45.00 | SUP-14 | Set |  |  | Active | 2019-12-11 |  |
| KIDS-0014 | BrightKids Classic Geometry Set | Stationery | BrightKids | 18.00 | SUP-13 | Set |  |  | Declining | 2022-05-18 |  |
| KIDS-0015 | LittleLearners Coding Robot Kit | Learning Products | LittleLearners | 279.00 | SUP-14 | Set |  |  | New | 2026-07-12 |  |
| HOME-0001 | Dar Al Zakhrafa Ramadan Lantern Large | Decor | Dar Al Zakhrafa | 149.00 | SUP-15 | Each |  | Ramadan | Active | 2019-01-08 |  |
| HOME-0002 | Dar Al Zakhrafa Ramadan Table Linen Set | Decor | Dar Al Zakhrafa | 129.00 | SUP-15 | Set |  | Ramadan | Active | 2022-06-15 |  |
| HOME-0003 | Majlis Floor Cushion Set | Furniture | Majlis | 599.00 | SUP-15 | Set |  |  | Active | 2020-11-22 |  |
| HOME-0004 | Casa Moderne 3-Seater Sofa | Furniture | Casa Moderne | 1,499.00 | SUP-16 | Each |  |  | Active | 2023-04-02 |  |
| HOME-0005 | Casa Moderne Coffee Table | Furniture | Casa Moderne | 549.00 | SUP-16 | Each |  |  | Active | 2021-09-09 |  |
| HOME-0006 | Lumina LED Floor Lamp | Lighting | Lumina | 249.00 | SUP-16 | Each |  |  | Active | 2019-02-16 |  |
| HOME-0007 | Lumina Crystal Chandelier | Lighting | Lumina | 1,299.00 | SUP-16 | Each |  |  | Active | 2022-07-23 |  |
| HOME-0008 | SoftHome Cotton Bedding Set Queen | Bedding | SoftHome | 349.00 | SUP-15 | Set |  |  | Active | 2020-12-03 |  |
| HOME-0009 | SoftHome Memory Foam Pillow 2-Pack | Bedding | SoftHome | 159.00 | SUP-15 | Pack |  |  | Active | 2023-05-10 |  |
| HOME-0010 | Weave Persian-Style Rug 200x300 | Rugs | Weave | 899.00 | SUP-16 | Each |  |  | Active | 2021-10-17 |  |
| HOME-0011 | CookWell Non-Stick Cookware Set | Kitchenware | CookWell | 429.00 | SUP-15 | Set |  |  | Active | 2019-03-24 |  |
| HOME-0012 | CookWell Dinner Set 24 pcs | Kitchenware | CookWell | 299.00 | SUP-15 | Set |  |  | Active | 2022-08-04 |  |
| HOME-0013 | Dar Al Zakhrafa Wall Art Canvas (old collection) | Decor | Dar Al Zakhrafa | 199.00 | SUP-15 | Each |  |  | Declining | 2020-01-11 |  |
| HOME-0014 | Casa Moderne Shoe Cabinet (retired) | Furniture | Casa Moderne | 449.00 | SUP-16 | Each |  |  | Discontinued | 2020-06-18 | 2026-07-15 |
| HOME-0015 | OrganizeIt Storage Boxes 6-Pack | Storage | OrganizeIt | 89.00 | SUP-15 | Pack |  |  | Active | 2025-05-20 |  |

## 7. Season Windows

Each calendar day has one commercial season. When windows overlap, the season with the highest precedence wins. Precedence from highest to lowest: White Friday, Eid al-Fitr, Hajj and Eid al-Adha, Ramadan, National Day, Founding Day, Back to School, Summer, Winter, Regular. Winter covers 1 December to the end of February. Every other day is Regular. `is_ramadan` stays true for the whole of Ramadan even when the season value is Eid al-Fitr; `is_eid` is true in the Eid al-Fitr and Hajj and Eid al-Adha seasons.

| Year | Season | Start | End | Definition |
|---|---|---|---|---|
| 2024 | Founding Day | 2024-02-20 | 2024-02-23 | 20 to 23 February; public holiday on 22 February |
| 2024 | Ramadan | 2024-03-11 | 2024-04-09 | 1 to 29/30 Ramadan; the last 7 days are classified as Eid al-Fitr by precedence |
| 2024 | Eid al-Fitr | 2024-04-03 | 2024-04-12 | last 7 days of Ramadan plus 1 to 3 Shawwal |
| 2024 | Summer | 2024-06-01 | 2024-08-31 | 1 June to 31 August, lowest precedence among events (August is overridden by Back to School) |
| 2024 | Hajj and Eid al-Adha | 2024-06-11 | 2024-06-20 | Arafat Day minus 4 days to Arafat Day plus 5 days |
| 2024 | Back to School | 2024-08-01 | 2024-09-15 | 1 August to 15 September |
| 2024 | National Day | 2024-09-18 | 2024-09-24 | 18 to 24 September; public holiday on 23 September |
| 2024 | White Friday | 2024-11-22 | 2024-12-01 | Friday one week before White Friday to the Sunday after |
| 2025 | Founding Day | 2025-02-20 | 2025-02-23 | 20 to 23 February; public holiday on 22 February |
| 2025 | Ramadan | 2025-03-01 | 2025-03-29 | 1 to 29/30 Ramadan; the last 7 days are classified as Eid al-Fitr by precedence |
| 2025 | Eid al-Fitr | 2025-03-23 | 2025-04-01 | last 7 days of Ramadan plus 1 to 3 Shawwal |
| 2025 | Hajj and Eid al-Adha | 2025-06-01 | 2025-06-10 | Arafat Day minus 4 days to Arafat Day plus 5 days |
| 2025 | Summer | 2025-06-01 | 2025-08-31 | 1 June to 31 August, lowest precedence among events (August is overridden by Back to School) |
| 2025 | Back to School | 2025-08-01 | 2025-09-15 | 1 August to 15 September |
| 2025 | National Day | 2025-09-18 | 2025-09-24 | 18 to 24 September; public holiday on 23 September |
| 2025 | White Friday | 2025-11-21 | 2025-11-30 | Friday one week before White Friday to the Sunday after |
| 2026 | Ramadan | 2026-02-18 | 2026-03-19 | 1 to 29/30 Ramadan; the last 7 days are classified as Eid al-Fitr by precedence |
| 2026 | Founding Day | 2026-02-20 | 2026-02-23 | 20 to 23 February; public holiday on 22 February |
| 2026 | Eid al-Fitr | 2026-03-13 | 2026-03-22 | last 7 days of Ramadan plus 1 to 3 Shawwal |
| 2026 | Hajj and Eid al-Adha | 2026-05-22 | 2026-05-31 | Arafat Day minus 4 days to Arafat Day plus 5 days |
| 2026 | Summer | 2026-06-01 | 2026-08-31 | 1 June to 31 August, lowest precedence among events (August is overridden by Back to School) |
| 2026 | Back to School | 2026-08-01 | 2026-09-15 | 1 August to 15 September |
| 2026 | National Day | 2026-09-18 | 2026-09-24 | 18 to 24 September; public holiday on 23 September |
| 2026 | White Friday | 2026-11-20 | 2026-11-29 | Friday one week before White Friday to the Sunday after (planning estimate) |

Public holidays (`calendar.is_holiday` and `holiday_name`):

| Year | Holiday | First day | Last day |
|---|---|---|---|
| 2024 | Founding Day | 2024-02-22 | 2024-02-22 |
| 2024 | Eid al-Fitr Holiday | 2024-04-09 | 2024-04-12 |
| 2024 | Arafat Day | 2024-06-15 | 2024-06-15 |
| 2024 | Eid al-Adha Holiday | 2024-06-16 | 2024-06-19 |
| 2024 | National Day | 2024-09-23 | 2024-09-23 |
| 2025 | Founding Day | 2025-02-22 | 2025-02-22 |
| 2025 | Eid al-Fitr Holiday | 2025-03-29 | 2025-04-01 |
| 2025 | Arafat Day | 2025-06-05 | 2025-06-05 |
| 2025 | Eid al-Adha Holiday | 2025-06-06 | 2025-06-09 |
| 2025 | National Day | 2025-09-23 | 2025-09-23 |
| 2026 | Founding Day | 2026-02-22 | 2026-02-22 |
| 2026 | Eid al-Fitr Holiday | 2026-03-19 | 2026-03-22 |
| 2026 | Arafat Day | 2026-05-26 | 2026-05-26 |
| 2026 | Eid al-Adha Holiday | 2026-05-27 | 2026-05-30 |
| 2026 | National Day | 2026-09-23 | 2026-09-23 |

Islamic dates for 2024 to 2026 follow the dates announced in Saudi Arabia: Ramadan 2026 ran from 2026-02-18 to 2026-03-19 and Eid al-Fitr fell on 2026-03-20; Arafat Day 2026 was 2026-05-26 and Eid al-Adha began on 2026-05-27. White Friday 2026 (2026-11-27) is a planning estimate beyond the data period. Founding Day 2026 (22 February) fell inside Ramadan, so its season value is Ramadan while its holiday flag stays true. The payday flag covers the 25th to the 28th of every month.

## 8. Promotions (40)

Store-wide promotions never exceed 20 percent, the lowest line cap; line promotions stay at or below the cap of their line. Line discount caps: ELEC 25, APPL 25, FASH 50, GROC 20, BEAU 30, SPRT 40, KIDS 35, HOME 40 percent.

| ID | Code | Name | Type | Discount % | Start | End | Season | Line | Channel scope | Min basket (SAR) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PROMO-WC-2024 | Winter Camping Clearance 2024 | Clearance | 30.0 | 2024-01-01 | 2024-01-31 | Winter | SPRT | All |  |
| 2 | PROMO-HRF-2024 | Home Refresh Before Ramadan 2024 | Percentage Off | 20.0 | 2024-02-12 | 2024-03-10 | Ramadan | HOME | All |  |
| 3 | PROMO-FD-2024 | Founding Day Rewards 2024 | Loyalty Bonus | 10.0 | 2024-02-20 | 2024-02-23 | Founding Day | All lines | All |  |
| 4 | PROMO-RAM-2024 | Ramadan Kareem Offers 2024 | Seasonal Sale | 10.0 | 2024-03-11 | 2024-04-09 | Ramadan | All lines | All | 150 |
| 5 | PROMO-RAMG-2024 | Ramadan Grocery Basket Deals 2024 | Percentage Off | 15.0 | 2024-03-11 | 2024-04-09 | Ramadan | GROC | In-Store |  |
| 6 | PROMO-EIDB-2024 | Eid Gifting Fragrance Offers 2024 | Bundle Deal | 15.0 | 2024-04-03 | 2024-04-12 | Eid al-Fitr | BEAU | All |  |
| 7 | PROMO-EIDF-2024 | Eid al-Fitr Fashion Festival 2024 | Percentage Off | 20.0 | 2024-04-03 | 2024-04-12 | Eid al-Fitr | FASH | All |  |
| 8 | PROMO-SUM-2024 | Summer Cooling Sale 2024 | Percentage Off | 15.0 | 2024-06-01 | 2024-07-31 | Summer | APPL | All |  |
| 9 | PROMO-EIDA-2024 | Eid al-Adha Celebration 2024 | Seasonal Sale | 10.0 | 2024-06-11 | 2024-06-20 | Hajj and Eid al-Adha | All lines | All |  |
| 10 | PROMO-BTS-2024 | Back to School Savings 2024 | Percentage Off | 20.0 | 2024-08-01 | 2024-09-15 | Back to School | KIDS | All |  |
| 11 | PROMO-ND-2024 | Saudi National Day Offers 2024 | Seasonal Sale | 12.0 | 2024-09-18 | 2024-09-24 | National Day | All lines | All | 200 |
| 12 | PROMO-NDB-2024 | National Day Fragrance Bundle 2024 | Bundle Deal | 15.0 | 2024-09-18 | 2024-09-24 | National Day | BEAU | Online |  |
| 13 | PROMO-WF-2024 | White Friday 2024 | Percentage Off | 15.0 | 2024-11-22 | 2024-12-01 | White Friday | All lines | All | 300 |
| 14 | PROMO-WFE-2024 | White Friday Electronics Deals 2024 | Percentage Off | 25.0 | 2024-11-22 | 2024-12-01 | White Friday | ELEC | All |  |
| 15 | PROMO-WC-2025 | Winter Camping Clearance 2025 | Clearance | 30.0 | 2024-12-01 | 2025-01-31 | Winter | SPRT | All |  |
| 16 | PROMO-HRF-2025 | Home Refresh Before Ramadan 2025 | Percentage Off | 20.0 | 2025-02-01 | 2025-02-28 | Ramadan | HOME | All |  |
| 17 | PROMO-FD-2025 | Founding Day Rewards 2025 | Loyalty Bonus | 10.0 | 2025-02-20 | 2025-02-23 | Founding Day | All lines | All |  |
| 18 | PROMO-RAM-2025 | Ramadan Kareem Offers 2025 | Seasonal Sale | 10.0 | 2025-03-01 | 2025-03-29 | Ramadan | All lines | All | 150 |
| 19 | PROMO-RAMG-2025 | Ramadan Grocery Basket Deals 2025 | Percentage Off | 15.0 | 2025-03-01 | 2025-03-29 | Ramadan | GROC | In-Store |  |
| 20 | PROMO-EIDB-2025 | Eid Gifting Fragrance Offers 2025 | Bundle Deal | 15.0 | 2025-03-23 | 2025-04-01 | Eid al-Fitr | BEAU | All |  |
| 21 | PROMO-EIDF-2025 | Eid al-Fitr Fashion Festival 2025 | Percentage Off | 20.0 | 2025-03-23 | 2025-04-01 | Eid al-Fitr | FASH | All |  |
| 22 | PROMO-EIDA-2025 | Eid al-Adha Celebration 2025 | Seasonal Sale | 10.0 | 2025-06-01 | 2025-06-10 | Hajj and Eid al-Adha | All lines | All |  |
| 23 | PROMO-SUM-2025 | Summer Cooling Sale 2025 | Percentage Off | 15.0 | 2025-06-01 | 2025-07-31 | Summer | APPL | All |  |
| 24 | PROMO-BTS-2025 | Back to School Savings 2025 | Percentage Off | 20.0 | 2025-08-01 | 2025-09-15 | Back to School | KIDS | All |  |
| 25 | PROMO-ND-2025 | Saudi National Day Offers 2025 | Seasonal Sale | 12.0 | 2025-09-18 | 2025-09-24 | National Day | All lines | All | 200 |
| 26 | PROMO-NDB-2025 | National Day Fragrance Bundle 2025 | Bundle Deal | 15.0 | 2025-09-18 | 2025-09-24 | National Day | BEAU | Online |  |
| 27 | PROMO-WF-2025 | White Friday 2025 | Percentage Off | 15.0 | 2025-11-21 | 2025-11-30 | White Friday | All lines | All | 300 |
| 28 | PROMO-WFE-2025 | White Friday Electronics Deals 2025 | Percentage Off | 25.0 | 2025-11-21 | 2025-11-30 | White Friday | ELEC | All |  |
| 29 | PROMO-WC-2026 | Winter Camping Clearance 2026 | Clearance | 30.0 | 2025-12-01 | 2026-01-31 | Winter | SPRT | All |  |
| 30 | PROMO-HRF-2026 | Home Refresh Before Ramadan 2026 | Percentage Off | 20.0 | 2026-01-21 | 2026-02-17 | Ramadan | HOME | All |  |
| 31 | PROMO-RAM-2026 | Ramadan Kareem Offers 2026 | Seasonal Sale | 10.0 | 2026-02-18 | 2026-03-19 | Ramadan | All lines | All | 150 |
| 32 | PROMO-RAMG-2026 | Ramadan Grocery Basket Deals 2026 | Percentage Off | 15.0 | 2026-02-18 | 2026-03-19 | Ramadan | GROC | In-Store |  |
| 33 | PROMO-FD-2026 | Founding Day Rewards 2026 | Loyalty Bonus | 10.0 | 2026-02-20 | 2026-02-23 | Founding Day | All lines | All |  |
| 34 | PROMO-EIDB-2026 | Eid Gifting Fragrance Offers 2026 | Bundle Deal | 15.0 | 2026-03-13 | 2026-03-22 | Eid al-Fitr | BEAU | All |  |
| 35 | PROMO-EIDF-2026 | Eid al-Fitr Fashion Festival 2026 | Percentage Off | 20.0 | 2026-03-13 | 2026-03-22 | Eid al-Fitr | FASH | All |  |
| 36 | PROMO-EIDA-2026 | Eid al-Adha Celebration 2026 | Seasonal Sale | 10.0 | 2026-05-22 | 2026-05-31 | Hajj and Eid al-Adha | All lines | All |  |
| 37 | PROMO-SUM-2026 | Summer Cooling Sale 2026 | Percentage Off | 15.0 | 2026-06-01 | 2026-07-31 | Summer | APPL | All |  |
| 38 | PROMO-BTS-2026 | Back to School Savings 2026 | Percentage Off | 20.0 | 2026-08-01 | 2026-09-15 | Back to School | KIDS | All |  |
| 39 | PROMO-ND-2026 | Saudi National Day Offers 2026 | Seasonal Sale | 12.0 | 2026-09-18 | 2026-09-24 | National Day | All lines | All | 200 |
| 40 | PROMO-NDB-2026 | National Day Fragrance Bundle 2026 | Bundle Deal | 15.0 | 2026-09-18 | 2026-09-24 | National Day | BEAU | Online |  |

## 9. Policy Parameters

| Policy | Parameter | Value |
|---|---|---|
| Loyalty | Tier rule | Tier is set by trailing 12-month net spend (excluding VAT) of an individual customer, recalculated nightly |
| Loyalty | Silver / Gold / Platinum thresholds | SAR 3,000 / SAR 10,000 / SAR 25,000 |
| Loyalty | Points | 1 point per SAR 10 of net spend; 100 points redeem for SAR 5 |
| Loyalty | Member discount on non-promotional lines | Gold 5 percent, Platinum 10 percent |
| Delivery | Delivery fee | SAR 25 on Online and Mobile App orders with subtotal under SAR 250 from customers who are not Gold or Platinum |
| Delivery | Free delivery | Orders of SAR 250 or more, all Gold and Platinum orders, all In-Store and B2B orders |
| Returns | Return window | 14 days from the order date; 30 days for Defective items |
| Returns | Restocking | Defective and Damaged in Transit returns are not restocked |
| Sales targets | Monthly target | Same month of the previous year multiplied by 1.10 |
| Inventory | Service level by ABC class | A 98 percent (z 2.05), B 95 percent (z 1.65), C 90 percent (z 1.28) |
| Inventory | Reorder point | Demand during lead time plus safety stock |
| Inventory | Maximum stock level | Reorder point plus reorder quantity |
| Inventory | Dead stock | Stock on hand and no completed sale in the last 13 weeks |
| Inventory | Stock status order | Out of Stock, Critical, Reorder Now, Overstock, Healthy |
| Procurement | Supplier on-time target | 92 percent |
| Procurement | Late delivery penalty | 0.5 percent of the late line value per day, capped at 5 percent |
| Procurement | PO approval | Up to SAR 50,000: Procurement Manager; SAR 50,001 to SAR 250,000: Head of Supply Chain; above SAR 250,000: Chief Financial Officer |
| Forecasting | Horizon | Maximum 13 weeks; first forecast week starts 2026-11-01 |

## 10. Leadership and Branch Managers

The full employee records are in the knowledge base (`rag_sources/knowledge_base/employees/`). The branch manager names below match `branches.manager_name`.

| Employee ID | Name | Title | Location |
|---|---|---|---|
| EMP-0001 | Abdulaziz Al-Rashid | Chief Executive Officer | HQ |
| EMP-0002 | Maha Al-Sudairi | Chief Financial Officer | HQ |
| EMP-0003 | Tariq Al-Shehri | Chief Operating Officer | HQ |
| EMP-0004 | Noura Al-Fahad | Chief Commercial Officer | HQ |
| EMP-0005 | Omar Bakr | Chief Technology and Data Officer | HQ |
| EMP-0025 | Faisal Al-Harbi | Branch Manager, Riyadh Olaya Flagship | RYD-OLY |
| EMP-0026 | Huda Al-Otaibi | Branch Manager, Riyadh Malqa Standard | RYD-MLQ |
| EMP-0027 | Khalid Al-Mutairi | Distribution Center Manager | RYD-DC |
| EMP-0028 | Nasser Al-Ghamdi | Branch Manager, Jeddah Tahlia Flagship | JED-THL |
| EMP-0029 | Salma Al-Zahrani | Branch Manager, Jeddah Obhur Express | JED-OBH |
| EMP-0030 | Yousef Al-Juhani | Branch Manager, Madinah Quba Standard | MED-QBA |
| EMP-0031 | Abdullah Al-Dossary | Branch Manager, Dammam Faisaliyah Standard | DMM-FSL |
| EMP-0032 | Reem Al-Qahtani | Branch Manager, Al Khobar Corniche Standard | KHB-COR |
| EMP-0033 | Mohammed Al-Asmari | Branch Manager, Abha City Express | ABH-CTY |

## 11. Open Consistency Note

`03_database_design.md` uses `customer_type` values Individual and Business in the data dictionary, while guarantees G-05 and G-09 refer to type Corporate. The RAG sources and this registry use **Business** (the data dictionary value). Phase 2 should align the guarantee wording or the column values before loading data.
