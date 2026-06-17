"""Seed demo data: real WC2026 teams + simulated historical matches + Elo ratings."""
import sqlite3
import random
from datetime import datetime, timedelta

random.seed(42)
DB = "copa.db"

TEAMS = [
    (1, "Brasil",      "BRA", "Brazil",      1900),
    (2, "Argentina",   "ARG", "Argentina",   1870),
    (3, "França",      "FRA", "France",      1850),
    (4, "Inglaterra",  "ENG", "England",     1820),
    (5, "Espanha",     "ESP", "Spain",       1800),
    (6, "Alemanha",    "GER", "Germany",     1780),
    (7, "Países Baixos","NED","Netherlands", 1760),
    (8, "Portugal",    "POR", "Portugal",    1750),
    (9, "Uruguai",     "URU", "Uruguay",     1680),
    (10,"Colombia",    "COL", "Colombia",    1650),
    (11,"México",      "MEX", "Mexico",      1620),
    (12,"Estados Unidos","USA","United States",1600),
    (13,"Japão",       "JPN", "Japan",       1580),
    (14,"Marrocos",    "MAR", "Morocco",     1560),
    (15,"Senegal",     "SEN", "Senegal",     1540),
    (16,"Equador",     "ECU", "Ecuador",     1500),
]

ELO_SNAPSHOTS = [
    # (code, year, elo)
    ("BRA", 2022, 1920), ("BRA", 2023, 1910), ("BRA", 2024, 1905), ("BRA", 2025, 1900),
    ("ARG", 2022, 1900), ("ARG", 2023, 1890), ("ARG", 2024, 1880), ("ARG", 2025, 1870),
    ("FRA", 2022, 1870), ("FRA", 2023, 1860), ("FRA", 2024, 1855), ("FRA", 2025, 1850),
    ("ENG", 2022, 1840), ("ENG", 2023, 1830), ("ENG", 2024, 1825), ("ENG", 2025, 1820),
    ("ESP", 2022, 1820), ("ESP", 2023, 1810), ("ESP", 2024, 1805), ("ESP", 2025, 1800),
    ("GER", 2022, 1800), ("GER", 2023, 1790), ("GER", 2024, 1785), ("GER", 2025, 1780),
    ("NED", 2022, 1780), ("NED", 2023, 1770), ("NED", 2024, 1765), ("NED", 2025, 1760),
    ("POR", 2022, 1760), ("POR", 2023, 1755), ("POR", 2024, 1752), ("POR", 2025, 1750),
    ("URU", 2022, 1700), ("URU", 2023, 1690), ("URU", 2024, 1685), ("URU", 2025, 1680),
    ("COL", 2022, 1670), ("COL", 2023, 1660), ("COL", 2024, 1655), ("COL", 2025, 1650),
    ("MEX", 2022, 1640), ("MEX", 2023, 1630), ("MEX", 2024, 1625), ("MEX", 2025, 1620),
    ("USA", 2022, 1610), ("USA", 2023, 1605), ("USA", 2024, 1602), ("USA", 2025, 1600),
    ("JPN", 2022, 1590), ("JPN", 2023, 1585), ("JPN", 2024, 1582), ("JPN", 2025, 1580),
    ("MAR", 2022, 1570), ("MAR", 2023, 1565), ("MAR", 2024, 1562), ("MAR", 2025, 1560),
    ("SEN", 2022, 1550), ("SEN", 2023, 1545), ("SEN", 2024, 1542), ("SEN", 2025, 1540),
    ("ECU", 2022, 1510), ("ECU", 2023, 1505), ("ECU", 2024, 1502), ("ECU", 2025, 1500),
]

WC2026_MATCHES = [
    # (home_id, away_id, home_goals, away_goals)  — fase de grupos simulada
    (1, 16, 3, 0),  # Brasil 3x0 Equador
    (2, 15, 2, 1),  # Argentina 2x1 Senegal
    (3, 14, 1, 1),  # França 1x1 Marrocos
    (4, 13, 2, 2),  # Inglaterra 2x2 Japão
    (5, 12, 3, 1),  # Espanha 3x1 EUA
    (6, 11, 2, 0),  # Alemanha 2x0 México
    (7, 10, 1, 2),  # Países Baixos 1x2 Colombia
    (8, 9,  2, 1),  # Portugal 2x1 Uruguai
    (1, 15, 2, 0),  # Brasil 2x0 Senegal
    (2, 16, 4, 0),  # Argentina 4x0 Equador
]

con = sqlite3.connect(DB)

# Teams
con.executemany(
    "INSERT OR REPLACE INTO teams (id, name, code, country, is_wc2026) VALUES (?,?,?,?,1)",
    [(t[0], t[1], t[2], t[3]) for t in TEAMS]
)

# Elo ratings
for code, year, elo in ELO_SNAPSHOTS:
    con.execute(
        "INSERT OR REPLACE INTO elo_ratings (team_code, snapshot_date, elo) VALUES (?,?,?)",
        (code, f"{year}-12-31", elo)
    )

# Historical fixtures (2020-2025): random matchups to train Modelo A
start = datetime(2020, 1, 1)
fid = 1000
for _ in range(800):
    day_offset = random.randint(0, 365*5)
    date = start + timedelta(days=day_offset)
    h, a = random.sample(TEAMS, 2)
    elo_h = next(e for c, y, e in ELO_SNAPSHOTS if c == h[2] and y == 2025)
    elo_a = next(e for c, y, e in ELO_SNAPSHOTS if c == a[2] and y == 2025)
    # Poisson-sampled goals weighted by Elo
    import math
    lam_h = 1.4 * (10 ** ((elo_h - elo_a) / 800))
    lam_a = 1.1 * (10 ** ((elo_a - elo_h) / 800))
    import numpy as np
    hg = int(np.random.poisson(max(0.3, lam_h)))
    ag = int(np.random.poisson(max(0.3, lam_a)))
    con.execute(
        """INSERT OR IGNORE INTO fixtures
           (id, league_id, season, date_utc, is_neutral, status,
            home_team_id, away_team_id, home_goals, away_goals, is_wc2026)
           VALUES (?,1,?,?,1,'FT',?,?,?,?,0)""",
        (fid, date.year, date.isoformat(), h[0], a[0], hg, ag)
    )
    fid += 1

# WC2026 fixtures
for i, (h, a, hg, ag) in enumerate(WC2026_MATCHES, start=2000):
    date = datetime(2026, 6, 11) + timedelta(days=i*3)
    con.execute(
        """INSERT OR REPLACE INTO fixtures
           (id, league_id, season, date_utc, is_neutral, status,
            home_team_id, away_team_id, home_goals, away_goals, is_wc2026)
           VALUES (?,1,2026,?,1,'FT',?,?,?,?,1)""",
        (i, date.isoformat(), h, a, hg, ag)
    )

con.commit()
con.close()
print("✓ Demo data seeded: 16 teams, 800 historical matches, 10 WC2026 matches")
