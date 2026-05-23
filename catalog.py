"""
NIKE CATALOG
============
100 real Nike shoes with prices, categories, and searchable keywords.

Structure per item:
  name        : display name
  price       : USD retail price
  currency    : always USD here
  category    : running | lifestyle | training | basketball | trail | soccer | golf | sandals | kids
  keywords    : list of terms used for fuzzy matching (simulates vector embeddings)
  description : one-line product description

Swap guide (Phase 4+):
  - Replace this dict with a DB-backed loader: `load_catalog_from_db()`
  - The search layer (search.py) is unaffected — it only sees the same dict schema
"""

CATALOG: dict[str, dict] = {

    # ── RUNNING ──────────────────────────────────────────────────────────────
    "pegasus_41": {
        "name": "Nike Air Zoom Pegasus 41",
        "price": 130.00, "currency": "USD", "category": "running",
        "keywords": ["running", "pegasus", "zoom", "daily trainer", "versatile", "neutral"],
        "description": "The everyday workhorse — responsive zoom, smooth ride"
    },
    "react_infinity_run_4": {
        "name": "Nike React Infinity Run Flyknit 4",
        "price": 160.00, "currency": "USD", "category": "running",
        "keywords": ["running", "react", "infinity", "injury prevention", "plush", "cushioned"],
        "description": "Max cushion for high-mileage runners, reduces injury risk"
    },
    "invincible_3": {
        "name": "Nike InvincibleRun 3",
        "price": 180.00, "currency": "USD", "category": "running",
        "keywords": ["running", "invincible", "max cushion", "soft", "plush", "premium"],
        "description": "Softest ride in the Nike lineup, built for easy days"
    },
    "vomero_17": {
        "name": "Nike Air Zoom Vomero 17",
        "price": 180.00, "currency": "USD", "category": "running",
        "keywords": ["running", "vomero", "zoom", "cushioned", "neutral", "premium"],
        "description": "Premium daily trainer with full-length Zoom Air"
    },
    "structure_25": {
        "name": "Nike Air Zoom Structure 25",
        "price": 130.00, "currency": "USD", "category": "running",
        "keywords": ["running", "structure", "support", "stability", "zoom", "overpronation"],
        "description": "Stability runner with dual-density foam for overpronators"
    },
    "tempo_next": {
        "name": "Nike Air Zoom Tempo NEXT%",
        "price": 200.00, "currency": "USD", "category": "running",
        "keywords": ["running", "tempo", "race", "fast", "carbon", "speed", "sub-elite"],
        "description": "Carbon-plated tempo trainer bridging training and racing"
    },
    "alphafly_3": {
        "name": "Nike Air Zoom Alphafly NEXT% 3",
        "price": 285.00, "currency": "USD", "category": "running",
        "keywords": ["marathon", "racing", "elite", "carbon plate", "alphafly", "fastest"],
        "description": "Nike's flagship marathon racing shoe — carbon + ZoomX"
    },
    "streakfly": {
        "name": "Nike ZoomX Streakfly",
        "price": 150.00, "currency": "USD", "category": "running",
        "keywords": ["racing", "fast", "5k", "10k", "lightweight", "streakfly", "speed"],
        "description": "Lightweight racer built for 5K–10K distances"
    },
    "zoom_fly_5": {
        "name": "Nike Zoom Fly 5",
        "price": 160.00, "currency": "USD", "category": "running",
        "keywords": ["marathon", "running", "zoom fly", "speed", "carbon", "race prep", "training"],
        "description": "Carbon-fiber plate for race-day simulation in training"
    },
    "air_zoom_rival_fly": {
        "name": "Nike Air Zoom Rival Fly 3",
        "price": 100.00, "currency": "USD", "category": "running",
        "keywords": ["running", "rival", "race", "zoom", "fast", "tempo", "value"],
        "description": "Affordable zoom racer for tempo runs and local races"
    },
    "winflo_11": {
        "name": "Nike Air Winflo 11",
        "price": 90.00, "currency": "USD", "category": "running",
        "keywords": ["running", "budget", "affordable", "daily", "winflo", "neutral"],
        "description": "Solid everyday runner at an accessible price point"
    },
    "quest_6": {
        "name": "Nike Quest 6",
        "price": 75.00, "currency": "USD", "category": "running",
        "keywords": ["running", "affordable", "beginner", "quest", "entry level", "budget"],
        "description": "Best entry-level running shoe for new runners"
    },
    "revolution_7": {
        "name": "Nike Revolution 7",
        "price": 65.00, "currency": "USD", "category": "running",
        "keywords": ["running", "affordable", "beginner", "budget", "daily", "entry level"],
        "description": "Lightweight and affordable — great first running shoe"
    },
    "downshifter_13": {
        "name": "Nike Downshifter 13",
        "price": 70.00, "currency": "USD", "category": "running",
        "keywords": ["running", "affordable", "lightweight", "budget", "daily", "beginner"],
        "description": "Breathable, cushioned everyday runner under $75"
    },
    "free_rn_5": {
        "name": "Nike Free RN 5.0 Next Nature",
        "price": 100.00, "currency": "USD", "category": "running",
        "keywords": ["running", "free", "natural", "flexible", "lightweight", "minimalist", "barefoot"],
        "description": "Flexible sole that moves with your foot naturally"
    },
    "flex_experience_rn": {
        "name": "Nike Flex Experience Run 12",
        "price": 65.00, "currency": "USD", "category": "running",
        "keywords": ["running", "affordable", "flexible", "budget", "entry level", "womens"],
        "description": "Ultra-flexible affordable runner, great for beginners"
    },

    # ── LIFESTYLE ─────────────────────────────────────────────────────────────
    "air_max_270": {
        "name": "Nike Air Max 270",
        "price": 150.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "270", "lifestyle", "chunky", "streetwear", "casual", "fashion"],
        "description": "Largest Air unit heel for all-day comfort and street style"
    },
    "air_force_1_07": {
        "name": "Nike Air Force 1 '07",
        "price": 110.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air force 1", "af1", "classic", "white", "lifestyle", "iconic", "basketball"],
        "description": "The original 1982 basketball icon, now a streetwear staple"
    },
    "air_max_90": {
        "name": "Nike Air Max 90",
        "price": 130.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "90", "retro", "classic", "og", "lifestyle", "heritage"],
        "description": "1990 icon — the OG Air Max that defined a generation"
    },
    "air_max_95": {
        "name": "Nike Air Max 95",
        "price": 175.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "95", "retro", "neon", "lifestyle", "streetwear", "gradient"],
        "description": "Inspired by the human spine — neon and gradient design"
    },
    "air_max_97": {
        "name": "Nike Air Max 97",
        "price": 175.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "97", "silver bullet", "retro", "lifestyle", "full length air"],
        "description": "First full-length Air unit — the Silver Bullet"
    },
    "air_max_1": {
        "name": "Nike Air Max 1",
        "price": 130.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "1", "og", "original", "retro", "classic", "first air"],
        "description": "Where it all started — the original visible Air Max"
    },
    "air_max_plus": {
        "name": "Nike Air Max Plus",
        "price": 175.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max plus", "tn", "tuned air", "lifestyle", "gradient", "streetwear"],
        "description": "Tuned Air cushioning with bold gradient upper"
    },
    "air_max_720": {
        "name": "Nike Air Max 720",
        "price": 180.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "720", "full air", "lifestyle", "futuristic", "max air"],
        "description": "Tallest Air unit ever — 360-degree full-height Air"
    },
    "air_max_2090": {
        "name": "Nike Air Max 2090",
        "price": 130.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "2090", "futuristic", "lifestyle", "modern", "chunky"],
        "description": "Futuristic design inspired by the iconic Air Max 90"
    },
    "air_max_sc": {
        "name": "Nike Air Max SC",
        "price": 85.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "sc", "affordable", "casual", "budget", "everyday"],
        "description": "Simple, clean Air Max at an everyday price"
    },
    "air_max_pulse": {
        "name": "Nike Air Max Pulse",
        "price": 150.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "pulse", "modern", "lifestyle", "fashion", "streetwear", "new"],
        "description": "Modern Air Max inspired by London music scene energy"
    },
    "air_max_dawn": {
        "name": "Nike Air Max Dawn",
        "price": 100.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "dawn", "chunky", "platform", "retro", "lifestyle", "budget"],
        "description": "Platform Air Max with retro running heritage details"
    },
    "blazer_mid_77": {
        "name": "Nike Blazer Mid '77",
        "price": 105.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["blazer", "mid", "vintage", "classic", "skate", "lifestyle", "retro"],
        "description": "Vintage high-top basketball silhouette from 1977"
    },
    "blazer_low": {
        "name": "Nike Blazer Low '77",
        "price": 90.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["blazer", "low", "vintage", "classic", "lifestyle", "retro", "clean"],
        "description": "Low-profile vintage basketball shoe — clean and minimal"
    },
    "cortez": {
        "name": "Nike Cortez",
        "price": 90.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["cortez", "retro", "classic", "vintage", "og", "nylon", "heritage"],
        "description": "Nike's first-ever running shoe, now a heritage icon"
    },
    "dunk_low": {
        "name": "Nike Dunk Low",
        "price": 115.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["dunk", "low", "skateboarding", "streetwear", "lifestyle", "iconic", "colorway"],
        "description": "1985 basketball shoe reborn as streetwear essential"
    },
    "dunk_high": {
        "name": "Nike Dunk High",
        "price": 125.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["dunk", "high", "basketball", "streetwear", "lifestyle", "colorway", "high top"],
        "description": "High-top Dunk with ankle support and bold colorways"
    },
    "sb_dunk_low": {
        "name": "Nike SB Dunk Low Pro",
        "price": 110.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["sb", "dunk", "skate", "pro", "skateboarding", "zoom", "low"],
        "description": "Skate-specific Dunk with Zoom Air and extra padding"
    },
    "killshot_2": {
        "name": "Nike Killshot 2 Leather",
        "price": 95.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["killshot", "tennis", "clean", "simple", "classic", "court", "minimal"],
        "description": "Clean leather tennis shoe — understated and timeless"
    },
    "zoom_vomero_5": {
        "name": "Nike Zoom Vomero 5",
        "price": 200.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["vomero", "5", "dad shoe", "chunky", "retro", "lifestyle", "premium", "y2k"],
        "description": "Y2K-era running shoe reborn as premium lifestyle staple"
    },
    "tech_hera": {
        "name": "Nike Tech Hera",
        "price": 90.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["tech hera", "chunky", "platform", "lifestyle", "fashion", "streetwear", "women"],
        "description": "Chunky platform lifestyle shoe with tech-inspired details"
    },
    "gamma_force": {
        "name": "Nike Gamma Force",
        "price": 90.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["gamma force", "basketball inspired", "chunky", "platform", "lifestyle", "women"],
        "description": "Basketball-inspired platform shoe for everyday wear"
    },
    "internationalist": {
        "name": "Nike Internationalist",
        "price": 90.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["internationalist", "retro", "runner", "lifestyle", "heritage", "80s"],
        "description": "1980s running heritage meets everyday lifestyle wear"
    },
    "waffle_debut": {
        "name": "Nike Waffle Debut",
        "price": 85.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["waffle", "retro", "vintage", "lifestyle", "heritage", "suede", "og"],
        "description": "Retro running silhouette with original waffle outsole"
    },
    "court_vision": {
        "name": "Nike Court Vision Low Next Nature",
        "price": 75.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["court vision", "budget", "affordable", "casual", "sustainable", "clean"],
        "description": "Sustainable casual court shoe at an accessible price"
    },
    "air_force_1_premium": {
        "name": "Nike Air Force 1 '07 LV8",
        "price": 120.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air force 1", "premium", "lv8", "elevated", "exclusive", "leather"],
        "description": "Premium leather Air Force 1 with elevated details"
    },
    "air_max_1_og": {
        "name": "Nike Air Max 1 '86 OG",
        "price": 180.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "1", "og", "original", "heritage", "collectors", "retro"],
        "description": "The 1986 original reissued with heritage-accurate details"
    },
    "full_force_low": {
        "name": "Nike Full Force Low",
        "price": 80.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["full force", "low", "affordable", "casual", "lifestyle", "everyday"],
        "description": "Low-profile casual shoe inspired by basketball courts"
    },
    "air_max_intrlk": {
        "name": "Nike Air Max Intrlk",
        "price": 85.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "intrlk", "affordable", "casual", "everyday", "budget"],
        "description": "Affordable Air Max for everyday casual wear"
    },

    # ── TRAINING ──────────────────────────────────────────────────────────────
    "metcon_9": {
        "name": "Nike Metcon 9",
        "price": 150.00, "currency": "USD", "category": "training",
        "keywords": ["training", "gym", "crossfit", "metcon", "lifting", "workout", "wod"],
        "description": "Most popular CrossFit and gym training shoe — stable and durable"
    },
    "free_metcon_5": {
        "name": "Nike Free Metcon 5",
        "price": 130.00, "currency": "USD", "category": "training",
        "keywords": ["training", "flexible", "metcon", "gym", "versatile", "free", "run+lift"],
        "description": "Flexible forefoot for running + stable heel for lifting"
    },
    "superrep_go": {
        "name": "Nike SuperRep Go 3 Flyknit",
        "price": 110.00, "currency": "USD", "category": "training",
        "keywords": ["training", "hiit", "superrep", "gym", "workout", "classes", "cardio"],
        "description": "Designed for HIIT, group fitness, and studio workouts"
    },
    "air_zoom_superrep": {
        "name": "Nike Air Zoom SuperRep 4",
        "price": 130.00, "currency": "USD", "category": "training",
        "keywords": ["training", "hiit", "zoom", "superrep", "gym", "cardio", "classes"],
        "description": "Air Zoom cushioning for high-impact cardio sessions"
    },
    "react_metcon": {
        "name": "Nike React Metcon Turbo",
        "price": 120.00, "currency": "USD", "category": "training",
        "keywords": ["training", "react", "metcon", "gym", "cushioned", "versatile"],
        "description": "React foam comfort meets Metcon stability in one shoe"
    },
    "mc_trainer": {
        "name": "Nike MC Trainer 3",
        "price": 85.00, "currency": "USD", "category": "training",
        "keywords": ["training", "affordable", "gym", "budget", "versatile", "everyday"],
        "description": "Versatile budget training shoe for gym and studio work"
    },
    "legend_essential": {
        "name": "Nike Legend Essential 3",
        "price": 65.00, "currency": "USD", "category": "training",
        "keywords": ["training", "affordable", "beginner", "gym", "essential", "budget", "entry"],
        "description": "Entry-level training shoe — clean, simple, affordable"
    },

    # ── BASKETBALL ────────────────────────────────────────────────────────────
    "lebron_22": {
        "name": "Nike LeBron XXII",
        "price": 200.00, "currency": "USD", "category": "basketball",
        "keywords": ["basketball", "lebron", "james", "hoop", "court", "signature", "premium"],
        "description": "LeBron James' signature shoe — power and cushioning"
    },
    "kd_17": {
        "name": "Nike KD 17",
        "price": 160.00, "currency": "USD", "category": "basketball",
        "keywords": ["basketball", "durant", "kd", "court", "hoop", "signature", "kevin durant"],
        "description": "Kevin Durant's signature — speed and precision on court"
    },
    "kyrie_infinity": {
        "name": "Nike Kyrie Infinity",
        "price": 130.00, "currency": "USD", "category": "basketball",
        "keywords": ["basketball", "kyrie", "irving", "court", "hoop", "low", "quick"],
        "description": "Low-cut Kyrie Irving signature for quick guards"
    },
    "pg_7": {
        "name": "Nike PG 7",
        "price": 110.00, "currency": "USD", "category": "basketball",
        "keywords": ["basketball", "pg", "paul george", "court", "hoop", "versatile"],
        "description": "Paul George's versatile all-around basketball shoe"
    },
    "zoom_freak_5": {
        "name": "Nike Zoom Freak 5",
        "price": 120.00, "currency": "USD", "category": "basketball",
        "keywords": ["basketball", "giannis", "freak", "court", "hoop", "signature", "power"],
        "description": "Giannis Antetokounmpo's power-forward signature shoe"
    },
    "cosmic_unity_3": {
        "name": "Nike Cosmic Unity 3",
        "price": 130.00, "currency": "USD", "category": "basketball",
        "keywords": ["basketball", "sustainable", "court", "zoom", "hoop", "eco", "green"],
        "description": "Performance basketball shoe made with sustainable materials"
    },
    "precision_7": {
        "name": "Nike Precision VII",
        "price": 75.00, "currency": "USD", "category": "basketball",
        "keywords": ["basketball", "affordable", "budget", "court", "hoop", "entry level"],
        "description": "Budget basketball shoe — solid court performance at $75"
    },

    # ── TRAIL RUNNING ─────────────────────────────────────────────────────────
    "wildhorse_8": {
        "name": "Nike Wildhorse 8",
        "price": 125.00, "currency": "USD", "category": "trail",
        "keywords": ["trail", "outdoor", "wildhorse", "rugged", "off-road", "hiking", "mud"],
        "description": "Rugged trail runner with aggressive traction outsole"
    },
    "pegasus_trail_5": {
        "name": "Nike Pegasus Trail 5",
        "price": 135.00, "currency": "USD", "category": "trail",
        "keywords": ["trail", "outdoor", "pegasus", "running", "versatile", "road to trail"],
        "description": "Road-to-trail versatility built on the Pegasus platform"
    },
    "terra_kiger_9": {
        "name": "Nike Air Zoom Terra Kiger 9",
        "price": 140.00, "currency": "USD", "category": "trail",
        "keywords": ["trail", "off-road", "terra kiger", "zoom", "aggressive", "rugged", "technical"],
        "description": "Technical trail shoe for aggressive off-road terrain"
    },
    "juniper_trail_2": {
        "name": "Nike Juniper Trail 2",
        "price": 85.00, "currency": "USD", "category": "trail",
        "keywords": ["trail", "affordable", "outdoor", "beginner", "budget", "entry trail"],
        "description": "Accessible trail shoe for beginner off-road runners"
    },
    "react_pegasus_trail": {
        "name": "Nike React Pegasus Trail 4",
        "price": 130.00, "currency": "USD", "category": "trail",
        "keywords": ["trail", "react", "cushioned", "pegasus", "outdoor", "comfortable"],
        "description": "Cushioned trail shoe with React foam for long distances"
    },

    # ── SOCCER / FOOTBALL BOOTS ───────────────────────────────────────────────
    "mercurial_vapor_16": {
        "name": "Nike Mercurial Vapor 16 Elite FG",
        "price": 275.00, "currency": "USD", "category": "soccer",
        "keywords": ["soccer", "football", "speed", "mercurial", "fg", "boots", "elite", "mbappe"],
        "description": "Elite speed boot — worn by the world's fastest forwards"
    },
    "phantom_gx_2": {
        "name": "Nike Phantom GX 2 Elite FG",
        "price": 275.00, "currency": "USD", "category": "soccer",
        "keywords": ["soccer", "phantom", "precision", "fg", "boots", "strike", "playmaker"],
        "description": "Precision-focused boot for creative midfielders"
    },
    "tiempo_legend_10": {
        "name": "Nike Tiempo Legend 10 Elite FG",
        "price": 250.00, "currency": "USD", "category": "soccer",
        "keywords": ["soccer", "tiempo", "leather", "touch", "classic", "fg", "control"],
        "description": "Classic leather touch boot for technical ball control"
    },
    "premier_3": {
        "name": "Nike Premier 3 FG",
        "price": 75.00, "currency": "USD", "category": "soccer",
        "keywords": ["soccer", "budget", "affordable", "firm ground", "leather", "entry"],
        "description": "Premium leather touch at an entry-level price"
    },
    "react_gato": {
        "name": "Nike React Gato",
        "price": 65.00, "currency": "USD", "category": "soccer",
        "keywords": ["soccer", "futsal", "indoor", "react", "gato", "sala", "street"],
        "description": "React foam indoor/futsal shoe for quick court play"
    },

    # ── GOLF ──────────────────────────────────────────────────────────────────
    "air_zoom_infinity_tour": {
        "name": "Nike Air Zoom Infinity Tour 2",
        "price": 200.00, "currency": "USD", "category": "golf",
        "keywords": ["golf", "tour", "zoom", "performance", "course", "premium", "cleated"],
        "description": "Tour-level golf shoe with Zoom Air cushioning"
    },
    "roshe_g_tour": {
        "name": "Nike Roshe G Tour",
        "price": 150.00, "currency": "USD", "category": "golf",
        "keywords": ["golf", "roshe", "spikeless", "course", "comfortable", "casual", "light"],
        "description": "Spikeless golf shoe combining comfort with course performance"
    },

    # ── SANDALS / SLIDES ──────────────────────────────────────────────────────
    "benassi_jdi": {
        "name": "Nike Benassi JDI",
        "price": 30.00, "currency": "USD", "category": "sandals",
        "keywords": ["sandals", "slides", "benassi", "casual", "beach", "pool", "affordable"],
        "description": "Classic Nike slide — the original pool and locker room staple"
    },
    "victori_one": {
        "name": "Nike Victori One",
        "price": 35.00, "currency": "USD", "category": "sandals",
        "keywords": ["sandals", "slides", "victori", "casual", "beach", "pool", "women"],
        "description": "Lightweight women's slide with cushioned footbed"
    },
    "asuna_2": {
        "name": "Nike Asuna 2",
        "price": 40.00, "currency": "USD", "category": "sandals",
        "keywords": ["sandals", "slides", "asuna", "casual", "comfortable", "everyday"],
        "description": "Durable everyday slide with wide strap for secure fit"
    },

    # ── KIDS ──────────────────────────────────────────────────────────────────
    "air_max_270_gs": {
        "name": "Nike Air Max 270 (Grade School)",
        "price": 120.00, "currency": "USD", "category": "kids",
        "keywords": ["kids", "grade school", "air max", "270", "youth", "children", "gs"],
        "description": "Kids' version of the Air Max 270 — same comfort, smaller size"
    },
    "revolution_7_gs": {
        "name": "Nike Revolution 7 (Grade School)",
        "price": 60.00, "currency": "USD", "category": "kids",
        "keywords": ["kids", "youth", "affordable", "running", "school", "gs", "children"],
        "description": "Affordable running shoe for active kids"
    },
    "air_force_1_gs": {
        "name": "Nike Air Force 1 LE (Grade School)",
        "price": 90.00, "currency": "USD", "category": "kids",
        "keywords": ["kids", "grade school", "air force 1", "classic", "youth", "gs", "white"],
        "description": "Classic white Air Force 1 sized for grade school"
    },

    # ── WOMEN'S SPECIFIC ──────────────────────────────────────────────────────
    "air_max_270_womens": {
        "name": "Nike Air Max 270 Women's",
        "price": 150.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["women", "air max", "270", "lifestyle", "casual", "feminine", "colorway"],
        "description": "Women's colorways of the Air Max 270"
    },
    "air_max_bliss": {
        "name": "Nike Air Max Bliss",
        "price": 130.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["women", "air max", "bliss", "lifestyle", "soft", "feminine", "pastel"],
        "description": "Women's lifestyle Air Max with soft cushioning and feminine palette"
    },
    "free_rn_5_womens": {
        "name": "Nike Free RN 5.0 Women's",
        "price": 100.00, "currency": "USD", "category": "running",
        "keywords": ["women", "running", "free", "flexible", "natural", "lightweight", "minimalist"],
        "description": "Women's natural-motion running shoe with flexible Free sole"
    },
    "air_zoom_superrep_womens": {
        "name": "Nike Air Zoom SuperRep 4 Women's",
        "price": 130.00, "currency": "USD", "category": "training",
        "keywords": ["women", "training", "hiit", "gym", "zoom", "classes", "studio"],
        "description": "Women's HIIT shoe with Zoom Air for high-impact classes"
    },
    "dunk_low_womens": {
        "name": "Nike Dunk Low Women's",
        "price": 115.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["women", "dunk", "low", "lifestyle", "streetwear", "colorway", "fashion"],
        "description": "Women's Dunk Low in seasonal colorways"
    },

    # ── PREMIUM / SPECIAL EDITIONS ────────────────────────────────────────────
    "air_max_1_premium": {
        "name": "Nike Air Max 1 Premium",
        "price": 160.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "premium", "leather", "quality", "exclusive", "elevated"],
        "description": "Premium leather Air Max 1 with upgraded materials"
    },
    "dunk_low_retro_premium": {
        "name": "Nike Dunk Low Retro Premium",
        "price": 130.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["dunk", "premium", "retro", "leather", "quality", "elevated", "exclusive"],
        "description": "Premium leather Dunk Low with vintage details"
    },
    "waffle_trainer_2_se": {
        "name": "Nike Waffle Trainer 2 SE",
        "price": 100.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["waffle", "trainer", "retro", "heritage", "se", "special edition", "suede"],
        "description": "Special edition Waffle Trainer with premium suede upper"
    },
    "air_pegasus_89": {
        "name": "Nike Air Pegasus '89 Premium",
        "price": 100.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["pegasus", "89", "retro", "heritage", "runner", "vintage", "premium"],
        "description": "80s running heritage with premium materials update"
    },
    "air_max_terrascape": {
        "name": "Nike Air Max Terrascape 270",
        "price": 160.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "terrascape", "nature", "outdoor", "lifestyle", "sustainable", "earth"],
        "description": "Nature-inspired Air Max 270 with sustainable materials"
    },

    # ── ADDITIONAL ────────────────────────────────────────────────────────────
    "air_max_correlate": {
        "name": "Nike Air Max Correlate",
        "price": 90.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "correlate", "budget", "casual", "everyday", "lightweight"],
        "description": "Lightweight casual Air Max for everyday errands"
    },
    "pegasus_premium": {
        "name": "Nike Air Zoom Pegasus 41 Premium",
        "price": 160.00, "currency": "USD", "category": "running",
        "keywords": ["running", "pegasus", "zoom", "premium", "daily trainer", "leather"],
        "description": "Premium Pegasus with upgraded leather and materials"
    },
    "air_max_dn": {
        "name": "Nike Air Max Dn",
        "price": 135.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "dn", "dynamic", "new", "modern", "lifestyle", "streetwear"],
        "description": "The next chapter of Air Max — dynamic dual-tube Air"
    },
    "dunk_low_next_nature": {
        "name": "Nike Dunk Low Next Nature",
        "price": 105.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["dunk", "low", "sustainable", "eco", "next nature", "lifestyle", "streetwear"],
        "description": "Dunk Low made with at least 20% recycled materials"
    },
    "air_max_sc_womens": {
        "name": "Nike Air Max SC Women's",
        "price": 85.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["women", "air max", "sc", "affordable", "casual", "budget", "everyday"],
        "description": "Women's simple, clean Air Max at an everyday price"
    },
    "react_infinity_run_3": {
        "name": "Nike React Infinity Run Flyknit 3",
        "price": 140.00, "currency": "USD", "category": "running",
        "keywords": ["running", "react", "infinity", "injury prevention", "plush", "older model"],
        "description": "Previous-gen React Infinity — still excellent for easy miles"
    },
    "air_zoom_pegasus_40": {
        "name": "Nike Air Zoom Pegasus 40",
        "price": 110.00, "currency": "USD", "category": "running",
        "keywords": ["running", "pegasus", "zoom", "daily trainer", "previous gen", "value"],
        "description": "Previous-gen Pegasus at a reduced price — still great"
    },
    "flex_runner_3": {
        "name": "Nike Flex Runner 3",
        "price": 55.00, "currency": "USD", "category": "kids",
        "keywords": ["kids", "toddler", "youth", "slip on", "flexible", "school", "affordable"],
        "description": "Easy slip-on school shoe for young kids"
    },
    "hypervenom_phantom": {
        "name": "Nike Hypervenom Phantom III Academy FG",
        "price": 90.00, "currency": "USD", "category": "soccer",
        "keywords": ["soccer", "football", "fg", "mid-range", "attack", "hypervenom"],
        "description": "Mid-range strike boot for attacking players"
    },
    "air_max_excee": {
        "name": "Nike Air Max Excee",
        "price": 90.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["air max", "excee", "retro", "90s", "lifestyle", "casual", "chunky"],
        "description": "90s-inspired chunky Air Max with retro color blocking"
    },
    "air_monarch_iv": {
        "name": "Nike Air Monarch IV",
        "price": 65.00, "currency": "USD", "category": "training",
        "keywords": ["training", "gym", "dad shoe", "wide fit", "affordable", "classic", "monarch"],
        "description": "The legendary dad-trainer — durable, wide, affordable"
    },
    "elite_crew_socks": {
        "name": "Nike Elite Crew Basketball Socks",
        "price": 18.00, "currency": "USD", "category": "accessories",
        "keywords": ["socks", "accessories", "elite", "basketball", "cushioned", "crew"],
        "description": "Nike's best-selling performance basketball socks"
    },
    "roshe_two": {
        "name": "Nike Roshe Two",
        "price": 85.00, "currency": "USD", "category": "lifestyle",
        "keywords": ["roshe", "two", "lifestyle", "minimal", "comfortable", "casual", "flyknit"],
        "description": "Ultra-minimal everyday lifestyle shoe — lightweight and clean"
    },
}


def get_catalog_summary() -> dict:
    """Returns a stats summary without exposing the full catalog."""
    categories: dict = {}
    price_min = float('inf')
    price_max = 0.0

    for item in CATALOG.values():
        cat = item["category"]
        categories[cat] = categories.get(cat, 0) + 1
        price_min = min(price_min, item["price"])
        price_max = max(price_max, item["price"])

    return {
        "total_items":  len(CATALOG),
        "categories":   categories,
        "price_range":  {"min": price_min, "max": price_max},
        "currency":     "USD"
    }
