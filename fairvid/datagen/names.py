"""Small pools of made-up names, so we don't need the external `faker` library.

Names are grouped by region only to give the cohort some surface variety. The
groupings are arbitrary and carry no real-world meaning.
"""

from __future__ import annotations

import numpy as np

FIRST_NAMES = {
    "region_a": ("Aarav", "Diya", "Kabir", "Meera", "Rohan", "Saanvi", "Vihaan", "Anaya"),
    "region_b": ("Liam", "Emma", "Noah", "Olivia", "Lucas", "Mia", "Ethan", "Ava"),
    "region_c": ("Wei", "Lan", "Hao", "Mei", "Jin", "Yan", "Feng", "Xia"),
    "region_d": ("Amara", "Kwame", "Zola", "Tendai", "Naila", "Obi", "Sefu", "Ife"),
}

LAST_NAMES = {
    "region_a": ("Sharma", "Patel", "Nair", "Reddy", "Iyer", "Bose"),
    "region_b": ("Smith", "Johnson", "Brown", "Wilson", "Davis", "Clark"),
    "region_c": ("Chen", "Wang", "Li", "Zhang", "Liu", "Huang"),
    "region_d": ("Okafor", "Mensah", "Dube", "Adeyemi", "Banda", "Sow"),
}


def make_name(region: str, rng: np.random.Generator) -> str:
    """Pick a first and last name for the given region."""
    first = rng.choice(FIRST_NAMES[region])
    last = rng.choice(LAST_NAMES[region])
    return f"{first} {last}"
