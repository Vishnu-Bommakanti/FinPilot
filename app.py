# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
import os
# pyrefly: ignore [missing-import]
import plotly.express as px
# pyrefly: ignore [missing-import]
from langchain_google_genai import ChatGoogleGenerativeAI
# pyrefly: ignore [missing-import]
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from subscription_analyzer import load_and_clean_data, render_subscription_cancellation_ui

# --- UI/UX HACKS: Make Streamlit look aesthetic ---
st.set_page_config(page_title="FinPilot", page_icon="💳", layout="wide")

# Hide default Streamlit menus and add basic styling
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stMetric {background-color: #f0f2f6; padding: 15px; border-radius: 10px;}
    </style>
""", unsafe_allow_html=True)

st.title("💳 FinPilot: Personal Finance Intelligence")
st.write("Upload your bank statement or analyze `bank_statements.csv` to track recurring subscriptions and optimize your finances.")

# --- SIDEBAR: Configuration ---
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key", value="", type="password")
    uploaded_file = st.file_uploader("Upload Bank Statement (CSV or PDF)", type=["csv", "pdf"])
    # Determine input source
    file_to_load = None
    if uploaded_file is not None:
        file_to_load = uploaded_file
        st.success("Loaded uploaded bank statement CSV.")
    elif os.path.exists("bank_statements.csv"):
        file_to_load = "bank_statements.csv"
        st.info("Using local `bank_statements.csv`.")
        
    st.divider()
    st.subheader("🎯 Financial Goals")
    monthly_budget = st.number_input("Set Monthly Expense Budget (₹)", value=25000)
    goal_name = st.text_input("Savings Goal Name", value="Emergency Fund")
    goal_amount = st.number_input("Target Amount (₹)", value=50000)

# --- MAIN APP LOGIC ---
if file_to_load:
    # Load & standardize dataset
    df = load_and_clean_data(file_to_load)
    
    # Langchain Agent setup if API key is provided
    agent = None
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        try:
            llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
            agent = create_pandas_dataframe_agent(
                llm, 
                df, 
                verbose=True, 
                allow_dangerous_code=True,
                agent_type="zero-shot-react-description",
                agent_executor_kwargs={"handle_parsing_errors": True}
            )
        except Exception as e:
            st.sidebar.warning(f"AI Agent Warning: {e}")

    # --- TABS FOR CLEAN UI ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Visual Analytics", 
        "🔄 Subscriptions & Cancellations", 
        "🎯 Goals & Insights", 
        "💬 AI Assistant"
    ])

    # ==========================================
    # TAB 1: VISUAL ANALYTICS
    # ==========================================
    with tab1:
        st.subheader("Monthly Overview")
        
        # Top Metrics
        col1, col2, col3 = st.columns(3)
        total_spent = df[df['Amount'] < 0]['Amount'].sum() * -1
        total_income = df[df['Amount'] > 0]['Amount'].sum()
        
        col1.metric("Total Income", f"₹{total_income:,.2f}")
        col2.metric("Total Spent", f"₹{total_spent:,.2f}")
        col3.metric("Net Flow", f"₹{(total_income - total_spent):,.2f}")
        
        st.divider()
        
        # Side-by-Side Visual Charts
        st.subheader("Spending Breakdown")
        expense_df = df[df['Amount'] < 0].copy()
        expense_df['Amount'] = expense_df['Amount'].abs()
        
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            fig_bar = px.bar(expense_df, x="Category", y="Amount", color="Category", title="Expenses by Category (₹)")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with chart_col2:
            fig_pie = px.pie(expense_df, names="Category", values="Amount", hole=0.4, title="Expense Distribution")
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
            
        st.divider()
        
        # Raw Data Expander at bottom of Tab 1
        with st.expander("📄 View Raw Bank Statement Data"):
            st.dataframe(df, use_container_width=True)

    # ==========================================
    # TAB 2: RECURRING SUBSCRIPTIONS & CANCELLATION
    # ==========================================
    with tab2:
        render_subscription_cancellation_ui(df)

    # ==========================================
    # TAB 3: GOALS & INSIGHTS
    # ==========================================
    with tab3:
        # 1. Upcoming Obligations
        st.subheader("Upcoming Recurring Obligations")
        st.caption("Auto-detected subscriptions and utilities due based on recurring patterns.")
        subs_df = df[df['Category'].isin(['Entertainment', 'Utilities', 'Health & Fitness', 'Shopping'])]
        st.dataframe(subs_df[['Date', 'Description', 'Amount']], hide_index=True, use_container_width=True)

        st.divider()

        # 2. Budget & Goals Side-by-Side
        goal_col1, goal_col2 = st.columns(2)
        
        with goal_col1:
            st.subheader("Budget Tracking")
            budget_diff = monthly_budget - total_spent
            budget_used_pct = min(total_spent / monthly_budget, 1.0) if monthly_budget > 0 else 1.0
            
            st.metric(
                "Budget Remaining", 
                f"₹{budget_diff:,.2f}", 
                delta=f"{'Over Budget' if budget_diff < 0 else 'Under Budget'}",
                delta_color="normal" if budget_diff >= 0 else "inverse"
            )
            st.progress(budget_used_pct, text=f"Used {budget_used_pct*100:.1f}% of ₹{monthly_budget:,.2f} budget")

        with goal_col2:
            st.subheader(f"Goal: {goal_name}")
            net_savings = total_income - total_spent
            if net_savings > 0:
                months_to_goal = goal_amount / net_savings
                st.metric("Target Projection", f"{months_to_goal:.1f} Months", delta="On Track")
                st.info(f"Saving ₹{net_savings:,.2f}/mo to reach **₹{goal_amount:,.2f}**.")
            else:
                st.error("Expenses exceed income. Adjust budget to track goals.")
            
        st.divider()
        
        # 3. Monthly Financial Summary (Zero-API Rule-Based Generator)
        st.subheader("Monthly Financial Summary")
        if st.button("Generate Action Items & Insights"):
            with st.spinner("Compiling report with FinPilot AI..."):
                try:
                    # Pure Python logic to generate the summary without an API
                    expense_df = df[df['Amount'] < 0].copy()
                    expense_df['Amount'] = expense_df['Amount'].abs()
                    
                    # 1. Find highest category
                    if not expense_df.empty:
                        highest_category = expense_df.groupby('Category')['Amount'].sum().idxmax()
                        highest_amount = expense_df.groupby('Category')['Amount'].sum().max()
                    else:
                        highest_category = "None"
                        highest_amount = 0.0
                    
                    # 2. Total subscriptions
                    subs_df = df[df['Category'].isin(['Entertainment', 'Utilities', 'Health & Fitness'])]
                    subs_total = abs(subs_df['Amount'].sum())

                    # Build the markdown response
                    summary_report = f"""
**Final Answer:**
* **Unusual/High Spending Pattern:** Your highest spending category this period was **{highest_category}**, totaling **₹{highest_amount:,.2f}**.
* **Actionable Recommendation:** Review your recent {highest_category} transactions. Cutting non-essential spending in this category by just 10% could significantly boost your monthly savings rate.
* **Committed Subscriptions:** Your total committed budget for upcoming recurring obligations is **₹{subs_total:,.2f}**.
                    """
                    st.success(summary_report)
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # ==========================================
    # TAB 4: AI ASSISTANT (CHAT)
    # ==========================================
    with tab4:
        st.subheader("Ask FinPilot Anything")
        st.markdown(
            """
            **Try asking:** 
            * 🔍 *"Identify all recurring subscriptions and their total cost."* 
            * 🍽️ *"How much did I spend on food and dining via UPI?"*
            * 📉 *"Am I tracking within my budget, and what is one area to cut back?"*
            """
        )
        st.divider()
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("e.g., Which subscriptions am I paying for?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                if agent:
                    with st.spinner("Analyzing your transactions..."):
                        try:
                            system_rules = (
                                "You are FinPilot, an expert personal finance decision-support agent. "
                                "Your job is to analyze the provided financial transactions (dataframe) to help the user understand their spending habits.\n"
                                "- Always prioritize identifying recurring subscriptions and unusual spending.\n"
                                "- When summarizing, group similar categories and provide absolute rupee amounts (₹).\n"
                                "- DO NOT provide investment advice.\n"
                                "- If asked a question that cannot be answered by the data, politely state that the information is missing.\n"
                                "- Keep your answers structured, utilizing bullet points for readability.\n"
                                "- Always use the python_repl_ast tool to analyze the dataframe.\n"
                                "- MANDATORY FORMATTING RULES:\n"
                                "  1. All monetary values MUST be formatted in Indian Rupees using the '₹' symbol.\n"
                                "  NEVER use the '$' symbol under any circumstance.\n"
                                "  2. When ready, output your response starting with 'Final Answer:'.\n\n"
                                f"User query: {prompt}"
                            )
                            response = agent.invoke(system_rules)
                            answer = response["output"]
                            st.markdown(answer)
                            st.session_state.messages.append({"role": "assistant", "content": answer})
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                else:
                    st.warning("Please provide a valid Gemini API key in the sidebar to use the AI Chat Assistant.")

else:
    st.info("👈 Please upload a CSV bank statement or ensure `bank_statements.csv` is present to begin.")