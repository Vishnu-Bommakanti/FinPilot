from subscription_analyzer import load_and_clean_data, find_recurring_charges

df = load_and_clean_data('bank_statements.csv')
print("Data loaded successfully. Rows:", len(df))
print("Columns:", df.columns.tolist())

recurring = find_recurring_charges(df)
print("Recurring merchants detected:", len(recurring))
print("\nTop 5 Most Expensive Subscriptions / Recurring Charges:")
for idx, row in recurring.head(5).iterrows():
    merchant = row['Merchant']
    annual_cost = row['Annualized Cost (₹)']
    last_amt = row['Last Amount (₹)']
    count = row['Charge Count']
    freq = row['Estimated Frequency']
    print(f"{idx+1}. Merchant: {merchant} | Annual Cost: INR {annual_cost:,.2f} | Last Billed: INR {last_amt:,.2f} | Count: {count} | Frequency: {freq}")
