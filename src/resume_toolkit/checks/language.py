"""Built-in English linguistic data and SI unit symbols."""

import re

US_SPELLING_STEMS = (
    "analyz",
    "behavior",
    "characteriz",
    "color",
    "customiz",
    "maximiz",
    "minimiz",
    "modeling",
    "optimiz",
    "organiz",
    "prioritiz",
    "standardiz",
    "summariz",
    "utiliz",
    "visualiz",
)

UNIT_SYMBOLS = (
    "%",
    "°C",
    "A",
    "Ah",
    "bar",
    "cm",
    "g",
    "h",
    "Hz",
    "kA",
    "kg",
    "kHz",
    "km",
    "kPa",
    "kV",
    "kW",
    "kWh",
    "L",
    "m",
    "mA",
    "mAh",
    "MHz",
    "min",
    "mL",
    "mm",
    "MPa",
    "ms",
    "mV",
    "MW",
    "MWh",
    "N",
    "Nm",
    "Pa",
    "rpm",
    "s",
    "V",
    "W",
    "Wh",
)

UNIT_SYMBOL_PATTERN = "|".join(
    map(re.escape, sorted(UNIT_SYMBOLS, key=len, reverse=True))
)

UNIT_WITHOUT_SPACE = re.compile(
    r"(?P<number>(?<![\w.])(?:[<>≤≥±~]?\d+(?:[.,]\d+)?))"
    rf"(?P<unit>{UNIT_SYMBOL_PATTERN})"
    r"(?=$|[^\w])"
)

PRESENT_VERBS = {
    "Architect",
    "Automate",
    "Build",
    "Create",
    "Define",
    "Deliver",
    "Develop",
    "Drive",
    "Enforce",
    "Fix",
    "Implement",
    "Lead",
    "Maintain",
    "Manage",
    "Own",
    "Run",
    "Set",
    "Ship",
    "Specify",
    "Turn",
    "Write",
}

IRREGULAR_PAST = {
    "Built",
    "Brought",
    "Held",
    "Kept",
    "Led",
    "Made",
    "Ran",
    "Set",
    "Took",
    "Won",
    "Wrote",
}

NON_PROSE_KEYS = {
    "$schema",
    "canonical",
    "countryCode",
    "email",
    "postalCode",
    "source",
    "url",
    "username",
    "x-highlights",
    "x-tags",
}

SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
