import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

def predict_stock_trend(history):
    """
    Predict the stock trend using a simple Random Forest classifier.
    
    :param history: pandas DataFrame containing historical stock data
    :return: tuple (prediction, confidence)
    """
    # Prepare the data
    df = history.copy()
    df['Tomorrow'] = df['Close'].shift(-1)
    df['Target'] = (df['Tomorrow'] > df['Close']).astype(int)
    df = df.dropna()

    # Create features
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df = df.dropna()

    # Prepare features and target
    features = ['Close', 'Volume', 'SMA5', 'SMA20', 'RSI']
    X = df[features]
    y = df['Target']

    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train the model
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Make prediction
    last_data = X.iloc[-1].values.reshape(1, -1)
    prediction = model.predict(last_data)[0]

    # Calculate confidence
    y_pred = model.predict(X_test)
    confidence = accuracy_score(y_test, y_pred) * 100

    return ("increase" if prediction == 1 else "decrease", confidence)

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
