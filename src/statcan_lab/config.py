"""Tablas y filtros por defecto.

Los productId vienen de las paginas oficiales de StatCan. Los nombres de dimensiones y
categorias de los filtros son la mejor suposicion: corre `describe <tabla>` despues del
primer `fetch` y ajusta aca lo que no coincida (el codigo falla con un mensaje claro).
"""

LFS_PROVINCE = "14-10-0287-03"   # Labour force characteristics by province, monthly, SA
EI_REGULAR = "14-10-0011-01"     # EI beneficiaries (regular) by province, monthly, SA
LFS_IMMIGRANT = "14-10-0471-01"  # LFS por estatus migratorio, media movil 3 meses, con CMA
JVWS_RATIO = "14-10-0443-01"     # Job Vacancy and Wage Survey: unemployed per vacancy

TABLES = {
    LFS_PROVINCE: "LFS por provincia (desempleados, tasa)",
    EI_REGULAR: "Beneficiarios de EI regular",
    LFS_IMMIGRANT: "LFS por estatus migratorio y CMA",
    JVWS_RATIO: "Ratio desempleados por vacante",
}

PROVINCES = {
    "Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia", "New Brunswick",
    "Quebec", "Ontario", "Manitoba", "Saskatchewan", "Alberta", "British Columbia",
}

# --- Filtros (regex de columna -> regex de valor; '?' = opcional) ---
F_LFS_UNEMPLOYED = {
    "^Labour force char": r"^Unemployment$",
    "?^Statistics$": r"^Estimate$",
    "?^Data type$": r"^Seasonally adjusted$",
    "?^Gender|^Sex": r"^Total|^Both",
    "?^Age": r"^15 years and over$",
}
F_LFS_RATE = {**F_LFS_UNEMPLOYED, "^Labour force char": r"^Unemployment rate$"}

F_EI_REGULAR = {
    "?^Sex|^Gender": r"^Total|^Both",
    "?^Age": r"^15 years and over$|^Total",
    "?^Declared": r"^Total",
}

F_IMMIGRANT_RATE = {
    "^Labour force char": r"^Unemployment rate$",
    "?^Gender|^Sex": r"^Total|^Both",
    "?^Age": r"^15 years and over$",
    "?^Statistics$": r"^Estimate$",
    "?^Data type$": r"^Unadjusted|^Three-month",
}
K_IMMIGRANT_STATUS = r"^Immigrant"

F_JVWS_RATIO = {"?^Statistics|^Data type": r"ratio"}
K_EDUCATION = r"^Education|^Level"
