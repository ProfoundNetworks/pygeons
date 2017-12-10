#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2013
#
from __future__ import unicode_literals
import unittest
import io

import pygeons.process


class CountryInfoTest(unittest.TestCase):

    def test_should_report_languages_correctly(self):
        buf = io.StringIO("""{"country": "Switzerland", "languages": \
["de-CH", "fr-CH", "it-CH", "rm"], "iso3": "CHE", "iso": "CH", "names": [], \
"capital": "Berne", "_id": 2658434, "population": 7581000}""")
        cinfo = pygeons.process.CountryInfo(buf)
        self.assertEqual(cinfo.languages_spoken_in("CH"),
                         ["de", "fr", "it", "rm"])

    def test_should_report_iso6391_languages_only(self):
        #
        # These are the main languages of the world.  There are less than 200.
        #
        buf = io.StringIO("""{"name":"Russia","languages":["ru","tt","xal",\
"cau","ady","kv","ce","tyv","cv","udm","tut","mns","bua","myv","mdf","chm",\
"ba","inh","tut","kbd","krc","ava","sah","nog"],"iso3":"RUS","fips":"RS",\
"capital":"Moscow","iso":"RU","_id":2017370,"population":140702000}""")
        cinfo = pygeons.process.CountryInfo(buf)
        self.assertEqual(cinfo.languages_spoken_in("RU"),
                         ["ru", "tt", "kv", "ce", "cv", "ba"])


class AppendAlternateNamesCountry(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_should_append_only_relevant_languages(self):
        altnames_buf = io.StringIO("""\
1226413\t2658434\tde\tSchweizerische Eidgenossenschaft
1226414\t2658434\tfr\tConfédération Suisse
1226415\t2658434\tit\tConfederazione Svizzera
1226416\t2658434\t  \tSchweizg
1226417\t2658434\t  \tSvizzera
1226418\t2658434\t  \tHelvetia
1226419\t2658434\t  \tSwiss Confederation
1226420\t2658434\t  \tConfederatio Helvetica g
1226421\t2658434\t  \tSwitzerland
1226422\t2658434\t  \tSchweizerische Eidgenossenschaft
1226423\t2658434\t  \tSchwiz
1226424\t2658434\t  \tSuisse
1558461\t2658434\taf\tSwitserland
1558464\t2658434\tbg\tШвейцария
1558466\t2658434\tca\tSuïssa
1558467\t2658434\tcs\tŠvýcarsko
1558468\t2658434\tcy\tY Swistir
1558469\t2658434\tda\tSchweizg
1558470\t2658434\tde\tSchweiz
1558472\t2658434\tel\tΕλβετία
1558473\t2658434\ten\tSwitzerland
1558474\t2658434\teo\tSvisujog
1558475\t2658434\tes\tSuiza
1558476\t2658434\tet\tŠveits
1558477\t2658434\teu\tSuitza
1558479\t2658434\tfi\tSveitsig
1558480\t2658434\tfo\tSveis
1558481\t2658434\tfr\tSuisse
1558482\t2658434\tga\tAn Eilvéis
1558485\t2658434\thr\tŠvicarska
1558486\t2658434\thu\tSvájc
1558487\t2658434\thy\tՇվեյցարիա
1558488\t2658434\tid\tSwiss
1558489\t2658434\tis\tSviss
1558490\t2658434\tit\tSvizzera
1558491\t2658434\tja\tスイス
1558496\t2658434\tlt\tŠveicarija
1558497\t2658434\tlv\tŠveice
1558498\t2658434\tmk\tШвајцарија
1558499\t2658434\tms\tSwitzerland
1558500\t2658434\tmt\tSvizzera
1558501\t2658434\tnb\tSveits
1558502\t2658434\tnl\tZwitserland
1558503\t2658434\tnn\tSveits
1558504\t2658434\tpl\tSzwajcaria
1558506\t2658434\tpt\tSuíça
1558508\t2658434\tru\tШвейцария
1558509\t2658434\tsk\tŠvajčiarsko
1558510\t2658434\tsl\tŠvica
1558511\t2658434\tso\tSwiiserlaand
1558512\t2658434\tsq\tZvicër
1558513\t2658434\tsr\tШвајцарска
1558514\t2658434\tsv\tSchweizg
1558515\t2658434\tsw\tUswisi
1558519\t2658434\tuk\tШвейцарія
1558520\t2658434\tvi\tThụy Sĩg
2419881\t2658434\tbe\tШвейцарыя
2419884\t2658434\tgl\tSuíza
""")
        reader = pygeons.process.NameReader(altnames_buf)
        alt_names = reader.read(2658434)
        cinfo_buf = io.StringIO("""{"country": "Switzerland", "languages": \
["de-CH", "fr-CH", "it-CH", "rm"], "iso3": "CHE", "iso": "CH", "names": [], \
"capital": "Berne", "_id": 2658434, "population": 7581000}""")
        cinfo = pygeons.process.CountryInfo(cinfo_buf)

        switzerland = {"iso": "CH", "iso3": "CHE", "_id": 2658434,
                       "name": "Switzerland"}
        pygeons.process._append_alt_names_country(switzerland, alt_names, cinfo)

        expected = {
            "iso": "CH", "iso3": "CHE", "_id": 2658434, "name": "Switzerland",
            "names": sorted(
                ["ch", "che", "schweizerische eidgenossenschaft", "schweiz",
                 "confédération suisse", "suisse",
                 "confederazione svizzera", "svizzera", "switzerland"]
            ),
            "names_lang": {
                "en": ["ch", "che", "switzerland"],
                "de": ["schweiz", "schweizerische eidgenossenschaft"],
                "fr": ["confédération suisse", "suisse"],
                "it": ["confederazione svizzera", "svizzera"]
            },
            "abbr": ["ch", "che"],
        }
        self.assertEqual(switzerland, expected)

    def test_should_append_abbreviations_and_iso_codes(self):
        altnames_buf = io.StringIO("""\
1564136	6252001	es	Estados Unidos	1	1
1564134	6252001	en	United States		1
2428385	6252001	en	America
2428563	6252001	en	United States of America	1
1564142	6252001	fr	États-Unis	1
7297444	6252001	abbr	U.S.
""")
        reader = pygeons.process.NameReader(altnames_buf)
        alt_names = reader.read(6252001)

        cinfo_buf = io.StringIO("""{"name":"United States","languages":\
["en-US","es-US","haw","fr"],"iso3":"USA","fips":"US","capital":"Washington",\
"iso":"US","_id":6252001,"population":310232863}""")
        cinfo = pygeons.process.CountryInfo(cinfo_buf)

        theus = {"iso": "US", "_id": 6252001, "name": "United States",
                 "iso3": "USA"}
        pygeons.process._append_alt_names_country(theus, alt_names, cinfo)

        expected = {
            "iso": "US", "iso3": "USA", "_id": 6252001, "iso3": "USA",
            "name": "United States",
            "names": sorted(
                ["america", "estados unidos", "us", "usa", "united states",
                 "united states of america", "états-unis"]
            ),
            "names_lang": {
                "en": ["america", "united states",
                       "united states of america", "us", "usa"],
                "fr": ["états-unis"],
                "es": ["estados unidos"]
            },
            "abbr": ["us", "usa"],
        }
        self.assertEqual(expected, theus)


class AppendAlternateNamesTest(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_should_only_append_relevant_names(self):
        altnames_buf = io.StringIO("""\
1632234\t5815135\tes\tEstado de Washington
2080155\t5815135\tes\tWashington
2080156\t5815135\ten\tState of Washington
2089568\t5815135\ten\tWashington
2184809\t5815135\t \tWashington
2426857\t5815135\tru\tВашингтон
2730095\t5815135\tabbr\tWA""")
        reader = pygeons.process.NameReader(altnames_buf)
        alt_names = reader.read(5815135)

        country_buf = io.StringIO("""{"country": "United States", \
"languages": ["en-US", "es-US", "haw", "fr"], "iso3": "USA", "iso": "US", \
"_id": 6252001}""")
        cinfo = pygeons.process.CountryInfo(country_buf)

        washington = {"_id": 5815135, "name": "Washington",
                      "asciiname": "Washington", "countryCode": "US"}
        pygeons.process._append_alt_names(washington, alt_names, cinfo)
        expected = {
            "_id": 5815135, "abbr": ["wa"], "countryCode": "US",
            "name": "Washington", "asciiname": "Washington",
            "names": ["estado de washington", "state of washington",
                      "wa", "washington"],
            "names_lang": {
                "en": ["state of washington", "washington"],
                "es": ["estado de washington", "washington"],
            }
        }
        self.assertEqual(expected, washington)

    def test_should_append_names_of_unknown_language_code(self):
        altnames_buf = io.StringIO("""\
1526607	3915714		Florida
4511938	3915714		Provincia Florida
""")
        reader = pygeons.process.NameReader(altnames_buf)
        alt_names = reader.read(3915714)

        country_buf = io.BytesIO(
            b"""{"name":"Bolivia","iso":"BO","languages":[]}""")
        cinfo = pygeons.process.CountryInfo(country_buf)

        florida = {"_id": 3915714, "name": "Provincia Florida",
                   "asciiname": "Provincia Florida", "countryCode": "BO"}
        pygeons.process._append_alt_names(florida, alt_names, cinfo)
        expected = {
            "_id": 3915714, "countryCode": "BO", "abbr": [],
            "name": "Provincia Florida", "asciiname": "Provincia Florida",
            "names": ["florida", "provincia florida"],
            "names_lang": {
                "en": ["provincia florida"],
                "??": ["florida", "provincia florida"],
            }
        }
        self.assertEqual(expected, florida)


class NameReaderTest(unittest.TestCase):

    def test_should_read_all_names_start(self):
        fin = io.StringIO("""\
2040357\t524925\ten\tMoscow Oblast
2298552\t524925\tru\tМосковская область
""")
        reader = pygeons.process.NameReader(fin)
        names = reader.read(524925)
        expected = ['Moscow Oblast', 'Московская область']
        self.assertEqual(expected, [n.name for n in names])

    def test_should_read_all_names_end(self):
        fin = io.StringIO("""\
2040357\t524925\ten\tMoscow Oblast
2298552\t524925\tru\tМосковская область
3059202\t2147714\ten\tSydney
""")
        reader = pygeons.process.NameReader(fin)
        names = reader.read(2147714)
        expected = ['Sydney']
        self.assertEqual(expected, [n.name for n in names])

    def test_should_not_drop_names(self):
        fin = io.StringIO("""\
2040357\t524925\ten\tMoscow Oblast
2298552\t524925\tru\tМосковская область
3059202\t2147714\ten\tSydney
""")
        reader = pygeons.process.NameReader(fin)
        reader.read(524925)
        names = reader.read(2147714)
        expected = ['Sydney']
        self.assertEqual(expected, [n.name for n in names])

    def test_should_fail_on_unsorted_input(self):
        fin = io.StringIO("""\
2040357\t524925\ten\tMoscow Oblast
2298552\t524925\tru\tМосковская область
""")
        reader = pygeons.process.NameReader(fin)
        reader.read(524925)
        self.assertRaises(ValueError, reader.read, 524925)

    def test_should_fail_on_unsorted_input2(self):
        fin = io.StringIO("""\
2040357\t524925\ten\tMoscow Oblast
2298552\t524925\tru\tМосковская область
3059202\t2147714\ten\tSydney
""")
        reader = pygeons.process.NameReader(fin)
        reader.read(2147714)
        self.assertRaises(ValueError, reader.read, 524925)

    def test_should_drop_links(self):
        fin = io.StringIO("""\
2923986\t524925\tlink\thttp://en.wikipedia.org/wiki/Moscow_Oblast
2040357\t524925\ten\tMoscow Oblast
2298552\t524925\tru\tМосковская область
""")
        reader = pygeons.process.NameReader(fin)
        names = reader.read(524925)
        expected = ['Moscow Oblast', 'Московская область']
        self.assertEqual(expected, [n.name for n in names])
