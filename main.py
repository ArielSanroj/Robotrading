import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from utils import predict_stock_trend
from fuzzywuzzy import process

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
    'McDonald\'s': 'MCD',
    'Boeing': 'BA',
    'JPMorgan': 'JPM',
    'Walmart': 'WMT',
    'Visa': 'V'
}

# App title and description
st.title("Stock Data Visualization and Prediction")
st.write("Enter a company name to view its stock data and predictions.")

# User input for company name
company_name = st.text_input("Enter company name (e.g., Apple)", "Apple")

if company_name:
    # Find matching companies using fuzzy matching
    matches = process.extract(company_name, list(COMPANY_SYMBOLS.keys()), limit=5)
    matching_companies = [match[0] for match in matches if match[1] >= 60]  # Only show matches with score >= 60
    
    if not matching_companies:
        st.warning("No matching companies found. Please try a different company name.")
    else:
        # Create dropdown for company selection
        selected_company = st.selectbox("Select a company", matching_companies)
        
        if selected_company:
            stock_symbol = COMPANY_SYMBOLS[selected_company]
            
            try:
                # Fetch stock data
                stock = yf.Ticker(stock_symbol)
                info = stock.info
                history = stock.history(period="1y")
                
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
                fig.update_layout(title=f"{stock_symbol} Stock Price - Past Year", xaxis_title="Date", yaxis_title="Price (USD)")
                st.plotly_chart(fig, use_container_width=True)
                
                # Download CSV button
                csv = history.to_csv().encode('utf-8')
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"{stock_symbol}_stock_data.csv",
                    mime="text/csv"
                )
                
                # Stock prediction
                st.header("Stock Price Predictions")
                predictions = predict_stock_trend(history)
                
                # Display Random Forest predictions
                rf_pred, rf_conf, rf_explanation = predictions['Random Forest']
                st.subheader("Random Forest Model Prediction")
                st.write(f"**Prediction:** The stock is expected to {rf_pred} over the next 7 days")
                st.write(f"**Confidence:** {rf_conf:.2f}%")
                st.write("**Analysis:**")
                st.write(rf_explanation)
                st.write("---")
                
                # Display ARIMA predictions with tabs
                st.subheader("ARIMA Model Predictions")
                arima_predictions = predictions['ARIMA']
                
                # Create tabs for different forecast periods
                tab7, tab15, tab30, tab90, tab120 = st.tabs([
                    "7 Days", "15 Days", "30 Days", "90 Days", "120 Days"
                ])
                
                # Function to display forecast data in a tab
                def display_forecast(tab, period, forecast_data):
                    with tab:
                        st.write(f"**{period}-Day Forecast**")
                        st.write(f"**Prediction:** The stock is expected to {forecast_data['prediction']} over the next {period} days")
                        st.write(f"**Confidence:** {forecast_data['confidence']:.2f}%")
                        
                        # Create forecast DataFrame
                        forecast_df = pd.DataFrame({
                            'Date': forecast_data['daily_forecasts'].index,
                            'Predicted Price': forecast_data['daily_forecasts'].values
                        })
                        st.dataframe(forecast_df.style.format({'Predicted Price': '${:.2f}'}))
                        
                        # Plot forecast
                        fig_forecast = go.Figure()
                        fig_forecast.add_trace(go.Scatter(
                            x=history.index[-30:],
                            y=history['Close'][-30:],
                            name="Historical Price"
                        ))
                        fig_forecast.add_trace(go.Scatter(
                            x=forecast_data['daily_forecasts'].index,
                            y=forecast_data['daily_forecasts'],
                            name="Forecast",
                            line=dict(dash='dash')
                        ))
                        fig_forecast.update_layout(
                            title=f"{period}-Day Price Forecast",
                            xaxis_title="Date",
                            yaxis_title="Price (USD)"
                        )
                        st.plotly_chart(fig_forecast, use_container_width=True)
                
                # Display forecasts in tabs
                display_forecast(tab7, 7, arima_predictions[7])
                display_forecast(tab15, 15, arima_predictions[15])
                display_forecast(tab30, 30, arima_predictions[30])
                display_forecast(tab90, 90, arima_predictions[90])
                display_forecast(tab120, 120, arima_predictions[120])
                
                st.write("---")
                st.write("Note: These predictions are based on historical data and should not be used as financial advice.")
                
            except Exception as e:
                st.error(f"Error fetching data for {stock_symbol}. Please try again.")
                st.exception(e)

# Add footer
st.markdown("---")
st.write("Data provided by Yahoo Finance. This app is for educational purposes only and should not be used for financial advice.")
