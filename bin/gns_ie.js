//
// There's administrative entity with an alternative name of "Dublin" that confuses the Irish address parser.
// Find it and destroy it.
//
var cursor = db.admin2.find({"names_lang.en": "dublin", countryCode: "IE"});
if (cursor.hasNext()) {
    var dublin = cursor.next();
    dublin.names_lang["en"].splice(dublin.names_lang["en"].indexOf("dublin"), 1);
    db.admin2.save(dublin);
}

var ireland = db.countries.findOne({name: "Ireland"});
var rep = "rep of ireland";
if (ireland.names_lang["en"].indexOf(rep) === -1) {
    ireland.names_lang["en"].push(rep);
    db.countries.save(ireland);
}
