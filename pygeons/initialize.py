"""Initialize data structures.

Downloads approx. 500MB of data from geonames.org.
"""
import codecs
import csv
import contextlib
import io
import logging
import os
import os.path as P
import sqlite3
import zipfile

from typing import (
    IO,
    Iterator,
)

import marisa_trie  # type: ignore
import pySmartDL  # type: ignore
import smart_open  # type: ignore

import pygeons.db

_ENCODING = 'utf-8'
_CSV_PARAMS = dict(delimiter='\t', quotechar='', quoting=csv.QUOTE_NONE)


def init_countryinfo(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
CREATE TABLE countryinfo(
    iso TEXT PRIMARY_KEY,
    iso3 TEXT,
    iso_numeric TEXT,
    fips TEXT,
    country TEXT,
    capital TEXT,
    area NUMERIC,
    population NUMERIC,
    continent TEXT,
    tld TEXT,
    currency_code TEXT,
    currency_name TEXT,
    phone TEXT,
    postal_code_format TEXT,
    postal_code_regex TEXT,
    languages TEXT,
    geonameid NUMERIC,
    neighbors TEXT,
    equivalent_fips_code TEXT
)
""")

    url = 'http://download.geonames.org/export/dump/countryInfo.txt'
    lines = [line for line in smart_open.open(url) if not line.startswith('#')]
    buf = io.StringIO('\n'.join(lines))
    reader = csv.reader(buf, **_CSV_PARAMS)  # type: ignore
    command = (
        'INSERT INTO countryinfo VALUES '
        '(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    )
    for row in reader:
        if len(row) == 19:
            c.execute(command, row)

    c.close()
    conn.commit()


def init_geoname(db_path: str, fin: IO[str]) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
CREATE TABLE geoname(
    geonameid NUMERIC PRIMARY KEY,  -- integer id of record in geonames database
    name TEXT,              -- name of geographical point (utf8) varchar(200)
    asciiname TEXT,         -- name of geographical point in plain ascii characters
    alternatenames TEXT,    -- comma separated, ascii names automatically transliterated
    latitude NUMERIC,       -- latitude in decimal degrees (wgs84)
    longitude NUMERIC,      -- longitude in decimal degrees (wgs84)
    feature_class TEXT,     -- see http://www.geonames.org/export/codes.html, char(1)
    feature_code TEXT,      -- see http://www.geonames.org/export/codes.html, varchar(10)
    country_code TEXT,      -- ISO-3166 2-letter country code, 2 characters
    cc2 TEXT,               -- alternate country codes, comma separated
    admin1_code TEXT,       -- fipscode (subject to change to iso code)
    admin2_code TEXT,       -- code for the second administrative division
    admin3_code TEXT,       -- code for third level administrative division, varchar(20)
    admin4_code TEXT,       -- code for fourth level administrative division, varchar(20)
    population NUMERIC,     -- bigint (8 byte int)
    elevation NUMERIC,      -- in meters, integer
    dem NUMERIC,            -- digital elevation model, srtm3 or gtopo30
    timezone TEXT,          -- the iana timezone id (see file timeZone.txt) varchar(40)
    modification_date TEXT  -- date of last modification in yyyy-MM-dd format
);
""")

    insert_cmd = """
INSERT INTO geoname
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

    reader = csv.reader(fin, **_CSV_PARAMS)  # type: ignore
    for row in reader:

        if len(row) != 19:
            logging.error('bad row: %r', row)
        elif row[6] in ('A', 'P'):
            #
            # get rid of alternatenames, we have a separate table for that
            #
            row[3] = ''
            c.execute(insert_cmd, row)

    c.execute('CREATE INDEX geoname_name on geoname(name)')
    c.execute('CREATE INDEX geoname_asciiname on geoname(asciiname)')
    c.execute('CREATE INDEX geoname_feature_class on geoname(feature_class)')
    c.execute('CREATE INDEX geoname_feature_code on geoname(feature_code)')
    c.execute('CREATE INDEX geoname_country_code on geoname(country_code)')
    c.execute('CREATE INDEX geoname_country_feature on geoname(country_code, feature_code)')
    c.execute('CREATE INDEX geoname_admin1_code on geoname(country_code, admin1_code)')
    c.execute('CREATE INDEX geoname_admin2_code on geoname(country_code, admin2_code)')
    c.execute('CREATE INDEX geoname_admin3_code on geoname(country_code, admin3_code)')
    c.execute('CREATE INDEX geoname_admin4_code on geoname(country_code, admin4_code)')

    c.close()
    conn.commit()


def init_alternatename(db_path: str, fin: IO[str]) -> None:
    geonameids = set()

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for result in c.execute('SELECT geonameid FROM geoname'):
        geonameids.add(result[0])
    for result in c.execute('SELECT geonameid FROM countryinfo'):
        geonameids.add(result[0])

    c.execute("""
CREATE TABLE alternatename(
    alternateNameId NUMERIC PRIMARY KEY,    -- the id of this alternate name, int
    geonameid NUMERIC,          -- geonameId referring to id in table 'geoname', int
    isolanguage TEXT,           -- iso 639 language code 2- or 3-characters
    alternate_name TEXT,        -- alternate name or name variant, varchar(400)
    isPreferredName BOOLEAN,    -- if this alternate name is an official/preferred name
    isShortName BOOLEAN,        -- if this is a short name
    isColloquial BOOLEAN,       -- if this alternate name is a colloquial or slang term.
    isHistoric BOOLEAN,         -- if this alternate name was used in the past.
    fromPeriod TEXT,            -- from period when the name was used
    toPeriod TEXT               -- to period when the name was used
)""")

    insert_cmd = 'INSERT INTO alternatename VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'

    reader = csv.reader(fin, **_CSV_PARAMS)  # type: ignore
    for row in reader:
        geonameid = int(row[1])
        isolanguage = row[2]
        if geonameid in geonameids and isolanguage not in ('link', 'wkdt'):
            c.execute(insert_cmd, row)

    #
    # TODO: add our own alternate names below
    #

    c.execute('CREATE INDEX alternatename_geonameid on alternatename(geonameid)')
    c.execute('CREATE INDEX alternatename_alternate_name on alternatename(alternate_name)')

    c.close()
    conn.commit()


def init_postcode(db_path: str, fin: IO[str]) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
CREATE TABLE postcode(
    id NUMERIC PRIMARY KEY,
    country_code TEXT, -- iso country code, 2 characters
    postal_code TEXT,  -- varchar(20)
    place_name TEXT,   -- varchar(180)
    admin_name1 TEXT,  -- 1. order subdivision (state) varchar(100)
    admin_code1 TEXT,  -- 1. order subdivision (state) varchar(20)
    admin_name2 TEXT,  -- 2. order subdivision (county/province) varchar(100)
    admin_code2 TEXT,  -- 2. order subdivision (county/province) varchar(20)
    admin_name3 TEXT,  -- 3. order subdivision (community) varchar(100)
    admin_code3 TEXT,  -- 3. order subdivision (community) varchar(20)
    latitude TEXT,     -- estimated latitude (wgs84)
    longitude TEXT,    -- estimated longitude (wgs84)
    accuracy NUMERIC  -- accuracy of lat/lng from 1=estimated, 4=geonameid, 6=centroid of addresses or shape
)""")

    insert_cmd = 'INSERT INTO postcode VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'

    reader = csv.reader(fin, **_CSV_PARAMS)  # type: ignore
    for i, row in enumerate(reader):
        #
        # NB. the admin_ stuff is all denormalized.  Would have been much more
        # helpful if it consisted of geonameids so that it could be joined
        # onto the geoname table.
        #
        c.execute(insert_cmd, [i] + row)

    c.execute('CREATE INDEX postcode_country_code on postcode(country_code)')
    c.execute('CREATE INDEX postcode_postal_code on postcode(postal_code)')
    c.execute('CREATE INDEX postcode_place_name on postcode(place_name)')

    #
    # FIXME: what other indices do we need here?
    #

    c.close()

    conn.commit()


def build_trie(db_path: str, marisa_path: str) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    def record(feature_class, country_code, pk, alt_name_id=-1):
        #
        # See db.MARISA_FORMAT for the packing format of the record
        # Also https://docs.python.org/3/library/struct.html
        #
        return (feature_class.encode(_ENCODING), country_code.encode(_ENCODING), pk, alt_name_id)

    def g():
        command = (
            'SELECT G.geonameid, G.feature_class, G.country_code, alternateNameId, alternate_name '
            'FROM geoname G JOIN alternatename A ON G.geonameid = A.geonameid'
        )
        for r in c.execute(command):
            geonameid, feature_class, country_code, alt_name_id, alt_name = r
            yield alt_name.lower(), record(feature_class, country_code, geonameid, alt_name_id)

        #
        # canonical name and asciiname seem to be missing from the alternatename
        # table for most records, so we add them explicitly here.  Don't worry
        # about deduplicating for now.
        #
        command = 'SELECT geonameid, name, asciiname, feature_class, country_code FROM geoname'
        for (geonameid, name, asciiname, feature_class, country_code) in c.execute(command):
            rec = record(feature_class, country_code, geonameid)
            yield name.lower(), rec
            if asciiname != name:
                yield asciiname.lower(), rec

        command = 'SELECT id, country_code, place_name FROM postcode'
        for (pk, country_code, place_name) in c.execute(command):
            yield place_name.lower(), record('Z', country_code, pk)

    trie = marisa_trie.RecordTrie(pygeons.db.MARISA_FORMAT, g())
    trie.save(marisa_path)

    c.close()


@contextlib.contextmanager
def _unzip_temporary(url: str, member: str) -> Iterator[IO[str]]:
    dl = pySmartDL.SmartDL(url)
    dl.start()
    with zipfile.ZipFile(dl.get_dest()) as fin_zip:
        yield codecs.getreader(_ENCODING)(fin_zip.open(member))


def main():
    logging.basicConfig(level=logging.INFO)

    dbpath = P.join(pygeons.db.DEFAULT_SUBDIR, 'db.sqlite3')

    if P.isfile(dbpath):
        os.unlink(dbpath)
 
    init_countryinfo(dbpath)
 
    url = 'http://download.geonames.org/export/dump/allCountries.zip'
    with _unzip_temporary(url, 'allCountries.txt') as fin:
        init_geoname(dbpath, fin)
 
    url = 'http://download.geonames.org/export/dump/alternateNamesV2.zip'
    with _unzip_temporary(url, 'alternateNamesV2.txt') as fin:
        init_alternatename(dbpath, fin)
 
    url = 'http://download.geonames.org/export/zip/allCountries.zip'
    with _unzip_temporary(url, 'allCountries.txt') as fin:
        init_postcode(dbpath, fin)

    build_trie(dbpath, P.join(pygeons.db.DEFAULT_SUBDIR, pygeons.db.MARISA_FILENAME))


if __name__ == '__main__':
    main()
