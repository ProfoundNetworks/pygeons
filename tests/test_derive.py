#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
from __future__ import unicode_literals

import logging
import sys

import yaml
import os.path as P
from parameterizedtestcase import ParameterizedTestCase

import pygeons.derive
import pygeons.process

CURR_DIR = P.dirname(P.abspath(__file__))


def load_test_cases():
    with open(P.join(CURR_DIR, "test_derive.yml")) as fin:
        return [(x,) for x in yaml.full_load(fin)]


class DeriveNamesTest(ParameterizedTestCase):

    def setUp(self):
        self.maxDiff = None
        with open(P.join(CURR_DIR, "countries.json")) as fin:
            self.info = pygeons.process.CountryInfo(fin)

    @ParameterizedTestCase.parameterize(("test_case",), load_test_cases())
    def test(self, test_case):
        name = test_case.get("name", "")
        asciiname = test_case.get("asciiname", name)
        assert name or asciiname, "Test is broken!"

        country = test_case["countryCode"]
        alt_names = test_case.get("alternativenames", "")
        place = pygeons.derive.Place(name, asciiname, country, alt_names)

        expected = sorted(set(test_case["expected"]))
        derived = [x.text for x in pygeons.derive._derive_names(place, self.info)]
        logging.debug("expected: %s", ", ".join(expected))
        logging.debug("derived: %s", ", ".join(derived))
        self.assertEqual(expected, derived)


logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
