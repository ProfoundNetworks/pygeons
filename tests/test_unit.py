#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import unittest
import io
import logging
import os
import os.path as P
import math

import mock
from parameterizedtestcase import ParameterizedTestCase

import pygeons.pygeons as pygeons


class LoadConfigurationTest(unittest.TestCase):

    def setUp(self):
        os.environ.pop("PYGEON_CONFIG_PATH", None)

    @mock.patch("pygeons.pygeons.open")
    @mock.patch("pygeons.pygeons.P.isfile")
    def test_file_exists(self, mock_isfile, mock_open):
        mock_isfile.return_value = True
        mock_open.return_value = io.StringIO("""
host: foo
port: 1234
dbname: bar
auth_dbname: baz
username: homer
password: simpson
        """)
        setattr(mock_open, "__exit__", mock.MagicMock())

        cfg = pygeons._load_configuration()
        logging.info("cfg: %s", cfg)
        self.assertEquals(cfg.host, "foo")
        self.assertEquals(cfg.port, 1234)
        self.assertEquals(cfg.dbname, "bar")
        self.assertEquals(cfg.auth_dbname, "baz")
        self.assertEquals(cfg.username, "homer")
        self.assertEquals(cfg.password, "simpson")

    @mock.patch("pygeons.pygeons.P.isfile")
    def test_file_doesnt_exist(self, mock_isfile):
        mock_isfile.return_value = False
        cfg = pygeons._load_configuration()
        self.assertEquals(cfg.host, pygeons.DEFAULT_HOST)
        self.assertEquals(cfg.port, pygeons.DEFAULT_PORT)
        self.assertEquals(cfg.dbname, pygeons.DEFAULT_DBNAME)
        self.assertEquals(cfg.auth_dbname, pygeons.DEFAULT_AUTH_DBNAME)
        self.assertEquals(cfg.username, pygeons.DEFAULT_USERNAME)
        self.assertEquals(cfg.password, pygeons.DEFAULT_PASSWORD)

    @mock.patch("pygeons.pygeons.open")
    @mock.patch("pygeons.pygeons.P.isfile")
    def test_empty_config_file_should_not_crash(self, mock_isfile, mock_open):
        mock_isfile.return_value = True
        mock_open.return_value = io.StringIO("")
        setattr(mock_open, "__exit__", mock.MagicMock())

        cfg = pygeons._load_configuration()
        logging.info("cfg: %s", cfg)
        self.assertEquals(cfg.host, pygeons.DEFAULT_HOST)
        self.assertEquals(cfg.port, pygeons.DEFAULT_PORT)
        self.assertEquals(cfg.dbname, pygeons.DEFAULT_DBNAME)
        self.assertEquals(cfg.auth_dbname, pygeons.DEFAULT_AUTH_DBNAME)
        self.assertEquals(cfg.username, pygeons.DEFAULT_USERNAME)
        self.assertEquals(cfg.password, pygeons.DEFAULT_PASSWORD)

    @mock.patch("pygeons.pygeons.open")
    @mock.patch("pygeons.pygeons.P.isfile")
    def test_default_config(self, mock_isfile, mock_open):
        mock_isfile.return_value = True
        mock_open.return_value = io.StringIO("")
        setattr(mock_open, "__exit__", mock.MagicMock())

        pygeons._load_configuration()

        expected = P.expanduser("~/pygeons.yaml")
        mock_isfile.assert_called_with(expected)
        mock_open.assert_called_with(expected)

    @mock.patch("pygeons.pygeons.open")
    @mock.patch("pygeons.pygeons.P.isfile")
    def test_custom_config(self, mock_isfile, mock_open):
        os.environ["PYGEON_CONFIG_PATH"] = "/foo/bar/pygeons.yaml"
        mock_isfile.return_value = True
        mock_open.return_value = io.StringIO("")
        setattr(mock_open, "__exit__", mock.MagicMock())

        pygeons._load_configuration()

        mock_isfile.assert_called_with("/foo/bar/pygeons.yaml")
        mock_open.assert_called_with("/foo/bar/pygeons.yaml")


class ReconnectHelperTest(unittest.TestCase):

    @mock.patch("pymongo.MongoClient")
    def test_no_authentication(self, mock_client):
        pygeons.CONFIG = pygeons.Config()
        db = mock.MagicMock()
        client = mock.MagicMock()
        client["geonames"] = db
        mock_client.return_value = client

        ret_client, ret_db = pygeons._reconnect_helper()

        self.assertEqual(ret_client, client)
        mock_client.assert_called_with("localhost", 27017, connect=True)

        self.assertEqual(ret_db, client["geonames"])
        client["geonames"].authenticate.assert_not_called()

    @mock.patch("pymongo.MongoClient")
    def test_authentication(self, mock_client):
        pygeons.CONFIG = pygeons.Config(username="a", password="b",
                                        auth_dbname="c")
        db = mock.MagicMock()
        client = mock.MagicMock()
        client["geonames"] = db
        mock_client.return_value = client

        ret_client, ret_db = pygeons._reconnect_helper()

        self.assertEqual(ret_client, client)
        mock_client.assert_called_with("localhost", 27017, connect=True)
        ret_db.authenticate.assert_called_with("a", "b", source="c")

        self.assertEqual(ret_db, client["geonames"])

    @mock.patch("pymongo.MongoClient")
    def test_authentication_without_source(self, mock_client):
        pygeons.CONFIG = pygeons.Config(username="a", password="b")
        db = mock.MagicMock()
        client = mock.MagicMock()
        client["geonames"] = db
        mock_client.return_value = client

        ret_client, ret_db = pygeons._reconnect_helper()

        self.assertEqual(ret_client, client)
        mock_client.assert_called_with("localhost", 27017, connect=True)
        ret_db.authenticate.assert_called_with("a", "b", source="admin")

        self.assertEqual(ret_db, client["geonames"])


class GetVersionTest(unittest.TestCase):

    def setUp(self):
        self.old_db = pygeons.DB

        pygeons.DB = mock.MagicMock()
        pygeons.DB.util = mock.MagicMock()
        pygeons.DB.util.find_one = mock.MagicMock()
        pygeons.DB.util.find_one.return_value = {"value": "2016.11.22-01.23.45"}

    def tearDown(self):
        pygeons.DB = self.old_db

    def test_util_table_exists(self):
        version = pygeons.get_version()
        self.assertEqual(version.year, 2016)
        self.assertEqual(version.month, 11)
        self.assertEqual(version.day, 22)
        self.assertEqual(version.hour, 1)
        self.assertEqual(version.minute, 23)
        self.assertEqual(version.second, 45)


class CleanNonAlphaTest(ParameterizedTestCase):

    @ParameterizedTestCase.parameterize(("input_", "expected", "message"), [
        ("foo", "foo", "sanity check"),
        (" foo", "foo", "should strip leading space"),
        ("    foo", "foo", "should strip multiple leading spaces"),
        ("foo ", "foo", "should strip trailing space"),
        ("foo   ", "foo", "should strip multiple trailing spaces"),
        (" foo ", "foo", "should strip leading/trailing spaces"),
        (" 1foo ", "foo", "should strip leading space and digit"),
        (" превед ", "превед", "should handle unicode (Russian)"),
        (" おはよう 　", "おはよう", "should handle unicode (Japanese)"),
    ])
    def test(self, input_, expected, message):
        self.assertEqual(pygeons._clean_nonalpha(input_), expected)

    def test_multiple_trailing(self):
        self.assertEqual(pygeons._clean_nonalpha("x  "), "x")


class CscCleanParamsTest(unittest.TestCase):

    def test_apostrophe(self):
        city_in, state_in, country_in = "O'Fallon", "MO", "US"
        expected = {"city": "o'fallon", "state": "mo", "country": "US"}
        city_out, state_out, country_out, _ = pygeons._csc_clean_params(
            city_in, state_in, country_in
        )
        actual = {"city": city_out, "state": state_out, "country": country_out}
        self.assertEqual(expected, actual)

    def test_parentheses(self):
        city_in = "Buchen (Odenwald)"
        state_in = 'Baden-W\xfcrttemberg'
        country_in = "DE"
        _, _, _, alt_city = pygeons._csc_clean_params(city_in, state_in,
                                                      country_in)
        self.assertEqual(alt_city, ["odenwald"])

    def test_should_not_suggest_bad_alternative_names(self):
        city_in = "Buchen (1234)"
        state_in = 'Baden-W\xfcrttemberg'
        country_in = "DE"
        _, _, _, alt_city = pygeons._csc_clean_params(city_in, state_in,
                                                      country_in)
        self.assertEqual(alt_city, [])


class GeonamesCitiesDedupTest(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_sanity(self):
        cities = [
            {
                "name": "X", "admin1": "Y", "admin2": "YY",
                "countryCode": "Z", "featureCode": "PPL",
                "latitude": 0, "longitude": 0, "_id": 1
            },
            {
                "name": "X", "admin1": "Y", "admin2": "YY",
                "countryCode": "Z", "featureCode": "PPL",
                "latitude": 0, "longitude": 0, "_id": 2
            },
        ]
        self.assertEqual(len(pygeons._geonames_cities_dedup(cities)), 1)

    def test_should_favor_big_cities(self):
        cities = [
            {
                "name": "X", "admin1": "Y", "admin2": "YY", "_id": 2,
                "countryCode": "Z", "featureCode": "PPL", "population": 0,
                "latitude": 0, "longitude": 0
            },
            {
                "name": "X", "admin1": "Y", "admin2": "YY", "_id": 1,
                "countryCode": "Z", "featureCode": "PPL", "population": 99999,
                "latitude": 0, "longitude": 0
            },
        ]
        deduped = pygeons._geonames_cities_dedup(cities)
        self.assertEqual(1, deduped[0]["_id"])

    def test_should_remove_cities_near_each_other(self):
        cities = [
            {
                "name": "X", "admin1": "Y", "admin2": "YY", "_id": 2,
                "countryCode": "Z", "featureCode": "PPL", "population": 0,
                "latitude": 1, "longitude": 1
            },
            {
                "name": "X1", "admin1": "Y", "admin2": "YY", "_id": 1,
                "countryCode": "Z", "featureCode": "PPLX", "population": 1,
                "latitude": 1.001, "longitude": 1.001
            },
        ]
        deduped = pygeons._geonames_cities_dedup(cities)
        self.assertEqual([cities[1]], deduped)

    def test_should_not_remove_cities_far_from_each_other(self):
        cities = [
            {
                "name": "X", "admin1": "Y", "admin2": "YY", "_id": 3,
                "countryCode": "Z", "featureCode": "PPL", "population": 0,
                "latitude": 1, "longitude": 1
            },
            {
                "name": "X'", "admin1": "Y", "admin2": "YY", "_id": 2,
                "countryCode": "Z", "featureCode": "PPL", "population": 0,
                "latitude": 10.002, "longitude": 10.002
            },
            {
                "name": "X", "admin1": "Y", "admin2": "ZZ", "_id": 1,
                "countryCode": "Z", "featureCode": "PPLX", "population": 1,
                "latitude": 20.001, "longitude": 20.001
            },
        ]
        deduped = pygeons._geonames_cities_dedup(cities)
        key = lambda x: x["_id"]
        self.assertEqual(sorted(cities, key=key), sorted(deduped, key=key))


class ToRadianTest(ParameterizedTestCase):

    @ParameterizedTestCase.parameterize(("degrees", "radians"), [
        (0, 0),
        (30, math.pi/6),
        (45, math.pi/4),
        (60, math.pi/3),
        (90, math.pi/2)
    ])
    def test(self, degrees, radians):
        self.assertAlmostEqual(pygeons._to_radian(degrees), radians)


class HaversineDistTest(ParameterizedTestCase):

    @ParameterizedTestCase.parameterize(
        ("lat1", "lng1", "lat2", "lng2", "dist"), [
            # Distance of the Moscow Kremlin to itself is zero
            (55.7520, 37.6175, 55.7520, 37.6175, 0),
            # Kremlin to the Sydney Opera house
            (55.7520, 37.6175, -33.8568, 151.2153, 14496),
            (-33.8568, 151.2153, 55.7520, 37.6175, 14496),
            # Sydney to Auckland
            (-33.8568, 151.2153, -36.866670, 174.766670, 2156),
            (-36.866670, 174.766670, -33.8568, 151.2153, 2156),
            # Sydney Opera House to the Falkland Islands
            #
            # Seems to be broken. The distance is around 10000km.
            # Perhaps it's wrapping around the other side?
            #
            # (55.7520, 37.6175, -52.102430, -60.844510, 14976),
            # (-52.102430, -60.844510, 55.7520, 37.6175, 14976),
        ]
    )
    def test(self, lat1, lng1, lat2, lng2, dist):
        actual = pygeons._haversine_dist(lat1, lng1, lat2, lng2)
        self.assertAlmostEquals(dist, actual, 0)


class ClusterCitiesTest(unittest.TestCase):

    def test(self):
        cities = [{"_id": 1, "latitude": 0, "longitude": 0},
                  {"_id": 2, "latitude": 0, "longitude": 0}]
        expected = [
            [{"_id": 1, "latitude": 0, "longitude": 0},
             {"_id": 2, "latitude": 0, "longitude": 0}]
        ]
        self.assertEqual(expected, pygeons._cluster_cities(cities))
