#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
import logging
import os.path as P
import unittest

import yaml
from parameterizedtestcase import ParameterizedTestCase

import pygeons.api
import pygeons.legacy


class CscExistsTest(unittest.TestCase):

    def au_test(self):
        assert 'sydney' in pygeons.api.Country('au').states['new south wales'].cities

    def au_abbrev_test(self):
        assert 'sydney' in pygeons.api.Country('au').states['nsw'].cities

    def au_false_test(self):
        assert 'sydney' not in pygeons.api.Country('au').states['victoria'].cities

    def us_test(self):
        assert 'bellevue' in pygeons.api.Country('US').states['washington'].cities

    def us_abbrev_test(self):
        assert 'bellevue' in pygeons.api.Country('US').states['WA'].cities

    def us_false_test(self):
        assert 'petrozavodsk' in pygeons.api.Country('US').states['WA'].cities

    def gb_admin1_test(self):
        assert 'london' in pygeons.api.Country('GB').states['England'].cities

    def gb_admin2_test(self):
        assert 'london' in pygeons.api.Country('GB').states['greater london'].cities

    def jp_admin1_test(self):
        assert 'sapporo' in pygeons.api.Country('JP').states['hokkaido'].cities

    def jp_admin1_ja_test(self):
        assert '札幌' in pygeons.api.Country('JP').states['北海道'].cities


class CountryToIsoTest(ParameterizedTestCase):

    @ParameterizedTestCase.parameterize(("input_", "expected"), [
        ("united states", "US"),
        ("us", "US"),
    ])
    def test(self, input_, expected):
        assert pygeons.api.Country(input_).iso == expected

    def test_empty_name(self):
        with self.assertRaises(ValueError):
            assert pygeons.api.Country('')

    def test_nonexisting_name(self):
        with self.assertRaises(ValueError):
            assert pygeons.api.Country('Kraplakistan')

    def test_nonenglish_name(self):
        assert pygeons.api.Country("日本").iso == 'JP'


#
# FIXME: parameterize this test
#
class NormalizeCountryTest(unittest.TestCase):

    def test_australia1(self):
        self.assertEqual(pygeons.legacy.norm_country("AU"), "Australia")

    def test_australia2(self):
        self.assertEqual(pygeons.legacy.norm_country("AUS"), "Australia")

    def test_australia3(self):
        self.assertEqual(pygeons.legacy.norm_country("australia"), "Australia")

    def test_uk1(self):
        self.assertEqual(pygeons.legacy.norm_country("UK"), "United Kingdom")

    def test_uk2(self):
        self.assertEqual(pygeons.legacy.norm_country("GB"), "United Kingdom")

    def test_uk3(self):
        self.assertEqual(pygeons.legacy.norm_country("GBR"), "United Kingdom")

    def test_uk4(self):
        self.assertEqual(pygeons.legacy.norm_country("Great Britain"), "United Kingdom")

    def test_uk5(self):
        self.assertEqual(pygeons.legacy.norm_country("united kingdom"), "United Kingdom")

    def test_nz1(self):
        self.assertEqual(pygeons.legacy.norm_country("NZ"), "New Zealand")

    def test_nz2(self):
        self.assertEqual(pygeons.legacy.norm_country("NZL"), "New Zealand")

    def test_nz3(self):
        self.assertEqual(pygeons.legacy.norm_country("new zealand"), "New Zealand")

    def test_us1(self):
        self.assertEqual(pygeons.legacy.norm_country("US"), "United States")

    def test_us2(self):
        self.assertEqual(pygeons.legacy.norm_country("U.S."), "United States")

    def test_us3(self):
        self.assertEqual(pygeons.legacy.norm_country("USA"), "United States")

    def test_us4(self):
        self.assertEqual(pygeons.legacy.norm_country("U.S.A"), "United States")

    def test_us5(self):
        self.assertEqual(pygeons.legacy.norm_country("united states"), "United States")

    def test_us6(self):
        self.assertEqual(pygeons.legacy.norm_country("united states of america"), "United States")

    def test_de_en(self):
        self.assertEqual(pygeons.legacy.norm_country("germany"), "Germany")

    def test_de_de(self):
        self.assertEqual(pygeons.legacy.norm_country("deutschland", "de"), "Germany")

    def test_br_en(self):
        self.assertEqual(pygeons.legacy.norm_country("brazil"), "Brazil")

    def test_br_pt(self):
        self.assertEqual(pygeons.legacy.norm_country("brasil", "pt"), "Brazil")

    def test_br_pt_period(self):
        self.assertEqual(pygeons.legacy.norm_country("brasil.", "pt"), "Brazil")

    def test_mx_en(self):
        self.assertEqual(pygeons.legacy.norm_country("mexico"), "Mexico")

    def test_mx_es(self):
        self.assertEqual(pygeons.legacy.norm_country(u"república mejicana", "es"), "Mexico")
        self.assertEqual(pygeons.legacy.norm_country(u"méjico", "es"), "Mexico")
        self.assertEqual(pygeons.legacy.norm_country(u"méxico", "es"), "Mexico")


class NormalizeCityTest(unittest.TestCase):
    def test_texas1(self):
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "US", "TX"), "Texas")

    def test_texas2(self):
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "US", "texas"), "Texas")

    def test_nsw1(self):
        exp = "State of New South Wales"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "AU", "nsw"), exp)

    def test_nsw2(self):
        exp = "State of New South Wales"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "AU", "NSW"), exp)

    def test_nsw3(self):
        exp = "State of New South Wales"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "AU", "NEW SOUTH WALES"), exp)

    def test_de_en(self):
        expected = "Munich"
        raw = "munich"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.CITY, "DE", raw), expected)

    def test_de_de(self):
        expected = "Munich"
        raw = u"München"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.CITY, "DE", raw, "de"), expected)

    def test_de_en2(self):
        exp = u'Murnau am Staffelsee'
        raw = u'MURNAU AM STAFFELSEE'
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.CITY, "DE", raw), exp)

    def test_mx(self):
        exp = u"Adolfo Ruiz Cortines"
        raw = u"ADOLFO RUIZ CORTINES"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.CITY, "MX", raw), exp)

    def test_mx_mexico(self):
        #
        # There are several cities called u"M\xd9xico" in the database,
        # but only one of them is known as "Mexico City".
        # TODO: is this a bug with the DB? How to deal with this ambiguity?
        #
        # Currently, we have a postprocessing method in the Mexican address
        # parser resolve the ambiguity.
        #
        exp = u"Mexico City"
        raw = u"M\xc9XICO"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.CITY, "MX", raw, "ES"), exp)


#
# FIXME: parameterize these tests
#
class NormalizeStateTest(unittest.TestCase):

    def test_us_ct(self):
        exp = u"Connecticut"
        raw = "CT"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "US", raw), exp)

    def test_us_fl(self):
        exp = u"Florida"
        raw = "fl"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "US", raw), exp)

    def test_de_en(self):
        expected = u"Free and Hanseatic City of Hamburg"
        raw = u"Free and Hanseatic City of Hamburg"
        self.assertEqual(expected, pygeons.legacy.norm(pygeons.legacy.ADM1, "DE", raw))

    def test_de_de(self):
        expected = u"Free and Hanseatic City of Hamburg"
        raw = u"freie hansestadt hamburg"
        self.assertEqual(expected, pygeons.legacy.norm(pygeons.legacy.ADM1, "DE", raw, "de"))

    def test_de_en2(self):
        exp = u"Weissensee Bezirk"
        raw = u"Weissensee Bezirk"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM2, "DE", raw), exp)

    def test_de_de2(self):
        exp = u"Weissensee Bezirk"
        raw = u"berlin-Wei\u00dfensee"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM2, "DE", raw, "de"), exp)

    def test_br_en1(self):
        exp = u"São Paulo"
        raw = "SP"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "BR", raw), exp)

    def test_br_en2(self):
        exp = u"São Paulo"
        raw = "SAO PAULO"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "BR", raw), exp)

    def test_br_pt1(self):
        exp = u"São Paulo"
        raw = "SP"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "BR", raw, "pt"), exp)

    def test_br_pt2(self):
        exp = u"São Paulo"
        raw = u"Sao Paulo"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "BR", raw, "pt"), exp)

    def test_mx_en(self):
        exp = u"Estado de Tabasco"
        raw = u"TABASCO"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "MX", raw), exp)

    def test_mx_en2(self):
        exp = u"Estado de Tabasco"
        raw = u"TAB"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM1, "MX", raw), exp)

    def test_mx_en3(self):
        exp = u"Nicolás Romero"
        raw = u"NICOLAS ROMERO"
        self.assertEqual(pygeons.legacy.norm(pygeons.legacy.ADM2, "MX", raw), exp)


class CscFindTest(unittest.TestCase):

    def test_unique_city_state_country(self):
        cities = pygeons.legacy.csc_find("Sydney", "NSW", "AU")
        expected = [2147714]
        actual = [city.geonameid for city in cities]
        self.assertEqual(expected, actual)

    def test_unique_city_country(self):
        cities = pygeons.legacy.csc_find("Sydney", None, "AU")
        expected = [2147714]
        actual = [city.geonameid for city in cities]
        self.assertEqual(expected, actual)

    def test_unique_city_state(self):
        cities = pygeons.legacy.csc_find("Sydney", "NSW", None)
        expected = [2147714]
        actual = [city.geonameid for city in cities]
        self.assertEqual(expected, actual)

    def test_multiple_city(self):
        cities = pygeons.legacy.csc_find("Sydney", None, None)
        expected = [950661, 950662, 2134763, 2147714, 4174663, 5062142, 6354908]
        actual = [city.geonameid for city in cities]
        self.assertEqual(set(expected), set(actual))

    def test_unique_city(self):
        cities = pygeons.legacy.csc_find("Chelyabinsk", None, None)
        expected = [1508291]
        actual = [city.geonameid for city in cities]
        self.assertEqual(expected, actual)


def load_test_cases():
    curr_dir = P.dirname(P.abspath(__file__))
    with open(P.join(curr_dir, "csc_scrub_test_data.yml")) as fin:
        data = yaml.full_load(fin)
    return data


def get(csc_result, key):
    if not csc_result:
        return None
    elif key == "city":
        return csc_result["result"].name
    elif key == "gnid":
        return csc_result["result"].geonameid
    elif key == "cc":
        return csc_result["result"].country_code
    return csc_result.get(key)


class CscScrubTest(ParameterizedTestCase):
    @ParameterizedTestCase.parameterize(("desc", "input_", "expected"), [
        (d["desc"], d["input"], d["expected"]) for d in load_test_cases()
    ])
    def test(self, desc, input_, expected):
        csc_result = pygeons.legacy.csc_scrub(
            input_.get("city"),
            input_.get("state"),
            input_.get("cc"),
        )
        if expected:
            actual = dict([(key, get(csc_result, key)) for key in expected])
        else:
            actual = csc_result
        self.assertEqual(expected, actual)

    def test_coal_city(self):
        actual = pygeons.legacy.csc_scrub("Coal City", "IL", "US")
        self.assertEqual(actual["result"]["_id"], 4888270)

    def test_coal_township(self):
        actual = pygeons.legacy.csc_scrub("Coal Township", "IL", "US")
        self.assertEqual(actual["result"]["_id"], 4888270)

    def test_should_derive_state_and_country(self):
        scrub = pygeons.legacy.csc_scrub("St. Petersburg", None, None)
        expected = {"countryCode": "RU", "st_status": "D", "cc_status": "D"}
        actual = {
            "countryCode": scrub["result"].country_code,
            "cc_status": scrub["cc_status"],
            "st_status": scrub["st_status"],
        }
        self.assertEqual(expected, actual)

    def test_should_derive_country_given_state(self):
        scrub = pygeons.legacy.csc_scrub("St. Petersburg", "FL", None)
        expected = {"countryCode": "US", "st_status": "O", "cc_status": "D"}
        actual = {
            "countryCode": scrub["result"].country_code,
            "cc_status": scrub["cc_status"],
            "st_status": scrub["st_status"],
        }
        self.assertEqual(expected, actual)

    def test_should_derive_state_given_country(self):
        scrub = pygeons.legacy.csc_scrub("St. Petersburg", None, "US")
        expected = {"countryCode": "US", "st_status": "D", "cc_status": "O"}
        actual = {
            "countryCode": scrub["result"].country_code,
            "cc_status": scrub["cc_status"],
            "st_status": scrub["st_status"],
        }
        self.assertEqual(expected, actual)

    def test_should_correct_state_given_country(self):
        scrub = pygeons.legacy.csc_scrub("St. Petersburg", "TX", "US")
        expected = {"admin1": "Florida", "st_status": "M", "cc_status": "O"}
        actual = {
            "admin1": scrub["result"].admin1.name,
            "cc_status": scrub["cc_status"],
            "st_status": scrub["st_status"],
        }
        self.assertEqual(expected, actual)

    def test_should_correct_state_given_country2(self):
        scrub = pygeons.legacy.csc_scrub("St. Petersburg", "TX", "RU")
        expected = {
            "admin1": "Sankt-Peterburg", "st_status": "M", "cc_status": "O"
        }
        actual = {
            "admin1": scrub["result"].admin1.name,
            "cc_status": scrub["cc_status"],
            "st_status": scrub["st_status"],
        }
        self.assertEqual(expected, actual)

    def test_should_correct_state_and_country(self):
        scrub = pygeons.legacy.csc_scrub("St. Petersburg", "NSW", "AU")
        expected = {
            "admin1": "Sankt-Peterburg", "st_status": "M", "cc_status": "M"
        }
        actual = {
            "admin1": scrub["result"].admin1.name,
            "cc_status": scrub["cc_status"],
            "st_status": scrub["st_status"],
        }
        self.assertEqual(expected, actual)

    def test_should_work_with_japanese_cities(self):
        scrub = pygeons.legacy.csc_scrub("北九州市", "福岡県", "JP")
        expected = {"st_status": pygeons.legacy.SCRUB_OK, "cc_status": pygeons.legacy.SCRUB_OK}
        actual = {x: scrub[x] for x in expected}
        self.assertEqual(expected, actual)

    def test_should_accept_admin2_as_city(self):
        scrub = pygeons.legacy.csc_scrub("港区", "東京都", "JP")
        self.assertIsNotNone(scrub)
        expected = {"st_status": pygeons.legacy.SCRUB_OK, "cc_status": pygeons.legacy.SCRUB_OK}
        actual = {x: scrub[x] for x in expected}
        self.assertEqual(expected, actual)


class IsStateTest(unittest.TestCase):

    def test_should_work_with_nonenglish_state_name(self):
        result = pygeons.legacy.is_state("福岡県", "JP")
        self.assertTrue(result)

    def test_should_work_with_nonenglish_country_name(self):
        result = pygeons.legacy.is_state("福岡県", "日本")
        self.assertTrue(result)


class CscListTest(unittest.TestCase):

    def test_get_city_state_country(self):
        cities = pygeons.api.csc_list("Sydney", "NSW", "AU")
        expected_ids = [2147714]
        actual_ids = [city.geonameid for city in cities]
        self.assertEqual(expected_ids, actual_ids)

    def test_get_city_country(self):
        cities = pygeons.api.csc_list("Sydney", None, "AU")
        expected_ids = [2147714]
        actual_ids = [city.geonameid for city in cities]
        self.assertEqual(expected_ids, actual_ids)

    def test_get_city(self):
        cities = pygeons.api.csc_list("Sydney", None, None)
        expected_ids = [950661, 950662, 2134763, 2147714, 4174663, 5062142, 6160752, 6354908]
        actual_ids = [city.geonameid for city in cities]
        self.assertEqual(sorted(expected_ids), sorted(actual_ids))

    def test_city_and_state_cannot_both_be_empty(self):
        with self.assertRaises(ValueError):
            pygeons.api.csc_list(None, None, "AU")


def load_city_data(filename):
    curr_dir = P.dirname(P.abspath(__file__))
    with open(P.join(curr_dir, filename)) as fin:
        data = yaml.full_load(fin)
    return [(d["name"], d["country"], d["geoid"]) for d in data]


class NoStateTest(ParameterizedTestCase):
    @ParameterizedTestCase.parameterize(
        ("name", "ccode", "expected"),
        load_city_data("millionniki.yml"),
    )
    def test_can_scrub_large_city_without_state(self, name, ccode, expected):
        scrubbed = pygeons.legacy.csc_scrub(name, None, ccode)
        logging.info(scrubbed)
        actual = scrubbed["result"].geonameid if scrubbed else None
        self.assertEqual(expected, actual)

    @ParameterizedTestCase.parameterize(
        ("name", "ccode", "expected"),
        load_city_data("capitals.yml"),
    )
    def test_can_scrub_capital_city_without_state(self, name, ccode, expected):
        scrubbed = pygeons.legacy.csc_scrub(name, None, ccode)
        logging.info(scrubbed)
        actual = scrubbed["result"].geonameid if scrubbed else None
        self.assertEqual(expected, actual)

    def test_sao_paulo(self):
        scrubbed = pygeons.legacy.csc_scrub("Sao Paulo", None, "BR")
        logging.info(scrubbed)
        actual = scrubbed["result"].geonameid if scrubbed else None
        self.assertEqual(3448439, actual)

    def test_washington_dc(self):
        scrubbed = pygeons.legacy.csc_scrub("Washington, D.C.", None, "US")
        logging.info(scrubbed)
        actual = scrubbed["result"].geonameid if scrubbed else None
        self.assertEqual(4140963, actual)

    def test_istanbul(self):
        scrubbed = pygeons.legacy.csc_scrub("İstanbul", None, "TR")
        logging.info(scrubbed)
        actual = scrubbed["result"].geonameid if scrubbed else None
        self.assertEqual(745044, actual)

    def test_istanbul_ascii(self):
        scrubbed = pygeons.legacy.csc_scrub("Istanbul", None, "TR")
        logging.info(scrubbed)
        actual = scrubbed["result"].geonameid if scrubbed else None
        self.assertEqual(745044, actual)


class IncorrectStateTest(ParameterizedTestCase):
    @ParameterizedTestCase.parameterize(
        ("city", "state", "ccode", "expected"),
        [
            ("kowloon", "kowloon", "HK", 1819609),
            ("napanee", "quebec", "CA", 5965812),
            ("paris", "idf", "FR", 2988507),
            ("torino", "to", "IT", 3165524),
        ]
    )
    def test(self, city, state, ccode, expected):
        scrubbed = pygeons.legacy.csc_scrub(city, state, ccode)
        logging.info(scrubbed)
        actual = scrubbed["result"].geonameid if scrubbed else None
        self.assertEqual(expected, actual)


class ApolloValueErrorTest(ParameterizedTestCase):

    @ParameterizedTestCase.parameterize(("city", "state", "country"), [
        ('Salta (4400)', 'Salta', 'AR'),
        ('Puerto Madero Buenos Aires (1107)', 'C.F.', 'AR'),
        ('Buenos Aires, (1408)', 'C.f.', 'AR'),
        ('San Luis (5700)', 'San Luis', 'AR'),
        ('Fresnedillas de la Oliva. (28214)', 'Comunidad de Madrid', 'ES'),
        ('Saint Quentin (02)', 'Picardie', 'FR'),
        ('Paris 11 (75)', 'Île-de-France', 'FR'),
        ('Grand Sud Seine & Marne (77) ET Nord Loiret (45)', 'Île-de-France', 'FR'),  # NOQA
        ('Lunel (34)', 'Languedoc-Roussillon', 'FR'),
        ('Neuwied OT Irlich (56567)', 'Rheinland-Pfalz', 'DE'),
        ('Lermoos Tel:+43 (5673) 20242', 'Tirol', 'AT'),
        ('Hermagor Tel.: (+43) 06502177000', 'Kärnten', 'AT'),
        ('مكة المكرمة الراشدية - الشرائع مخطط رقم (4)-', 'Makkah Province', 'SA'),  # NOQA
        ('Iban Kalan (275)', 'Punjab', 'IN'),
        ('Sialkot (51310)', 'Punjab', 'PK'),
        ('Bhati (286)', 'Himachal Pradesh', 'IN'),
        ('Sajooma (14)', 'Haryana', 'IN'),
        ('Deoban (44)', 'Haryana', 'IN'),
        ('Saini Majra (271)', 'Punjab', 'IN'),
        ('Kotla (237)', 'Punjab', 'IN'),
        ('Phnom Penh (078400233)', 'Phnom Penh', 'KH'),
        ('Kazhakuttom (695582)', 'Kerala', 'IN'),
        ('Las Flores (7200)', 'Buenos Aires', 'AR'),
        ('Maregaon (1)', 'Maharashtra', 'IN'),
        ('Kandamathan ( 6 )', 'Tamil Nadu', 'IN'),
        ('Edaicheruvai ( 62)', 'Tamil Nadu', 'IN'),
        ('Kodangudi ( 79 )', 'Tamil Nadu', 'IN'),
        ('Rokar (2)', 'Svay Rieng Province', 'KH')
    ])
    def test_should_not_raise_value_error(self, city, state, country):
        pygeons.legacy.csc_scrub(city, state, country)
