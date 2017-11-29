"""Split JSON files by their country codes."""
import argparse
import json
import os
import os.path as P


def _split(infile, output_dir):
    fouts = {}
    with open(infile) as fin:
        for line in fin:
            country_code = json.loads(line)['countryCode']
            try:
                fout = fouts[country_code]
            except KeyError:
                suffix = P.basename(infile)
                outfile = P.join(output_dir, country_code + '.' + suffix)
                fout = fouts[country_code] = open(outfile, 'w')
            fout.write(line)
    for fout in fouts.values():
        fout.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('output_dir')
    args = parser.parse_args()

    if not P.isdir(args.output_dir):
        os.mkdir(args.output_dir)
    _split(args.input_file, args.output_dir)


if __name__ == '__main__':
    main()
