import pandas as pd
import re

df = pd.read_csv('bank_statements.csv')
df['transactionTimestamp'] = pd.to_datetime(df['transactionTimestamp'])

debits = df[df['type'] == 'DEBIT'].copy()

summary = []
for narration, group in debits.groupby('narration'):
    count = len(group)
    if count >= 2: # repeated charge
        total_amount = group['amount'].sum()
        avg_amount = group['amount'].mean()
        min_date = group['transactionTimestamp'].min()
        max_date = group['transactionTimestamp'].max()
        days_span = (max_date - min_date).days
        
        # Calculate frequency / interval
        # If charged regularly monthly, annualized cost is approx monthly_cost * 12
        # Or based on active days span if span > 0
        if days_span >= 15:
            annualized = (total_amount / days_span) * 365
        else:
            annualized = avg_amount * 12 # estimate
            
        summary.append({
            'Merchant': narration,
            'Count': count,
            'Avg_Amount': round(avg_amount, 2),
            'Total_Spent': round(total_amount, 2),
            'First_Txn': min_date.strftime('%Y-%m-%d'),
            'Last_Txn': max_date.strftime('%Y-%m-%d'),
            'Span_Days': days_span,
            'Annualized_Cost': round(annualized, 2)
        })

summary_df = pd.DataFrame(summary).sort_values(by='Annualized_Cost', ascending=False)
print(summary_df.head(30).to_string(index=False))
