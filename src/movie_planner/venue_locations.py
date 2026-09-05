"""Hardcoded chain/city/country data for venues already logged - see
issue #111. Not geocoded dynamically: a venue name not listed here gets
no chain/location, never a guess. Chain and location confirmed by
research (Pathé's own cinema listings, GSC's), not assumed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueLocation:
    chain: str | None
    city: str
    country: str


KNOWN_VENUE_LOCATIONS: dict[str, VenueLocation] = {}


def _add(names: list[str], *, chain: str | None, city: str, country: str) -> None:
    location = VenueLocation(chain=chain, city=city, country=country)
    for name in names:
        KNOWN_VENUE_LOCATIONS[name] = location


# Pathé - confirmed operator of all five Amsterdam venues below (Pathé
# acquired the former MGM Netherlands chain, including Tuschinski, in
# 1995; the others are long-standing Pathé-branded multiplexes).
# Several logged names bake a screen/format (4DX, Dolby, Atmos, Relax)
# into the venue string rather than naming a separate physical venue -
# these are grouped under the same real-world location.
_PATHE = {"chain": "Pathé", "city": "Amsterdam", "country": "Netherlands"}
_add(["Tuschinski"], **_PATHE)
_add(
    [
        "De Munt",
        "De Munt 4DX",
        "De Munt Dolby",
        "De Munt Relax",
        "De Munt Dolby Cinema",
        "Pathé De Munt",
    ],
    **_PATHE,
)
_add(["City", "Pathé City"], **_PATHE)
_add(["Arena", "Pathé Arena"], **_PATHE)
_add(
    [
        "Amsterdam Noord",
        "Amsterdam Noord Dolby Cinema",
        "Amsterdam Noord Atmos",
        "Amsterdam Noord Dolby Atmos",
        "Pathe Noord",
        "Pathé Noord",
        "Pathé Amsterdam Noord",
    ],
    **_PATHE,
)

# GSC (Golden Screen Cinemas) - Malaysia's largest chain.
_add(["Gsc Gurney Plaza Penang"], chain="GSC", city="Penang", country="Malaysia")

# Independent, single-site Amsterdam cinemas - no chain.
_add(
    [
        "Eye",
        "Cinecenter",
        "Filmhallen",
        "De FilmHallen",
        "Rialto",
        "Rialto VU",
        "Studio/K",
        "Lab111",
        "De Balie",
    ],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
)
