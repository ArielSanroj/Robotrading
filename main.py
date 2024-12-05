import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils import predict_stock_trend
from fuzzywuzzy import process
import time
import concurrent.futures
from pandas.tseries.offsets import BDay

# Company symbols dictionary
COMPANY_SYMBOLS = {
    'Apple': 'AAPL', 'Microsoft': 'MSFT', 'Google': 'GOOGL', 'Alphabet': 'GOOGL',
    'Amazon': 'AMZN', 'Tesla': 'TSLA', 'Meta': 'META', 'Facebook': 'META',
    'Netflix': 'NFLX', 'NVIDIA': 'NVDA', 'Intel': 'INTC', 'AMD': 'AMD',
    'Coca-Cola': 'KO', 'Disney': 'DIS', 'Nike': 'NKE', "McDonald's": 'MCD',
    'Boeing': 'BA', 'JPMorgan': 'JPM', 'Walmart': 'WMT', 'Visa': 'V'
}

@st.cache_data(ttl=3600)
def fetch_stock_data(symbol, period="1y"):
    """Fetch stock data with caching"""
    try:
        # Convert period format if needed
        if period.endswith('d'):
            yf_period = period  # yfinance accepts '30d' format
        else:
            # Convert year format to yfinance format
            years = int(period.replace('y', ''))
            if years <= 2:
                yf_period = f"{years}y"
            else:
                yf_period = "max"  # For periods > 2 years, use max data
        
        stock = yf.Ticker(symbol)
        history = stock.history(period=yf_period)
        return history, stock.info
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None, None

def calculate_metrics(history):
    """Calculate key financial metrics"""
    if history is None or len(history) < 1:
        return None
    
    current_price = history['Close'].iloc[-1]
    high_52week = history['High'].max()
    low_52week = history['Low'].min()
    daily_returns = history['Close'].pct_change()
    
    metrics = {
        'Current Price': f"${current_price:.2f}",
        '52-Week High': f"${high_52week:.2f}",
        '52-Week Low': f"${low_52week:.2f}",
        'Volatility (Daily)': f"{daily_returns.std() * 100:.2f}%",
        'YTD Return': f"{((current_price / history['Close'].iloc[0]) - 1) * 100:.2f}%"
    }
    
    return metrics

def plot_comparison_chart(stock_data_dict, chart_type="Price"):
    """Create comparative chart for selected stocks"""
    fig = go.Figure()
    
    for company, data in stock_data_dict.items():
        if data is not None:
            if chart_type == "Price":
                y_data = data['Close']
                title = "Stock Price Comparison"
                yaxis_title = "Price (USD)"
            else:  # Normalized
                y_data = (data['Close'] / data['Close'].iloc[0]) * 100
                title = "Normalized Price Comparison (Base 100)"
                yaxis_title = "Normalized Price"
                
            fig.add_trace(go.Scatter(
                x=data.index,
                y=y_data,
                name=company,
                mode='lines'
            ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=yaxis_title,
        height=600,
        showlegend=True
    )
    
    return fig

def create_comparison_metrics_table(metrics_dict):
    """Create a comparative metrics table"""
    if not metrics_dict:
        return None
    
    # Convert metrics dictionary to DataFrame
    df = pd.DataFrame.from_dict(metrics_dict, orient='index')
    return df

# Set page config
st.set_page_config(
    page_title="Stock Market Insights",
    page_icon="📈",
    layout="wide"
)

# Add title and description
st.title("Stock Market Insights")
st.write("Advanced stock analysis and prediction platform with investment calculator")
@st.cache_data(ttl=3600)
def get_top_performers(period="1mo"):
    """Fetch top performing stocks dynamically from Yahoo Finance"""
    try:
        # List of major market indices to get top movers
        indices = ['^GSPC', '^DJI', '^IXIC']  # S&P 500, Dow Jones, NASDAQ
        performance_data = []
        
        for index in indices:
            try:
                # Get index data
                index_ticker = yf.Ticker(index)
                # Get top components
                components = index_ticker.info.get('components', [])
                if not components:
                    continue
                
                # Process each component
                for symbol in components[:20]:  # Take top 20 from each index
                    try:
                        ticker = yf.Ticker(symbol)
                        history = ticker.history(period=period)
                        info = ticker.info
                        
                        if not history.empty:
                            start_price = history['Close'].iloc[0]
                            current_price = history['Close'].iloc[-1]
                            change_pct = ((current_price - start_price) / start_price) * 100
                            volume = history['Volume'].mean()
                            
                            performance_data.append({
                                'Symbol': symbol,
                                'Company': info.get('shortName', symbol),
                                'Price': f"${current_price:.2f}",
                                'Change %': f"{'🔼' if change_pct > 0 else '🔽'} {abs(change_pct):.2f}%",
                                'Volume': f"{volume:,.0f}",
                                'Change_Numeric': float(change_pct)
                            })
                            
                            # Add small delay to avoid rate limiting
                            time.sleep(0.1)
                            
                    except Exception as e:
                        print(f"Error processing {symbol}: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"Error processing index {index}: {str(e)}")
                continue
        
        if not performance_data:
            return pd.DataFrame(columns=['Symbol', 'Company', 'Price', 'Change %', 'Volume'])
        
        # Convert to DataFrame and sort by performance
        df = pd.DataFrame(performance_data)
        df = df.sort_values('Change_Numeric', ascending=False).head(15)
        
        # Drop the numeric column used for sorting
        df = df.drop('Change_Numeric', axis=1)
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching top performers: {str(e)}")
        return pd.DataFrame(columns=['Symbol', 'Company', 'Price', 'Change %', 'Volume'])

# Top Performers Section
st.subheader("Top 15 Performing Stocks")
tabs = st.tabs(["5 Days", "1 Month", "3 Months", "6 Months", "12 Months"])
periods = ["5d", "1mo", "3mo", "6mo", "1y"]

for tab, period in zip(tabs, periods):
    with tab:
        with st.spinner('Fetching top performers...'):
            top_stocks = get_top_performers(period)
            st.dataframe(
                top_stocks,
                hide_index=True,
                use_container_width=True
            )

st.write("---")  # Add separator

# Add Stock Comparison Section
st.header("Stock Comparison Analysis")

# Multi-select for stocks
selected_companies = st.multiselect(
    "Select companies to compare (2-4 recommended)",
    options=list(COMPANY_SYMBOLS.keys()),
    default=["Apple", "Microsoft"],
    max_selections=4
)

if len(selected_companies) > 1:
    # Time period selection
    comparison_period = st.selectbox(
        "Select time period",
        options=["30d", "90d", "180d", "1y", "2y", "5y"],
        index=3
    )
    
    # Chart type selection
    chart_type = st.radio(
        "Select chart type",
        options=["Price", "Normalized"],
        horizontal=True
    )
    
    # Fetch data for selected companies
    stock_data = {}
    metrics_data = {}
    
    with st.spinner('Fetching data for selected companies...'):
        for company in selected_companies:
            symbol = COMPANY_SYMBOLS[company]
            history, info = fetch_stock_data(symbol, comparison_period)
            
            if history is not None:
                stock_data[company] = history
                metrics_data[company] = calculate_metrics(history)
    
    # Display comparison chart
    if stock_data:
        st.plotly_chart(plot_comparison_chart(stock_data, chart_type), use_container_width=True)
        
        # Display metrics comparison
        st.subheader("Comparative Metrics")
        metrics_df = create_comparison_metrics_table(metrics_data)
        if metrics_df is not None:
            st.dataframe(metrics_df, height=200)
        
        # Performance Analysis
        st.subheader("Performance Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            # Volatility comparison
            volatilities = {company: data['Close'].pct_change().std() * 100 
                          for company, data in stock_data.items()}
            
            fig_vol = go.Figure([go.Bar(
                x=list(volatilities.keys()),
                y=list(volatilities.values()),
                text=[f"{v:.2f}%" for v in volatilities.values()],
                textposition='auto'
            )])
            fig_vol.update_layout(
                title="Volatility Comparison",
                yaxis_title="Volatility (%)",
                height=400
            )
            st.plotly_chart(fig_vol, use_container_width=True)
        
        with col2:
            # Total return comparison
            returns = {company: ((data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1) * 100 
                      for company, data in stock_data.items()}
            
            fig_ret = go.Figure([go.Bar(
                x=list(returns.keys()),
                y=list(returns.values()),
                text=[f"{v:.2f}%" for v in returns.values()],
                textposition='auto'
            )])
            fig_ret.update_layout(
                title=f"Total Return Comparison ({comparison_period})",
                yaxis_title="Return (%)",
                height=400
            )
            st.plotly_chart(fig_ret, use_container_width=True)
        
        # Correlation Analysis
        st.subheader("Correlation Analysis")
        returns_df = pd.DataFrame({
            company: data['Close'].pct_change() 
            for company, data in stock_data.items()
        })
        correlation_matrix = returns_df.corr()
        
        fig_corr = go.Figure(data=go.Heatmap(
            z=correlation_matrix,
            x=correlation_matrix.columns,
            y=correlation_matrix.columns,
            text=[[f"{val:.2f}" for val in row] for row in correlation_matrix.values],
            texttemplate="%{text}",
            textfont={"size": 10},
            hoverongaps=False
        ))
        fig_corr.update_layout(
            title="Return Correlation Matrix",
            height=400
        )
        st.plotly_chart(fig_corr, use_container_width=True)
        
        # Trading Volume Analysis
        st.subheader("Trading Volume Analysis")
        fig_vol = go.Figure()
        for company, data in stock_data.items():
            fig_vol.add_trace(go.Scatter(
                x=data.index,
                y=data['Volume'],
                name=company,
                mode='lines'
            ))
        fig_vol.update_layout(
            title="Trading Volume Comparison",
            xaxis_title="Date",
            yaxis_title="Volume",
            height=400
        )
        st.plotly_chart(fig_vol, use_container_width=True)
        
else:
    st.info("Please select at least 2 companies to compare.")

# Separator
st.write("---")

# Single Stock Analysis Section
st.header("Single Stock Analysis")

# Company search with fuzzy matching
company_search = st.text_input("Search for a company (name or symbol)")
selected_company = None

if company_search:
    # Fuzzy match company name or symbol
    matches = process.extract(company_search, list(COMPANY_SYMBOLS.keys()) + list(COMPANY_SYMBOLS.values()), limit=5)
    best_matches = [match[0] for match in matches if match[1] > 60]
    
    if best_matches:
        selected_company = st.selectbox("Select company:", best_matches)
        if selected_company in COMPANY_SYMBOLS:  # If company name selected
            symbol = COMPANY_SYMBOLS[selected_company]
        else:  # If symbol selected
            symbol = selected_company
            selected_company = [k for k, v in COMPANY_SYMBOLS.items() if v == symbol][0]
        
        # Fetch stock data
        with st.spinner(f'Fetching data for {selected_company} ({symbol})...'):
            history, info = fetch_stock_data(symbol, "2y")
            
            if history is not None and info is not None:
                # Company Information
                st.subheader("Company Information")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Current Price", f"${info.get('currentPrice', 'N/A')}")
                with col2:
                    st.metric("Market Cap", f"${info.get('marketCap', 0) / 1e9:.2f}B")
                with col3:
                    st.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A')}")
                
                # Price History Chart
                st.subheader("Price History")
                timeframe = st.selectbox("Select timeframe:", ["30d", "90d", "180d", "1y", "2y"], index=3)
                # Calculate the date range based on timeframe and handle timezones
                if 'd' in timeframe:
                    days = int(timeframe.replace('d', ''))
                    cutoff_date = pd.Timestamp.now().tz_localize(None) - pd.DateOffset(days=days)
                else:
                    years = int(timeframe.replace('y', ''))
                    cutoff_date = pd.Timestamp.now().tz_localize(None) - pd.DateOffset(years=years)
                
                history_subset = history.copy()
                history_subset.index = history_subset.index.tz_localize(None)
                history_subset = history_subset[history_subset.index > cutoff_date]
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=history_subset.index,
                    open=history_subset['Open'],
                    high=history_subset['High'],
                    low=history_subset['Low'],
                    close=history_subset['Close'],
                    name="Price"
                ))
                
                # Add moving averages
                fig.add_trace(go.Scatter(x=history_subset.index, y=history_subset['Close'].rolling(window=20).mean(),
                                       name="20-day MA", line=dict(color='orange')))
                fig.add_trace(go.Scatter(x=history_subset.index, y=history_subset['Close'].rolling(window=50).mean(),
                                       name="50-day MA", line=dict(color='blue')))
                
                fig.update_layout(title="Stock Price History", xaxis_title="Date", yaxis_title="Price (USD)",
                                height=600, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
                
                # Technical Analysis and Predictions
                st.subheader("Technical Analysis & Predictions")
                
                # Get predictions
                predictions = predict_stock_trend(history, symbol)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("Random Forest Prediction")
                    rf_pred, rf_conf, rf_exp = predictions['Random Forest']
                    st.metric("Prediction", rf_pred.title(), f"Confidence: {rf_conf:.1f}%")
                    
                    if rf_exp.get('news_analysis'):
                        st.write("Recent News Impact:")
                        for news in rf_exp['news_analysis']:
                            with st.expander(f"{news['headline'][:100]}..."):
                                st.write(f"Source: {news['source']}")
                                st.write(f"Published: {news['published']}")
                                st.write(f"Impact: {news['impact']}")
                                st.write(f"[Read more]({news['url']})")
                
                with col2:
                    st.write("Technical Indicators")
                    st.write(rf_exp['technical_analysis'])
                
                # ARIMA Predictions
                st.subheader("ARIMA Price Predictions")
                if predictions['ARIMA']:
                    tabs = st.tabs(['7 Days', '15 Days', '30 Days', '90 Days'])
                    periods = [7, 15, 30, 90]
                    
                    for tab, period in zip(tabs, periods):
                        with tab:
                            arima_pred = predictions['ARIMA'][period]
                            fig = go.Figure()
                            
                            # Historical data
                            fig.add_trace(go.Scatter(
                                x=history_subset.index[-30:],
                                y=history_subset['Close'][-30:],
                                name="Historical",
                                line=dict(color='blue')
                            ))
                            
                            # Predictions
                            fig.add_trace(go.Scatter(
                                x=arima_pred['daily_forecasts'].index,
                                y=arima_pred['daily_forecasts'],
                                name="Prediction",
                                line=dict(color='red', dash='dash')
                            ))
                            
                            # Confidence intervals
                            fig.add_trace(go.Scatter(
                                x=arima_pred['upper_bound'].index,
                                y=arima_pred['upper_bound'],
                                fill=None,
                                mode='lines',
                                line_color='rgba(0,0,0,0)',
                                showlegend=False
                            ))
                            
                            fig.add_trace(go.Scatter(
                                x=arima_pred['lower_bound'].index,
                                y=arima_pred['lower_bound'],
                                fill='tonexty',
                                mode='lines',
                                line_color='rgba(0,0,0,0)',
                                name='Confidence Interval'
                            ))
                            
                            fig.update_layout(
                                title=f"{period}-Day Price Prediction",
                                xaxis_title="Date",
                                yaxis_title="Price (USD)",
                                height=400
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            st.metric("Prediction", arima_pred['prediction'].title(),
                                    f"Confidence: {arima_pred['confidence']:.1f}%")
                
                # Investment Calculator
                st.subheader("Investment Calculator")
                
                col1, col2 = st.columns(2)
                with col1:
                    investment_amount = st.number_input("Initial Investment ($)", min_value=100, value=10000)
                    investment_period = st.selectbox("Investment Period", [
                        "7 Days", "15 Days", "30 Days", "90 Days"
                    ])
                
                with col2:
                    risk_tolerance = st.select_slider(
                        "Risk Tolerance",
                        options=["Low", "Medium", "High"],
                        value="Medium"
                    )
                
                period_days = int(investment_period.split()[0])
                if predictions['ARIMA'] and period_days in predictions['ARIMA']:
                    arima_pred = predictions['ARIMA'][period_days]
                    final_price = arima_pred['daily_forecasts'][-1]
                    price_change = (final_price - arima_pred['last_price']) / arima_pred['last_price']
                    
                    # Calculate potential returns
                    expected_return = investment_amount * (1 + price_change)
                    worst_case = investment_amount * (1 + (price_change - (0.2 if risk_tolerance == "High" else 0.1)))
                    best_case = investment_amount * (1 + (price_change + (0.2 if risk_tolerance == "High" else 0.1)))
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Expected Return", f"${expected_return:,.2f}",
                                f"{(expected_return/investment_amount - 1)*100:.1f}%")
                    with col2:
                        st.metric("Best Case", f"${best_case:,.2f}",
                                f"{(best_case/investment_amount - 1)*100:.1f}%")
                    with col3:
                        st.metric("Worst Case", f"${worst_case:,.2f}",
                                f"{(worst_case/investment_amount - 1)*100:.1f}%")
                    
                    # Risk Analysis
                    st.write("Risk Analysis")
                    risk_factors = []
                    
                    # Volatility risk
                    volatility = history['Close'].pct_change().std() * np.sqrt(252)  # Annualized volatility
                    risk_factors.append(f"Historical Volatility: {volatility*100:.1f}%")
                    
                    # Price trend risk
                    recent_trend = "upward" if history['Close'].iloc[-1] > history['Close'].iloc[-20] else "downward"
                    risk_factors.append(f"Recent Price Trend: {recent_trend}")
                    
                    # Technical indicator risks
                    if rf_exp['technical_analysis']:
                        risk_factors.append(f"Technical Indicators: {rf_exp['technical_analysis']}")
                    
                    # News sentiment risk
                    if rf_exp.get('news_analysis'):
                        avg_sentiment = np.mean([float(news['sentiment']) for news in rf_exp['news_analysis']])
                        risk_factors.append(f"News Sentiment: {'Positive' if avg_sentiment > 0 else 'Negative' if avg_sentiment < 0 else 'Neutral'}")
                    
                    for factor in risk_factors:
                        st.write(f"• {factor}")
            else:
                st.error("Error fetching data for the selected company.")
    else:
        st.warning("No matching companies found. Please try a different search term.")