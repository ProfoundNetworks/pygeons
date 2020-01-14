#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
"""Read place names from standard input (in allCities.txt format).  Derive
place names deterministically and add them to the list of names.  Outputs CSV
to stdout in the same format as the input."""
from __future__ import unicode_literals
from __future__ import print_function

import re
import collections
import os.path as P
import logging
import sys
import json
import argparse

import yaml

import append_alternatenames


ADMIN_REGEX = re.compile(r"ADM\dH?")


def load_support(name):
    """Load the support file with the specified name."""
    curr = P.dirname(P.abspath(__file__))
    with open(P.join(curr, "data", "%s.yml" % name)) as fin:
        return yaml.full_load(fin)

GB_SUPPORT = load_support("gb-support")

Place = collections.namedtuple("Place", ["name", "asciiname", "countryCode",
                                         "alternativeNames"])

Name = collections.namedtuple("Name", ["text", "lang"])

SAINT_REGEX = re.compile(r"\bsaint\b", re.IGNORECASE)
MOUNT_REGEX = re.compile(r"\bmount\b", re.IGNORECASE)
XOY_REGEX = re.compile(r"\s+o[’']\s+", re.IGNORECASE)
O_REGEX = re.compile(r"^o[’']\s+", re.IGNORECASE)

COUNTY_REGEX = re.compile(r"^county\b *", re.IGNORECASE)

JP_KEN_SUFFIX = re.compile("[- ]ken$")
JP_FU_SUFFIX = re.compile("[- ]fu$")
JP_SHI_SUFFIX = re.compile("[- ]shi$")
JP_KU_SUFFIX = re.compile("[- ]ku$")
JA_JP_SHI_SUFFIX = re.compile("市$")

RU_SUPPORT = load_support("ru-support")

RU_OBLAST_SUFFIX = re.compile("область$", re.IGNORECASE)
EN_RU_OBLAST_SUFFIX = re.compile("oblast['’]?$", re.IGNORECASE)
EN_RU_KRAY_SUFFIX = re.compile("kra[iy]$", re.IGNORECASE)

PARENTHETICAL = re.compile(r"\(([^)]+)\)")
MX_COLONIA = re.compile(r"^colonia\b", re.IGNORECASE)
MX_DELEG = re.compile(r"^delegación\b( de\b)?", re.IGNORECASE)
MX_CIUDAD = re.compile(r"^ciudad\b", re.IGNORECASE)

MX_SUPPORT = load_support("mx-support")


def languages_spoken_in(country):
    """A generator for the languages spoken in a single country."""
    for lang, countries in LANGUAGES.items():
        if country in countries:
            yield lang


def derive_country_GB(place):
    """Derive British place names."""
    logging.debug("derive_country_gb: %r", place)
    alt = GB_SUPPORT["alternative_names"]
    try:
        derived = alt[place.name.lower()]
    except KeyError:
        derived = []
    return [Name(text, "en") for text in derived]


def derive_country_IE(place):
    """Derive Irish place names."""
    derived = []
    if COUNTY_REGEX.search(place.name):
        stripped = COUNTY_REGEX.sub("", place.name.lower())
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

    return [Name(text, "en") for text in derived]


def derive_country_JP(place):
    """Derive Japanese place names."""
    derived = []
    if JP_FU_SUFFIX.search(place.asciiname):
        bare = JP_FU_SUFFIX.sub("", place.asciiname)
        derived += [bare, bare + " prefecture", bare + " pref"]
    elif JP_KEN_SUFFIX.search(place.asciiname):
        bare = JP_KEN_SUFFIX.sub("", place.asciiname)
        derived += [bare, bare + " prefecture", bare + " pref",
                    bare + "-ken", bare + " ken"]
    elif JP_SHI_SUFFIX.search(place.name):
        bare = JP_SHI_SUFFIX.sub("", place.name)
        derived += [bare, bare + "-city", bare + " city"]
    elif JP_KU_SUFFIX.search(place.name):
        bare = JP_KU_SUFFIX.sub("", place.name)
        derived += [bare, bare + "-ku", bare + " ku", bare + " ward"]

    en_names = [Name(text.lower(), "en") for text in derived]
    logging.debug("derive_country_JP: en_names: %r", en_names)

    if JA_JP_SHI_SUFFIX.search(place.name):
        bare = JA_JP_SHI_SUFFIX.sub("", place.name)
        ja_names = [Name(bare, "ja")]
    else:
        ja_names = []
    return en_names + ja_names


def derive_country_RU(place):
    """Derive Russian country names."""
    derived = {"en": [], "ru": []}

    unconjugation = RU_SUPPORT["unconjugation"]
    if EN_RU_OBLAST_SUFFIX.search(place.name):
        bare = EN_RU_OBLAST_SUFFIX.sub("", place.name).strip().lower()
        try:
            bare = unconjugation[bare]
        except KeyError:
            logging.debug("RU: unable to unconjugate bare name: %s", bare)
        derived["en"] += [bare, bare + " oblast", bare + " region",
                          bare + " reg"]

        for name in place.alternativeNames:
            if RU_OBLAST_SUFFIX.search(name):
                dative_full = re.sub("ая область", "ой области", name.lower())
                dative_abbr = re.sub("ая область", "ой обл", name.lower())
                derived["ru"] += [dative_full, dative_abbr]
    elif EN_RU_KRAY_SUFFIX.search(place.name):
        bare = EN_RU_KRAY_SUFFIX.sub("", place.name).strip().lower()
        try:
            bare = unconjugation[bare]
        except KeyError:
            logging.debug("RU: unable to unconjugate bare name: %s", bare)
        derived["en"] += [bare, bare + " kray",
                          bare + " region", bare + " reg"]

    logging.debug("ru: %r", place.name.lower())

    for lang in ("en", "ru"):
        alternative_names = RU_SUPPORT["alternative_names"][lang]
        try:
            derived[lang] += alternative_names[place.name.lower()]
        except KeyError:
            pass

    names = []
    for lang, derived_names in derived.items():
        names += [Name(text, lang) for text in derived_names]
    logging.debug("ru: names: %r", names)
    return names


def derive_country_MX(place):
    """Derive names for Mexican places."""
    lname = place.name.lower()
    derived = []
    match = PARENTHETICAL.search(lname)
    if match:
        derived.append(PARENTHETICAL.sub("", lname).strip())
        derived.append(match.group(1).strip())

    if MX_COLONIA.search(place.name):
        derived.append(MX_COLONIA.sub("col", lname))

    if MX_DELEG.search(place.name):
        derived.append(MX_DELEG.sub("delegación", lname))
        derived.append(MX_DELEG.sub("del", lname))
        derived.append(MX_DELEG.sub("deleg", lname))

    if MX_CIUDAD.search(place.name):
        derived.append(MX_CIUDAD.sub("cd", lname))

    alternative_names = MX_SUPPORT["alternative_names"]["es"]
    try:
        derived += alternative_names[lname]
    except KeyError:
        pass

    return [Name(text, "es") for text in derived]


def derive_lang_en(place):
    """Derive place names for an English-speaking country."""
    logging.debug("derive_lang_en: %r", place)

    en_names = [place.name.lower(), place.asciiname.lower()]
    derive_from = sorted(set(
        en_names + [x.lower() for x in place.alternativeNames]
    ))
    derived = []

    #
    # Hyphenated names should always have space-separated variants
    #
    derived.append(place.name.lower().replace("-", " "))
    derived.append(place.asciiname.lower().replace("-", " "))

    #
    # Saint X names should always have St X variants
    #
    if SAINT_REGEX.search(place.name):
        derived.extend([SAINT_REGEX.sub("st", n) for n in derive_from])

    #
    # Mount X names should always have Mt X variants
    #
    if MOUNT_REGEX.search(place.name):
        derived.extend([MOUNT_REGEX.sub("mt", n) for n in derive_from])

    #
    # X O' Y names should always have 'of' and 'o' variants
    #
    if XOY_REGEX.search(place.name):
        derived.extend([XOY_REGEX.sub(" o' ", n) for n in derive_from])
        derived.extend([XOY_REGEX.sub(" o’ ", n) for n in derive_from])
        derived.extend([XOY_REGEX.sub(" of ", n) for n in derive_from])
        derived.extend([XOY_REGEX.sub(" o ", n) for n in derive_from])

    #
    # O' XYZ names should have variants with that space removed
    #
    if O_REGEX.search(place.name):
        derived.extend([O_REGEX.sub("o'", n) for n in derive_from])
        derived.extend([O_REGEX.sub("o’", n) for n in derive_from])

    return [Name(text, "en") for text in derived]


def derive_names(place, country_info):
    logging.debug("derive_names: %r", place)

    derived = []
    for lang in country_info.languages_spoken_in(place.countryCode):
        try:
            lang_function = globals()["derive_lang_" + lang]
        except KeyError:
            pass
        else:
            derived.extend(lang_function(place))

    try:
        country_function = globals()["derive_country_" + place.countryCode]
        derived.extend(country_function(place))
    except KeyError:
        logging.debug("no country_function for %r", place.countryCode)
        pass

    already_have = [place.name.lower(), place.asciiname.lower()]
    already_have += [x.lower() for x in place.alternativeNames]

    return sorted(set([x for x in derived
                       if x.text and x.text not in already_have]))


def process_obj(obj, country_info):
    #
    # http://download.geonames.org/export/dump/readme.txt
    #
    logging.debug(obj)
    place = Place(obj["name"], obj["asciiname"], obj["countryCode"],
                  obj["names"])
    derived = derive_names(place, country_info)

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

    obj["names"] = sorted(set(obj["names"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("countryInfo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    with open(args.countryInfo) as fin:
        country_info = append_alternatenames.CountryInfo(fin)

    for line in sys.stdin:
        obj = json.loads(line)
        process_obj(obj, country_info)
        sys.stdout.write(json.dumps(obj))
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
