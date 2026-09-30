# LiquidityRouter - Adaptive Payment Routing System

LiquidityRouter is a simulated international payment routing web application built with Python, Flask, SQLite3, Jinja2, HTML, CSS, and Bootstrap.

It demonstrates dynamic, adaptive bank selection for international transfers based on real-time liquidity, FX spread, latency, transaction limits, and compliance checks.

---

## Technical Stack

- **Backend**: Python 3, Flask
- **Database**: SQLite3 (native Python `sqlite3` driver)
- **Frontend**: HTML5, CSS3, Bootstrap 5, Jinja2 Templating
- **Authentication**: Flask Session-based Role Management
- **Architecture**: Monolithic Flask App with SQLite persistence

---

## Key Features

1. **Treasury Management**:
   - Submit international payment requests (Amount, Source, Destination).
   - View real-time transaction routing results, FX costs, processing fees, and bank route evaluations.
   - Profile management and transaction history.
2. **Bank Portal**:
   - Monitor assigned transactions.
   - Update operational metrics (Liquidity, FX Spread, Latency, Transaction Limit, Active Status).
   - Demonstrate real-time adaptive routing when metrics change.
3. **Admin Panel**:
   - Manage Bank Users (Approve, Reject, Activate, Deactivate).
   - Manage User Accounts.
   - Monitor system-wide transactions.
   - Configure Compliance Rules.
   - View comprehensive Audit Logs.
4. **Adaptive Routing Engine**:
   - Evaluates active approved banks.
   - Performs compliance and eligibility checks.
   - Calculates route scores based on liquidity, FX spread, and latency.
   - Dynamically selects the best eligible bank.

---

## How to Run the Application

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the Application**:
   ```bash
   python app.py
   ```

3. **Access the Application**:
   Open browser at: `http://127.0.0.1:5000`

---

## Default Credentials

### Admin Account
- **Email**: `admin@liquidity.com`
- **Password**: `admin123`

### Demo Treasury Account
- **Email**: `treasury@demo.com`
- **Password**: `treasury123`

### Demo Bank Accounts
- **Bank A**: `banka@demo.com` / `bank123`
- **Bank B**: `bankb@demo.com` / `bank123`
- **Bank C**: `bankc@demo.com` / `bank123`

---

## Dynamic Routing Demo Flow (Hackathon Scenario)

1. **Initial State**:
   - Log in as **Treasury** (`treasury@demo.com` / `treasury123`).
   - Create a payment: **₹10,00,000** from **India (INR)** to **USA (USD)**.
   - Observe that **Global Bank A** is selected due to its high score (Liquidity: ₹25,00,000, FX Spread: 0.35%, Latency: 120ms).

2. **Simulating Route Metric Change**:
   - Log in as **Bank A** (`banka@demo.com` / `bank123`).
   - Go to **Update Values**.
   - Change Liquidity to **₹2,00,000**, FX Spread to **1.20%**, Latency to **1800ms**.
   - Click **Update**.

3. **Adaptive Routing Execution**:
   - Log in back as **Treasury** (`treasury@demo.com` / `treasury123`).
   - Submit another payment: **₹10,00,000** from **India (INR)** to **USA (USD)**.
   - The router evaluates **Bank A** and rejects it because its liquidity (₹2,00,000) is less than the transaction amount (₹10,00,000).
   - The router selects **Global Bank B** instead.
   - View **Transaction Details** to verify route score breakdown and rejection rationale.

4. **Audit Trail Verification**:
   - Log in as **Admin** (`admin@liquidity.com` / `admin123`).
   - Open **Audit Logs** to see complete transparent logging of route evaluations and events.
