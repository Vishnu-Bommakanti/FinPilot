import pandas as pd
import numpy as np

def process_bank_statements(csv_path="bank_statements.csv"):
    df = pd.read_csv(csv_path)
    
    if 'transactionTimestamp' in df.columns:
        df['Date'] = pd.to_datetime(df['transactionTimestamp'])
    elif 'valueDate' in df.columns:
        df['Date'] = pd.to_datetime(df['valueDate'])
        
    if 'narration' in df.columns and 'Description' not in df.columns:
        df['Description'] = df['narration']
        
    if 'amount' in df.columns and 'Amount' not in df.columns:
        if 'type' in df.columns:
            df['Amount'] = df.apply(lambda r: r['amount'] if str(r['type']).upper() == 'CREDIT' else -r['amount'], axis=1)
        else:
            df['Amount'] = df['amount']

    return df

def detect_recurring_subscriptions(df):
    if 'type' in df.columns:
        debits = df[df['type'].str.upper() == 'DEBIT'].copy()
    else:
        debits = df[df['Amount'] < 0].copy()
        debits['amount'] = debits['Amount'].abs()
        
    if debits.empty:
        return pd.DataFrame()
        
    debits['narration_clean'] = debits['narration'].fillna('Unknown').astype(str).str.strip()
    
    records = []
    for merchant, group in debits.groupby('narration_clean'):
        count = len(group)
        if count >= 2:
            total_spent = group['amount'].sum()
            avg_amount = group['amount'].mean()
            last_amount = group.sort_values(by='Date').iloc[-1]['amount']
            min_date = group['Date'].min()
            max_date = group['Date'].max()
            days_span = (max_date - min_date).days
            
            if days_span >= 15:
                annualized_cost = (total_spent / days_span) * 365
            else:
                annualized_cost = avg_amount * 12
                
            if days_span > 0:
                avg_gap = days_span / (count - 1) if count > 1 else days_span
                if 25 <= avg_gap <= 35:
                    frequency = "Monthly"
                elif 6 <= avg_gap <= 10:
                    frequency = "Weekly"
                elif 80 <= avg_gap <= 100:
                    frequency = "Quarterly"
                else:
                    frequency = f"Every ~{int(round(avg_gap))} days"
            else:
                frequency = "Multiple per day"
                
            records.append({
                'Merchant': merchant,
                'Charge Count': count,
                'Last Charged (INR)': last_amount,
                'Average Charge (INR)': round(avg_amount, 2),
                'Total Spent (INR)': round(total_spent, 2),
                'Estimated Frequency': frequency,
                'First Date': min_date.strftime('%Y-%m-%d'),
                'Last Date': max_date.strftime('%Y-%m-%d'),
                'Annualized Cost (INR)': round(annualized_cost, 2)
            })
            
    res_df = pd.DataFrame(records).sort_values(by='Annualized Cost (INR)', ascending=False)
    return res_df

df = process_bank_statements()
subs = detect_recurring_subscriptions(df)
print(subs.head(20).to_string())
