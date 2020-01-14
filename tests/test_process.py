import unittest

import pygeons.process


class ParseRowTest(unittest.TestCase):

    def test(self):
        obj = pygeons.process._parse_row(["foo", 1], ["foo", "bar"], ["str", "int"])
        self.assertEqual(obj, {"foo": "foo", "bar": 1})

    def test_bad_type(self):
        with self.assertRaises(ValueError):
            pygeons.process._parse_row(["foo", 1], ["foo", "bar"], ["str", "baz"])

    def test_bad_len(self):
        with self.assertRaises(ValueError):
            pygeons.process._parse_row(["foo", 1, 2], ["foo", "bar"], ["str", "int"])
