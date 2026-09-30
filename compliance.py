import database

RESTRICTED_COUNTRIES = ['north korea', 'iran', 'syria', 'cuba', 'sudan']

def check_transaction_compliance(amount, source_country, destination_country, source_currency, destination_currency):
    """
    Evaluates a proposed transaction against active compliance rules stored in SQLite.
    Returns tuple: (passed: bool, reason: str)
    """
    if amount <= 0:
        return False, "Transaction amount must be greater than zero."

    # Retrieve active compliance rules from database
    rules = database.get_compliance_rules()

    for rule in rules:
        if rule['status'] != 'Active':
            continue

        rule_type = rule['rule_type']
        limit_val = rule['limit_value']

        if rule_type == 'MAX_AMOUNT' and limit_val > 0:
            if amount > limit_val:
                return False, f"Blocked: Transaction amount (₹{amount:,.2f}) exceeds configured maximum limit of ₹{limit_val:,.2f} ({rule['rule_name']})."

        elif rule_type == 'LRS_LIMIT' and limit_val > 0:
            if amount > limit_val:
                return False, f"Blocked: Transaction amount (₹{amount:,.2f}) exceeds LRS single transfer limit of ₹{limit_val:,.2f} ({rule['rule_name']})."

        elif rule_type == 'RESTRICTED_CORRIDOR':
            if destination_country.strip().lower() in RESTRICTED_COUNTRIES:
                return False, f"Blocked: Destination country '{destination_country}' is listed under restricted compliance corridors ({rule['rule_name']})."

    return True, "Compliance checks passed successfully."
