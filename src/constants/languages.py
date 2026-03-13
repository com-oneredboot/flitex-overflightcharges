"""
Official Languages by Country

Maps ISO 3166-1 alpha-2 country codes to their official language(s) using ISO 639-1 codes.
Multiple languages are represented as a list.

ISO 639-1 Language Codes:
- ar: Arabic, de: German, en: English, es: Spanish, fr: French
- pt: Portuguese, ru: Russian, zh: Chinese, ja: Japanese, ko: Korean
- and many more...

Note: This includes primary official/national languages. Some countries have
multiple official languages or regional variations.

Requirements: Internationalization support
"""

# ISO 3166-1 alpha-2 country code to ISO 639-1 language code(s) mapping
COUNTRY_TO_LANGUAGES = {
    # A
    "AD": ["ca"],  # Andorra - Catalan
    "AE": ["ar"],  # United Arab Emirates - Arabic
    "AF": ["ps", "fa"],  # Afghanistan - Pashto, Dari
    "AG": ["en"],  # Antigua and Barbuda - English
    "AI": ["en"],  # Anguilla - English
    "AL": ["sq"],  # Albania - Albanian
    "AM": ["hy"],  # Armenia - Armenian
    "AO": ["pt"],  # Angola - Portuguese
    "AQ": [],      # Antarctica - No official language
    "AR": ["es"],  # Argentina - Spanish
    "AS": ["en", "sm"],  # American Samoa - English, Samoan
    "AT": ["de"],  # Austria - German
    "AU": ["en"],  # Australia - English
    "AW": ["nl", "pap"],  # Aruba - Dutch, Papiamento
    "AX": ["sv"],  # Åland Islands - Swedish
    "AZ": ["az"],  # Azerbaijan - Azerbaijani
    # B
    "BA": ["bs", "hr", "sr"],  # Bosnia and Herzegovina - Bosnian, Croatian, Serbian
    "BB": ["en"],  # Barbados - English
    "BD": ["bn"],  # Bangladesh - Bengali
    "BE": ["nl", "fr", "de"],  # Belgium - Dutch, French, German
    "BF": ["fr"],  # Burkina Faso - French
    "BG": ["bg"],  # Bulgaria - Bulgarian
    "BH": ["ar"],  # Bahrain - Arabic
    "BI": ["fr", "rn"],  # Burundi - French, Kirundi
    "BJ": ["fr"],  # Benin - French
    "BL": ["fr"],  # Saint Barthélemy - French
    "BM": ["en"],  # Bermuda - English
    "BN": ["ms"],  # Brunei Darussalam - Malay
    "BO": ["es", "qu", "ay"],  # Bolivia - Spanish, Quechua, Aymara
    "BQ": ["nl"],  # Bonaire, Sint Eustatius and Saba - Dutch
    "BR": ["pt"],  # Brazil - Portuguese
    "BS": ["en"],  # Bahamas - English
    "BT": ["dz"],  # Bhutan - Dzongkha
    "BV": ["no"],  # Bouvet Island - Norwegian
    "BW": ["en", "tn"],  # Botswana - English, Tswana
    "BY": ["be", "ru"],  # Belarus - Belarusian, Russian
    "BZ": ["en"],  # Belize - English
    # C
    "CA": ["en", "fr"],  # Canada - English, French
    "CC": ["en"],  # Cocos (Keeling) Islands - English
    "CD": ["fr"],  # Congo, Democratic Republic - French
    "CF": ["fr"],  # Central African Republic - French
    "CG": ["fr"],  # Congo - French
    "CH": ["de", "fr", "it", "rm"],  # Switzerland - German, French, Italian, Romansh
    "CI": ["fr"],  # Côte d'Ivoire - French
    "CK": ["en"],  # Cook Islands - English
    "CL": ["es"],  # Chile - Spanish
    "CM": ["en", "fr"],  # Cameroon - English, French
    "CN": ["zh"],  # China - Chinese
    "CO": ["es"],  # Colombia - Spanish
    "CR": ["es"],  # Costa Rica - Spanish
    "CU": ["es"],  # Cuba - Spanish
    "CV": ["pt"],  # Cabo Verde - Portuguese
    "CW": ["nl", "pap"],  # Curaçao - Dutch, Papiamento
    "CX": ["en"],  # Christmas Island - English
    "CY": ["el", "tr"],  # Cyprus - Greek, Turkish
    "CZ": ["cs"],  # Czechia - Czech
    # D
    "DE": ["de"],  # Germany - German
    "DJ": ["fr", "ar"],  # Djibouti - French, Arabic
    "DK": ["da"],  # Denmark - Danish
    "DM": ["en"],  # Dominica - English
    "DO": ["es"],  # Dominican Republic - Spanish
    "DZ": ["ar"],  # Algeria - Arabic
    # E
    "EC": ["es"],  # Ecuador - Spanish
    "EE": ["et"],  # Estonia - Estonian
    "EG": ["ar"],  # Egypt - Arabic
    "EH": ["ar"],  # Western Sahara - Arabic
    "ER": ["ti", "ar", "en"],  # Eritrea - Tigrinya, Arabic, English
    "ES": ["es"],  # Spain - Spanish
    "ET": ["am"],  # Ethiopia - Amharic
    # F
    "FI": ["fi", "sv"],  # Finland - Finnish, Swedish
    "FJ": ["en", "fj"],  # Fiji - English, Fijian
    "FK": ["en"],  # Falkland Islands - English
    "FM": ["en"],  # Micronesia - English
    "FO": ["fo"],  # Faroe Islands - Faroese
    "FR": ["fr"],  # France - French
    # G
    "GA": ["fr"],  # Gabon - French
    "GB": ["en"],  # United Kingdom - English
    "GD": ["en"],  # Grenada - English
    "GE": ["ka"],  # Georgia - Georgian
    "GF": ["fr"],  # French Guiana - French
    "GG": ["en"],  # Guernsey - English
    "GH": ["en"],  # Ghana - English
    "GI": ["en"],  # Gibraltar - English
    "GL": ["kl"],  # Greenland - Greenlandic
    "GM": ["en"],  # Gambia - English
    "GN": ["fr"],  # Guinea - French
    "GP": ["fr"],  # Guadeloupe - French
    "GQ": ["es", "fr", "pt"],  # Equatorial Guinea - Spanish, French, Portuguese
    "GR": ["el"],  # Greece - Greek
    "GS": ["en"],  # South Georgia - English
    "GT": ["es"],  # Guatemala - Spanish
    "GU": ["en"],  # Guam - English
    "GW": ["pt"],  # Guinea-Bissau - Portuguese
    "GY": ["en"],  # Guyana - English
    # H-Z (continuing alphabetically)
    "HK": ["zh", "en"],  # Hong Kong - Chinese, English
    "HM": ["en"],  # Heard Island - English
    "HN": ["es"],  # Honduras - Spanish
    "HR": ["hr"],  # Croatia - Croatian
    "HT": ["fr", "ht"],  # Haiti - French, Haitian Creole
    "HU": ["hu"],  # Hungary - Hungarian
    "ID": ["id"],  # Indonesia - Indonesian
    "IE": ["en", "ga"],  # Ireland - English, Irish
    "IL": ["he", "ar"],  # Israel - Hebrew, Arabic
    "IM": ["en"],  # Isle of Man - English
    "IN": ["hi", "en"],  # India - Hindi, English
    "IO": ["en"],  # British Indian Ocean Territory - English
    "IQ": ["ar", "ku"],  # Iraq - Arabic, Kurdish
    "IR": ["fa"],  # Iran - Persian
    "IS": ["is"],  # Iceland - Icelandic
    "IT": ["it"],  # Italy - Italian
    "JE": ["en"],  # Jersey - English
    "JM": ["en"],  # Jamaica - English
    "JO": ["ar"],  # Jordan - Arabic
    "JP": ["ja"],  # Japan - Japanese
    "KE": ["en", "sw"],  # Kenya - English, Swahili
    "KG": ["ky", "ru"],  # Kyrgyzstan - Kyrgyz, Russian
    "KH": ["km"],  # Cambodia - Khmer
    "KI": ["en"],  # Kiribati - English
    "KM": ["ar", "fr"],  # Comoros - Arabic, French
    "KN": ["en"],  # Saint Kitts and Nevis - English
    "KP": ["ko"],  # North Korea - Korean
    "KR": ["ko"],  # South Korea - Korean
    "KW": ["ar"],  # Kuwait - Arabic
    "KY": ["en"],  # Cayman Islands - English
    "KZ": ["kk", "ru"],  # Kazakhstan - Kazakh, Russian
    "LA": ["lo"],  # Laos - Lao
    "LB": ["ar", "fr"],  # Lebanon - Arabic, French
    "LC": ["en"],  # Saint Lucia - English
    "LI": ["de"],  # Liechtenstein - German
    "LK": ["si", "ta"],  # Sri Lanka - Sinhala, Tamil
    "LR": ["en"],  # Liberia - English
    "LS": ["en", "st"],  # Lesotho - English, Sesotho
    "LT": ["lt"],  # Lithuania - Lithuanian
    "LU": ["lb", "fr", "de"],  # Luxembourg - Luxembourgish, French, German
    "LV": ["lv"],  # Latvia - Latvian
    "LY": ["ar"],  # Libya - Arabic
    "MA": ["ar"],  # Morocco - Arabic
    "MC": ["fr"],  # Monaco - French
    "MD": ["ro"],  # Moldova - Romanian
    "ME": ["sr"],  # Montenegro - Serbian
    "MF": ["fr"],  # Saint Martin - French
    "MG": ["mg", "fr"],  # Madagascar - Malagasy, French
    "MH": ["en"],  # Marshall Islands - English
    "MK": ["mk"],  # North Macedonia - Macedonian
    "ML": ["fr"],  # Mali - French
    "MM": ["my"],  # Myanmar - Burmese
    "MN": ["mn"],  # Mongolia - Mongolian
    "MO": ["zh", "pt"],  # Macao - Chinese, Portuguese
    "MP": ["en"],  # Northern Mariana Islands - English
    "MQ": ["fr"],  # Martinique - French
    "MR": ["ar"],  # Mauritania - Arabic
    "MS": ["en"],  # Montserrat - English
    "MT": ["mt", "en"],  # Malta - Maltese, English
    "MU": ["en", "fr"],  # Mauritius - English, French
    "MV": ["dv"],  # Maldives - Dhivehi
    "MW": ["en"],  # Malawi - English
    "MX": ["es"],  # Mexico - Spanish
    "MY": ["ms"],  # Malaysia - Malay
    "MZ": ["pt"],  # Mozambique - Portuguese
    "NA": ["en"],  # Namibia - English
    "NC": ["fr"],  # New Caledonia - French
    "NE": ["fr"],  # Niger - French
    "NF": ["en"],  # Norfolk Island - English
    "NG": ["en"],  # Nigeria - English
    "NI": ["es"],  # Nicaragua - Spanish
    "NL": ["nl"],  # Netherlands - Dutch
    "NO": ["no"],  # Norway - Norwegian
    "NP": ["ne"],  # Nepal - Nepali
    "NR": ["en", "na"],  # Nauru - English, Nauruan
    "NU": ["en"],  # Niue - English
    "NZ": ["en"],  # New Zealand - English
    "OM": ["ar"],  # Oman - Arabic
    "PA": ["es"],  # Panama - Spanish
    "PE": ["es"],  # Peru - Spanish
    "PF": ["fr"],  # French Polynesia - French
    "PG": ["en"],  # Papua New Guinea - English
    "PH": ["en", "tl"],  # Philippines - English, Filipino
    "PK": ["ur", "en"],  # Pakistan - Urdu, English
    "PL": ["pl"],  # Poland - Polish
    "PM": ["fr"],  # Saint Pierre and Miquelon - French
    "PN": ["en"],  # Pitcairn - English
    "PR": ["es", "en"],  # Puerto Rico - Spanish, English
    "PS": ["ar"],  # Palestine - Arabic
    "PT": ["pt"],  # Portugal - Portuguese
    "PW": ["en"],  # Palau - English
    "PY": ["es", "gn"],  # Paraguay - Spanish, Guarani
    "QA": ["ar"],  # Qatar - Arabic
    "RE": ["fr"],  # Réunion - French
    "RO": ["ro"],  # Romania - Romanian
    "RS": ["sr"],  # Serbia - Serbian
    "RU": ["ru"],  # Russia - Russian
    "RW": ["rw", "en", "fr"],  # Rwanda - Kinyarwanda, English, French
    "SA": ["ar"],  # Saudi Arabia - Arabic
    "SB": ["en"],  # Solomon Islands - English
    "SC": ["en", "fr"],  # Seychelles - English, French
    "SD": ["ar", "en"],  # Sudan - Arabic, English
    "SE": ["sv"],  # Sweden - Swedish
    "SG": ["en", "ms", "zh", "ta"],  # Singapore - English, Malay, Chinese, Tamil
    "SH": ["en"],  # Saint Helena - English
    "SI": ["sl"],  # Slovenia - Slovenian
    "SJ": ["no"],  # Svalbard and Jan Mayen - Norwegian
    "SK": ["sk"],  # Slovakia - Slovak
    "SL": ["en"],  # Sierra Leone - English
    "SM": ["it"],  # San Marino - Italian
    "SN": ["fr"],  # Senegal - French
    "SO": ["so", "ar"],  # Somalia - Somali, Arabic
    "SR": ["nl"],  # Suriname - Dutch
    "SS": ["en"],  # South Sudan - English
    "ST": ["pt"],  # Sao Tome and Principe - Portuguese
    "SV": ["es"],  # El Salvador - Spanish
    "SX": ["nl", "en"],  # Sint Maarten - Dutch, English
    "SY": ["ar"],  # Syria - Arabic
    "SZ": ["en", "ss"],  # Eswatini - English, Swazi
    "TC": ["en"],  # Turks and Caicos - English
    "TD": ["fr", "ar"],  # Chad - French, Arabic
    "TF": ["fr"],  # French Southern Territories - French
    "TG": ["fr"],  # Togo - French
    "TH": ["th"],  # Thailand - Thai
    "TJ": ["tg", "ru"],  # Tajikistan - Tajik, Russian
    "TK": ["en"],  # Tokelau - English
    "TL": ["pt", "tet"],  # Timor-Leste - Portuguese, Tetum
    "TM": ["tk"],  # Turkmenistan - Turkmen
    "TN": ["ar"],  # Tunisia - Arabic
    "TO": ["en", "to"],  # Tonga - English, Tongan
    "TR": ["tr"],  # Turkey - Turkish
    "TT": ["en"],  # Trinidad and Tobago - English
    "TV": ["en"],  # Tuvalu - English
    "TW": ["zh"],  # Taiwan - Chinese
    "TZ": ["sw", "en"],  # Tanzania - Swahili, English
    "UA": ["uk"],  # Ukraine - Ukrainian
    "UG": ["en", "sw"],  # Uganda - English, Swahili
    "UM": ["en"],  # US Minor Outlying Islands - English
    "US": ["en"],  # United States - English
    "UY": ["es"],  # Uruguay - Spanish
    "UZ": ["uz"],  # Uzbekistan - Uzbek
    "VA": ["it", "la"],  # Holy See - Italian, Latin
    "VC": ["en"],  # Saint Vincent and the Grenadines - English
    "VE": ["es"],  # Venezuela - Spanish
    "VG": ["en"],  # Virgin Islands (British) - English
    "VI": ["en"],  # Virgin Islands (US) - English
    "VN": ["vi"],  # Vietnam - Vietnamese
    "VU": ["bi", "en", "fr"],  # Vanuatu - Bislama, English, French
    "WF": ["fr"],  # Wallis and Futuna - French
    "WS": ["sm", "en"],  # Samoa - Samoan, English
    "YE": ["ar"],  # Yemen - Arabic
    "YT": ["fr"],  # Mayotte - French
    "ZA": ["en", "af", "zu", "xh"],  # South Africa - English, Afrikaans, Zulu, Xhosa (+ 7 more)
    "ZM": ["en"],  # Zambia - English
    "ZW": ["en", "sn", "nd"],  # Zimbabwe - English, Shona, Ndebele
}

# ISO 639-1 Language Code to Language Name mapping (for reference)
LANGUAGE_NAMES = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "ay": "Aymara",
    "az": "Azerbaijani", "be": "Belarusian", "bg": "Bulgarian", "bi": "Bislama",
    "bn": "Bengali", "bs": "Bosnian", "ca": "Catalan", "cs": "Czech",
    "da": "Danish", "de": "German", "dv": "Dhivehi", "dz": "Dzongkha",
    "el": "Greek", "en": "English", "es": "Spanish", "et": "Estonian",
    "fa": "Persian", "fi": "Finnish", "fj": "Fijian", "fo": "Faroese",
    "fr": "French", "ga": "Irish", "gn": "Guarani", "he": "Hebrew",
    "hi": "Hindi", "hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian",
    "hy": "Armenian", "id": "Indonesian", "is": "Icelandic", "it": "Italian",
    "ja": "Japanese", "ka": "Georgian", "kk": "Kazakh", "kl": "Greenlandic",
    "km": "Khmer", "ko": "Korean", "ku": "Kurdish", "ky": "Kyrgyz",
    "la": "Latin", "lb": "Luxembourgish", "lo": "Lao", "lt": "Lithuanian",
    "lv": "Latvian", "mg": "Malagasy", "mk": "Macedonian", "mn": "Mongolian",
    "ms": "Malay", "mt": "Maltese", "my": "Burmese", "na": "Nauruan",
    "nd": "Ndebele", "ne": "Nepali", "nl": "Dutch", "no": "Norwegian",
    "pap": "Papiamento", "pl": "Polish", "ps": "Pashto", "pt": "Portuguese",
    "qu": "Quechua", "rm": "Romansh", "rn": "Kirundi", "ro": "Romanian",
    "ru": "Russian", "rw": "Kinyarwanda", "si": "Sinhala", "sk": "Slovak",
    "sl": "Slovenian", "sm": "Samoan", "sn": "Shona", "so": "Somali",
    "sq": "Albanian", "sr": "Serbian", "ss": "Swazi", "st": "Sesotho",
    "sv": "Swedish", "sw": "Swahili", "ta": "Tamil", "tet": "Tetum",
    "tg": "Tajik", "th": "Thai", "ti": "Tigrinya", "tk": "Turkmen",
    "tl": "Filipino", "tn": "Tswana", "to": "Tongan", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese",
    "xh": "Xhosa", "zh": "Chinese", "zu": "Zulu",
}
