"""
fixtures.py — Sample bill definitions used by seed.py and tests.

Instances are generated from these definitions via db.generate_month_instances().
"""

SAMPLE_DEFINITIONS = [
    # ── Monthly bills ──────────────────────────────────────────────────────────
    {"description": "Life Insurance Policy",         "frequency": "Monthly", "typical_amount": 442.97, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Mortgage [AUTO PAY IS ON]",     "frequency": "Monthly", "typical_amount": 602.13, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Parking",                       "frequency": "Monthly", "typical_amount": 145.00, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Medical Payment Plan",          "frequency": "Monthly", "typical_amount":  70.00, "due_day":  4, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Spouse Life Insurance",         "frequency": "Monthly", "typical_amount":  36.76, "due_day":  6, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Natural Gas Bill",              "frequency": "Monthly", "typical_amount":  63.00, "due_day":  7, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Internet & Phone",              "frequency": "Monthly", "typical_amount": 134.05, "due_day": 13, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Pet Insurance",                 "frequency": "Monthly", "typical_amount":  64.67, "due_day": 13, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Credit Card 1",                 "frequency": "Monthly", "typical_amount": 131.00, "due_day": 15, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "City Utilities [Manual Pay]",   "frequency": "Monthly", "typical_amount": 219.84, "due_day": 15, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Vehicle Loan",                  "frequency": "Monthly", "typical_amount": 283.24, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Auto Insurance",                "frequency": "Monthly", "typical_amount": 408.79, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Cell Phone Bill",               "frequency": "Monthly", "typical_amount": 327.54, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Term Life Insurance",           "frequency": "Monthly", "typical_amount":  75.60, "due_day": 21, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Flex Payment Plan",             "frequency": "Monthly", "typical_amount": 282.00, "due_day": 21, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Monthly Subscriptions",         "frequency": "Monthly", "typical_amount": 200.00, "due_day": 21, "months_active": "", "adhoc_month": "", "notes": ""},
    # ── AdHoc bills ────────────────────────────────────────────────────────────
    {"description": "Credit Card Payoff A",          "frequency": "AdHoc",   "typical_amount":   0.00, "due_day": 21, "months_active": "", "adhoc_month": "2026-06", "notes": ""},
    {"description": "Credit Card Payoff B",          "frequency": "AdHoc",   "typical_amount": 669.50, "due_day": 21, "months_active": "", "adhoc_month": "2026-06", "notes": ""},
    {"description": "Store Card Payoff",             "frequency": "AdHoc",   "typical_amount":   0.00, "due_day": 21, "months_active": "", "adhoc_month": "2026-06", "notes": ""},
]

# June 2026 total: 16 monthly ($3,486.59) + 3 adhoc ($669.50) = $4,156.09
SAMPLE_JUNE_TOTAL = 4156.09
# May 2026 total: 16 monthly bills only (no adhoc) = $3,486.59
SAMPLE_MAY_TOTAL = 3486.59
