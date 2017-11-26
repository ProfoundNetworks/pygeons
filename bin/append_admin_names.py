"""Append the admin1names and admin2names lists to each row."""
import sys
import argparse
import logging
import collections
import json

Admin = collections.namedtuple("Admin", ["geoid", "code", "name", "names"])

HISTORICAL = ["ADM1H", "ADM2H", "ADMDH"]


def get_admin_code(plc, kind):
    """Return the admin code for a place."""
    if kind == "ADM1":
        return ".".join([plc["countryCode"], plc["admin1"]])
    elif kind == "ADM2":
        return ".".join([plc["countryCode"], plc["admin1"], plc["admin2"]])
    else:
        raise ValueError("unexpected kind: %r", kind)


def get_alternate_names(plc):
    if plc["featureCode"].startswith("ADM1"):
        return plc["admin1names"]
    elif plc["featureCode"].startswith("ADM2"):
        return plc["admin2names"]
    raise ValueError("do not know how to handle featureCode: %r",
                     plc["featureCode"])


def read_names(fin):
    """Read the file and return a mapping of admin code to names."""
    by_code = {}
    for line in fin:
        place = json.loads(line)
        geoid = place["_id"]
        feature_code = place["featureCode"]
        name = place["name"]
        asciiname = place["asciiname"]

        if feature_code in HISTORICAL:
            #
            # Ignore historical names because they conflict with current names.
            # e.g. GB.ENG has a historical ADM1 name of "Britannia Superior",
            # which isn't what we want to map to GB.ENG here.
            #
            continue

        admin_code = get_admin_code(place, place["featureCode"])

        alternative_names = get_alternate_names(place)
        names = alternative_names + [name, asciiname]
        names = sorted(set([x.lower() for x in names]))
        by_code[admin_code] = Admin(geoid, admin_code, name, names)
    return by_code


def transform_obj(obj, admin1, admin2):
    """Append admin1names/admin2names, convert admin codes to names."""
    admin1code = get_admin_code(obj, "ADM1")
    admin2code = get_admin_code(obj, "ADM2")

    if admin1code:
        try:
            place = admin1[admin1code]
        except KeyError:
            logging.info("unknown admin1 code: %r", admin1code)
            obj["admin1names"] = []
        else:
            obj["admin1"] = place.name
            obj["admin1names"] = place.names

    if admin2code and admin2:
        try:
            place = admin2[admin2code]
        except KeyError:
            logging.info("unknown admin2 code: %r", admin2code)
            obj["admin2names"] = []
        else:
            obj["admin2"] = place.name
            obj["admin2names"] = place.names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("allAdmin1")
    parser.add_argument("--admin2", type=str, default=None)
    parser.add_argument("--loglevel", type=str, default=logging.ERROR)
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    with open(args.allAdmin1) as fin:
        admin1 = read_names(fin)

    if args.admin2:
        with open(args.admin2) as fin:
            admin2 = read_names(fin)
    else:
        admin2 = {}

    for line in sys.stdin:
        try:
            obj = json.loads(line)
        except ValueError:
            logging.error("cannot decode JSON from line")
            logging.error(line)
            raise
        transform_obj(obj, admin1, admin2)
        sys.stdout.write(json.dumps(obj))
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
