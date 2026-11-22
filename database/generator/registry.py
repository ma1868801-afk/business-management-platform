"""Single source of truth for all Phase 1 facts (fictional company: Nakhla Retail Group)."""
from datetime import date, timedelta

REF_DATE = date(2026, 10, 31)
DATA_START = date(2024, 1, 1)
COMPANY = "Nakhla Retail Group"


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    import calendar
    day = min(d.day, calendar.monthrange(y, m + 1)[1])
    return date(y, m + 1, day)


# ---------------------------------------------------------------- branches
# code, name, city, region, type, opened, area_sqm, staff, manager, hours, base_weight
BRANCHES = [
    ("RYD-OLY", "Riyadh Olaya Flagship", "Riyadh", "Central", "Flagship Store", date(2016, 3, 15), 4200, 78, "Faisal Al-Harbi", "10:00-23:00", 100),
    ("JED-THL", "Jeddah Tahlia Flagship", "Jeddah", "Western", "Flagship Store", date(2017, 9, 20), 3800, 70, "Nasser Al-Ghamdi", "10:00-23:00", 82),
    ("RYD-MLQ", "Riyadh Malqa Standard", "Riyadh", "Central", "Standard Store", date(2019, 5, 12), 2600, 46, "Huda Al-Otaibi", "10:00-23:00", 58),
    ("DMM-FSL", "Dammam Faisaliyah Standard", "Dammam", "Eastern", "Standard Store", date(2018, 11, 8), 2400, 42, "Abdullah Al-Dossary", "10:00-23:00", 50),
    ("KHB-COR", "Al Khobar Corniche Standard", "Al Khobar", "Eastern", "Standard Store", date(2020, 2, 27), 2300, 40, "Reem Al-Qahtani", "10:00-23:00", 46),
    ("MED-QBA", "Madinah Quba Standard", "Madinah", "Western", "Standard Store", date(2019, 10, 3), 2100, 38, "Yousef Al-Juhani", "10:00-23:00", 36),
    ("JED-OBH", "Jeddah Obhur Express", "Jeddah", "Western", "Express Store", date(2021, 6, 17), 1100, 20, "Salma Al-Zahrani", "11:00-23:00", 24),
    ("ABH-CTY", "Abha City Express", "Abha", "Southern", "Express Store", date(2022, 4, 21), 950, 17, "Mohammed Al-Asmari", "11:00-23:00", 18),
    ("RYD-DC", "Riyadh Distribution Center", "Riyadh", "Central", "Distribution Center", date(2015, 8, 1), 18000, 95, "Khalid Al-Mutairi", "24/7", 0),
]
BRANCH = {b[0]: b for b in BRANCHES}

BRANCH_NOTES = {
    "RYD-OLY": ("Olaya Street, central Riyadh", "Largest store and highest-revenue location; full range of all eight product lines; flagship for White Friday and Ramadan campaigns."),
    "JED-THL": ("Tahlia Street, Jeddah", "Second-largest store; strong fashion, beauty and electronics sales; serves the Western region and Red Sea tourism."),
    "RYD-MLQ": ("Malqa district, north Riyadh", "Family-oriented standard store with strong grocery, kids and home lines."),
    "DMM-FSL": ("Faisaliyah district, Dammam", "Main Eastern Province store; serves the Dammam community and corporate customers of the Eastern region."),
    "KHB-COR": ("Corniche area, Al Khobar", "Eastern Province store close to the Corniche; very similar customer profile and basket size to Dammam Faisaliyah."),
    "MED-QBA": ("Quba district, Madinah", "Store with a strong pilgrim and visitor effect: demand rises in Ramadan and the Hajj season."),
    "JED-OBH": ("Obhur waterfront, north Jeddah", "Small express store; summer and holiday season demand is strong because of the waterfront location."),
    "ABH-CTY": ("City centre, Abha", "Smallest store; summer demand is strong because Abha is a summer tourism destination in the Southern region."),
    "RYD-DC": ("Industrial area, south-east Riyadh", "Central warehouse for all stores; also fulfils Online, Mobile App and B2B orders, so online and B2B sales are attributed to this location."),
}

# ---------------------------------------------------------------- product lines
# id, code, name, department, target_margin, peak_season, price_min, price_max, discount_cap, description
LINES = [
    (1, "ELEC", "Consumer Electronics", "Technology", 14.0, "White Friday", 100, 4200, 25, "Phones, laptops, audio, wearables, smart home and TVs."),
    (2, "APPL", "Home Appliances", "Technology", 22.0, "Summer", 90, 3200, 25, "Cooling and fans, kitchen, laundry, cleaning and heating appliances."),
    (3, "FASH", "Fashion and Apparel", "Lifestyle", 46.0, "Eid al-Fitr", 40, 650, 50, "Traditional wear, casual wear, footwear, bags and accessories."),
    (4, "GROC", "Grocery and Gourmet", "Consumables", 24.0, "Ramadan", 6, 180, 20, "Dates, pantry staples, coffee, snacks, beverages and gift baskets."),
    (5, "BEAU", "Beauty and Fragrance", "Lifestyle", 55.0, "Eid al-Fitr and National Day", 25, 900, 30, "Fragrance, oud, skincare, hair care, make-up and grooming."),
    (6, "SPRT", "Sports and Outdoor", "Family and Leisure", 34.0, "Winter", 35, 1800, 40, "Camping, hiking, fitness, cycling, water and team sports."),
    (7, "KIDS", "Kids and School", "Family and Leisure", 38.0, "Back to School", 8, 420, 35, "School bags, stationery, toys, learning products and baby gear."),
    (8, "HOME", "Home Decor and Furnishing", "Lifestyle", 44.0, "Ramadan and White Friday", 30, 1500, 40, "Decor, furniture, lighting, bedding, rugs and kitchenware."),
]
LINE = {l[1]: l for l in LINES}
LINE_BY_ID = {l[0]: l for l in LINES}

# ---------------------------------------------------------------- suppliers
# idx, code, name, country, city, line, lead, moq, terms, otd, quality, currency, contract_start
SUPPLIERS_RAW = [
    (1, "Gulf Digital Trading Co.", "Saudi Arabia", "Riyadh", "ELEC", 7, 40, 45, 96.5, 4.6, "SAR", date(2023, 2, 1)),
    (2, "Shenzhen Nova Electronics Ltd.", "China", "Shenzhen", "ELEC", 42, 200, 60, 91.0, 4.2, "USD", date(2022, 9, 1)),
    (3, "Al Jazeera Home Appliances Co.", "Saudi Arabia", "Jeddah", "APPL", 6, 25, 45, 94.0, 4.4, "SAR", date(2023, 4, 1)),
    (4, "Istanbul Cooling Systems A.S.", "Turkey", "Istanbul", "APPL", 21, 60, 60, 84.0, 4.0, "EUR", date(2023, 6, 1)),
    (5, "Levant Fashion House", "Jordan", "Amman", "FASH", 14, 120, 45, 93.0, 4.3, "USD", date(2023, 1, 15)),
    (6, "Bosphorus Textile Group", "Turkey", "Istanbul", "FASH", 24, 150, 60, 87.5, 4.1, "EUR", date(2024, 1, 10)),
    (7, "Al Qassim Dates Cooperative", "Saudi Arabia", "Buraydah", "GROC", 4, 300, 30, 97.5, 4.7, "SAR", date(2022, 11, 1)),
    (8, "Mediterranean Gourmet Imports", "United Arab Emirates", "Dubai", "GROC", 9, 250, 30, 82.5, 3.9, "AED", date(2024, 3, 1)),
    (9, "Dubai Oud and Perfumes FZE", "United Arab Emirates", "Dubai", "BEAU", 8, 80, 30, 95.0, 4.8, "AED", date(2023, 5, 1)),
    (10, "Paris Beaute Distribution SARL", "France", "Paris", "BEAU", 30, 100, 60, 91.0, 4.5, "EUR", date(2023, 9, 1)),
    (11, "Tabuk Outdoor Gear Co.", "Saudi Arabia", "Tabuk", "SPRT", 7, 50, 45, 92.5, 4.2, "SAR", date(2024, 2, 1)),
    (12, "Munich Sport Systems GmbH", "Germany", "Munich", "SPRT", 35, 80, 60, 89.0, 4.6, "EUR", date(2022, 10, 1)),
    (13, "Cairo Educational Supplies", "Egypt", "Cairo", "KIDS", 18, 200, 45, 90.5, 4.0, "USD", date(2024, 5, 1)),
    (14, "Bright Minds Toys Ltd.", "China", "Guangzhou", "KIDS", 45, 250, 60, 91.5, 4.1, "USD", date(2023, 3, 1)),
    (15, "Jeddah Home Interiors Co.", "Saudi Arabia", "Jeddah", "HOME", 5, 30, 30, 98.0, 4.5, "SAR", date(2023, 7, 1)),
    (16, "Milan Casa Design S.r.l.", "Italy", "Milan", "HOME", 33, 40, 60, 93.5, 4.7, "EUR", date(2025, 1, 15)),
]
SUPPLIERS = []
for (i, name, country, city, line, lead, moq, terms, otd, q, cur, start) in SUPPLIERS_RAW:
    end = add_months(start, 36) - timedelta(days=1)
    renewals = 0
    while end <= REF_DATE:
        end = add_months(end + timedelta(days=1), 12) - timedelta(days=1)
        renewals += 1
    SUPPLIERS.append(dict(idx=i, code=f"SUP-{i:02d}", name=name, country=country, city=city, line=line,
                          lead=lead, moq=moq, terms=terms, otd=otd, quality=q, currency=cur,
                          start=start, end=end, renewals=renewals,
                          contract=f"SC-{start.year}-{i:03d}"))
SUP = {s["code"]: s for s in SUPPLIERS}
SUP_BY_LINE = {}
for s in SUPPLIERS:
    SUP_BY_LINE.setdefault(s["line"], []).append(s["code"])

# ---------------------------------------------------------------- business customers
# idx, name, industry, city, region, start, term_months, discount, credit, terms_days, focus, manager
BUS_RAW = [
    (1, "Al Rawabi Hospitality Group", "Hospitality", "Riyadh", "Central", date(2023, 3, 1), 24, 8.0, 900000, 45, "Home Appliances, Home Decor and Furnishing, Grocery and Gourmet", "Bandar Al-Rasheed"),
    (2, "Eastern Province Medical Center", "Healthcare", "Dammam", "Eastern", date(2023, 9, 1), 24, 6.0, 450000, 30, "Consumer Electronics, Home Appliances", "Turki Al-Harthi"),
    (3, "Najd Business Schools", "Education", "Riyadh", "Central", date(2024, 1, 1), 12, 10.0, 300000, 30, "Kids and School, Consumer Electronics", "Bandar Al-Rasheed"),
    (4, "Red Sea Resorts and Spa", "Hospitality", "Jeddah", "Western", date(2023, 6, 1), 24, 9.0, 1200000, 60, "Home Decor and Furnishing, Beauty and Fragrance, Grocery and Gourmet", "Lina Al-Najjar"),
    (5, "Khobar Business Park Management", "Facilities Management", "Al Khobar", "Eastern", date(2024, 4, 1), 12, 5.0, 200000, 30, "Home Appliances, Consumer Electronics", "Turki Al-Harthi"),
    (6, "Tuwaiq Engineering Contractors", "Construction", "Riyadh", "Central", date(2023, 11, 1), 24, 7.0, 600000, 45, "Consumer Electronics, Sports and Outdoor", "Bandar Al-Rasheed"),
    (7, "Madinah Pilgrim Services Co.", "Pilgrim Services", "Madinah", "Western", date(2024, 2, 1), 12, 11.0, 750000, 45, "Grocery and Gourmet, Home Appliances, Fashion and Apparel", "Lina Al-Najjar"),
    (8, "Asir Tourism Development Co.", "Tourism", "Abha", "Southern", date(2024, 6, 1), 12, 8.5, 350000, 30, "Sports and Outdoor, Home Decor and Furnishing", "Lina Al-Najjar"),
    (9, "Gulf Catering Services", "Catering", "Dammam", "Eastern", date(2023, 8, 1), 24, 12.0, 500000, 30, "Grocery and Gourmet, Home Appliances", "Turki Al-Harthi"),
    (10, "Hijaz University Staff Fund", "Education", "Jeddah", "Western", date(2025, 1, 1), 12, 6.5, 250000, 30, "Consumer Electronics, Kids and School", "Lina Al-Najjar"),
    (11, "Riyadh Corporate Gifting Co.", "Corporate Gifting", "Riyadh", "Central", date(2024, 9, 1), 12, 10.5, 800000, 60, "Beauty and Fragrance, Grocery and Gourmet, Fashion and Apparel", "Bandar Al-Rasheed"),
    (12, "Al Manara Telecom Staff Association", "Telecommunications", "Riyadh", "Central", date(2025, 3, 1), 12, 7.5, 150000, 30, "Consumer Electronics, Sports and Outdoor", "Bandar Al-Rasheed"),
]
BUS_CUSTOMERS = []
for (i, name, ind, city, region, start, term, disc, credit, days, focus, mgr) in BUS_RAW:
    end = add_months(start, term) - timedelta(days=1)
    while end <= REF_DATE:
        end = add_months(end + timedelta(days=1), 12) - timedelta(days=1)
    BUS_CUSTOMERS.append(dict(idx=i, code=f"CUST-B{i:03d}", name=name, industry=ind, city=city, region=region,
                              start=start, term=term, end=end, discount=disc, credit=credit, days=days,
                              focus=focus, manager=mgr, contract=f"CC-{start.year}-{i:03d}"))
BUS = {c["code"]: c for c in BUS_CUSTOMERS}

# ---------------------------------------------------------------- SKUs
# line -> list of 15 tuples: (name, subcategory, brand, price, supplier_slot(0/1), peak_season or None, shelf_life or None)
S = None
SKU_DEF = {
    "ELEC": [
        ("Zenix Pro 15 Smartphone 256GB", "Smartphones", "Zenix", 3199, 1, None, None),
        ("Zenix Lite 12 Smartphone 128GB", "Smartphones", "Zenix", 1299, 1, None, None),
        ("Novabook Pro 16 Laptop", "Laptops and Tablets", "Novabook", 4199, 1, None, None),
        ("Novabook Student 15 Laptop", "Laptops and Tablets", "Novabook", 2199, 1, None, None),
        ("Tabletek Slate 11 Tablet", "Laptops and Tablets", "Tabletek", 1599, 1, None, None),
        ("SoundArc Wireless Earbuds", "Audio", "SoundArc", 349, 0, None, None),
        ("SoundArc Studio Over-Ear Headphones", "Audio", "SoundArc", 699, 0, None, None),
        ("PulseFit Smartwatch S2", "Wearables", "PulseFit", 899, 0, None, None),
        ("PulseFit Fitness Band 5", "Wearables", "PulseFit", 249, 0, None, None),
        ("HomeSense Smart Speaker", "Smart Home", "HomeSense", 279, 0, None, None),
        ("HomeSense Smart Plug 4-Pack", "Smart Home", "HomeSense", 159, 0, None, None),
        ("PixelView 55-inch 4K Smart TV", "TV and Display", "PixelView", 2599, 1, None, None),
        ("PixelView 43-inch HD TV (previous generation)", "TV and Display", "PixelView", 1099, 1, None, None),
        ("Nexa Portable Power Bank 20000mAh", "Accessories", "Nexa", 189, 0, None, None),
        ("HomeSense Smart Hub Gen 2", "Smart Home", "HomeSense", 449, 0, None, None),
    ],
    "APPL": [
        ("BreezeMax Split AC 18000 BTU", "Cooling and Fans", "BreezeMax", 2699, 1, "Summer", None),
        ("BreezeMax Split AC 24000 BTU", "Cooling and Fans", "BreezeMax", 3199, 1, "Summer", None),
        ("BreezeMax Portable AC 12000 BTU", "Cooling and Fans", "BreezeMax", 1899, 1, "Summer", None),
        ("AirWhirl Tower Fan", "Cooling and Fans", "AirWhirl", 249, 0, "Summer", None),
        ("AirWhirl Pedestal Fan 18-inch", "Cooling and Fans", "AirWhirl", 169, 0, "Summer", None),
        ("AquaChill Water Cooler Dispenser", "Cooling and Fans", "AquaChill", 899, 0, "Summer", None),
        ("ChefMate Air Fryer 6L", "Kitchen Appliances", "ChefMate", 449, 0, None, None),
        ("ChefMate Microwave Oven 30L", "Kitchen Appliances", "ChefMate", 699, 0, None, None),
        ("ChefMate Espresso Machine", "Kitchen Appliances", "ChefMate", 1299, 1, None, None),
        ("FreshKeep French Door Refrigerator", "Large Appliances", "FreshKeep", 3199, 1, None, None),
        ("FreshKeep Top-Load Washing Machine 9kg", "Large Appliances", "FreshKeep", 1599, 1, None, None),
        ("CleanWave Robot Vacuum", "Cleaning", "CleanWave", 1399, 0, None, None),
        ("CleanWave Cordless Stick Vacuum", "Cleaning", "CleanWave", 899, 0, None, None),
        ("WarmGlow Oil Heater", "Heating", "WarmGlow", 329, 0, "Winter", None),
        ("ChefMate Smart Blender Pro", "Kitchen Appliances", "ChefMate", 389, 0, None, None),
    ],
    "FASH": [
        ("Al Noor Classic White Thobe", "Mens Traditional Wear", "Al Noor", 189, 0, "Eid al-Fitr", None),
        ("Al Noor Premium Winter Thobe", "Mens Traditional Wear", "Al Noor", 249, 0, "Winter", None),
        ("Layali Embroidered Abaya", "Womens Traditional Wear", "Layali", 389, 0, "Eid al-Fitr", None),
        ("Layali Everyday Black Abaya", "Womens Traditional Wear", "Layali", 229, 0, None, None),
        ("UrbanLine Slim Jeans", "Casual Wear", "UrbanLine", 149, 1, None, None),
        ("UrbanLine Cotton Polo Shirt", "Casual Wear", "UrbanLine", 89, 1, None, None),
        ("UrbanLine Hooded Sweatshirt", "Casual Wear", "UrbanLine", 129, 1, "Winter", None),
        ("StridePro Running Shoes", "Footwear", "StridePro", 349, 1, None, None),
        ("StridePro Leather Loafers", "Footwear", "StridePro", 299, 1, None, None),
        ("Layali Silk Scarf", "Accessories", "Layali", 119, 0, None, None),
        ("Marasim Leather Handbag", "Bags", "Marasim", 599, 0, None, None),
        ("Marasim Weekend Travel Bag", "Bags", "Marasim", 249, 0, None, None),
        ("UrbanLine Denim Jacket (old collection)", "Casual Wear", "UrbanLine", 199, 1, None, None),
        ("Marasim Evening Clutch (limited 2024 edition)", "Bags", "Marasim", 159, 0, None, None),
        ("Layali Linen Kaftan", "Womens Traditional Wear", "Layali", 329, 0, None, None),
    ],
    "GROC": [
        ("Qassim Gold Khalas Dates 1kg", "Dates", "Qassim Gold", 45, 0, "Ramadan", 365),
        ("Qassim Gold Sukkari Dates Gift Box 2kg", "Dates", "Qassim Gold", 129, 0, "Ramadan", 365),
        ("Nakhla Select Ramadan Essentials Basket", "Gift Baskets", "Nakhla Select", 179, 0, "Ramadan", 180),
        ("Qahwa House Arabic Coffee with Cardamom 500g", "Coffee and Tea", "Qahwa House", 62, 0, None, 270),
        ("GoldenGrain Premium Basmati Rice 5kg", "Pantry Staples", "GoldenGrain", 48, 1, None, 540),
        ("Olivia Extra Virgin Olive Oil 1L", "Pantry Staples", "Olivia", 54, 1, None, 540),
        ("PureFarm Long Life Milk 1L (12 pack)", "Dairy and Beverages", "PureFarm", 42, 1, None, 120),
        ("AquaPure Sparkling Water 330ml (24 pack)", "Dairy and Beverages", "AquaPure", 28, 1, None, 365),
        ("NutHouse Mixed Nuts Tin 800g", "Snacks", "NutHouse", 68, 1, None, 240),
        ("Chocolat Royal Belgian Chocolate Selection Box", "Confectionery", "Chocolat Royal", 89, 1, "Eid al-Fitr", 300),
        ("Zafran Co Saffron Threads 5g", "Spices", "Zafran Co", 76, 1, None, 720),
        ("Qamar Al-Din Apricot Drink 1L", "Dairy and Beverages", "Qamar Al-Din", 12, 0, "Ramadan", 365),
        ("Bellini Pasta 500g (12 pack)", "Pantry Staples", "Bellini", 56, 1, None, 720),
        ("Nakhla Select Frozen Samosa Ramadan Pack 60 pcs", "Frozen Food", "Nakhla Select", 38, 0, "Ramadan", 180),
        ("BeeBlessed Organic Honey 500g", "Pantry Staples", "BeeBlessed", 85, 0, None, 720),
    ],
    "BEAU": [
        ("Oud Royale Eau de Parfum 100ml", "Fragrance", "Oud Royale", 489, 0, "Eid al-Fitr", None),
        ("Oud Royale Deluxe Gift Set", "Fragrance", "Oud Royale", 899, 0, "Eid al-Fitr", None),
        ("Bakhoor Incense Burner Gift Set", "Fragrance", "Oud Royale", 249, 0, "National Day", None),
        ("Musk Attar Oil 12ml", "Fragrance", "Oud Royale", 129, 0, None, None),
        ("Rose Garden Eau de Toilette 100ml", "Fragrance", "Rose Garden", 329, 1, None, None),
        ("Lumiere Day Moisturizer SPF50", "Skincare", "Lumiere", 119, 1, None, 730),
        ("Lumiere Night Repair Serum", "Skincare", "Lumiere", 219, 1, None, 730),
        ("Lumiere Hydrating Face Mask 5-Pack", "Skincare", "Lumiere", 59, 1, None, 540),
        ("SilkLine Shampoo 400ml", "Hair Care", "SilkLine", 35, 1, None, 900),
        ("SilkLine Argan Hair Oil 100ml", "Hair Care", "SilkLine", 69, 1, None, 900),
        ("ColorPop Matte Lipstick", "Makeup", "ColorPop", 79, 1, None, 900),
        ("ColorPop Stay-Matte Foundation", "Makeup", "ColorPop", 119, 1, None, 900),
        ("Barber and Co Beard Care Kit", "Mens Grooming", "Barber and Co", 159, 0, None, None),
        ("Barber and Co Electric Trimmer", "Mens Grooming", "Barber and Co", 249, 0, None, None),
        ("Lumiere Vitamin C Serum", "Skincare", "Lumiere", 189, 1, None, 730),
    ],
    "SPRT": [
        ("TrailNest 4-Person Camping Tent", "Camping Gear", "TrailNest", 799, 0, "Winter", None),
        ("TrailNest 2-Person Camping Tent", "Camping Gear", "TrailNest", 449, 0, "Winter", None),
        ("TrailNest Sleeping Bag (-5C)", "Camping Gear", "TrailNest", 279, 0, "Winter", None),
        ("TrailNest Portable Camping Stove", "Camping Gear", "TrailNest", 189, 0, "Winter", None),
        ("Summit 65L Trekking Backpack", "Hiking", "Summit", 459, 1, None, None),
        ("IronCore Adjustable Dumbbell Set 24kg", "Fitness Equipment", "IronCore", 649, 1, None, None),
        ("IronCore Treadmill T500", "Fitness Equipment", "IronCore", 1799, 1, None, None),
        ("FlexFit Yoga Mat", "Fitness Equipment", "FlexFit", 79, 1, None, None),
        ("FlexFit Resistance Bands Set", "Fitness Equipment", "FlexFit", 59, 1, None, None),
        ("VeloCity Road Bike 21-Speed", "Cycling", "VeloCity", 1499, 1, None, None),
        ("VeloCity Cycling Helmet", "Cycling", "VeloCity", 159, 1, None, None),
        ("AquaGlide Swim Goggles", "Water Sports", "AquaGlide", 49, 0, None, None),
        ("PlayZone Football Size 5", "Team Sports", "PlayZone", 89, 0, None, None),
        ("PlayZone Classic Tennis Racket", "Team Sports", "PlayZone", 329, 0, None, None),
        ("Hydro Insulated Bottle 1L", "Accessories", "Hydro", 85, 0, None, None),
    ],
    "KIDS": [
        ("SchoolPro Backpack 18-inch", "School Bags", "SchoolPro", 129, 0, "Back to School", None),
        ("SchoolPro Rolling Backpack", "School Bags", "SchoolPro", 219, 0, "Back to School", None),
        ("SchoolPro Lunch Box Set", "School Bags", "SchoolPro", 49, 0, "Back to School", None),
        ("WriteWell Notebook Set 10-Pack", "Stationery", "WriteWell", 36, 0, "Back to School", None),
        ("WriteWell Pencil Case and Pens Kit", "Stationery", "WriteWell", 29, 0, "Back to School", None),
        ("ArtBox Colouring Set 72 pcs", "Arts and Crafts", "ArtBox", 55, 0, None, None),
        ("BrickWorld Building Blocks 500 pcs", "Toys", "BrickWorld", 149, 1, None, None),
        ("BrickWorld Remote Control Car", "Toys", "BrickWorld", 199, 1, None, None),
        ("LittleLearners Educational Tablet", "Learning Products", "LittleLearners", 329, 1, None, None),
        ("LittleLearners Arabic Alphabet Puzzle", "Learning Products", "LittleLearners", 39, 1, None, None),
        ("Cuddle Plush Camel Toy", "Toys", "Cuddle", 59, 1, None, None),
        ("TinyTots Baby Stroller Lite", "Baby Gear", "TinyTots", 419, 1, None, None),
        ("TinyTots Baby Bottle Set", "Baby Gear", "TinyTots", 45, 1, None, None),
        ("BrightKids Classic Geometry Set", "Stationery", "BrightKids", 18, 0, None, None),
        ("LittleLearners Coding Robot Kit", "Learning Products", "LittleLearners", 279, 1, None, None),
    ],
    "HOME": [
        ("Dar Al Zakhrafa Ramadan Lantern Large", "Decor", "Dar Al Zakhrafa", 149, 0, "Ramadan", None),
        ("Dar Al Zakhrafa Ramadan Table Linen Set", "Decor", "Dar Al Zakhrafa", 129, 0, "Ramadan", None),
        ("Majlis Floor Cushion Set", "Furniture", "Majlis", 599, 0, None, None),
        ("Casa Moderne 3-Seater Sofa", "Furniture", "Casa Moderne", 1499, 1, None, None),
        ("Casa Moderne Coffee Table", "Furniture", "Casa Moderne", 549, 1, None, None),
        ("Lumina LED Floor Lamp", "Lighting", "Lumina", 249, 1, None, None),
        ("Lumina Crystal Chandelier", "Lighting", "Lumina", 1299, 1, None, None),
        ("SoftHome Cotton Bedding Set Queen", "Bedding", "SoftHome", 349, 0, None, None),
        ("SoftHome Memory Foam Pillow 2-Pack", "Bedding", "SoftHome", 159, 0, None, None),
        ("Weave Persian-Style Rug 200x300", "Rugs", "Weave", 899, 1, None, None),
        ("CookWell Non-Stick Cookware Set", "Kitchenware", "CookWell", 429, 0, None, None),
        ("CookWell Dinner Set 24 pcs", "Kitchenware", "CookWell", 299, 0, None, None),
        ("Dar Al Zakhrafa Wall Art Canvas (old collection)", "Decor", "Dar Al Zakhrafa", 199, 0, None, None),
        ("Casa Moderne Shoe Cabinet (retired)", "Furniture", "Casa Moderne", 449, 1, None, None),
        ("OrganizeIt Storage Boxes 6-Pack", "Storage", "OrganizeIt", 89, 0, None, None),
    ],
}

# lifecycle overrides: sku -> (status, launch_date or None, discontinued_date or None)
NEW_LAUNCH = {"ELEC-0015": date(2026, 5, 17), "APPL-0015": date(2026, 6, 7), "BEAU-0015": date(2026, 6, 21), "KIDS-0015": date(2026, 7, 12)}
DISCONTINUED = {"ELEC-0013": date(2026, 3, 31), "FASH-0014": date(2026, 5, 31), "SPRT-0014": date(2026, 6, 30), "HOME-0014": date(2026, 7, 15)}
DEAD_DECLINING = ["FASH-0013", "HOME-0013"]                      # declining, no sales since 2026-08-03
DECLINING_OTHER = ["ELEC-0012", "APPL-0014", "KIDS-0014", "GROC-0014", "SPRT-0013", "BEAU-0014"]
LATE_LAUNCH = {"FASH-0015": date(2024, 4, 1), "GROC-0015": date(2025, 3, 10), "SPRT-0015": date(2024, 9, 15), "HOME-0015": date(2025, 5, 20)}
DEAD_STOCK = sorted(list(DISCONTINUED) + DEAD_DECLINING)         # 6 SKUs

SKUS = []
for li, line in enumerate(LINES):
    code = line[1]
    for n, (name, sub, brand, price, slot, peak, shelf) in enumerate(SKU_DEF[code], start=1):
        sku = f"{code}-{n:04d}"
        sup = SUP_BY_LINE[code][slot]
        if sku in NEW_LAUNCH:
            status, launch, disc = "New", NEW_LAUNCH[sku], None
        elif sku in DISCONTINUED:
            status, disc = "Discontinued", DISCONTINUED[sku]
            launch = date(2020 + (n + li) % 3, 1 + (n * 5 + li) % 12, 1 + (n * 7) % 27)
        else:
            status = "Declining" if (sku in DEAD_DECLINING or sku in DECLINING_OTHER) else "Active"
            disc = None
            launch = LATE_LAUNCH.get(sku) or date(2019 + (n * 3 + li) % 5, 1 + (n * 5 + li) % 12, 1 + (n * 7) % 27)
        uom = "Set" if (" Set" in name or " Kit" in name) else "Pack" if ("Pack" in name or "pack" in name) else "Box" if "Box" in name else "Each"
        assert line[6] <= price <= line[7], (sku, price)
        SKUS.append(dict(sku=sku, name=name, line=code, sub=sub, brand=brand, price=price, supplier=sup,
                         peak=peak, seasonal=peak is not None, shelf=shelf, status=status, launch=launch,
                         discontinued=disc, uom=uom))
SKU = {s["sku"]: s for s in SKUS}
assert len(SKUS) == 120

# ---------------------------------------------------------------- season windows
RAMADAN = {2024: (date(2024, 3, 11), date(2024, 4, 9)), 2025: (date(2025, 3, 1), date(2025, 3, 29)), 2026: (date(2026, 2, 18), date(2026, 3, 19))}
EID_FITR_DAY1 = {2024: date(2024, 4, 10), 2025: date(2025, 3, 30), 2026: date(2026, 3, 20)}
ARAFAT = {2024: date(2024, 6, 15), 2025: date(2025, 6, 5), 2026: date(2026, 5, 26)}
EID_ADHA_DAY1 = {y: d + timedelta(days=1) for y, d in ARAFAT.items()}
WHITE_FRIDAY = {2024: date(2024, 11, 29), 2025: date(2025, 11, 28), 2026: date(2026, 11, 27)}

SEASON_WINDOWS = []   # (year, season, start, end, note)
for y in (2024, 2025, 2026):
    r0, r1 = RAMADAN[y]
    e1 = EID_FITR_DAY1[y]
    SEASON_WINDOWS.append((y, "Ramadan", r0, r1, "1 to 29/30 Ramadan; the last 7 days are classified as Eid al-Fitr by precedence"))
    SEASON_WINDOWS.append((y, "Eid al-Fitr", r1 - timedelta(days=6), e1 + timedelta(days=2), "last 7 days of Ramadan plus 1 to 3 Shawwal"))
    a = ARAFAT[y]
    SEASON_WINDOWS.append((y, "Hajj and Eid al-Adha", a - timedelta(days=4), a + timedelta(days=5), "Arafat Day minus 4 days to Arafat Day plus 5 days"))
    wf = WHITE_FRIDAY[y]
    SEASON_WINDOWS.append((y, "White Friday", wf - timedelta(days=7), wf + timedelta(days=2), "Friday one week before White Friday to the Sunday after" + (" (planning estimate)" if y == 2026 else "")))
    SEASON_WINDOWS.append((y, "National Day", date(y, 9, 18), date(y, 9, 24), "18 to 24 September; public holiday on 23 September"))
    SEASON_WINDOWS.append((y, "Founding Day", date(y, 2, 20), date(y, 2, 23), "20 to 23 February; public holiday on 22 February"))
    SEASON_WINDOWS.append((y, "Back to School", date(y, 8, 1), date(y, 9, 15), "1 August to 15 September"))
    SEASON_WINDOWS.append((y, "Summer", date(y, 6, 1), date(y, 8, 31), "1 June to 31 August, lowest precedence among events (August is overridden by Back to School)"))
SEASON_PRECEDENCE = ["White Friday", "Eid al-Fitr", "Hajj and Eid al-Adha", "Ramadan", "National Day", "Founding Day", "Back to School", "Summer", "Winter", "Regular"]
PUBLIC_HOLIDAYS = []  # (year, name, start, end)
for y in (2024, 2025, 2026):
    PUBLIC_HOLIDAYS.append((y, "Founding Day", date(y, 2, 22), date(y, 2, 22)))
    PUBLIC_HOLIDAYS.append((y, "Eid al-Fitr Holiday", RAMADAN[y][1], EID_FITR_DAY1[y] + timedelta(days=2)))
    PUBLIC_HOLIDAYS.append((y, "Arafat Day", ARAFAT[y], ARAFAT[y]))
    PUBLIC_HOLIDAYS.append((y, "Eid al-Adha Holiday", EID_ADHA_DAY1[y], EID_ADHA_DAY1[y] + timedelta(days=3)))
    PUBLIC_HOLIDAYS.append((y, "National Day", date(y, 9, 23), date(y, 9, 23)))


def season_of(d):
    """Return the single commercial season of a date (precedence order)."""
    hits = set()
    for (y, s, a, b, _n) in SEASON_WINDOWS:
        if a <= d <= b:
            hits.add(s)
    if d.month in (12, 1, 2):
        hits.add("Winter")
    for s in SEASON_PRECEDENCE:
        if s in hits:
            return s
    return "Regular"


# ---------------------------------------------------------------- promotions
PROMO_TEMPLATES = [
    # abbr, name, type, discount, line, scope, min_basket, season, window-fn key
    ("FD", "Founding Day Rewards", "Loyalty Bonus", 10.0, None, "All", None, "Founding Day", "founding"),
    ("RAM", "Ramadan Kareem Offers", "Seasonal Sale", 10.0, None, "All", 150, "Ramadan", "ramadan"),
    ("RAMG", "Ramadan Grocery Basket Deals", "Percentage Off", 15.0, "GROC", "In-Store", None, "Ramadan", "ramadan"),
    ("HRF", "Home Refresh Before Ramadan", "Percentage Off", 20.0, "HOME", "All", None, "Ramadan", "preramadan"),
    ("EIDF", "Eid al-Fitr Fashion Festival", "Percentage Off", 20.0, "FASH", "All", None, "Eid al-Fitr", "eidfitr"),
    ("EIDB", "Eid Gifting Fragrance Offers", "Bundle Deal", 15.0, "BEAU", "All", None, "Eid al-Fitr", "eidfitr"),
    ("EIDA", "Eid al-Adha Celebration", "Seasonal Sale", 10.0, None, "All", None, "Hajj and Eid al-Adha", "hajj"),
    ("SUM", "Summer Cooling Sale", "Percentage Off", 15.0, "APPL", "All", None, "Summer", "summer"),
    ("BTS", "Back to School Savings", "Percentage Off", 20.0, "KIDS", "All", None, "Back to School", "bts"),
    ("ND", "Saudi National Day Offers", "Seasonal Sale", 12.0, None, "All", 200, "National Day", "nday"),
    ("NDB", "National Day Fragrance Bundle", "Bundle Deal", 15.0, "BEAU", "Online", None, "National Day", "nday"),
    ("WF", "White Friday", "Percentage Off", 15.0, None, "All", 300, "White Friday", "wf"),
    ("WFE", "White Friday Electronics Deals", "Percentage Off", 25.0, "ELEC", "All", None, "White Friday", "wf"),
    ("WC", "Winter Camping Clearance", "Clearance", 30.0, "SPRT", "All", None, "Winter", "winter"),
]
PROMO_YEARS = {
    2024: ["FD", "RAM", "RAMG", "HRF", "EIDF", "EIDB", "EIDA", "SUM", "BTS", "ND", "NDB", "WF", "WFE", "WC"],
    2025: ["FD", "RAM", "RAMG", "HRF", "EIDF", "EIDB", "EIDA", "SUM", "BTS", "ND", "NDB", "WF", "WFE", "WC"],
    2026: ["FD", "RAM", "RAMG", "HRF", "EIDF", "EIDB", "EIDA", "SUM", "BTS", "ND", "NDB", "WC"],
}


def _window(key, y):
    if key == "founding": return date(y, 2, 20), date(y, 2, 23)
    if key == "ramadan": return RAMADAN[y]
    if key == "preramadan": return RAMADAN[y][0] - timedelta(days=28), RAMADAN[y][0] - timedelta(days=1)
    if key == "eidfitr": return RAMADAN[y][1] - timedelta(days=6), EID_FITR_DAY1[y] + timedelta(days=2)
    if key == "hajj": return ARAFAT[y] - timedelta(days=4), ARAFAT[y] + timedelta(days=5)
    if key == "summer": return date(y, 6, 1), date(y, 7, 31)
    if key == "bts": return date(y, 8, 1), date(y, 9, 15)
    if key == "nday": return date(y, 9, 18), date(y, 9, 24)
    if key == "wf": return WHITE_FRIDAY[y] - timedelta(days=7), WHITE_FRIDAY[y] + timedelta(days=2)
    if key == "winter":
        # Winter Camping YYYY runs 1 December of the previous year to 31 January of YYYY
        return date(y - 1, 12, 1), date(y, 1, 31)
    raise KeyError(key)


PROMOTIONS = []
for y, abbrs in PROMO_YEARS.items():
    for ab in abbrs:
        t = next(t for t in PROMO_TEMPLATES if t[0] == ab)
        start, end = _window(t[8], y)
        if start < DATA_START:
            start = DATA_START
        PROMOTIONS.append(dict(code=f"PROMO-{ab}-{y}", name=f"{t[1]} {y}", type=t[2], pct=t[3], start=start, end=end,
                               season=t[7], line=t[4], scope=t[5], min_basket=t[6]))
PROMOTIONS.sort(key=lambda p: (p["start"], p["code"]))
for i, p in enumerate(PROMOTIONS, start=1):
    p["id"] = i
assert len(PROMOTIONS) == 40
for p in PROMOTIONS:
    cap = LINE[p["line"]][8] if p["line"] else min(l[8] for l in LINES)
    assert p["pct"] <= cap, p

# ---------------------------------------------------------------- policy parameters
POLICY = dict(
    vat_pct=15, currency="SAR", timezone="Asia/Riyadh (UTC+3)",
    loyalty=[("None", 0, "Entry level"), ("Silver", 3000, ""), ("Gold", 10000, ""), ("Platinum", 25000, "")],
    shipping_fee=25, free_shipping_min=250,
    return_days=14, return_days_defective=30,
    target_growth=1.10,
    service_level={"A": 98, "B": 95, "C": 90}, z={"A": 2.05, "B": 1.65, "C": 1.28},
    dead_stock_weeks=13, forecast_horizon_weeks=13,
    po_approval=[("Up to SAR 50,000", "Procurement Manager"), ("SAR 50,001 to SAR 250,000", "Head of Supply Chain"), ("Above SAR 250,000", "Chief Financial Officer")],
    supplier_otd_target=92, late_penalty_pct_per_day=0.5, late_penalty_cap_pct=5,
)

# ---------------------------------------------------------------- people
# id, name, title, department, location, hired, reports_to, salary, file
PEOPLE_RAW = [
    ("Abdulaziz Al-Rashid", "Chief Executive Officer", "Executive Office", "HQ", date(2015, 6, 1), "Board of Directors", 85000, "01_executive_leadership"),
    ("Maha Al-Sudairi", "Chief Financial Officer", "Finance", "HQ", date(2016, 2, 1), "Abdulaziz Al-Rashid", 62000, "01_executive_leadership"),
    ("Tariq Al-Shehri", "Chief Operating Officer", "Operations", "HQ", date(2015, 9, 15), "Abdulaziz Al-Rashid", 60000, "01_executive_leadership"),
    ("Noura Al-Fahad", "Chief Commercial Officer", "Commercial", "HQ", date(2017, 4, 1), "Abdulaziz Al-Rashid", 58000, "01_executive_leadership"),
    ("Omar Bakr", "Chief Technology and Data Officer", "Technology and Data", "HQ", date(2019, 1, 10), "Abdulaziz Al-Rashid", 56000, "01_executive_leadership"),
    ("Sara Al-Mansour", "Head of E-commerce", "Commercial", "HQ", date(2019, 8, 1), "Noura Al-Fahad", 34000, "02_commercial_and_marketing"),
    ("Rakan Al-Anazi", "Head of Marketing", "Commercial", "HQ", date(2018, 3, 12), "Noura Al-Fahad", 32000, "02_commercial_and_marketing"),
    ("Dina Haddad", "Category Manager, Electronics and Appliances", "Commercial", "HQ", date(2018, 9, 1), "Noura Al-Fahad", 26000, "02_commercial_and_marketing"),
    ("Lama Al-Sheikh", "Category Manager, Fashion and Beauty", "Commercial", "HQ", date(2019, 2, 17), "Noura Al-Fahad", 25000, "02_commercial_and_marketing"),
    ("Hassan Al-Zahrani", "Category Manager, Grocery, Home, Kids and Sports", "Commercial", "HQ", date(2020, 5, 3), "Noura Al-Fahad", 24000, "02_commercial_and_marketing"),
    ("Ibrahim Al-Qarni", "Head of Supply Chain", "Supply Chain", "HQ", date(2016, 11, 1), "Tariq Al-Shehri", 38000, "03_supply_chain_and_procurement"),
    ("Wafa Al-Dosari", "Procurement Manager", "Supply Chain", "HQ", date(2018, 6, 10), "Ibrahim Al-Qarni", 28000, "03_supply_chain_and_procurement"),
    ("Saad Al-Malki", "Inventory Planning Manager", "Supply Chain", "HQ", date(2019, 4, 22), "Ibrahim Al-Qarni", 27000, "03_supply_chain_and_procurement"),
    ("Yara Khoury", "Demand Planner", "Supply Chain", "HQ", date(2021, 1, 11), "Saad Al-Malki", 18500, "03_supply_chain_and_procurement"),
    ("Majed Al-Subaie", "Supplier Quality Specialist", "Supply Chain", "HQ", date(2022, 3, 7), "Wafa Al-Dosari", 14500, "03_supply_chain_and_procurement"),
    ("Rawan Al-Ajmi", "Finance Manager", "Finance", "HQ", date(2017, 8, 14), "Maha Al-Sudairi", 30000, "04_finance_and_hr"),
    ("Sultan Al-Bishi", "Financial Controller", "Finance", "HQ", date(2019, 10, 1), "Maha Al-Sudairi", 29000, "04_finance_and_hr"),
    ("Hind Al-Shammari", "HR Director", "Human Resources", "HQ", date(2016, 5, 2), "Tariq Al-Shehri", 36000, "04_finance_and_hr"),
    ("Badr Al-Yami", "HR Business Partner", "Human Resources", "HQ", date(2020, 9, 13), "Hind Al-Shammari", 17000, "04_finance_and_hr"),
    ("Aisha Al-Hamdan", "Payroll Specialist", "Human Resources", "HQ", date(2021, 6, 20), "Hind Al-Shammari", 13500, "04_finance_and_hr"),
    ("Fahad Al-Tamimi", "IT Operations Manager", "Technology and Data", "HQ", date(2018, 1, 8), "Omar Bakr", 29000, "05_technology_and_data"),
    ("Joud Al-Khaldi", "Business Intelligence Lead", "Technology and Data", "HQ", date(2020, 2, 24), "Omar Bakr", 27000, "05_technology_and_data"),
    ("Nawaf Al-Rowaili", "Database Administrator", "Technology and Data", "HQ", date(2021, 3, 15), "Fahad Al-Tamimi", 20000, "05_technology_and_data"),
    ("Ghada Al-Subhi", "Information Security Officer", "Technology and Data", "HQ", date(2022, 1, 30), "Omar Bakr", 22000, "05_technology_and_data"),
    ("Faisal Al-Harbi", "Branch Manager, Riyadh Olaya Flagship", "Retail Operations", "RYD-OLY", date(2016, 3, 15), "Tariq Al-Shehri", 32000, "06_branch_managers_central"),
    ("Huda Al-Otaibi", "Branch Manager, Riyadh Malqa Standard", "Retail Operations", "RYD-MLQ", date(2019, 5, 12), "Tariq Al-Shehri", 24000, "06_branch_managers_central"),
    ("Khalid Al-Mutairi", "Distribution Center Manager", "Supply Chain", "RYD-DC", date(2015, 8, 1), "Tariq Al-Shehri", 33000, "06_branch_managers_central"),
    ("Nasser Al-Ghamdi", "Branch Manager, Jeddah Tahlia Flagship", "Retail Operations", "JED-THL", date(2017, 9, 20), "Tariq Al-Shehri", 30000, "07_branch_managers_western"),
    ("Salma Al-Zahrani", "Branch Manager, Jeddah Obhur Express", "Retail Operations", "JED-OBH", date(2021, 6, 17), "Tariq Al-Shehri", 21000, "07_branch_managers_western"),
    ("Yousef Al-Juhani", "Branch Manager, Madinah Quba Standard", "Retail Operations", "MED-QBA", date(2019, 10, 3), "Tariq Al-Shehri", 23500, "07_branch_managers_western"),
    ("Abdullah Al-Dossary", "Branch Manager, Dammam Faisaliyah Standard", "Retail Operations", "DMM-FSL", date(2018, 11, 8), "Tariq Al-Shehri", 24500, "08_branch_managers_eastern_and_southern"),
    ("Reem Al-Qahtani", "Branch Manager, Al Khobar Corniche Standard", "Retail Operations", "KHB-COR", date(2020, 2, 27), "Tariq Al-Shehri", 23500, "08_branch_managers_eastern_and_southern"),
    ("Mohammed Al-Asmari", "Branch Manager, Abha City Express", "Retail Operations", "ABH-CTY", date(2022, 4, 21), "Tariq Al-Shehri", 20500, "08_branch_managers_eastern_and_southern"),
    ("Amal Al-Dakheel", "Head of Customer Service", "Customer Service", "HQ", date(2018, 7, 1), "Noura Al-Fahad", 27000, "09_customer_service_and_b2b"),
    ("Bandar Al-Rasheed", "B2B Account Manager, Central Region", "Customer Service", "HQ", date(2019, 11, 4), "Noura Al-Fahad", 21000, "09_customer_service_and_b2b"),
    ("Lina Al-Najjar", "B2B Account Manager, Western and Southern Regions", "Customer Service", "HQ", date(2020, 10, 12), "Noura Al-Fahad", 20500, "09_customer_service_and_b2b"),
    ("Turki Al-Harthi", "B2B Account Manager, Eastern Region", "Customer Service", "HQ", date(2021, 8, 29), "Noura Al-Fahad", 20000, "09_customer_service_and_b2b"),
    ("Osama Al-Shamrani", "Logistics Coordinator", "Supply Chain", "RYD-DC", date(2019, 3, 18), "Khalid Al-Mutairi", 15500, "10_warehouse_and_logistics"),
    ("Maram Al-Balawi", "Inbound Operations Supervisor", "Supply Chain", "RYD-DC", date(2020, 1, 5), "Khalid Al-Mutairi", 14500, "10_warehouse_and_logistics"),
    ("Hamad Al-Enezi", "Outbound Operations Supervisor", "Supply Chain", "RYD-DC", date(2020, 6, 14), "Khalid Al-Mutairi", 14500, "10_warehouse_and_logistics"),
    ("Jaber Al-Thaqafi", "Fleet and Delivery Supervisor", "Supply Chain", "RYD-DC", date(2021, 2, 2), "Khalid Al-Mutairi", 14000, "10_warehouse_and_logistics"),
]
PEOPLE = []
for i, (name, title, dept, loc, hired, boss, sal, fl) in enumerate(PEOPLE_RAW, start=1):
    PEOPLE.append(dict(id=f"EMP-{i:04d}", name=name, title=title, dept=dept, loc=loc, hired=hired, boss=boss,
                       salary=sal, file=fl, email=name.lower().replace("-", "").replace(" ", ".") + "@nakhla-retail.example"))
PERSON = {p["name"]: p for p in PEOPLE}
assert len(PEOPLE) == 41
for b in BRANCHES:
    assert b[8] in PERSON, b[8]

# ---------------------------------------------------------------- known data landmarks (from guarantees G-xx)
STORE_RANKING_2025 = ["RYD-OLY", "JED-THL", "RYD-MLQ", "DMM-FSL", "KHB-COR", "MED-QBA", "JED-OBH", "ABH-CTY"]

if __name__ == "__main__":
    from collections import Counter
    print("branches", len(BRANCHES), "suppliers", len(SUPPLIERS), "skus", len(SKUS), "promos", len(PROMOTIONS), "people", len(PEOPLE))
    print(Counter(s["status"] for s in SKUS))
    print("below85", [s["code"] for s in SUPPLIERS if s["otd"] < 85], "below90", [s["code"] for s in SUPPLIERS if s["otd"] < 90])
    print("lead range", min(s["lead"] for s in SUPPLIERS), max(s["lead"] for s in SUPPLIERS))
    print("seasonal skus", sum(s["seasonal"] for s in SKUS), "shelf-life skus", sum(s["shelf"] is not None for s in SKUS))
    print("promo types", Counter(p["type"] for p in PROMOTIONS))
    for y in (2024, 2025, 2026):
        print(y, [(d, season_of(d)) for d in (date(y, 2, 22), date(y, 4, 5) if y == 2024 else date(y, 3, 21), date(y, 9, 23), date(y, 8, 10), date(y, 10, 15))])
    print([ (s["code"], s["contract"], str(s["end"])) for s in SUPPLIERS[:4]])
    print([ (c["code"], c["contract"], str(c["end"])) for c in BUS_CUSTOMERS[:4]])
