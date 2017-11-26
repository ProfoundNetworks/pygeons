//
// "Great Britain" is a country
//
cursor = db.countries.find({name: "United Kingdom"});
if (cursor.hasNext()) {
    var gb = cursor.next();
    if (gb.names_lang["en"].indexOf("great britain") == -1) {
        gb.names_lang["en"].push("great britain");
        db.countries.save(gb);
    }
}
