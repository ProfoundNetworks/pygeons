#!/usr/bin/env python
"""Convert TSV rows to JSON lines."""
import csv
import json
import argparse
import sys
import logging


def parse_row(row, names, types):
    """Parse a TSV row into a dictionary."""
    if not (len(row) == len(names) == len(types)):
        raise ValueError("row, names, and types must of the same length")
    obj = {}
    for val, key, type_ in zip(row, names, types):
        if type_ == "int":
            obj[key] = int(val) if val else None
        elif type_ == "float":
            obj[key] = float(val) if val else None
        elif type_ == "str":
            obj[key] = val
        elif type_ == "skip":
            pass
        else:
            raise ValueError("unsupported type: %r" % type_)
    return obj


def get_admin_code(plc, kind):
    """Return the admin code for a place."""
    if kind == "ADM1":
        return ".".join([plc["countryCode"], plc["admin1"]])
    elif kind == "ADM2":
        return ".".join([plc["countryCode"], plc["admin1"], plc["admin2"]])
    else:
        raise ValueError("unexpected kind: %r", kind)


def adjust_fields(obj):
    """Adjust fields to conform to some existing business logic."""
    if "featureCode" in obj and obj["featureCode"].startswith("ADM1"):
        obj["admin1id"] = get_admin_code(obj, "ADM1")
    elif "featureCode" in obj and obj["featureCode"].startswith("ADM2"):
        obj["admin2id"] = get_admin_code(obj, "ADM2")
    if "languages" in obj:
        obj["languages"] = obj["languages"].split(",")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--field-names", nargs="+", type=str)
    parser.add_argument("--field-types", nargs="+", type=str)
    parser.add_argument("--loglevel", type=str, default=logging.INFO)
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    if not (args.field_names and args.field_types):
        parser.error("must specify field_names and field_types")
    elif len(args.field_names) != len(args.field_types):
        parser.error("field_names and field_types must be of the same length")

    reader = csv.reader(sys.stdin, delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        logging.debug(row)
        obj = parse_row(row, args.field_names, args.field_types)
        adjust_fields(obj)
        sys.stdout.write(json.dumps(obj))
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()


import unittest


class ParseRowTest(unittest.TestCase):

    def test(self):
        obj = parse_row(["foo", 1], ["foo", "bar"], ["str", "int"])
        self.assertEquals(obj, {"foo": "foo", "bar": 1})

    def test_bad_type(self):
        with self.assertRaises(ValueError):
            parse_row(["foo", 1], ["foo", "bar"], ["str", "baz"])

    def test_bad_len(self):
        with self.assertRaises(ValueError):
            parse_row(["foo", 1, 2], ["foo", "bar"], ["str", "int"])
