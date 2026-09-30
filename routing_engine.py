import database

# Simulated FX Rates table (Base currency to Target currency)
FX_RATES = {
    ('INR', 'USD'): 0.0114,  # ~ 88.00 INR / USD
    ('USD', 'INR'): 88.00,
    ('INR', 'GBP'): 0.0085,  # ~ 118.00 INR / GBP
    ('GBP', 'INR'): 118.00,
    ('INR', 'EUR'): 0.0097,  # ~ 103.00 INR / EUR
    ('EUR', 'INR'): 103.00,
    ('USD', 'EUR'): 0.92,
    ('EUR', 'USD'): 1.09,
    ('USD', 'GBP'): 0.79,
    ('GBP', 'USD'): 1.27
}

def get_fx_rate(source_curr, dest_curr):
    """Retrieve simulated FX exchange rate."""
    if source_curr.upper() == dest_curr.upper():
        return 1.0
    return FX_RATES.get((source_curr.upper(), dest_curr.upper()), 1.0)

def select_best_bank(amount, source_currency, destination_currency):
    """
    Evaluates all registered banks in SQLite database.
    Checks eligibility (active status, user approval, liquidity, transaction limits).
    Calculates route score based on liquidity, FX spread, and processing latency.
    Selects the highest scoring eligible bank.
    
    Returns dict containing selected bank details, cost calculations, and route evaluation records.
    """
    all_banks = database.get_all_banks()
    evaluations = []
    eligible_banks = []

    for bank in all_banks:
        bank_id = bank['bank_id']
        bank_name = bank['bank_name']
        liquidity = bank['liquidity']
        fx_spread = bank['fx_spread']
        latency = bank['latency']
        limit = bank['transaction_limit']
        status = bank['status']
        user_approval = bank['approval_status']
        user_account = bank['user_account_status']

        is_eligible = True
        reasons = []

        # Eligibility checks
        if status != 'Active':
            is_eligible = False
            reasons.append("Bank account is inactive.")

        if user_approval != 'Approved':
            is_eligible = False
            reasons.append("Bank institution pending admin approval.")

        if user_account != 'Active':
            is_eligible = False
            reasons.append("Bank user account disabled.")

        if liquidity < amount:
            is_eligible = False
            reasons.append(f"Insufficient liquidity (Available: ₹{liquidity:,.2f}, Required: ₹{amount:,.2f}).")

        if limit > 0 and amount > limit:
            is_eligible = False
            reasons.append(f"Transaction exceeds bank limit (Limit: ₹{limit:,.2f}, Required: ₹{amount:,.2f}).")

        score = 0.0
        if is_eligible:
            # Score formula: 100 - (FX Spread * 15) - (Latency / 20) + Liquidity Bonus
            fx_penalty = fx_spread * 15.0
            latency_penalty = latency / 20.0
            liquidity_ratio = liquidity / amount if amount > 0 else 1.0
            liquidity_bonus = min(10.0, liquidity_ratio * 2.0)

            score = round(max(1.0, 100.0 - fx_penalty - latency_penalty + liquidity_bonus), 2)
            reason_str = f"Eligible route. Sufficient liquidity (₹{liquidity:,.2f}), low latency ({latency}ms), FX spread ({fx_spread}%)."
            
            eligible_banks.append({
                'bank': bank,
                'score': score
            })
        else:
            reason_str = "Not eligible: " + " ".join(reasons)

        evaluations.append({
            'bank_id': bank_id,
            'bank_name': bank_name,
            'liquidity': liquidity,
            'fx_spread': fx_spread,
            'latency': latency,
            'score': score,
            'selected': 0,
            'reason': reason_str,
            'eligible': is_eligible
        })

    if not eligible_banks:
        return {
            'selected_bank': None,
            'fx_rate': 0.0,
            'fx_cost': 0.0,
            'processing_fee': 0.0,
            'total_cost': 0.0,
            'route_evaluations': evaluations,
            'reason': 'No eligible bank available for this transaction.'
        }

    # Sort eligible banks by score descending
    eligible_banks.sort(key=lambda x: x['score'], reverse=True)
    best_item = eligible_banks[0]
    best_bank = best_item['bank']

    # Update selected flag in evaluations
    for ev in evaluations:
        if ev['bank_id'] == best_bank['bank_id']:
            ev['selected'] = 1
            ev['reason'] += " [SELECTED - Best Route Score]"

    # Calculate financial costs
    fx_rate = get_fx_rate(source_currency, destination_currency)
    fx_cost = round(amount * (best_bank['fx_spread'] / 100.0), 2)
    processing_fee = round(amount * 0.001, 2)  # 0.1% processing fee
    total_cost = round(fx_cost + processing_fee, 2)

    return {
        'selected_bank': best_bank,
        'fx_rate': fx_rate,
        'fx_cost': fx_cost,
        'processing_fee': processing_fee,
        'total_cost': total_cost,
        'route_evaluations': evaluations
    }
