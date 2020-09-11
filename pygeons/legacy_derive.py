#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
"""Derive place names."""
from __future__ import unicode_literals
from __future__ import print_function

import re
import collections
import os.path as P
import logging
import sys
import json

import yaml

from . import process

_LOGGER = logging.getLogger(__name__)
#
# Prevent stderr message about "no handlers found".
# It is possible that somebody is using Pygeon without logging.
# https://docs.python.org/2/howto/logging.html#configuring-logging-for-a-library
#
_LOGGER.addHandler(logging.NullHandler())


def _load_support(name):
    """Load the support file with the specified name."""
    curr = P.dirname(P.abspath(__file__))
    with open(P.join(curr, "data", "%s.yml" % name)) as fin:
        return yaml.full_load(fin)


_GB_SUPPORT = _load_support("gb-support")
_RU_SUPPORT = _load_support("ru-support")
_MX_SUPPORT = _load_support("mx-support")

_ADMIN_REGEX = re.compile(r"ADM\dH?")

Place = collections.namedtuple("Place", ["name", "asciiname", "countryCode", "alternativeNames"])
DerivedName = collections.namedtuple("DerivedName", ["text", "lang"])

_SAINT_REGEX = re.compile(r"\bsaint\b", re.IGNORECASE)
_MOUNT_REGEX = re.compile(r"\bmount\b", re.IGNORECASE)
_XOY_REGEX = re.compile(r"\s+o[’']\s+", re.IGNORECASE)
_O_REGEX = re.compile(r"^o[’']\s+", re.IGNORECASE)

_COUNTY_REGEX = re.compile(r"^county\b *", re.IGNORECASE)

_JP_KEN_SUFFIX = re.compile("[- ]ken$")
_JP_FU_SUFFIX = re.compile("[- ]fu$")
_JP_SHI_SUFFIX = re.compile("[- ]shi$")
_JP_KU_SUFFIX = re.compile("[- ]ku$")
_JA_JP_SHI_SUFFIX = re.compile("市$")

_RU_OBLAST_SUFFIX = re.compile("область$", re.IGNORECASE)
_EN_RU_OBLAST_SUFFIX = re.compile("oblast['’]?$", re.IGNORECASE)
_EN_RU_KRAY_SUFFIX = re.compile("kra[iy]$", re.IGNORECASE)

_PARENTHETICAL = re.compile(r"\(([^)]+)\)")
_MX_COLONIA = re.compile(r"^colonia\b", re.IGNORECASE)
_MX_DELEG = re.compile(r"^delegación\b( de\b)?", re.IGNORECASE)
_MX_CIUDAD = re.compile(r"^ciudad\b", re.IGNORECASE)


def _derive_country_GB(place):
    """Derive British place names."""
    _LOGGER.debug("derive_country_gb: %r", place)
    alt = _GB_SUPPORT["alternative_names"]
    try:
        derived = alt[place.name.lower()]
    except KeyError:
        derived = []
    return [DerivedName(text, "en") for text in derived]


def _derive_country_IE(place):
    """Derive Irish place names."""
    derived = []
    if _COUNTY_REGEX.search(place.name):
        stripped = _COUNTY_REGEX.sub("", place.name.lower())
        derived += ["co " + stripped, "county " + stripped]

    #
    # Alternative name cases that aren't as straightforward as the above.
    #
    try:
        derived += {
            "loch garman": ["co wexford"],
            "uíbh fhailí": ["co offaly"],
            "maigh eo": ["co mayo"],
            "an iarmhí": ["co westmeath"],
        }[place.name.lower()]
    except KeyError:
        pass

    return [DerivedName(text, "en") for text in derived]


def _derive_country_JP(place):
    """Derive Japanese place names."""
    derived = []
    if _JP_FU_SUFFIX.search(place.asciiname):
        bare = _JP_FU_SUFFIX.sub("", place.asciiname)
        derived += [bare, bare + " prefecture", bare + " pref"]
    elif _JP_KEN_SUFFIX.search(place.asciiname):
        bare = _JP_KEN_SUFFIX.sub("", place.asciiname)
        derived += [bare, bare + " prefecture", bare + " pref",
                    bare + "-ken", bare + " ken"]
    elif _JP_SHI_SUFFIX.search(place.name):
        bare = _JP_SHI_SUFFIX.sub("", place.name)
        derived += [bare, bare + "-city", bare + " city"]
    elif _JP_KU_SUFFIX.search(place.name):
        bare = _JP_KU_SUFFIX.sub("", place.name)
        derived += [bare, bare + "-ku", bare + " ku", bare + " ward"]

    en_names = [DerivedName(text.lower(), "en") for text in derived]
    _LOGGER.debug("derive_country_JP: en_names: %r", en_names)

    if _JA_JP_SHI_SUFFIX.search(place.name):
        bare = _JA_JP_SHI_SUFFIX.sub("", place.name)
        ja_names = [DerivedName(bare, "ja")]
    else:
        ja_names = []
    return en_names + ja_names


def _derive_country_RU(place):
    """Derive Russian country names."""
    derived = {"en": [], "ru": []}

    unconjugation = _RU_SUPPORT["unconjugation"]
    if _EN_RU_OBLAST_SUFFIX.search(place.name):
        bare = _EN_RU_OBLAST_SUFFIX.sub("", place.name).strip().lower()
        try:
            bare = unconjugation[bare]
        except KeyError:
            _LOGGER.debug("RU: unable to unconjugate bare name: %s", bare)
        derived["en"] += [bare, bare + " oblast", bare + " region", bare + " reg"]

        for name in place.alternativeNames:
            if _RU_OBLAST_SUFFIX.search(name):
                dative_full = re.sub("ая область", "ой области", name.lower())
                dative_abbr = re.sub("ая область", "ой обл", name.lower())
                derived["ru"] += [dative_full, dative_abbr]
    elif _EN_RU_KRAY_SUFFIX.search(place.name):
        bare = _EN_RU_KRAY_SUFFIX.sub("", place.name).strip().lower()
        try:
            bare = unconjugation[bare]
        except KeyError:
            _LOGGER.debug("RU: unable to unconjugate bare name: %s", bare)
        derived["en"] += [bare, bare + " kray",
                          bare + " region", bare + " reg"]

    _LOGGER.debug("ru: %r", place.name.lower())

    for lang in ("en", "ru"):
        alternative_names = _RU_SUPPORT["alternative_names"][lang]
        try:
            derived[lang] += alternative_names[place.name.lower()]
        except KeyError:
            pass

    names = []
    for lang, derived_names in derived.items():
        names += [DerivedName(text, lang) for text in derived_names]
    _LOGGER.debug("ru: names: %r", names)
    return names


def _derive_country_MX(place):
    """Derive names for Mexican places."""
    lname = place.name.lower()
    derived = []
    match = _PARENTHETICAL.search(lname)
    if match:
        derived.append(_PARENTHETICAL.sub("", lname).strip())
        derived.append(match.group(1).strip())

    if _MX_COLONIA.search(place.name):
        derived.append(_MX_COLONIA.sub("col", lname))

    if _MX_DELEG.search(place.name):
        derived.append(_MX_DELEG.sub("delegación", lname))
        derived.append(_MX_DELEG.sub("del", lname))
        derived.append(_MX_DELEG.sub("deleg", lname))

    if _MX_CIUDAD.search(place.name):
        derived.append(_MX_CIUDAD.sub("cd", lname))

    alternative_names = _MX_SUPPORT["alternative_names"]["es"]
    try:
        derived += alternative_names[lname]
    except KeyError:
        pass

    return [DerivedName(text, "es") for text in derived]


def _dedup(x):
    return sorted(set(x))


def _derive_lang_en(place):
    """Derive place names for an English-speaking country."""
    _LOGGER.debug("derive_lang_en: %r", place)

    en_names = [place.name.lower(), place.asciiname.lower()]
    derive_from = _dedup(en_names + [x.lower() for x in place.alternativeNames])
    derived = []

    #
    # Hyphenated names should always have space-separated variants
    #
    derived.append(place.name.lower().replace("-", " "))
    derived.append(place.asciiname.lower().replace("-", " "))

    #
    # Saint X names should always have St X variants
    #
    if _SAINT_REGEX.search(place.name):
        derived.extend([_SAINT_REGEX.sub("st", n) for n in derive_from])

    #
    # Mount X names should always have Mt X variants
    #
    if _MOUNT_REGEX.search(place.name):
        derived.extend([_MOUNT_REGEX.sub("mt", n) for n in derive_from])

    #
    # X O' Y names should always have 'of' and 'o' variants
    #
    if _XOY_REGEX.search(place.name):
        derived.extend([_XOY_REGEX.sub(" o' ", n) for n in derive_from])
        derived.extend([_XOY_REGEX.sub(" o’ ", n) for n in derive_from])
        derived.extend([_XOY_REGEX.sub(" of ", n) for n in derive_from])
        derived.extend([_XOY_REGEX.sub(" o ", n) for n in derive_from])

    #
    # O' XYZ names should have variants with that space removed
    #
    if _O_REGEX.search(place.name):
        derived.extend([_O_REGEX.sub("o'", n) for n in derive_from])
        derived.extend([_O_REGEX.sub("o’", n) for n in derive_from])

    return [DerivedName(text, "en") for text in derived]


def _derive_names(place, country_info):
    _LOGGER.debug("derive_names: %r", place)

    derived = []
    for lang in country_info.languages_spoken_in(place.countryCode):
        try:
            lang_function = globals()["_derive_lang_" + lang]
        except KeyError:
            pass
        else:
            derived.extend(lang_function(place))

    try:
        country_function = globals()["_derive_country_" + place.countryCode]
        derived.extend(country_function(place))
    except KeyError:
        _LOGGER.debug("no country_function for %r", place.countryCode)
        pass

    already_have = [place.name.lower(), place.asciiname.lower()]
    already_have += [x.lower() for x in place.alternativeNames]

    return _dedup([x for x in derived if x.text and x.text not in already_have])


def _process_obj(obj, country_info):
    #
    # http://download.geonames.org/export/dump/readme.txt
    #
    _LOGGER.debug(obj)
    place = Place(obj["name"], obj["asciiname"], obj["countryCode"], obj["names"])
    derived = _derive_names(place, country_info)

    if "names_lang" not in obj:
        obj["names_lang"] = {}

    for name in derived:
        try:
            lang = obj["names_lang"][name.lang]
        except KeyError:
            obj["names_lang"][name.lang] = []
            lang = obj["names_lang"][name.lang]

        text = name.text.lower()
        lang.append(text)
        obj["names"].append(text)

    obj["names"] = _dedup(obj["names"])


def derive(country_info_path, stdin=sys.stdin, stdout=sys.stdout):
    with open(country_info_path) as fin:
        country_info = process.CountryInfo(fin)

    for line in stdin:
        obj = json.loads(line)
        _process_obj(obj, country_info)
        stdout.write(json.dumps(obj))
        stdout.write("\n")
        stdout.flush()
