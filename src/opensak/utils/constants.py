"""
src/opensak/utils/constants.py — Centralised domain constants for OpenSAK.

Single source of truth for cache types, container sizes, attribute IDs,
waypoint prefixes, colour mappings, and shared numeric constants.
"""

# ── Cache types (Groundspeak standard) ────────────────────────────────────────

CACHE_TYPES: list[str] = [
    # Common types
    "Traditional Cache",
    "Multi-cache",
    "Unknown Cache",
    "Letterbox Hybrid",
    "Wherigo Cache",
    "Earthcache",
    "Virtual Cache",
    "Webcam Cache",
    # Event types
    "Event Cache",
    "Cache In Trash Out Event",
    "Mega-Event Cache",
    "Giga-Event Cache",
    "Community Celebration Event",
    "Geocaching HQ Celebration",
    "Geocaching HQ Block Party",
    # Special / HQ types
    "Geocaching HQ Cache",
    "GPS Adventures Maze",
    "Lab Cache",
    "Project A.P.E. Cache",
    # Legacy / rare types
    "Locationless (Reverse) Cache",
    # Custom waypoint types (issue #141) — created manually by the user
    "Waypoint",
    "Hotel/POI",
]

# ── Valid D/T rating values (Groundspeak standard) ────────────────────────────
# D/T must be one of these — 1.7, 2.3 etc. are not valid geocache ratings.

VALID_DT: set[float] = {1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0}

# ── Custom waypoint types shown in the dialog when mode = "Custom Waypoint" ───
# Displayed in the Type dropdown; maps display-label → internal cache_type value.

CUSTOM_WP_TYPES: list[str] = [
    "Parking Area",
    "Trailhead",
    "Stage",
    "Final Location",
    "Reference Point",
    "Waypoint",
    "Hotel/POI",
    "Custom",
]

# ── Container sizes ───────────────────────────────────────────────────────────

CONTAINER_SIZES: list[str] = [
    "Micro",
    "Small",
    "Regular",
    "Large",
    "Other",
    "Not chosen",
]

# ── Geocache attribute IDs (Groundspeak) ──────────────────────────────────────
# Each tuple: (attribute_id, translation_key)

ATTRIBUTES: list[tuple[int, str]] = [
    # Permissions
    (1,  "attr_dogs"),
    (32, "attr_bicycles"),
    (33, "attr_motorcycles"),
    (34, "attr_atv"),
    (35, "attr_snowmobile"),
    (36, "attr_horses"),
    (16, "attr_campfires"),
    (65, "attr_trucks"),

    # Conditions
    (6,  "attr_kids"),
    (7,  "attr_onehour"),
    (8,  "attr_scenic"),
    (9,  "attr_hiking"),
    (10, "attr_climbing"),
    (11, "attr_wading"),
    (12, "attr_swimming"),
    (13, "attr_available"),
    (14, "attr_night"),
    (15, "attr_winter"),
    (40, "attr_stealth"),
    (68, "attr_needs_maintenance"),
    (18, "attr_dangerous_animals"),
    (49, "attr_field_puzzle"),
    (37, "attr_nightcache"),
    (53, "attr_park_and_grab"),
    (57, "attr_abandoned_structure"),
    (43, "attr_short_hike"),
    (44, "attr_medium_hike"),
    (45, "attr_long_hike"),
    (62, "attr_seasonal"),
    (22, "attr_tourist"),
    (46, "attr_private"),
    (60, "attr_teamwork"),
    (71, "attr_challenge"),
    (72, "attr_power_trail"),
    (73, "attr_bonus"),

    # Special
    (67, "attr_lost_found_tour"),
    (69, "attr_partnership"),
    (70, "attr_geotour"),
    (74, "attr_solution_checker"),
    (56, "attr_wireless_beacon"),    # Wireless Beacon

    # Equipment
    (2,  "attr_fee"),
    (3,  "attr_rappelling"),
    (4,  "attr_boat"),
    (5,  "attr_scuba"),
    (51, "attr_flashlight"),
    (42, "attr_flashlight"),         # Flashlight (old GPX ID — same attribute)
    (50, "attr_uv"),
    (41, "attr_snowshoes"),
    (58, "attr_ski"),
    (25, "attr_special_tool"),
    (64, "attr_tree_climbing"),

    # Hazards
    (17, "attr_poisonous_plants"),
    (19, "attr_ticks"),
    (20, "attr_mine"),
    (21, "attr_cliff"),
    (52, "attr_hunting"),
    (26, "attr_dangerous_area"),
    (28, "attr_thorns"),
    (38, "attr_first_aid"),          # First Aid nearby
    (39, "attr_livestock"),          # Livestock / Watch for cattle

    # Facilities
    (24, "attr_wheelchair"),
    (23, "attr_parking"),
    (27, "attr_public_transport"),
    (29, "attr_restrooms"),
    (30, "attr_telephone"),
    (48, "attr_picnic"),
    (47, "attr_camping"),
    (63, "attr_stroller"),
    (66, "attr_fuel"),
    (54, "attr_fuel"),               # Fuel (old GPX ID — same attribute)
    (31, "attr_food"),
    (55, "attr_food"),               # Food (old GPX ID — same attribute)

    # Conditions (legacy IDs mapping to existing attributes)
    (59, "attr_hiking"),             # Significant Hike (old GPX ID — same as 9)
    (61, "attr_tourist"),            # Tourist Friendly (old GPX ID — same as 22)
]

# ── Waypoint prefix registries ────────────────────────────────────────────────

KNOWN_PREFIXES: dict[str, str] = {
    # Groundspeak standard
    "PK": "Parking Area",
    "TH": "Trailhead",
    "S1": "Stage", "S2": "Stage", "S3": "Stage", "S4": "Stage",
    "S5": "Stage", "S6": "Stage", "S7": "Stage", "S8": "Stage", "S9": "Stage",
    "FN": "Final Location",
    "RF": "Reference Point",
    "WP": "Waypoint",
    "SB": "Stages of a Multicache",
    "CM": "Custom",
    "CP": "Custom",
    "PP": "Physical Stage",
    "VX": "Virtual Stage",
    "QA": "Question to Answer",
    # GSAK-specific and extended prefixes
    "LC": "Listed Coordinates",
    "LB": "Listed By",
    "LA": "Listed Area",
    "PA": "Parking Area",
    "PG": "Parking",
    "PT": "Point",
    "PN": "Point",
    "PB": "Point",
    "RP": "Reference Point",
    "ST": "Stage",
    "SP": "Stage Point",
    "AA": "Additional Waypoint",
    "UL": "Additional Waypoint",
    "TE": "Additional Waypoint",
    "FK": "Additional Waypoint",
    # Extended user-file prefixes
    "BR": "Reference Point",
    "UA": "Additional Waypoint",
    "TW": "Additional Waypoint",
    "TU": "Additional Waypoint",
    "TO": "Additional Waypoint",
    "SX": "Stage",
    "SS": "Stage",
    "SM": "Stage",
    "SH": "Stage",
    "SE": "Stage",
}

KNOWN_SINGLE_PREFIXES: dict[str, str] = {
    "T": "Trailhead",
    "V": "Virtual Stage",
    "P": "Parking Area",
    "S": "Stage",
    "F": "Final Location",
    "R": "Reference Point",
}

# ── Colour mappings ───────────────────────────────────────────────────────────

CACHE_COLOURS: dict[str, str] = {
    "Traditional Cache":  "#2e7d32",
    "Multi-cache":        "#e65100",
    "Unknown Cache":      "#1565c0",
    "Letterbox Hybrid":   "#6a1b9a",
    "Wherigo Cache":      "#00838f",
    "Event Cache":        "#ad1457",
    "Mega-Event Cache":   "#ad1457",
    "Giga-Event Cache":   "#ad1457",
    "Earthcache":         "#558b2f",
    "Virtual Cache":      "#f57f17",
}
DEFAULT_CACHE_COLOUR = "#757575"

LOG_COLOURS: dict[str, str] = {
    "Found it":          "#2e7d32",
    "Didn't find it":    "#c62828",
    "Write note":        "#1565c0",
    "Owner Maintenance": "#6a1b9a",
}

# ── Shared numeric constants ──────────────────────────────────────────────────

EARTH_RADIUS_M = 6_371_000.0  # WGS-84 mean radius in metres
