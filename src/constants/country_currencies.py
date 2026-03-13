"""
Country to Currency Mapping

Maps ISO 3166-1 alpha-2 country codes to their ISO 4217 currency codes.
Based on ISO 4217 standard (updated January 2026).

Note: Some countries use multiple currencies or share currencies.
This mapping shows the primary/official currency for each country.

Requirements: 6.1
"""

# ISO 3166-1 alpha-2 country code to ISO 4217 currency code mapping
COUNTRY_TO_CURRENCY = {
    # A
    "AD": "EUR",  # Andorra
    "AE": "AED",  # United Arab Emirates
    "AF": "AFN",  # Afghanistan
    "AG": "XCD",  # Antigua and Barbuda
    "AI": "XCD",  # Anguilla
    "AL": "ALL",  # Albania
    "AM": "AMD",  # Armenia
    "AO": "AOA",  # Angola
    "AQ": None,   # Antarctica (no universal currency)
    "AR": "ARS",  # Argentina
    "AS": "USD",  # American Samoa
    "AT": "EUR",  # Austria
    "AU": "AUD",  # Australia
    "AW": "AWG",  # Aruba
    "AX": "EUR",  # Åland Islands
    "AZ": "AZN",  # Azerbaijan
    # B
    "BA": "BAM",  # Bosnia and Herzegovina
    "BB": "BBD",  # Barbados
    "BD": "BDT",  # Bangladesh
    "BE": "EUR",  # Belgium
    "BF": "XOF",  # Burkina Faso
    "BG": "EUR",  # Bulgaria
    "BH": "BHD",  # Bahrain
    "BI": "BIF",  # Burundi
    "BJ": "XOF",  # Benin
    "BL": "EUR",  # Saint Barthélemy
    "BM": "BMD",  # Bermuda
    "BN": "BND",  # Brunei Darussalam
    "BO": "BOB",  # Bolivia
    "BQ": "USD",  # Bonaire, Sint Eustatius and Saba
    "BR": "BRL",  # Brazil
    "BS": "BSD",  # Bahamas
    "BT": "BTN",  # Bhutan
    "BV": "NOK",  # Bouvet Island
    "BW": "BWP",  # Botswana
    "BY": "BYN",  # Belarus
    "BZ": "BZD",  # Belize
    # C
    "CA": "CAD",  # Canada
    "CC": "AUD",  # Cocos (Keeling) Islands
    "CD": "CDF",  # Congo, Democratic Republic of the
    "CF": "XAF",  # Central African Republic
    "CG": "XAF",  # Congo
    "CH": "CHF",  # Switzerland
    "CI": "XOF",  # Côte d'Ivoire
    "CK": "NZD",  # Cook Islands
    "CL": "CLP",  # Chile
    "CM": "XAF",  # Cameroon
    "CN": "CNY",  # China
    "CO": "COP",  # Colombia
    "CR": "CRC",  # Costa Rica
    "CU": "CUP",  # Cuba (also CUC)
    "CV": "CVE",  # Cabo Verde
    "CW": "XCG",  # Curaçao
    "CX": "AUD",  # Christmas Island
    "CY": "EUR",  # Cyprus
    "CZ": "CZK",  # Czechia
    # D
    "DE": "EUR",  # Germany
    "DJ": "DJF",  # Djibouti
    "DK": "DKK",  # Denmark
    "DM": "XCD",  # Dominica
    "DO": "DOP",  # Dominican Republic
    "DZ": "DZD",  # Algeria
    # E
    "EC": "USD",  # Ecuador
    "EE": "EUR",  # Estonia
    "EG": "EGP",  # Egypt
    "EH": "MAD",  # Western Sahara
    "ER": "ERN",  # Eritrea
    "ES": "EUR",  # Spain
    "ET": "ETB",  # Ethiopia
    # F
    "FI": "EUR",  # Finland
    "FJ": "FJD",  # Fiji
    "FK": "FKP",  # Falkland Islands (Malvinas)
    "FM": "USD",  # Micronesia, Federated States of
    "FO": "DKK",  # Faroe Islands
    "FR": "EUR",  # France
    # G
    "GA": "XAF",  # Gabon
    "GB": "GBP",  # United Kingdom
    "GD": "XCD",  # Grenada
    "GE": "GEL",  # Georgia
    "GF": "EUR",  # French Guiana
    "GG": "GBP",  # Guernsey
    "GH": "GHS",  # Ghana
    "GI": "GIP",  # Gibraltar
    "GL": "DKK",  # Greenland
    "GM": "GMD",  # Gambia
    "GN": "GNF",  # Guinea
    "GP": "EUR",  # Guadeloupe
    "GQ": "XAF",  # Equatorial Guinea
    "GR": "EUR",  # Greece
    "GS": None,   # South Georgia and the South Sandwich Islands
    "GT": "GTQ",  # Guatemala
    "GU": "USD",  # Guam
    "GW": "XOF",  # Guinea-Bissau
    "GY": "GYD",  # Guyana
    # H
    "HK": "HKD",  # Hong Kong
    "HM": "AUD",  # Heard Island and McDonald Islands
    "HN": "HNL",  # Honduras
    "HR": "EUR",  # Croatia
    "HT": "HTG",  # Haiti (also USD)
    "HU": "HUF",  # Hungary
    # I
    "ID": "IDR",  # Indonesia
    "IE": "EUR",  # Ireland
    "IL": "ILS",  # Israel
    "IM": "GBP",  # Isle of Man
    "IN": "INR",  # India
    "IO": "USD",  # British Indian Ocean Territory
    "IQ": "IQD",  # Iraq
    "IR": "IRR",  # Iran
    "IS": "ISK",  # Iceland
    "IT": "EUR",  # Italy
    # J
    "JE": "GBP",  # Jersey
    "JM": "JMD",  # Jamaica
    "JO": "JOD",  # Jordan
    "JP": "JPY",  # Japan
    # K
    "KE": "KES",  # Kenya
    "KG": "KGS",  # Kyrgyzstan
    "KH": "KHR",  # Cambodia
    "KI": "AUD",  # Kiribati
    "KM": "KMF",  # Comoros
    "KN": "XCD",  # Saint Kitts and Nevis
    "KP": "KPW",  # Korea, Democratic People's Republic of
    "KR": "KRW",  # Korea, Republic of
    "KW": "KWD",  # Kuwait
    "KY": "KYD",  # Cayman Islands
    "KZ": "KZT",  # Kazakhstan
    # L
    "LA": "LAK",  # Lao People's Democratic Republic
    "LB": "LBP",  # Lebanon
    "LC": "XCD",  # Saint Lucia
    "LI": "CHF",  # Liechtenstein
    "LK": "LKR",  # Sri Lanka
    "LR": "LRD",  # Liberia
    "LS": "LSL",  # Lesotho (also ZAR)
    "LT": "EUR",  # Lithuania
    "LU": "EUR",  # Luxembourg
    "LV": "EUR",  # Latvia
    "LY": "LYD",  # Libya
    # M
    "MA": "MAD",  # Morocco
    "MC": "EUR",  # Monaco
    "MD": "MDL",  # Moldova
    "ME": "EUR",  # Montenegro
    "MF": "EUR",  # Saint Martin (French part)
    "MG": "MGA",  # Madagascar
    "MH": "USD",  # Marshall Islands
    "MK": "MKD",  # North Macedonia
    "ML": "XOF",  # Mali
    "MM": "MMK",  # Myanmar
    "MN": "MNT",  # Mongolia
    "MO": "MOP",  # Macao
    "MP": "USD",  # Northern Mariana Islands
    "MQ": "EUR",  # Martinique
    "MR": "MRU",  # Mauritania
    "MS": "XCD",  # Montserrat
    "MT": "EUR",  # Malta
    "MU": "MUR",  # Mauritius
    "MV": "MVR",  # Maldives
    "MW": "MWK",  # Malawi
    "MX": "MXN",  # Mexico
    "MY": "MYR",  # Malaysia
    "MZ": "MZN",  # Mozambique
    # N
    "NA": "NAD",  # Namibia (also ZAR)
    "NC": "XPF",  # New Caledonia
    "NE": "XOF",  # Niger
    "NF": "AUD",  # Norfolk Island
    "NG": "NGN",  # Nigeria
    "NI": "NIO",  # Nicaragua
    "NL": "EUR",  # Netherlands
    "NO": "NOK",  # Norway
    "NP": "NPR",  # Nepal
    "NR": "AUD",  # Nauru
    "NU": "NZD",  # Niue
    "NZ": "NZD",  # New Zealand
    # O
    "OM": "OMR",  # Oman
    # P
    "PA": "PAB",  # Panama (also USD)
    "PE": "PEN",  # Peru
    "PF": "XPF",  # French Polynesia
    "PG": "PGK",  # Papua New Guinea
    "PH": "PHP",  # Philippines
    "PK": "PKR",  # Pakistan
    "PL": "PLN",  # Poland
    "PM": "EUR",  # Saint Pierre and Miquelon
    "PN": "NZD",  # Pitcairn
    "PR": "USD",  # Puerto Rico
    "PS": None,   # Palestine, State of (no universal currency)
    "PT": "EUR",  # Portugal
    "PW": "USD",  # Palau
    "PY": "PYG",  # Paraguay
    # Q
    "QA": "QAR",  # Qatar
    # R
    "RE": "EUR",  # Réunion
    "RO": "RON",  # Romania
    "RS": "RSD",  # Serbia
    "RU": "RUB",  # Russian Federation
    "RW": "RWF",  # Rwanda
    # S
    "SA": "SAR",  # Saudi Arabia
    "SB": "SBD",  # Solomon Islands
    "SC": "SCR",  # Seychelles
    "SD": "SDG",  # Sudan
    "SE": "SEK",  # Sweden
    "SG": "SGD",  # Singapore
    "SH": "SHP",  # Saint Helena, Ascension and Tristan da Cunha
    "SI": "EUR",  # Slovenia
    "SJ": "NOK",  # Svalbard and Jan Mayen
    "SK": "EUR",  # Slovakia
    "SL": "SLE",  # Sierra Leone
    "SM": "EUR",  # San Marino
    "SN": "XOF",  # Senegal
    "SO": "SOS",  # Somalia
    "SR": "SRD",  # Suriname
    "SS": "SSP",  # South Sudan
    "ST": "STN",  # Sao Tome and Principe
    "SV": "USD",  # El Salvador (also SVC)
    "SX": "XCG",  # Sint Maarten (Dutch part)
    "SY": "SYP",  # Syrian Arab Republic
    "SZ": "SZL",  # Eswatini
    # T
    "TC": "USD",  # Turks and Caicos Islands
    "TD": "XAF",  # Chad
    "TF": "EUR",  # French Southern Territories
    "TG": "XOF",  # Togo
    "TH": "THB",  # Thailand
    "TJ": "TJS",  # Tajikistan
    "TK": "NZD",  # Tokelau
    "TL": "USD",  # Timor-Leste
    "TM": "TMT",  # Turkmenistan
    "TN": "TND",  # Tunisia
    "TO": "TOP",  # Tonga
    "TR": "TRY",  # Türkiye
    "TT": "TTD",  # Trinidad and Tobago
    "TV": "AUD",  # Tuvalu
    "TW": "TWD",  # Taiwan
    "TZ": "TZS",  # Tanzania
    # U
    "UA": "UAH",  # Ukraine
    "UG": "UGX",  # Uganda
    "UM": "USD",  # United States Minor Outlying Islands
    "US": "USD",  # United States of America
    "UY": "UYU",  # Uruguay
    "UZ": "UZS",  # Uzbekistan
    # V
    "VA": "EUR",  # Holy See
    "VC": "XCD",  # Saint Vincent and the Grenadines
    "VE": "VED",  # Venezuela (VEF deprecated, VED current)
    "VG": "USD",  # Virgin Islands (British)
    "VI": "USD",  # Virgin Islands (U.S.)
    "VN": "VND",  # Viet Nam
    "VU": "VUV",  # Vanuatu
    # W
    "WF": "XPF",  # Wallis and Futuna
    "WS": "WST",  # Samoa
    # Y
    "YE": "YER",  # Yemen
    "YT": "EUR",  # Mayotte
    # Z
    "ZA": "ZAR",  # South Africa
    "ZM": "ZMW",  # Zambia
    "ZW": "ZWL",  # Zimbabwe
}

# Reverse mapping: Currency to list of countries using it
CURRENCY_TO_COUNTRIES = {}
for country, currency in COUNTRY_TO_CURRENCY.items():
    if currency:
        if currency not in CURRENCY_TO_COUNTRIES:
            CURRENCY_TO_COUNTRIES[currency] = []
        CURRENCY_TO_COUNTRIES[currency].append(country)

