# Ceny v centoch (vrátane DPH).
PRICES_CENTS_ONE_TIME = {
    "convert_docx": 100,  # 1.00 €
    "protect":      30,   # 0.30 €
    "ocr_text":     20,   # 0.20 €
}

# Percento pre charitu podľa typu platby / plánu (ako desatinné čísla).
CHARITY_PERCENT = {
    "one_time": 0.15,  # 15 %
    "free":     0.15,  # fallback pre free
    "premium":  0.20,  # 20 %
    "pro":      0.25,  # 25 %
}

def charity_percent_for_plan(plan: str) -> float:
    return CHARITY_PERCENT.get(plan, CHARITY_PERCENT["one_time"])

# Bezpečnostná sieťka: ak by sa niekde omylom používala táto mapa,
# je tiež vo float formáte – takže výpočet ostane správny.
CHARITY_PERCENT_BY_PLAN = {
    "free":     0.15,
    "one_time": 0.15,
    "plus":     0.05,
    "premium":  0.07,
    "pro":      0.10,
}
