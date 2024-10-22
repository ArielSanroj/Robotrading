import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from utils import predict_stock_trend

# Set page config
st.set_page_config(page_title="Stock Data Visualization and Prediction", layout="wide")

# App title and description
st.title("Stock Data Visualization and Prediction")
st.write("Enter a stock symbol to view its data and predictions.")

# User input for stock symbol
stock_symbol = st.text_input("Enter stock symbol (e.g., AAPL for Apple Inc.)", "AAPL")

if stock_symbol:
    # Fetch stock data
    try:
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
        st.subheader("Stock Price Prediction")
        predictions = predict_stock_trend(history)
        
        for model, (prediction, confidence) in predictions.items():
            st.write(f"{model} Model:")
            st.write(f"Prediction: The stock price is expected to {prediction} in the near future.")
            st.write(f"Confidence: {confidence:.2f}%")
            st.write("---")
        
        st.write("Note: These predictions are based on historical data and should not be used as financial advice.")
        
    except Exception as e:
        st.error(f"Error fetching data for {stock_symbol}. Please check the symbol and try again.")
        st.exception(e)

# Add footer
st.markdown("---")
st.write("Data provided by Yahoo Finance. This app is for educational purposes only and should not be used for financial advice.")
