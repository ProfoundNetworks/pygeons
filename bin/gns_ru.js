load(SCRIPT_DIR + "/gns_common.js");

//
// Strange admin1/city in Russia
//
db.admin1.remove({countryCode: "RU", name: "Moskva"});
db.cities.remove({countryCode: "RU", name: "Moskva"});
db.cities.remove({countryCode: "RU", name: "Rossiya"});

var russia = db.countries.findOne({name: "Russia"});
if (addIfAbsent(russia.names_lang["ru"], "рф")) {
    db.countries.save(russia);
}
