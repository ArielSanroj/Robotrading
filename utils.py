import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from statsmodels.tsa.arima.model import ARIMA

def predict_stock_trend(history):
    """
    Predict the stock trend using multiple models.
    
    :param history: pandas DataFrame containing historical stock data
    :return: dict containing predictions and confidences for each model
    """
    rf_prediction, rf_confidence = random_forest_prediction(history)
    arima_pred, arima_conf = get_arima_prediction(history)
    
    return {
        'Random Forest': (rf_prediction, rf_confidence),
        'ARIMA': (arima_pred, arima_conf)
    }

def random_forest_prediction(history):
    """
    Predict the stock trend using a Random Forest classifier.
    
    :param history: pandas DataFrame containing historical stock data
    :return: tuple (prediction, confidence)
    """
    df = history.copy()
    df['Tomorrow'] = df['Close'].shift(-1)
    df['Target'] = (df['Tomorrow'] > df['Close']).astype(int)
    df = df.dropna()

    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df = df.dropna()

    features = ['Close', 'Volume', 'SMA5', 'SMA20', 'RSI']
    X = df[features]
    y = df['Target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    last_data = X.iloc[-1].values.reshape(1, -1)
    prediction = model.predict(last_data)[0]

    y_pred = model.predict(X_test)
    confidence = accuracy_score(y_test, y_pred) * 100

    return ("increase" if prediction == 1 else "decrease", confidence)

def get_arima_prediction(history):
    """
    Predict the stock trend using ARIMA model.
    
    :param history: pandas DataFrame containing historical stock data
    :return: tuple (prediction, confidence)
    """
    df = history['Close'].resample('D').last().fillna(method='ffill')
    model = ARIMA(df, order=(1, 1, 1))
    results = model.fit()
    
    forecast = results.forecast(steps=1)
    prediction = "increase" if forecast[0] > df.iloc[-1] else "decrease"
    
    # Use AIC as a proxy for confidence (lower AIC is better)
    confidence = 100 / (1 + results.aic)
    
    return (prediction, confidence)

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
