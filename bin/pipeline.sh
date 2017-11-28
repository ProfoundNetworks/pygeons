#
# Common processing for administrative and city instances.
# Appends alternative (non-English, abbreviations, etc.) and derived names.
# Reads TSV (in allCountries.txt format) from stdin, outputs JSON to stdout.
#
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

python $script_dir/tsv2json.py \
    --field-names _id name asciiname alternatenames latitude longitude\
        featureClass featureCode countryCode cc2 admin1 admin2 admin3 \
        admin4 population elevation dem timezone modificationDate \
    --field-types int str str skip float float str str str skip str str skip \
        skip int skip skip skip skip | \
python $script_dir/append_alternatenames.py alternateNames.tsv countries.json | \
python $script_dir/derive_names.py countries.json
