import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from utils import predict_stock_trend
from fuzzywuzzy import process
import time
import concurrent.futures

# Set page config
st.set_page_config(page_title="Stock Data Visualization and Prediction", layout="wide")

# Company symbols dictionary
COMPANY_SYMBOLS = {
    'Apple': 'AAPL',
    'Microsoft': 'MSFT',
    'Google': 'GOOGL',
    'Alphabet': 'GOOGL',
    'Amazon': 'AMZN',
    'Tesla': 'TSLA',
    'Meta': 'META',
    'Facebook': 'META',
    'Netflix': 'NFLX',
    'NVIDIA': 'NVDA',
    'Intel': 'INTC',
    'AMD': 'AMD',
    'Coca-Cola': 'KO',
    'Disney': 'DIS',
    'Nike': 'NKE',
    "McDonald's": 'MCD',
    'Boeing': 'BA',
    'JPMorgan': 'JPM',
    'Walmart': 'WMT',
    'Visa': 'V'
}

def fetch_stock_data(symbol, max_retries=3):
    """Fetch stock data with retry mechanism and fallback periods"""
    periods = ['1y', '6mo', '3mo', '1mo']
    
    for period in periods:
        retries = 0
        while retries < max_retries:
            try:
                stock = yf.Ticker(symbol)
                history = stock.history(period=period)
                if not history.empty:
                    return stock, history
                retries += 1
                time.sleep(1)  # Wait before retry
            except Exception as e:
                print(f"Error fetching {period} data: {str(e)}")
                retries += 1
                time.sleep(1)
        print(f"Failed to fetch {period} data after {max_retries} retries")
    
    return None, None

def fetch_historical_data_for_symbol(symbol):
    """Fetch historical data for a single symbol"""
    try:
        stock = yf.Ticker(symbol)
        history = stock.history(period="120d")
        return symbol, history
    except Exception as e:
        print(f"Error fetching data for {symbol}: {str(e)}")
        return symbol, None

def calculate_performance(history, days):
    """Calculate percentage gain over specified period"""
    if history is None or len(history) < days:
        return None
    
    current_price = history['Close'].iloc[-1]
    past_price = history['Close'].iloc[-min(days, len(history))]
    return ((current_price - past_price) / past_price) * 100

def get_top_performers(period_days):
    """Get top 10 performing stocks for given period"""
    performances = []
    
    with st.spinner(f'Fetching data for {period_days}-day performance...'):
        # Use ThreadPoolExecutor for parallel data fetching
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all fetch tasks
            future_to_symbol = {
                executor.submit(fetch_historical_data_for_symbol, symbol): (name, symbol)
                for name, symbol in COMPANY_SYMBOLS.items()
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_symbol):
                company_name, symbol = future_to_symbol[future]
                try:
                    symbol, history = future.result()
                    if history is not None:
                        gain = calculate_performance(history, period_days)
                        if gain is not None:
                            performances.append({
                                'Company': company_name,
                                'Symbol': symbol,
                                'Gain': gain
                            })
                except Exception as e:
                    print(f"Error processing {symbol}: {str(e)}")
    
    # Sort by gain and get top 10
    performances = pd.DataFrame(performances)
    if not performances.empty:
        return performances.nlargest(10, 'Gain')
    return pd.DataFrame()

# App title and description
st.title("Stock Data Visualization and Prediction")

# Add Top Performers section
st.header("Top 10 Performing Stocks")
period_tabs = st.tabs(["30 Days", "60 Days", "90 Days", "120 Days"])
periods = [30, 60, 90, 120]

# Cache the performance data to avoid recalculation
if 'performance_cache' not in st.session_state:
    st.session_state.performance_cache = {}

for tab, period in zip(period_tabs, periods):
    with tab:
        # Check if data is in cache
        if period not in st.session_state.performance_cache:
            st.session_state.performance_cache[period] = get_top_performers(period)
        
        top_performers = st.session_state.performance_cache[period]
        
        if not top_performers.empty:
            # Create bar chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=top_performers['Company'] + ' (' + top_performers['Symbol'] + ')',
                y=top_performers['Gain'],
                text=top_performers['Gain'].round(2).astype(str) + '%',
                textposition='auto',
            ))
            fig.update_layout(
                title=f'Top Performers - {period} Days',
                xaxis_title="Company",
                yaxis_title="Gain (%)",
                showlegend=False,
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Display data table
            st.dataframe(
                top_performers.style.format({
                    'Gain': '{:.2f}%'
                }),
                hide_index=True
            )
        else:
            st.warning("Unable to fetch performance data for this period.")

# Add refresh button for performance data
if st.button("Refresh Performance Data"):
    st.session_state.performance_cache = {}
    st.experimental_rerun()

st.write("---")
st.write("Enter a company name to view detailed stock data and predictions.")

# User input for company name
company_name = st.text_input("Enter company name (e.g., Apple)", "Apple")

[... rest of the existing code ...]
