from flask import Flask, render_template, request, redirect, url_for, session, flash
import database
import compliance
import routing_engine

app = Flask(__name__)
app.secret_key = 'liquidity_router_secret_key'

# Initialize database schema, default admin, demo banks and compliance rules on startup
with app.app_context():
    database.create_tables()
    database.create_admin()
    database.create_demo_banks()

def get_current_user():
    """Retrieve logged in user record from database using session user_id."""
    if "user_id" in session:
        return database.get_user_by_id(session["user_id"])
    return None

# ==========================================
# AUTHENTICATION & CORE ROUTES
# ==========================================

@app.route("/")
def index():
    if "user_id" in session:
        role = session.get("role")
        if role == "treasury":
            return redirect(url_for("treasury_dashboard"))
        elif role == "bank":
            return redirect(url_for("bank_dashboard"))
        elif role == "admin":
            return redirect(url_for("admin_dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = database.get_user_by_email(email)

        if not user or user["password"] != password:
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        if user["account_status"] != "Active":
            flash("Your account is inactive. Please contact system administrator.", "error")
            return redirect(url_for("login"))

        if user["approval_status"] == "Pending":
            flash("Your bank account is awaiting admin approval.", "warning")
            return redirect(url_for("login"))

        if user["approval_status"] == "Rejected":
            flash("Your account registration was rejected by admin.", "error")
            return redirect(url_for("login"))

        # Set session values
        session["user_id"] = user["user_id"]
        session["role"] = user["role"]
        session["name"] = user["name"]
        session["email"] = user["email"]

        flash(f"Welcome back, {user['name']}!", "success")

        if user["role"] == "treasury":
            return redirect(url_for("treasury_dashboard"))
        elif user["role"] == "bank":
            return redirect(url_for("bank_dashboard"))
        elif user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        role = request.form.get("role", "").strip()

        if role not in ["treasury", "bank"]:
            flash("Invalid role selected.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        existing_user = database.get_user_by_email(email)
        if existing_user:
            flash("Email address is already registered.", "error")
            return redirect(url_for("register"))

        approval_status = "Approved" if role == "treasury" else "Pending"
        
        user_id = database.create_user(
            name=name,
            email=email,
            password=password,
            phone=phone,
            role=role,
            approval_status=approval_status,
            account_status="Active"
        )

        if role == "bank":
            # Create bank record for new bank user
            database.create_bank(
                user_id=user_id,
                bank_name=name,
                country="India",
                currency="INR",
                liquidity=1000000,
                fx_spread=0.50,
                latency=200,
                transaction_limit=500000,
                status="Active"
            )
            flash("Registration successful! Your bank account requires Admin approval before login.", "warning")
        else:
            flash("Registration successful! You can now login.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))

# ==========================================
# TREASURY ROUTES
# ==========================================

@app.route("/treasury_dashboard")
def treasury_dashboard():
    if "user_id" not in session or session.get("role") != "treasury":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    user = get_current_user()
    transactions = database.get_user_transactions(session["user_id"])

    total_count = len(transactions)
    completed_count = sum(1 for t in transactions if t["status"] == "Completed")
    rerouted_count = sum(1 for t in transactions if t["status"] == "Rerouted")
    blocked_count = sum(1 for t in transactions if t["status"] in ["Blocked", "Failed"])

    return render_template(
        "treasury_dashboard.html",
        user=user,
        transactions=transactions,
        total_count=total_count,
        completed_count=completed_count,
        rerouted_count=rerouted_count,
        blocked_count=blocked_count
    )

@app.route("/new_transaction", methods=["GET", "POST"])
def new_transaction():
    if "user_id" not in session or session.get("role") != "treasury":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            flash("Transaction amount must be a valid number.", "error")
            return redirect(url_for("new_transaction"))

        source_country = request.form.get("source_country", "India").strip()
        destination_country = request.form.get("destination_country", "USA").strip()
        source_currency = request.form.get("source_currency", "INR").strip()
        destination_currency = request.form.get("destination_currency", "USD").strip()

        if amount <= 0:
            flash("Transaction amount must be greater than zero.", "error")
            return redirect(url_for("new_transaction"))

        # STEP 1: Compliance Check
        passed, compliance_reason = compliance.check_transaction_compliance(
            amount, source_country, destination_country, source_currency, destination_currency
        )

        if not passed:
            # Create transaction record as Blocked
            tx_id = database.create_transaction(
                user_id=session["user_id"],
                amount=amount,
                source_country=source_country,
                destination_country=destination_country,
                source_currency=source_currency,
                destination_currency=destination_currency,
                selected_bank_id=None,
                status="Blocked"
            )

            database.add_audit_log(
                transaction_id=tx_id,
                event="TRANSACTION_BLOCKED",
                reason=compliance_reason
            )

            flash(compliance_reason, "error")
            return redirect(url_for("transaction_details", transaction_id=tx_id))

        # STEP 2: Routing Engine Selection
        routing_res = routing_engine.select_best_bank(amount, source_currency, destination_currency)

        selected_bank = routing_res["selected_bank"]
        evaluations = routing_res["route_evaluations"]

        if not selected_bank:
            # No eligible bank available
            tx_id = database.create_transaction(
                user_id=session["user_id"],
                amount=amount,
                source_country=source_country,
                destination_country=destination_country,
                source_currency=source_currency,
                destination_currency=destination_currency,
                selected_bank_id=None,
                status="Failed"
            )

            # Store route evaluation logs
            for ev in evaluations:
                database.save_transaction_route(
                    transaction_id=tx_id,
                    bank_id=ev["bank_id"],
                    liquidity=ev["liquidity"],
                    fx_spread=ev["fx_spread"],
                    latency=ev["latency"],
                    score=ev["score"],
                    selected=ev["selected"],
                    reason=ev["reason"]
                )

            database.add_audit_log(
                transaction_id=tx_id,
                event="TRANSACTION_FAILED",
                reason="No eligible bank available for transaction specifications."
            )

            flash("No eligible bank available for this transaction.", "error")
            return redirect(url_for("transaction_details", transaction_id=tx_id))

        # STEP 3: Successful Route Selection & Cost Computation
        tx_id = database.create_transaction(
            user_id=session["user_id"],
            amount=amount,
            source_country=source_country,
            destination_country=destination_country,
            source_currency=source_currency,
            destination_currency=destination_currency,
            selected_bank_id=selected_bank["bank_id"],
            fx_rate=routing_res["fx_rate"],
            fx_cost=routing_res["fx_cost"],
            processing_fee=routing_res["processing_fee"],
            total_cost=routing_res["total_cost"],
            status="Completed"
        )

        # Store route evaluations
        for ev in evaluations:
            database.save_transaction_route(
                transaction_id=tx_id,
                bank_id=ev["bank_id"],
                liquidity=ev["liquidity"],
                fx_spread=ev["fx_spread"],
                latency=ev["latency"],
                score=ev["score"],
                selected=ev["selected"],
                reason=ev["reason"]
            )

        # Add audit logs
        database.add_audit_log(
            transaction_id=tx_id,
            event="TRANSACTION_CREATED",
            reason=f"Treasury created international transfer of ₹{amount:,.2f} from {source_country} to {destination_country}."
        )

        selected_ev = next((ev for ev in evaluations if ev["bank_id"] == selected_bank["bank_id"]), None)
        score_val = selected_ev["score"] if selected_ev else 0.0

        database.add_audit_log(
            transaction_id=tx_id,
            event="ROUTE_SELECTED",
            new_bank_id=selected_bank["bank_id"],
            reason=f"Selected {selected_bank['bank_name']} with effective route score of {score_val}."
        )

        flash(f"Payment routed successfully via {selected_bank['bank_name']}!", "success")
        return redirect(url_for("transaction_details", transaction_id=tx_id))

    return render_template("new_transaction.html")

@app.route("/my_transactions")
def my_transactions():
    if "user_id" not in session or session.get("role") != "treasury":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    transactions = database.get_user_transactions(session["user_id"])
    return render_template("my_transactions.html", transactions=transactions)

@app.route("/transaction_details/<int:transaction_id>")
def transaction_details(transaction_id):
    if "user_id" not in session:
        flash("Please log in to view transaction details.", "error")
        return redirect(url_for("login"))

    transaction = database.get_transaction_by_id(transaction_id)
    if not transaction:
        flash("Transaction not found.", "error")
        return redirect(url_for("index"))

    # Role authorization check
    user_role = session.get("role")
    user_id = session.get("user_id")

    if user_role == "treasury" and transaction["user_id"] != user_id:
        flash("Unauthorized access to transaction details.", "error")
        return redirect(url_for("treasury_dashboard"))

    if user_role == "bank":
        bank = database.get_bank_by_user_id(user_id)
        if not bank or transaction["selected_bank_id"] != bank["bank_id"]:
            flash("Unauthorized access to transaction details.", "error")
            return redirect(url_for("bank_dashboard"))

    routes = database.get_transaction_routes(transaction_id)
    selected_route = next((r for r in routes if r["selected"] == 1), None)

    return render_template(
        "transaction_details.html",
        transaction=transaction,
        routes=routes,
        selected_route=selected_route
    )

@app.route("/reroute_transaction/<int:transaction_id>", methods=["POST"])
def reroute_transaction(transaction_id):
    if "user_id" not in session or session.get("role") != "treasury":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    transaction = database.get_transaction_by_id(transaction_id)
    if not transaction or transaction["user_id"] != session["user_id"]:
        flash("Transaction not found.", "error")
        return redirect(url_for("treasury_dashboard"))

    # Re-evaluate bank routing
    routing_res = routing_engine.select_best_bank(
        transaction["amount"], transaction["source_currency"], transaction["destination_currency"]
    )

    new_bank = routing_res["selected_bank"]
    old_bank_id = transaction["selected_bank_id"]

    if new_bank and new_bank["bank_id"] != old_bank_id:
        database.update_transaction_status(
            transaction_id=transaction_id,
            status="Rerouted",
            selected_bank_id=new_bank["bank_id"],
            fx_rate=routing_res["fx_rate"],
            fx_cost=routing_res["fx_cost"],
            processing_fee=routing_res["processing_fee"],
            total_cost=routing_res["total_cost"]
        )

        database.add_audit_log(
            transaction_id=transaction_id,
            event="ROUTE_REROUTED",
            old_bank_id=old_bank_id,
            new_bank_id=new_bank["bank_id"],
            reason=f"Transaction TX{transaction_id} rerouted to {new_bank['bank_name']} due to metric changes."
        )

        flash(f"Transaction successfully rerouted to {new_bank['bank_name']}!", "success")
    else:
        flash("Current route remains optimal.", "info")

    return redirect(url_for("transaction_details", transaction_id=transaction_id))

@app.route("/treasury_profile", methods=["GET", "POST"])
def treasury_profile():
    if "user_id" not in session or session.get("role") != "treasury":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    user = get_current_user()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        conn = database.create_connection()
        conn.execute("UPDATE users SET name = ?, phone = ? WHERE user_id = ?", (name, phone, session["user_id"]))
        conn.commit()
        conn.close()

        session["name"] = name
        flash("Profile updated successfully!", "success")
        return redirect(url_for("treasury_profile"))

    return render_template("treasury_profile.html", user=user)

# ==========================================
# BANK ROUTES
# ==========================================

@app.route("/bank_dashboard")
def bank_dashboard():
    if "user_id" not in session or session.get("role") != "bank":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    user = get_current_user()
    bank = database.get_bank_by_user_id(session["user_id"])
    transactions = database.get_bank_transactions(bank["bank_id"]) if bank else []

    return render_template(
        "bank_dashboard.html",
        user=user,
        bank=bank,
        transactions=transactions
    )

@app.route("/update_bank", methods=["GET", "POST"])
def update_bank():
    if "user_id" not in session or session.get("role") != "bank":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    bank = database.get_bank_by_user_id(session["user_id"])
    if not bank:
        flash("Bank record not found.", "error")
        return redirect(url_for("bank_dashboard"))

    if request.method == "POST":
        try:
            liquidity = float(request.form.get("liquidity", 0))
            fx_spread = float(request.form.get("fx_spread", 0))
            latency = int(request.form.get("latency", 0))
            transaction_limit = float(request.form.get("transaction_limit", 0))
        except ValueError:
            flash("Invalid numerical values provided.", "error")
            return redirect(url_for("update_bank"))

        status = request.form.get("status", "Active").strip()

        database.update_bank(
            bank_id=bank["bank_id"],
            liquidity=liquidity,
            fx_spread=fx_spread,
            latency=latency,
            transaction_limit=transaction_limit,
            status=status
        )

        database.add_audit_log(
            transaction_id=None,
            event="BANK_UPDATED",
            old_bank_id=bank["bank_id"],
            reason=f"Bank {bank['bank_name']} updated parameters (Liquidity: ₹{liquidity:,.2f}, FX Spread: {fx_spread}%, Latency: {latency}ms, Limit: ₹{transaction_limit:,.2f}, Status: {status})."
        )

        flash("Bank operational metrics updated successfully!", "success")
        return redirect(url_for("bank_dashboard"))

    return render_template("update_bank.html", bank=bank)

@app.route("/bank_transactions")
def bank_transactions():
    if "user_id" not in session or session.get("role") != "bank":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    bank = database.get_bank_by_user_id(session["user_id"])
    transactions = database.get_bank_transactions(bank["bank_id"]) if bank else []
    return render_template("bank_transactions.html", bank=bank, transactions=transactions)

@app.route("/bank_profile", methods=["GET", "POST"])
def bank_profile():
    if "user_id" not in session or session.get("role") != "bank":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    user = get_current_user()
    bank = database.get_bank_by_user_id(session["user_id"])

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        conn = database.create_connection()
        conn.execute("UPDATE users SET name = ?, phone = ? WHERE user_id = ?", (name, phone, session["user_id"]))
        conn.commit()
        conn.close()

        session["name"] = name
        flash("Profile updated successfully!", "success")
        return redirect(url_for("bank_profile"))

    return render_template("bank_profile.html", user=user, bank=bank)

# ==========================================
# ADMIN ROUTES
# ==========================================

@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    all_banks = database.get_all_banks()
    all_users = database.get_all_users()
    all_transactions = database.get_all_transactions()

    total_banks = len(all_banks)
    active_banks = sum(1 for b in all_banks if b["status"] == "Active")
    treasury_users_count = sum(1 for u in all_users if u["role"] == "treasury")

    total_tx_count = len(all_transactions)
    completed_tx_count = sum(1 for t in all_transactions if t["status"] == "Completed")
    rerouted_tx_count = sum(1 for t in all_transactions if t["status"] == "Rerouted")
    blocked_tx_count = sum(1 for t in all_transactions if t["status"] in ["Blocked", "Failed"])

    return render_template(
        "admin_dashboard.html",
        total_banks=total_banks,
        active_banks=active_banks,
        treasury_users_count=treasury_users_count,
        total_tx_count=total_tx_count,
        completed_tx_count=completed_tx_count,
        rerouted_tx_count=rerouted_tx_count,
        blocked_tx_count=blocked_tx_count
    )

@app.route("/manage_banks")
def manage_banks():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    banks = database.get_all_banks()
    return render_template("manage_banks.html", banks=banks)

@app.route("/approve_bank/<int:user_id>", methods=["POST"])
def approve_bank(user_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.approve_bank(user_id)
    user = database.get_user_by_id(user_id)

    database.add_audit_log(
        transaction_id=None,
        event="BANK_APPROVED",
        reason=f"Admin approved bank user account: {user['email']}"
    )

    flash(f"Bank user {user['name']} approved successfully!", "success")
    return redirect(url_for("manage_banks"))

@app.route("/reject_bank/<int:user_id>", methods=["POST"])
def reject_bank(user_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.reject_bank(user_id)
    user = database.get_user_by_id(user_id)

    database.add_audit_log(
        transaction_id=None,
        event="BANK_REJECTED",
        reason=f"Admin rejected bank user account: {user['email']}"
    )

    flash(f"Bank user {user['name']} registration rejected.", "warning")
    return redirect(url_for("manage_banks"))

@app.route("/activate_bank/<int:bank_id>", methods=["POST"])
def activate_bank(bank_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.activate_bank(bank_id)
    flash("Bank activated successfully.", "success")
    return redirect(url_for("manage_banks"))

@app.route("/deactivate_bank/<int:bank_id>", methods=["POST"])
def deactivate_bank(bank_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.deactivate_bank(bank_id)
    flash("Bank deactivated successfully.", "warning")
    return redirect(url_for("manage_banks"))

@app.route("/manage_users")
def manage_users():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    users = database.get_all_users()
    return render_template("manage_users.html", users=users)

@app.route("/activate_user/<int:user_id>", methods=["POST"])
def activate_user(user_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.activate_user(user_id)
    flash("User account activated.", "success")
    return redirect(url_for("manage_users"))

@app.route("/deactivate_user/<int:user_id>", methods=["POST"])
def deactivate_user(user_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.deactivate_user(user_id)
    flash("User account deactivated.", "warning")
    return redirect(url_for("manage_users"))

@app.route("/transactions")
def transactions():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    all_txs = database.get_all_transactions()
    return render_template("transactions.html", transactions=all_txs)

@app.route("/compliance_rules", methods=["GET", "POST"])
def compliance_rules():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        rule_name = request.form.get("rule_name", "").strip()
        rule_type = request.form.get("rule_type", "MAX_AMOUNT").strip()
        try:
            limit_value = float(request.form.get("limit_value", 0))
        except ValueError:
            limit_value = 0.0

        if rule_name:
            database.add_compliance_rule(rule_name, rule_type, limit_value, "Active")
            flash("Compliance rule added successfully!", "success")
            return redirect(url_for("compliance_rules"))

    rules = database.get_compliance_rules()
    return render_template("compliance_rules.html", rules=rules)

@app.route("/activate_rule/<int:rule_id>", methods=["POST"])
def activate_rule(rule_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.activate_compliance_rule(rule_id)
    flash("Compliance rule activated.", "success")
    return redirect(url_for("compliance_rules"))

@app.route("/deactivate_rule/<int:rule_id>", methods=["POST"])
def deactivate_rule(rule_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    database.deactivate_compliance_rule(rule_id)
    flash("Compliance rule deactivated.", "warning")
    return redirect(url_for("compliance_rules"))

@app.route("/audit_logs")
def audit_logs():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    logs = database.get_audit_logs()
    return render_template("audit_logs.html", logs=logs)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
