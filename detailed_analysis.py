import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np

df = pd.read_csv('bank_statements.csv')
print("Columns:", df.columns.tolist())

# Convert timestamp
df['transactionTimestamp'] = pd.to_datetime(df['transactionTimestamp'])

# Filter debits
debits = df[df['type'] == 'DEBIT'].copy()

# Print unique narrations and counts
print("\n--- Unique Narrations ---")
narrations = debits['narration'].value_counts()
print(narrations.to_string())

# Group by narration and analyze periodicity
results = []
for merchant, group in debits.groupby('narration'):
    if len(group) >= 2:
        dates = group['transactionTimestamp'].sort_values()
        diffs = dates.diff().dt.days.dropna()
        avg_diff = diffs.mean()
        total_spent = group['amount'].sum()
        avg_amount = group['amount'].mean()
        count = len(group)
        
        # Estimate frequency
        # If diffs around 25-35 days -> Monthly
        # If diffs around 6-8 days -> Weekly
        # If diffs around 80-100 days -> Quarterly
        # If diffs around 350-380 days -> Annual
        # Otherwise based on average interval or span
        time_span_days = (dates.max() - dates.min()).days
        if time_span_days > 0:
            annualized_cost = total_spent * (365.0 / max(time_span_days, 30))
        else:
            annualized_cost = avg_amount * 12
            
        results.append({
            'Merchant': merchant,
            'Count': count,
            'Avg Amount': avg_amount,
            'Total Spent': total_spent,
            'Avg Days Between': avg_diff,
            'Time Span (days)': time_span_days,
            'Annualized Cost': annualized_cost
        })

res_df = pd.DataFrame(results).sort_values(by='Annualized Cost', ascending=False)
print("\n--- Recurring Charges sorted by Annualized Cost ---")
print(res_df.head(30).to_string())
