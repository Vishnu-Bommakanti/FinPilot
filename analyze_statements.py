import pandas as pd

df = pd.read_csv('bank_statements.csv')
print("Columns:", df.columns.tolist())
print("Total rows:", len(df))

# Filter debits
debits = df[df['type'] == 'DEBIT'].copy()
debits['transactionTimestamp'] = pd.to_datetime(debits['transactionTimestamp'])

# Clean up narration to group merchants
debits['narration_clean'] = debits['narration'].str.strip()

print("\n--- Top Recurring Narrations (by count) ---")
narration_counts = debits['narration_clean'].value_counts()
print(narration_counts.head(30))

print("\n--- Value Counts with Amount grouping ---")
grouped = debits.groupby(['narration_clean', 'amount']).agg(
    count=('txnId', 'count'),
    min_date=('transactionTimestamp', 'min'),
    max_date=('transactionTimestamp', 'max'),
    total_amount=('amount', 'sum')
).reset_index()

grouped_recurring = grouped[grouped['count'] > 1].sort_values(by='total_amount', ascending=False)
print(grouped_recurring.head(30).to_string())
