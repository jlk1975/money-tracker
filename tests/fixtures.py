"""
fixtures.py — Sample bill definitions used by seed.py and tests.

Instances are generated from these definitions via db.generate_month_instances().
"""

SAMPLE_DEFINITIONS = [
    # ── Monthly bills ──────────────────────────────────────────────────────────
    {"account": "UWBC",       "description": "Jason & Heather SFB LIFE INS. POLICIES IN FORCE.", "frequency": "Monthly", "typical_amount": 442.97, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Mortgage [AUTO PAY IS ON]",                         "frequency": "Monthly", "typical_amount": 602.13, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Parking",                                            "frequency": "Monthly", "typical_amount": 145.00, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "BOAC1",      "description": "$80.64 - Atrium Health AccessOne Heather Imaging Bill", "frequency": "Monthly", "typical_amount":  70.00, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Heather Life Insurance Policy 1",                   "frequency": "Monthly", "typical_amount":  36.76, "due_day":  6, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Natural Gas Bill",                                   "frequency": "Monthly", "typical_amount":  63.00, "due_day":  7, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Internet & Phone",                                   "frequency": "Monthly", "typical_amount": 134.05, "due_day": 13, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "Sam's Card", "description": "Trupanion - Dog Health and Dental Insurance",        "frequency": "Monthly", "typical_amount":  64.67, "due_day": 13, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "BofA Credit Card",                                   "frequency": "Monthly", "typical_amount": 131.00, "due_day": 15, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "City Utilities [Manual Pay]",                        "frequency": "Monthly", "typical_amount": 219.84, "due_day": 15, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "17-SoFi 10k / 5yr / 12.950% Truck Loan (60 payments)", "frequency": "Monthly", "typical_amount": 283.24, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Auto Insurance",                                     "frequency": "Monthly", "typical_amount": 408.79, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Cell Phone Bill",                                    "frequency": "Monthly", "typical_amount": 327.54, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Jason EDJ Life Ins",                                 "frequency": "Monthly", "typical_amount":  75.60, "due_day": 21, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "CITI Flex Payment",                                  "frequency": "Monthly", "typical_amount": 282.00, "due_day": 21, "months_active": "", "adhoc_month": "", "notes": ""},
    {"account": "UWBC",       "description": "Monthly Subscriptions (Various and too many of them)", "frequency": "Monthly", "typical_amount": 200.00, "due_day": 21, "months_active": "", "adhoc_month": "", "notes": ""},
    # ── AdHoc bills ────────────────────────────────────────────────────────────
    {"account": "UWBC",       "description": "Discover Card Payoff",                               "frequency": "AdHoc",   "typical_amount":   0.00, "due_day": 21, "months_active": "", "adhoc_month": "2026-06", "notes": ""},
    {"account": "UWBC",       "description": "AMEX card payoff (Carson pressure washer)",          "frequency": "AdHoc",   "typical_amount": 669.50, "due_day": 21, "months_active": "", "adhoc_month": "2026-06", "notes": ""},
    {"account": "UWBC",       "description": "Sam's Card Payoff",                                  "frequency": "AdHoc",   "typical_amount":   0.00, "due_day": 21, "months_active": "", "adhoc_month": "2026-06", "notes": ""},
]

# June 2026 total: 16 monthly ($3,486.59) + 3 adhoc ($669.50) = $4,156.09
SAMPLE_JUNE_TOTAL = 4156.09
# May 2026 total: 16 monthly bills only (no adhoc) = $3,486.59
SAMPLE_MAY_TOTAL = 3486.59
