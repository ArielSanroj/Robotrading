import streamlit as st
import yfinance as yf
import pandas as pd
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

def fetch_historical_data_for_symbol(symbol):
    """Fetch historical data for a single symbol with enhanced error handling"""
    try:
        stock = yf.Ticker(symbol)
        history = stock.history(period="3mo")
        if history.empty:
            print(f"No data available for {symbol}")
            return symbol, None
        return symbol, history
    except Exception as e:
        print(f"Error fetching data for {symbol}: {str(e)}")
        return symbol, None

def calculate_performance(history, days):
    """Calculate percentage gain over specified business days"""
    if history is None or len(history) < days:
        return None
    
    try:
        history.index = pd.to_datetime(history.index)
        end_date = history.index[-1]
        start_date = end_date - BDay(days)
        
        closest_end = history.index[history.index <= end_date][-1]
        closest_start = history.index[history.index >= start_date][0]
        
        current_price = history.loc[closest_end, 'Close']
        past_price = history.loc[closest_start, 'Close']
        
        return ((current_price - past_price) / past_price) * 100
    except Exception as e:
        print(f"Error calculating performance: {str(e)}")
        return None

def get_top_performing_stocks(period_days):
    """Get top performing stocks with parallel processing"""
    performances = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {
            executor.submit(fetch_historical_data_for_symbol, symbol): (name, symbol)
            for name, symbol in COMPANY_SYMBOLS.items()
        }
        
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
    
    return pd.DataFrame(performances)

def display_top_performers(period_days, performances_df):
    """Display top performers chart and data"""
    if performances_df.empty:
        st.warning("No performance data available for this period.")
        return
    
    # Get top 10 performers
    top_10 = performances_df.nlargest(10, 'Gain')
    
    # Create bar chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top_10['Company'] + ' (' + top_10['Symbol'] + ')',
        y=top_10['Gain'],
        text=top_10['Gain'].round(2).astype(str) + '%',
        textposition='auto',
    ))
    
    fig.update_layout(
        title=f'Top 10 Performers - {period_days} Days',
        xaxis_title="Company",
        yaxis_title="Gain (%)",
        showlegend=False,
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display data table
    st.dataframe(
        top_10.style.format({'Gain': '{:.2f}%'}),
        hide_index=True
    )

# Set page config
st.set_page_config(
    page_title="Stock Market Insights",
    page_icon="📈",
    layout="wide"
)

# Add title and description
st.title("Stock Market Insights")
st.write("Advanced stock analysis and prediction platform with investment calculator")

# Add Top Performers section
st.header("Top 10 Performing Stocks")

# Initialize session state for caching
if 'performance_cache' not in st.session_state:
    st.session_state.performance_cache = {}

# Create tabs for different time periods
period_tabs = st.tabs(["30 Days", "60 Days", "90 Days", "120 Days"])
periods = [30, 60, 90, 120]

# Display performance data in tabs
for tab, period in zip(period_tabs, periods):
    with tab:
        if period not in st.session_state.performance_cache:
            with st.spinner(f'Fetching {period}-day performance data...'):
                performances = get_top_performing_stocks(period)
                st.session_state.performance_cache[period] = performances
        
        display_top_performers(period, st.session_state.performance_cache[period])

# Add refresh button
if st.button("Refresh Performance Data"):
    st.session_state.performance_cache = {}
    st.rerun()

# Separator
st.write("---")

# Stock Search Section
st.write("Enter a company name to view detailed stock data and predictions.")
company_name = st.text_input("Enter company name (e.g., Apple)", "Apple")

if company_name:
    # Find matching companies using fuzzy matching
    matches = process.extract(company_name, list(COMPANY_SYMBOLS.keys()), limit=5)
    matching_companies = [match[0] for match in matches if match[1] >= 60]
    
    if not matching_companies:
        st.warning("No matching companies found. Please try a different company name.")
    else:
        # Create dropdown for company selection
        selected_company = st.selectbox("Select a company", matching_companies)
        
        if selected_company:
            stock_symbol = COMPANY_SYMBOLS[selected_company]
            
            try:
                with st.spinner('Fetching stock data...'):
                    stock = yf.Ticker(stock_symbol)
                    history = stock.history(period="1y")
                    
                    if history.empty:
                        st.error(f"No data available for {stock_symbol}")
                    else:
                        info = stock.info
                        
                        # Display company information
                        st.header(f"{info['longName']} ({stock_symbol})")
                        st.subheader("Company Information")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"Sector: {info.get('sector', 'N/A')}")
                            st.write(f"Industry: {info.get('industry', 'N/A')}")
                            st.write(f"Country: {info.get('country', 'N/A')}")
                        with col2:
                            st.write(f"Market Cap: ${info.get('marketCap', 'N/A'):,}")
                            st.write(f"52 Week High: ${info.get('fiftyTwoWeekHigh', 'N/A'):.2f}")
                            st.write(f"52 Week Low: ${info.get('fiftyTwoWeekLow', 'N/A'):.2f}")
                        
                        # Financial data table
                        st.subheader("Key Financial Data")
                        financial_data = pd.DataFrame({
                            "Metric": ["Current Price", "P/E Ratio", "Forward P/E", "PEG Ratio", "Dividend Yield", "Book Value"],
                            "Value": [
                                f"${info.get('currentPrice', 'N/A'):.2f}",
                                f"{info.get('trailingPE', 'N/A'):.2f}",
                                f"{info.get('forwardPE', 'N/A'):.2f}",
                                f"{info.get('pegRatio', 'N/A'):.2f}",
                                f"{info.get('dividendYield', 'N/A')*100:.2f}%" if info.get('dividendYield') else 'N/A',
                                f"${info.get('bookValue', 'N/A'):.2f}"
                            ]
                        })
                        st.table(financial_data)
                        
                        # Stock price history chart
                        st.subheader("Stock Price History")
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=history.index, y=history['Close'], name="Close Price"))
                        fig.update_layout(
                            title=f"{stock_symbol} Stock Price - Past Year",
                            xaxis_title="Date",
                            yaxis_title="Price (USD)"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Download CSV button
                        csv = history.to_csv().encode('utf-8')
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"{stock_symbol}_stock_data.csv",
                            mime="text/csv"
                        )
                        
                        # Stock prediction section
                        st.header("Stock Price Predictions")
                        with st.spinner('Generating predictions...'):
                            predictions = predict_stock_trend(history, stock_symbol)
                            
                            # Display Random Forest predictions
                            rf_pred, rf_conf, rf_explanation = predictions['Random Forest']
                            st.subheader("Random Forest Model Prediction")
                            st.write(f"**Prediction:** The stock is expected to {rf_pred} over the next 7 days")
                            st.write(f"**Confidence:** {rf_conf:.2f}%")
                            
                            # Display enhanced analysis
                            st.write("**Technical Analysis:**")
                            st.write(rf_explanation['technical_analysis'])
                            
                            if rf_explanation['news_analysis']:
                                st.write("**Recent News Impact:**")
                                for news in rf_explanation['news_analysis']:
                                    st.markdown(f"- **{news['source']}:** [{news['headline']}]({news['url']}) - {news['impact']}")
                            
                            st.write("**Overall Analysis:**")
                            st.write(rf_explanation['combined_analysis'])
                            st.write("---")
                            
                            # Display ARIMA predictions
                            arima_predictions = predictions['ARIMA']
                            if arima_predictions:
                                st.subheader("ARIMA Model Predictions")
                                
                                # Create tabs for different forecast periods
                                forecast_tabs = st.tabs(["7 Days", "15 Days", "30 Days", "90 Days", "120 Days"])
                                forecast_periods = [7, 15, 30, 90, 120]
                                
                                for tab, period in zip(forecast_tabs, forecast_periods):
                                    with tab:
                                        forecast_data = arima_predictions[period]
                                        st.write(f"**{period}-Day Forecast**")
                                        st.write(f"**Prediction:** The stock is expected to {forecast_data['prediction']} over the next {period} days")
                                        st.write(f"**Confidence:** {forecast_data['confidence']:.2f}%")
                                        
                                        if forecast_data.get('news_analysis'):
                                            st.write("**News Impact on Forecast:**")
                                            for news in forecast_data['news_analysis']:
                                                st.markdown(f"- **{news['source']}:** [{news['headline']}]({news['url']}) - {news['impact']}")
                                        
                                        # Plot forecast with confidence intervals
                                        fig = go.Figure()
                                        fig.add_trace(go.Scatter(
                                            x=history.index[-30:],
                                            y=history['Close'][-30:],
                                            name="Historical Price"
                                        ))
                                        fig.add_trace(go.Scatter(
                                            x=forecast_data['daily_forecasts'].index,
                                            y=forecast_data['daily_forecasts'],
                                            name="Forecast",
                                            line=dict(dash='dash')
                                        ))
                                        fig.add_trace(go.Scatter(
                                            x=forecast_data['upper_bound'].index,
                                            y=forecast_data['upper_bound'],
                                            fill=None,
                                            mode='lines',
                                            line_color='rgba(0,100,80,0.2)',
                                            name='Upper Bound'
                                        ))
                                        fig.add_trace(go.Scatter(
                                            x=forecast_data['lower_bound'].index,
                                            y=forecast_data['lower_bound'],
                                            fill='tonexty',
                                            mode='lines',
                                            line_color='rgba(0,100,80,0.2)',
                                            name='Lower Bound'
                                        ))
                                        fig.update_layout(
                                            title=f"{period}-Day Price Forecast",
                                            xaxis_title="Date",
                                            yaxis_title="Price (USD)",
                                            showlegend=True
                                        )
                                        st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.error("ARIMA prediction failed. This might be due to insufficient or invalid data.")

                        # Investment Calculator Section
                        st.header(f"Investment Calculator - {selected_company} ({stock_symbol})")
                        st.write(f"Calculate potential returns for your investment in {selected_company} based on our prediction models.")
                        st.write(f"Current Stock Price: ${info['currentPrice']:.2f}")
                        investment_amount = st.number_input("Enter investment amount ($)", min_value=100, step=100, value=1000)
                        
                        if arima_predictions:
                            # Create investment analysis table
                            investment_data = []
                            
                            for period in [7, 15, 30, 90, 120]:
                                forecast = arima_predictions[period]
                                current_price = forecast['last_price']
                                
                                # Calculate number of shares
                                shares = investment_amount / current_price
                                
                                # Calculate predicted values
                                predicted_price = forecast['daily_forecasts'][-1]
                                upper_price = forecast['upper_bound'][-1]
                                lower_price = forecast['lower_bound'][-1]
                                
                                # Calculate returns
                                predicted_value = shares * predicted_price
                                potential_gain = predicted_value - investment_amount
                                potential_return = (potential_gain / investment_amount) * 100
                                
                                # Calculate best/worst case
                                best_case = shares * upper_price - investment_amount
                                worst_case = shares * lower_price - investment_amount
                                
                                # Determine risk level based on confidence intervals
                                price_range = upper_price - lower_price
                                price_volatility = price_range / predicted_price
                                risk_level = "High" if price_volatility > 0.15 else "Medium" if price_volatility > 0.07 else "Low"
                                
                                investment_data.append({
                                    "Timeframe": f"{period} Days",
                                    "Predicted Value": f"${predicted_value:,.2f}",
                                    "Potential Gain/Loss": f"${potential_gain:,.2f}",
                                    "Return": f"{potential_return:.1f}%",
                                    "Risk Level": risk_level,
                                    "Best Case": best_case,
                                    "Worst Case": worst_case,
                                    "Timeline": forecast['daily_forecasts'].index,
                                    "Values": forecast['daily_forecasts'] * (investment_amount / current_price),
                                    "Upper": forecast['upper_bound'] * (investment_amount / current_price),
                                    "Lower": forecast['lower_bound'] * (investment_amount / current_price)
                                })
                            
                            # Display investment analysis table
                            st.subheader("Investment Analysis")
                            investment_df = pd.DataFrame(investment_data)
                            st.table(investment_df[["Timeframe", "Predicted Value", "Potential Gain/Loss", "Return", "Risk Level"]])
                            
                            # Create investment growth chart
                            st.subheader("Potential Investment Growth")
                            selected_period = st.selectbox("Select timeframe", [7, 15, 30, 90, 120], format_func=lambda x: f"{x} Days")
                            
                            selected_data = next(data for data in investment_data if data["Timeframe"] == f"{selected_period} Days")
                            
                            fig = go.Figure()
                            
                            # Add initial investment line
                            fig.add_hline(y=investment_amount, line_dash="dash", line_color="gray", name="Initial Investment")
                            
                            # Add predicted growth
                            fig.add_trace(go.Scatter(
                                x=selected_data["Timeline"],
                                y=selected_data["Values"],
                                name="Expected Growth",
                                line=dict(color="blue")
                            ))
                            
                            # Add confidence intervals
                            fig.add_trace(go.Scatter(
                                x=selected_data["Timeline"],
                                y=selected_data["Upper"],
                                fill=None,
                                mode="lines",
                                line_color="rgba(0,100,80,0.2)",
                                name="Optimistic Scenario"
                            ))
                            
                            fig.add_trace(go.Scatter(
                                x=selected_data["Timeline"],
                                y=selected_data["Lower"],
                                fill="tonexty",
                                mode="lines",
                                line_color="rgba(0,100,80,0.2)",
                                name="Pessimistic Scenario"
                            ))
                            
                            fig.update_layout(
                                title=f"Potential {selected_period}-Day Investment Growth",
                                xaxis_title="Date",
                                yaxis_title="Investment Value ($)",
                                showlegend=True,
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                            st.write("""
                            **Note:**
                            - The expected growth line shows the most likely path based on historical data and current trends.
                            - The shaded area represents the range of potential outcomes, with the upper and lower bounds showing optimistic and pessimistic scenarios.
                            - Risk levels are calculated based on the volatility of predictions:
                                - Low: Less than 7% price variation
                                - Medium: 7-15% price variation
                                - High: More than 15% price variation
                            """)

            except Exception as e:
                st.error(f"Error fetching data for {stock_symbol}. Please try again.")
                st.exception(e)

# Add footer
st.markdown("---")
st.write("Data provided by Yahoo Finance. This app is for educational purposes only and should not be used for financial advice.")
