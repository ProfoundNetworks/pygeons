"""Append non-English names to places."""
from __future__ import print_function
from __future__ import unicode_literals

import collections
import json
import argparse
import sys
import logging
import csv
import os.path as P

ENGLISH = "en"
"""The language code for English, all countries speak it."""

ABBR = "abbr"
"""The language code for English abbreviations."""

LINK = "link"
"""The language code for Wikipedia links.  We ignore these."""

UNKNOWN = "??"
"""The language code for names without a language code."""

ALL_COUNTRIES = "allCountries"
COUNTRY_INFO = "countryInfo"


def _scrub(s):
    """Strip punctuation, make everything lowercase."""
    if not s:
        return s
    return "".join([x for x in s.lower().strip() if x != "."])


def read_iso6391():
    #
    # curl "https://www.loc.gov/standards/iso639-2/ISO-639-2_utf-8.txt" | awk -F'|' '{print $3}' | sort -u > iso639-1.txt  # noqa
    #
    curr_dir = P.dirname(P.abspath(__file__))
    with open(P.join(curr_dir, "data/iso639-1.txt")) as fin:
        return fin.read().strip().split("\n")
ISO639_1 = read_iso6391()
"""These are the main languages spoken in the world."""

Name = collections.namedtuple("Name", ["geoid", "lang", "name"])


def csv_to_name(row):
    row[1] = int(row[1])
    row[3] = row[3].decode("utf-8")
    if row[2] == "":
        row[2] = UNKNOWN
    return Name(*row[1:4])


class NameReader(object):
    """Reads names from alternateNames.tsv one-by-one.

    Expects the file to be sorted by geoid."""

    def __init__(self, fin):
        self.reader = csv.reader(fin, delimiter=b"\t", quoting=csv.QUOTE_NONE)
        self.last_requested_geoid = None
        self.buf = None

    def _buffered_read(self):
        if self.buf:
            name, self.buf = self.buf, None
            return name
        return csv_to_name(next(self.reader))

    def read(self, geoid):
        """Read all names for the specified geoid."""
        if self.last_requested_geoid and geoid <= self.last_requested_geoid:
            raise ValueError("geoid must be increasing with each read call")
        self.last_requested_geoid = geoid

        logging.debug("NameReader.read: called")
        names = []
        while True:
            try:
                name = self._buffered_read()
            except StopIteration:
                logging.debug("reached end of alternate names file")
                break

            if name.geoid == geoid and name.lang != LINK:
                names.append(name)
            elif name.geoid > geoid:
                self.buf = name
                logging.debug("moved past required geoid (%d < %d)", geoid, name.geoid)
                break

        return names


class CountryInfo(object):
    """Enables in-memory lookups of countryInfo.txt."""

    def __init__(self, fin):
        self.countries = {}
        for line in fin:
            cinfo = json.loads(line)
            self.countries[cinfo["iso"]] = cinfo

    def languages_spoken_in(self, country):
        """Return the languages spoken in the specified country (ISO2 code).

        Only returns languages specified in ISO639-1."""
        try:
            cinfo = self.countries[country]
        except KeyError:
            return [ENGLISH]
        else:
            codes = [c.split("-")[0] if "-" in c else c
                     for c in cinfo["languages"]]
            codes = [c for c in codes if c in ISO639_1]
            return codes


def get_names(geonames_id, country_code, all_names, cinfo):
    this_country_speaks = cinfo.languages_spoken_in(country_code)
    if ENGLISH not in this_country_speaks:
        this_country_speaks.append(ENGLISH)
    this_country_speaks.append(UNKNOWN)

    logging.debug("this_country_speaks: %r", this_country_speaks)
    alternate_names = [x for x in all_names if x.lang in this_country_speaks]
    logging.debug("alternate_names: %r", alternate_names)

    relevant_names_by_language = collections.defaultdict(list)
    for name in alternate_names:
        relevant_names_by_language[name.lang].append(_scrub(name.name))

    abbreviations = [x for x in all_names if x.lang == ABBR]
    abbr = [_scrub(n.name) for n in abbreviations]

    for lang, names in relevant_names_by_language.items():
        relevant_names_by_language[lang] = sorted(set(names))

    relevant_names = [_scrub(n.name) for n in alternate_names + abbreviations]

    #
    # N.B. save most of the deduping for later.
    #
    logging.debug("relevant_names: %r abbr: %r relevant_names_by_language: %r",
                  relevant_names, abbr, relevant_names_by_language)
    return relevant_names, abbr, relevant_names_by_language


def append_alternate_names_country(country, all_names, cinfo):
    geonames_id = country["_id"]
    iso = country["iso"]
    iso3 = country["iso3"]
    names, abbr, names_lang = get_names(geonames_id, iso, all_names, cinfo)

    scrubbed_name = _scrub(country["name"])
    names.extend([iso.lower(), iso3.lower(), scrubbed_name])
    names = sorted(set(names))

    names_lang["en"].extend([iso.lower(), iso3.lower(), scrubbed_name])
    names_lang["en"] = sorted(set(names_lang["en"]))

    abbr.extend([iso.lower(), iso3.lower()])
    abbr = sorted(set(abbr))

    country["names"] = names
    country["abbr"] = abbr
    country["names_lang"] = dict(names_lang)


def append_alternate_names(place, all_names, cinfo):
    geonames_id = place["_id"]
    country = place["countryCode"]

    names, abbr, names_lang = get_names(geonames_id, country, all_names, cinfo)

    names.append(place["name"].lower())
    names.append(place["asciiname"].lower())
    names = sorted(set(names))

    names_lang["en"].append(place["name"].lower())
    names_lang["en"].append(place["asciiname"].lower())
    names_lang["en"] = sorted(set(names_lang["en"]))

    place["names"] = names
    place["names_lang"] = dict(names_lang)
    place["abbr"] = abbr


def place_reader(fin):
    prev_id = None
    for line in sys.stdin:
        place = json.loads(line)
        if prev_id and place["_id"] < prev_id:
            raise ValueError("standard input isn't sorted by geoid")
        prev_id = place["_id"]
        yield place


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("alternateNames")
    parser.add_argument("countryInfo")
    parser.add_argument("--format", type=str, default=ALL_COUNTRIES)
    args = parser.parse_args()

    if args.format not in [ALL_COUNTRIES, COUNTRY_INFO]:
        parser.error("invalid format: %r" % args.format)

    with open(args.countryInfo) as fin:
        country_info = CountryInfo(fin)

    logging.basicConfig(level=logging.ERROR)

    append_function = {
        ALL_COUNTRIES: append_alternate_names,
        COUNTRY_INFO: append_alternate_names_country
    }[args.format]

    with open(args.alternateNames) as fin:
        name_reader = NameReader(fin)
        for place in place_reader(sys.stdin):
            names = name_reader.read(place["_id"])
            logging.debug("names: %r", names)
            append_function(place, names, country_info)
            sys.stdout.write(json.dumps(place))
            sys.stdout.write("\n")

    return 0

if __name__ == "__main__":
    sys.exit(main())
