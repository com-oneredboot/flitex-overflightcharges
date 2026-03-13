"""
Currency Constants

ISO 4217 currency codes used in overflight charge calculations.
Complete list of active currency codes as of January 2026.

Note: This maintains backward compatibility with the original CURRENCY_CONSTANTS
while providing a comprehensive list of all ISO 4217 codes.

Requirements: 6.1
"""

# Complete ISO 4217 currency codes (alphabetically sorted)
CURRENCY_CONSTANTS = {
    # Original currencies (for backward compatibility)
    "ANG": "ANG",  # Netherlands Antillean Guilder
    "ARS": "ARS",  # Argentine Peso
    "AUD": "AUD",  # Australian Dollar
    "BHD": "BHD",  # Bahraini Dinar
    "BRL": "BRL",  # Brazilian Real
    "BWP": "BWP",  # Botswana Pula
    "CAD": "CAD",  # Canadian Dollar
    "CHF": "CHF",  # Swiss Franc
    "CLP": "CLP",  # Chilean Peso
    "CNY": "CNY",  # Chinese Yuan
    "CUC": "CUC",  # Cuban Convertible Peso
    "CVE": "CVE",  # Cape Verde Escudo
    "DZD": "DZD",  # Algerian Dinar
    "EUR": "EUR",  # Euro
    "FJD": "FJD",  # Fiji Dollar
    "GBP": "GBP",  # Pound Sterling
    "GYD": "GYD",  # Guyana Dollar
    "HKD": "HKD",  # Hong Kong Dollar
    "IDR": "IDR",  # Indonesian Rupiah
    "INR": "INR",  # Indian Rupee
    "JOD": "JOD",  # Jordanian Dinar
    "JPY": "JPY",  # Japanese Yen
    "KGS": "KGS",  # Kyrgyzstan Som
    "KRW": "KRW",  # South Korean Won
    "KWD": "KWD",  # Kuwaiti Dinar
    "KZT": "KZT",  # Kazakhstani Tenge
    "LYD": "LYD",  # Libyan Dinar
    "MAD": "MAD",  # Moroccan Dirham
    "MMK": "MMK",  # Myanmar Kyat
    "MUR": "MUR",  # Mauritius Rupee
    "MXN": "MXN",  # Mexican Peso
    "MYR": "MYR",  # Malaysian Ringgit
    "NAD": "NAD",  # Namibian Dollar
    "NZD": "NZD",  # New Zealand Dollar
    "PAB": "PAB",  # Panamanian Balboa
    "PEN": "PEN",  # Peruvian Sol
    "PGK": "PGK",  # Papua New Guinea Kina
    "PKR": "PKR",  # Pakistani Rupee
    "SAR": "SAR",  # Saudi Riyal
    "SBD": "SBD",  # Solomon Islands Dollar
    "SRD": "SRD",  # Surinamese Dollar
    "THB": "THB",  # Thai Baht
    "USD": "USD",  # US Dollar
    "VND": "VND",  # Vietnamese Dong
    "ZAR": "ZAR",  # South African Rand
    
    # Additional ISO 4217 codes (comprehensive list)
    "AED": "AED",  # UAE Dirham
    "AFN": "AFN",  # Afghan Afghani
    "ALL": "ALL",  # Albanian Lek
    "AMD": "AMD",  # Armenian Dram
    "AOA": "AOA",  # Angolan Kwanza
    "AWG": "AWG",  # Aruban Florin
    "AZN": "AZN",  # Azerbaijani Manat
    "BAM": "BAM",  # Bosnia-Herzegovina Convertible Mark
    "BBD": "BBD",  # Barbadian Dollar
    "BDT": "BDT",  # Bangladeshi Taka
    "BGN": "BGN",  # Bulgarian Lev
    "BIF": "BIF",  # Burundian Franc
    "BMD": "BMD",  # Bermudan Dollar
    "BND": "BND",  # Brunei Dollar
    "BOB": "BOB",  # Bolivian Boliviano
    "BSD": "BSD",  # Bahamian Dollar
    "BTN": "BTN",  # Bhutanese Ngultrum
    "BYN": "BYN",  # Belarusian Ruble
    "BZD": "BZD",  # Belize Dollar
    "CDF": "CDF",  # Congolese Franc
    "CLF": "CLF",  # Chilean Unit of Account (UF)
    "COP": "COP",  # Colombian Peso
    "CRC": "CRC",  # Costa Rican Colón
    "CUP": "CUP",  # Cuban Peso
    "CZK": "CZK",  # Czech Koruna
    "DJF": "DJF",  # Djiboutian Franc
    "DKK": "DKK",  # Danish Krone
    "DOP": "DOP",  # Dominican Peso
    "EGP": "EGP",  # Egyptian Pound
    "ERN": "ERN",  # Eritrean Nakfa
    "ETB": "ETB",  # Ethiopian Birr
    "FKP": "FKP",  # Falkland Islands Pound
    "GEL": "GEL",  # Georgian Lari
    "GHS": "GHS",  # Ghanaian Cedi
    "GIP": "GIP",  # Gibraltar Pound
    "GMD": "GMD",  # Gambian Dalasi
    "GNF": "GNF",  # Guinean Franc
    "GTQ": "GTQ",  # Guatemalan Quetzal
    "HNL": "HNL",  # Honduran Lempira
    "HRK": "HRK",  # Croatian Kuna (deprecated, now EUR)
    "HTG": "HTG",  # Haitian Gourde
    "HUF": "HUF",  # Hungarian Forint
    "ILS": "ILS",  # Israeli New Shekel
    "IQD": "IQD",  # Iraqi Dinar
    "IRR": "IRR",  # Iranian Rial
    "ISK": "ISK",  # Icelandic Króna
    "JMD": "JMD",  # Jamaican Dollar
    "KES": "KES",  # Kenyan Shilling
    "KHR": "KHR",  # Cambodian Riel
    "KMF": "KMF",  # Comorian Franc
    "KPW": "KPW",  # North Korean Won
    "KYD": "KYD",  # Cayman Islands Dollar
    "LAK": "LAK",  # Lao Kip
    "LBP": "LBP",  # Lebanese Pound
    "LKR": "LKR",  # Sri Lankan Rupee
    "LRD": "LRD",  # Liberian Dollar
    "LSL": "LSL",  # Lesotho Loti
    "MDL": "MDL",  # Moldovan Leu
    "MGA": "MGA",  # Malagasy Ariary
    "MKD": "MKD",  # Macedonian Denar
    "MNT": "MNT",  # Mongolian Tugrik
    "MOP": "MOP",  # Macanese Pataca
    "MRU": "MRU",  # Mauritanian Ouguiya
    "MWK": "MWK",  # Malawian Kwacha
    "MXV": "MXV",  # Mexican Unidad de Inversion (UDI)
    "MZN": "MZN",  # Mozambican Metical
    "NGN": "NGN",  # Nigerian Naira
    "NIO": "NIO",  # Nicaraguan Córdoba
    "NOK": "NOK",  # Norwegian Krone
    "NPR": "NPR",  # Nepalese Rupee
    "OMR": "OMR",  # Omani Rial
    "PHP": "PHP",  # Philippine Peso
    "PLN": "PLN",  # Polish Zloty
    "PYG": "PYG",  # Paraguayan Guarani
    "QAR": "QAR",  # Qatari Riyal
    "RON": "RON",  # Romanian Leu
    "RSD": "RSD",  # Serbian Dinar
    "RUB": "RUB",  # Russian Ruble
    "RWF": "RWF",  # Rwandan Franc
    "SCR": "SCR",  # Seychellois Rupee
    "SDG": "SDG",  # Sudanese Pound
    "SEK": "SEK",  # Swedish Krona
    "SGD": "SGD",  # Singapore Dollar
    "SHP": "SHP",  # Saint Helena Pound
    "SLE": "SLE",  # Sierra Leonean Leone
    "SOS": "SOS",  # Somali Shilling
    "SSP": "SSP",  # South Sudanese Pound
    "STN": "STN",  # São Tomé and Príncipe Dobra
    "SVC": "SVC",  # Salvadoran Colón
    "SYP": "SYP",  # Syrian Pound
    "SZL": "SZL",  # Swazi Lilangeni
    "TJS": "TJS",  # Tajikistani Somoni
    "TMT": "TMT",  # Turkmenistani Manat
    "TND": "TND",  # Tunisian Dinar
    "TOP": "TOP",  # Tongan Paʻanga
    "TRY": "TRY",  # Turkish Lira
    "TTD": "TTD",  # Trinidad and Tobago Dollar
    "TWD": "TWD",  # New Taiwan Dollar
    "TZS": "TZS",  # Tanzanian Shilling
    "UAH": "UAH",  # Ukrainian Hryvnia
    "UGX": "UGX",  # Ugandan Shilling
    "UYU": "UYU",  # Uruguayan Peso
    "UZS": "UZS",  # Uzbekistani Som
    "VED": "VED",  # Venezuelan Bolívar Digital
    "VEF": "VEF",  # Venezuelan Bolívar (deprecated)
    "VUV": "VUV",  # Vanuatu Vatu
    "WST": "WST",  # Samoan Tala
    "XAF": "XAF",  # Central African CFA Franc
    "XCD": "XCD",  # East Caribbean Dollar
    "XCG": "XCG",  # Caribbean Guilder
    "XOF": "XOF",  # West African CFA Franc
    "XPF": "XPF",  # CFP Franc
    "YER": "YER",  # Yemeni Rial
    "ZMW": "ZMW",  # Zambian Kwacha
    "ZWL": "ZWL",  # Zimbabwean Dollar
    
    # Special/placeholder
    "NONE": "",    # No currency
}


# ISO 4217 Currency Code to Full Currency Name mapping
CURRENCY_NAMES = {
    "AED": "United Arab Emirates Dirham",
    "AFN": "Afghan Afghani",
    "ALL": "Albanian Lek",
    "AMD": "Armenian Dram",
    "ANG": "Netherlands Antillean Guilder",
    "AOA": "Angolan Kwanza",
    "ARS": "Argentine Peso",
    "AUD": "Australian Dollar",
    "AWG": "Aruban Florin",
    "AZN": "Azerbaijani Manat",
    "BAM": "Bosnia-Herzegovina Convertible Mark",
    "BBD": "Barbadian Dollar",
    "BDT": "Bangladeshi Taka",
    "BGN": "Bulgarian Lev",
    "BHD": "Bahraini Dinar",
    "BIF": "Burundian Franc",
    "BMD": "Bermudan Dollar",
    "BND": "Brunei Dollar",
    "BOB": "Bolivian Boliviano",
    "BOV": "Bolivian Mvdol",
    "BRL": "Brazilian Real",
    "BSD": "Bahamian Dollar",
    "BTN": "Bhutanese Ngultrum",
    "BWP": "Botswana Pula",
    "BYN": "Belarusian Ruble",
    "BZD": "Belize Dollar",
    "CAD": "Canadian Dollar",
    "CDF": "Congolese Franc",
    "CHF": "Swiss Franc",
    "CHE": "WIR Euro",
    "CHW": "WIR Franc",
    "CLF": "Chilean Unit of Account (UF)",
    "CLP": "Chilean Peso",
    "CNY": "Chinese Yuan",
    "COP": "Colombian Peso",
    "COU": "Colombian Unidad de Valor Real",
    "CRC": "Costa Rican Colón",
    "CUC": "Cuban Convertible Peso",
    "CUP": "Cuban Peso",
    "CVE": "Cape Verdean Escudo",
    "CZK": "Czech Koruna",
    "DJF": "Djiboutian Franc",
    "DKK": "Danish Krone",
    "DOP": "Dominican Peso",
    "DZD": "Algerian Dinar",
    "EGP": "Egyptian Pound",
    "ERN": "Eritrean Nakfa",
    "ETB": "Ethiopian Birr",
    "EUR": "Euro",
    "FJD": "Fijian Dollar",
    "FKP": "Falkland Islands Pound",
    "GBP": "British Pound Sterling",
    "GEL": "Georgian Lari",
    "GHS": "Ghanaian Cedi",
    "GIP": "Gibraltar Pound",
    "GMD": "Gambian Dalasi",
    "GNF": "Guinean Franc",
    "GTQ": "Guatemalan Quetzal",
    "GYD": "Guyanese Dollar",
    "HKD": "Hong Kong Dollar",
    "HNL": "Honduran Lempira",
    "HRK": "Croatian Kuna",
    "HTG": "Haitian Gourde",
    "HUF": "Hungarian Forint",
    "IDR": "Indonesian Rupiah",
    "ILS": "Israeli New Shekel",
    "INR": "Indian Rupee",
    "IQD": "Iraqi Dinar",
    "IRR": "Iranian Rial",
    "ISK": "Icelandic Króna",
    "JMD": "Jamaican Dollar",
    "JOD": "Jordanian Dinar",
    "JPY": "Japanese Yen",
    "KES": "Kenyan Shilling",
    "KGS": "Kyrgyzstani Som",
    "KHR": "Cambodian Riel",
    "KMF": "Comorian Franc",
    "KPW": "North Korean Won",
    "KRW": "South Korean Won",
    "KWD": "Kuwaiti Dinar",
    "KYD": "Cayman Islands Dollar",
    "KZT": "Kazakhstani Tenge",
    "LAK": "Lao Kip",
    "LBP": "Lebanese Pound",
    "LKR": "Sri Lankan Rupee",
    "LRD": "Liberian Dollar",
    "LSL": "Lesotho Loti",
    "LYD": "Libyan Dinar",
    "MAD": "Moroccan Dirham",
    "MDL": "Moldovan Leu",
    "MGA": "Malagasy Ariary",
    "MKD": "Macedonian Denar",
    "MMK": "Myanmar Kyat",
    "MNT": "Mongolian Tugrik",
    "MOP": "Macanese Pataca",
    "MRU": "Mauritanian Ouguiya",
    "MUR": "Mauritian Rupee",
    "MVR": "Maldivian Rufiyaa",
    "MWK": "Malawian Kwacha",
    "MXN": "Mexican Peso",
    "MXV": "Mexican Unidad de Inversion (UDI)",
    "MYR": "Malaysian Ringgit",
    "MZN": "Mozambican Metical",
    "NAD": "Namibian Dollar",
    "NGN": "Nigerian Naira",
    "NIO": "Nicaraguan Córdoba",
    "NOK": "Norwegian Krone",
    "NPR": "Nepalese Rupee",
    "NZD": "New Zealand Dollar",
    "OMR": "Omani Rial",
    "PAB": "Panamanian Balboa",
    "PEN": "Peruvian Sol",
    "PGK": "Papua New Guinean Kina",
    "PHP": "Philippine Peso",
    "PKR": "Pakistani Rupee",
    "PLN": "Polish Zloty",
    "PYG": "Paraguayan Guarani",
    "QAR": "Qatari Riyal",
    "RON": "Romanian Leu",
    "RSD": "Serbian Dinar",
    "RUB": "Russian Ruble",
    "RWF": "Rwandan Franc",
    "SAR": "Saudi Riyal",
    "SBD": "Solomon Islands Dollar",
    "SCR": "Seychellois Rupee",
    "SDG": "Sudanese Pound",
    "SEK": "Swedish Krona",
    "SGD": "Singapore Dollar",
    "SHP": "Saint Helena Pound",
    "SLE": "Sierra Leonean Leone",
    "SOS": "Somali Shilling",
    "SRD": "Surinamese Dollar",
    "SSP": "South Sudanese Pound",
    "STN": "São Tomé and Príncipe Dobra",
    "SVC": "Salvadoran Colón",
    "SYP": "Syrian Pound",
    "SZL": "Swazi Lilangeni",
    "THB": "Thai Baht",
    "TJS": "Tajikistani Somoni",
    "TMT": "Turkmenistani Manat",
    "TND": "Tunisian Dinar",
    "TOP": "Tongan Paʻanga",
    "TRY": "Turkish Lira",
    "TTD": "Trinidad and Tobago Dollar",
    "TWD": "New Taiwan Dollar",
    "TZS": "Tanzanian Shilling",
    "UAH": "Ukrainian Hryvnia",
    "UGX": "Ugandan Shilling",
    "USD": "United States Dollar",
    "UYI": "Uruguayan Peso en Unidades Indexadas",
    "UYU": "Uruguayan Peso",
    "UZS": "Uzbekistani Som",
    "VED": "Venezuelan Bolívar Digital",
    "VEF": "Venezuelan Bolívar",
    "VND": "Vietnamese Dong",
    "VUV": "Vanuatu Vatu",
    "WST": "Samoan Tala",
    "XAF": "Central African CFA Franc",
    "XCD": "East Caribbean Dollar",
    "XCG": "Caribbean Guilder",
    "XDR": "Special Drawing Rights",
    "XOF": "West African CFA Franc",
    "XPF": "CFP Franc",
    "YER": "Yemeni Rial",
    "ZAR": "South African Rand",
    "ZMW": "Zambian Kwacha",
    "ZWL": "Zimbabwean Dollar",
    "NONE": "No Currency",
}
