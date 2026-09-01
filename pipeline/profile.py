#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engagement frame parameters (synthetic, for the bundled demo scenario).

These are fixed demo constants — the fictional buyer, the stake percentage, and
the baseline date used to evaluate licence expiry etc. They are NOT extracted
from the data room; the target-company name and every fact/ratio/region ARE
extracted from the data room at runtime (see extract.py / analyze.py).

Keeping them in one explicit, documented module (instead of string literals
buried in render.py) makes the "input vs. constant" boundary auditable and
keeps output free of instance-specific proper nouns.
"""
# Fictional buyer used in the bundled demo scenario (synthetic; not a real entity).
ACQUIRER = "砚光数字产业投资（上海）有限公司"

# Fictional stake percentage in the bundled demo scenario.
DEAL_PCT = 65

# Baseline ("as-of") date for the bundled demo scenario.
BASELINE_DATE = "2026-07-15"

# No project code is ever hardcoded.
PROJECT_LABEL = ""
