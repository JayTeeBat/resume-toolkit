"""Built-in English linguistic data and unit symbols (SI Brochure, 9th edition)."""

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

#: Edition the unit_spacing rule follows; docs/standards.md must cite the same.
SI_BROCHURE = "SI Brochure, 9th edition (2019)"

# SI Brochure §5.4.3: a space always separates the number from the unit
# symbol, °C included; §5.4.7: the same for %. Only symbols listed here are
# checked, so a bare number never trips the rule.
UNIT_SYMBOLS = (
    # SI units, with their prefixed forms.
    "°C",
    "A",
    "cm",
    "g",
    "Hz",
    "kA",
    "kg",
    "kHz",
    "km",
    "kPa",
    "kV",
    "kW",
    "m",
    "mA",
    "MHz",
    "mm",
    "MPa",
    "ms",
    "mV",
    "MW",
    "N",
    "Pa",
    "s",
    "V",
    "W",
    # Non-SI units accepted for use with the SI (Brochure Table 8).
    "h",
    "L",
    "min",
    "mL",
    # The percent sign (§5.4.7).
    "%",
    # Non-SI units common in battery engineering, spaced by the same
    # convention. N m is left out: SI writes it with a space or a dot, never
    # "Nm", so a rule that accepted "20 Nm" would endorse the wrong form.
    "Ah",
    "bar",
    "kWh",
    "mAh",
    "MWh",
    "rpm",
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
    "Analyse",
    "Analyze",
    "Architect",
    "Automate",
    "Build",
    "Configure",
    "Coordinate",
    "Create",
    "Define",
    "Deliver",
    "Deploy",
    "Design",
    "Develop",
    "Drive",
    "Enforce",
    "Fix",
    "Implement",
    "Integrate",
    "Lead",
    "Maintain",
    "Manage",
    "Mentor",
    "Migrate",
    "Model",
    "Monitor",
    "Operate",
    "Optimise",
    "Optimize",
    "Own",
    "Run",
    "Set",
    "Ship",
    "Simulate",
    "Specify",
    "Support",
    "Test",
    "Train",
    "Turn",
    "Validate",
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
