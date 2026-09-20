# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
import re
# pyrefly: ignore [missing-import]
import pdfplumber

def categorize_narration(narration):
    """
    Assigns a category to transactions if missing in bank_statements.csv.
    """
    n = str(narration).upper()
    if any(k in n for k in ['GAS', 'FUEL', 'STATION', 'PETROL']):
        return 'Transport & Fuel'
    elif any(k in n for k in ['RECHARGE', 'BILL', 'ELECTRICITY', 'WATER', 'JIO', 'AIRTEL', 'PAYTMUP']):
        return 'Utilities'
    elif any(k in n for k in ['AMZN', 'AMAZON', 'FLIPKART', 'SHOPPING', 'FASHION']):
        return 'Shopping'
    elif any(k in n for k in ['NETFLIX', 'SPOTIFY', 'GPAY', 'ENTERTAINMENT', 'HOTSTAR', 'PRIME']):
        return 'Entertainment'
    elif any(k in n for k in ['FOOD', 'ZOMATO', 'SWIGGY', 'RESTAURANT', 'DINING']):
        return 'Food & Dining'
    elif any(k in n for k in ['ATM', 'CASH']):
        return 'Cash Withdrawal'
    else:
        return 'General / Transfers'

def load_and_clean_data(file_input):
    """
    Reads bank statements CSV or PDF and standardizes columns for pandas analysis.
    """
    df = pd.DataFrame()
    
    # 1. Safely extract filename (case-insensitive) to prevent routing errors
    filename = ""
    if isinstance(file_input, str):
        filename = file_input.lower()
    elif hasattr(file_input, 'name'):
        filename = file_input.name.lower()

    # 2. Route the file to the correct parser
    if filename.endswith('.pdf'):
        all_rows = []
        try:
            with pdfplumber.open(file_input) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_rows.extend(table)
            # Build DataFrame, setting the first extracted row as headers
            if all_rows and len(all_rows) > 1:
                df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        except Exception as e:
            print(f"PDF Parsing Error: {e}")
            return pd.DataFrame()
    else:
        # Default to CSV parser
        df = pd.read_csv(file_input)

    # If the file was empty or unreadable, stop here
    if df.empty:
        return df

    # 3. Standardize Column Names (Collision-Proof Mapping)
    col_mapping = {}
    mapped_targets = set()

    for col in df.columns:
        col_lower = str(col).lower()
        
        # Only map the FIRST matching column for each category to prevent duplicate keys
        if 'Date' not in mapped_targets and col_lower in ['transactiontimestamp', 'valuedate', 'date', 'txn_date']:
            col_mapping[col] = 'Date'
            mapped_targets.add('Date')
        elif 'Narration' not in mapped_targets and col_lower in ['narration', 'description', 'merchant', 'particulars']:
            col_mapping[col] = 'Narration'
            mapped_targets.add('Narration')
        elif 'amount' not in mapped_targets and col_lower in ['amount', 'txn_amount']:
            col_mapping[col] = 'amount'
            mapped_targets.add('amount')
        elif 'type' not in mapped_targets and col_lower in ['type', 'txn_type', 'cr/dr']:
            col_mapping[col] = 'type'
            mapped_targets.add('type')
            
    df = df.rename(columns=col_mapping)
    
    # Drop any leftover duplicate columns entirely to prevent Pandas crashes downstream
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    # 4. Process Datetime
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    else:
        df['Date'] = pd.Timestamp.now()
        
    if 'Narration' not in df.columns:
        df['Narration'] = 'Unknown Merchant'
    df['Description'] = df['Narration']
    
    # 5. Standardize Type & Amount (Handles both "CREDIT" and "CR" from the PDF)
    if 'type' in df.columns and 'amount' in df.columns:
        df['type'] = df['type'].astype(str).str.strip().str.upper()
        df['Amount'] = df.apply(
            lambda r: float(str(r['amount']).replace(',', '')) if r['type'] in ['CREDIT', 'CR'] else -abs(float(str(r['amount']).replace(',', ''))), axis=1
        )
    elif 'amount' in df.columns:
        df['Amount'] = pd.to_numeric(df['amount'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['type'] = df['Amount'].apply(lambda x: 'CREDIT' if x > 0 else 'DEBIT')
    elif 'Amount' in df.columns:
        df['Amount'] = pd.to_numeric(df['Amount'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['type'] = df['Amount'].apply(lambda x: 'CREDIT' if x > 0 else 'DEBIT')
    else:
        df['Amount'] = 0.0
        df['type'] = 'UNKNOWN'
        
    if 'Category' not in df.columns:
        df['Category'] = df['Narration'].apply(categorize_narration)
        
    return df

def find_recurring_charges(df):
    """
    Finds merchants with repeated debit charges and calculates annualized costs.
    """
    # Filter debits only
    if 'type' in df.columns:
        debits = df[df['type'] == 'DEBIT'].copy()
    else:
        debits = df[df['Amount'] < 0].copy()
        
    if debits.empty:
        return pd.DataFrame()
        
    debits['amount_abs'] = debits['Amount'].abs()
    debits['merchant_clean'] = debits['Narration'].fillna('Unknown').astype(str).str.strip()
    
    records = []
    for merchant, group in debits.groupby('merchant_clean'):
        count = len(group)
        if count >= 2:  # Repeated merchant charges
            total_spent = group['amount_abs'].sum()
            avg_amount = group['amount_abs'].mean()
            sorted_group = group.sort_values(by='Date')
            last_txn = sorted_group.iloc[-1]
            last_amount = last_txn['amount_abs']
            min_date = sorted_group['Date'].min()
            max_date = sorted_group['Date'].max()
            
            days_span = (max_date - min_date).days if pd.notnull(max_date) and pd.notnull(min_date) else 0
            
            # Annualized Cost Calculation Logic:
            # If charges span multiple days/months (days_span >= 15), extrapolate daily rate to 365 days
            # Else estimate annual cost as average_amount * 12 (monthly assumption)
            if days_span >= 15:
                annualized_cost = (total_spent / days_span) * 365.0
            else:
                annualized_cost = avg_amount * 12.0
                
            # Estimate frequency
            if days_span > 0:
                avg_gap = days_span / max((count - 1), 1)
                if 25 <= avg_gap <= 35:
                    freq = "Monthly"
                elif 6 <= avg_gap <= 10:
                    freq = "Weekly"
                elif 80 <= avg_gap <= 100:
                    freq = "Quarterly"
                elif avg_gap < 5:
                    freq = "Frequent (~Daily/Few Days)"
                else:
                    freq = f"Every ~{int(round(avg_gap))} Days"
            else:
                freq = "Multiple Charges (Same Day)"
                
            ref_id = str(last_txn.get('txnId', last_txn.get('reference', 'N/A')))
            if pd.isna(ref_id) or ref_id.lower() == 'nan':
                ref_id = 'N/A'
                
            records.append({
                'Merchant': merchant,
                'Charge Count': count,
                'Last Amount (₹)': last_amount,
                'Avg Charge (₹)': round(avg_amount, 2),
                'Total Spent (₹)': round(total_spent, 2),
                'Estimated Frequency': freq,
                'First Date': min_date.strftime('%Y-%m-%d') if pd.notnull(min_date) else 'N/A',
                'Last Date': max_date.strftime('%Y-%m-%d') if pd.notnull(max_date) else 'N/A',
                'Annualized Cost (₹)': round(annualized_cost, 2),
                'Ref ID': ref_id
            })
            
    res_df = pd.DataFrame(records)
    if not res_df.empty:
        res_df = res_df.sort_values(by='Annualized Cost (₹)', ascending=False).reset_index(drop=True)
    return res_df

def generate_cancellation_email(merchant_name, user_name, user_email, account_ref, last_amount, last_date, reason):
    """
    Generates a formal subscription cancellation email text.
    """
    subject = f"Cancellation Request - Subscription for {merchant_name} (Ref: {account_ref})"
    body = f"""Dear {merchant_name} Support Team,

I am writing to formally request the immediate cancellation of my recurring subscription / service associated with {merchant_name}.

Please process the termination of this subscription and ensure no further recurring charges are billed to my account or payment method.

Subscription & Account Details:
--------------------------------
• Subscriber Name: {user_name}
• Associated Email: {user_email}
• Reference / Txn ID: {account_ref}
• Last Billed Amount: ₹{last_amount:,.2f}
• Last Charge Date: {last_date}
• Reason for Cancellation: {reason}

Kindly confirm via return email that this subscription has been cancelled and that automatic recurring payments have been stopped. If any prorated refund is applicable, please credit it back to the original payment method.

Thank you for your prompt assistance.

Sincerely,
{user_name}
{user_email}
"""
    return subject, body

def render_subscription_cancellation_ui(df):
    """
    Renders Streamlit UI component for recurring charges analysis and draft cancellation email.
    """
    st.header("🔄 Recurring Charges & Subscription Cancellations")
    st.write("Find merchants that charge you repeatedly, review their annualized cost, and draft cancellation emails for your most expensive subscriptions.")
    
    recurring_df = find_recurring_charges(df)
    
    if recurring_df.empty:
        st.info("No recurring debit charges detected in the current statement data.")
        return
        
    # Top metrics
    total_recurring_merchants = len(recurring_df)
    total_annualized = recurring_df['Annualized Cost (₹)'].sum()
    est_monthly = total_annualized / 12.0
    top_row = recurring_df.iloc[0]
    top_merchant = top_row['Merchant']
    top_annual_cost = top_row['Annualized Cost (₹)']
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recurring Merchants", f"{total_recurring_merchants}")
    m2.metric("Est. Monthly Outflow", f"₹{est_monthly:,.2f}")
    m3.metric("Total Annualized Cost", f"₹{total_annualized:,.2f}")
    m4.metric("Top Cost Subscription", f"{top_merchant}", delta=f"₹{top_annual_cost:,.2f}/yr", delta_color="inverse")
    
    st.divider()
    
    # Table of recurring charges
    st.subheader("📋 Recurring Merchants & Calculated Annualized Cost")
    
    c_search, c_sort = st.columns([2, 1])
    with c_search:
        search_term = st.text_input("🔍 Search Merchant", placeholder="e.g. PAYTM, AMZN, GPAY...")
    with c_sort:
        sort_by = st.selectbox("Sort By", options=["Annualized Cost (₹)", "Total Spent (₹)", "Charge Count", "Last Amount (₹)"])
        
    filtered_df = recurring_df.copy()
    if search_term:
        filtered_df = filtered_df[filtered_df['Merchant'].str.contains(search_term, case=False, na=False)]
        
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=False)
    
    st.dataframe(
        filtered_df,
        column_config={
            "Last Amount (₹)": st.column_config.NumberColumn("Last Billed", format="₹%.2f"),
            "Avg Charge (₹)": st.column_config.NumberColumn("Avg Charge", format="₹%.2f"),
            "Total Spent (₹)": st.column_config.NumberColumn("Total Spent", format="₹%.2f"),
            "Annualized Cost (₹)": st.column_config.NumberColumn("Annualized Cost", format="₹%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # Email Draft Section
    st.subheader("✉️ Draft Cancellation Email Component")
    st.caption("Pre-selected with the **most expensive subscription** based on annualized cost.")
    
    merchant_options = recurring_df['Merchant'].tolist()
    selected_merchant_name = st.selectbox(
        "Select Subscription to Draft Email For:",
        options=merchant_options,
        index=0,
        help="Defaults to the most expensive subscription."
    )
    
    selected_row = recurring_df[recurring_df['Merchant'] == selected_merchant_name].iloc[0]
    
    # Highlight badge if most expensive
    if selected_merchant_name == top_merchant:
        st.warning(f"⚠️ **Most Expensive Subscription Selected**: {top_merchant} costs ₹{top_annual_cost:,.2f} per year.")
    
    with st.expander("🛠️ Personalize Cancellation Email Details", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            user_name = st.text_input("Subscriber Name", value="Alex Morgan")
            user_email = st.text_input("Subscriber Email", value="alex.morgan@example.com")
        with col_b:
            account_ref = st.text_input("Reference / Txn ID", value=str(selected_row['Ref ID']))
            last_amt = st.number_input("Last Billed Amount (₹)", value=float(selected_row['Last Amount (₹)']))
        with col_c:
            last_dt = st.text_input("Last Charge Date", value=str(selected_row['Last Date']))
            cancel_reason = st.selectbox(
                "Reason for Cancellation",
                options=[
                    "Reducing overall monthly subscription expenses",
                    "No longer active or using the service",
                    "Found an alternative service",
                    "Unexpected or unannounced price increase",
                    "Personal financial plan adjustment"
                ]
            )
            
    subject, body = generate_cancellation_email(
        merchant_name=selected_merchant_name,
        user_name=user_name,
        user_email=user_email,
        account_ref=account_ref,
        last_amount=last_amt,
        last_date=last_dt,
        reason=cancel_reason
    )
    
    st.markdown("#### Draft Cancellation Email")
    st.text_input("Subject Line:", value=subject, key="email_subject_field")
    st.text_area("Body:", value=body, height=330, key="email_body_field")
    
    b1, b2 = st.columns([1, 2])
    with b1:
        if st.button("📋 Copy Email Draft"):
            st.toast("Draft copied! Copy text directly from the email body box above.", icon="✅")
    with b2:
        if st.button(f"Mark '{selected_merchant_name}' For Cancellation"):
            st.success(f"Subscription for **{selected_merchant_name}** queued for cancellation! Potential savings: **₹{selected_row['Annualized Cost (₹)']:,.2f}/yr**.")
