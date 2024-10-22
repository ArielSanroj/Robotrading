import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from statsmodels.tsa.arima.model import ARIMA
import datetime

def predict_stock_trend(history):
    """
    Predict the stock trend using multiple models.
    
    :param history: pandas DataFrame containing historical stock data
    :return: dict containing predictions and confidences for each model
    """
    rf_prediction, rf_confidence, rf_explanation = random_forest_prediction(history)
    arima_pred, arima_conf, daily_forecasts = get_arima_prediction(history)
    
    return {
        'Random Forest': (rf_prediction, rf_confidence, rf_explanation),
        'ARIMA': (arima_pred, arima_conf, daily_forecasts)
    }

def random_forest_prediction(history):
    """
    Predict the stock trend using a Random Forest classifier.
    
    :param history: pandas DataFrame containing historical stock data
    :return: tuple (prediction, confidence, explanation)
    """
    df = history.copy()
    df['Tomorrow'] = df['Close'].shift(-1)
    df['Target'] = (df['Tomorrow'] > df['Close']).astype(int)
    df = df.dropna()

    # Calculate technical indicators
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['Price_Change'] = df['Close'].pct_change()
    df['Volume_Change'] = df['Volume'].pct_change()
    df = df.dropna()

    features = ['Close', 'Volume', 'SMA5', 'SMA20', 'RSI', 'Price_Change', 'Volume_Change']
    X = df[features]
    y = df['Target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Get feature importance and current values
    feature_importance = dict(zip(features, model.feature_importances_))
    current_values = X.iloc[-1]
    
    # Generate explanation
    explanation = generate_rf_explanation(feature_importance, current_values, df)

    last_data = X.iloc[-1].values.reshape(1, -1)
    prediction = model.predict(last_data)[0]

    y_pred = model.predict(X_test)
    confidence = accuracy_score(y_test, y_pred) * 100

    return ("increase" if prediction == 1 else "decrease", confidence, explanation)

def generate_rf_explanation(feature_importance, current_values, df):
    """Generate explanation for Random Forest prediction based on feature importance."""
    explanation = []
    
    # RSI analysis
    if current_values['RSI'] > 70:
        explanation.append("RSI indicates overbought conditions (>70)")
    elif current_values['RSI'] < 30:
        explanation.append("RSI indicates oversold conditions (<30)")
    
    # Moving averages analysis
    if current_values['SMA5'] > current_values['SMA20']:
        explanation.append("Short-term trend is above long-term trend (bullish)")
    else:
        explanation.append("Short-term trend is below long-term trend (bearish)")
    
    # Volume analysis
    if current_values['Volume_Change'] > 0.1:
        explanation.append("Significant increase in trading volume")
    
    # Most important features
    sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
    explanation.append(f"Most influential indicators: {sorted_features[0][0]} ({sorted_features[0][1]:.2f}), "
                      f"{sorted_features[1][0]} ({sorted_features[1][1]:.2f})")
    
    return " | ".join(explanation)

def get_arima_prediction(history):
    """
    Predict the stock trend using ARIMA model.
    
    :param history: pandas DataFrame containing historical stock data
    :return: tuple (prediction, confidence, daily_forecasts)
    """
    df = history['Close'].resample('D').last().ffill()
    model = ARIMA(df, order=(1, 1, 1))
    results = model.fit()
    
    # Generate 7-day forecast
    forecast = results.forecast(steps=7)
    dates = [df.index[-1] + datetime.timedelta(days=i+1) for i in range(7)]
    daily_forecasts = pd.Series(forecast, index=dates)
    
    # Determine overall trend
    prediction = "increase" if daily_forecasts.mean() > df.iloc[-1] else "decrease"
    
    # Use AIC as a proxy for confidence (lower AIC is better)
    confidence = 100 / (1 + results.aic)
    
    return (prediction, confidence, daily_forecasts)

def calculate_rsi(prices, period=14):
    """
    Calculate the Relative Strength Index (RSI) for a given price series.
    
    :param prices: pandas Series of prices
    :param period: RSI period (default is 14)
    :return: pandas Series containing RSI values
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
