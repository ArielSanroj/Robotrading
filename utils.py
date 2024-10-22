import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.arima.model import ARIMA
import datetime
import ta

def predict_stock_trend(history):
    """
    Predict the stock trend using multiple models.
    
    :param history: pandas DataFrame containing historical stock data
    :return: dict containing predictions and confidences for each model
    """
    rf_prediction, rf_confidence, rf_explanation = random_forest_prediction(history)
    arima_predictions = get_arima_prediction(history)
    
    return {
        'Random Forest': (rf_prediction, rf_confidence, rf_explanation),
        'ARIMA': arima_predictions
    }

def add_technical_indicators(df):
    """Add technical indicators to the dataframe."""
    # Trend Indicators
    df['SMA5'] = ta.trend.sma_indicator(df['Close'], window=5)
    df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['EMA12'] = ta.trend.ema_indicator(df['Close'], window=12)
    df['EMA26'] = ta.trend.ema_indicator(df['Close'], window=26)
    
    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()
    
    # Bollinger Bands
    bollinger = ta.volatility.BollingerBands(df['Close'])
    df['BB_High'] = bollinger.bollinger_hband()
    df['BB_Low'] = bollinger.bollinger_lband()
    df['BB_Mid'] = bollinger.bollinger_mavg()
    
    # RSI and Stochastic
    df['RSI'] = ta.momentum.rsi(df['Close'])
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
    df['Stoch_K'] = stoch.stoch()
    df['Stoch_D'] = stoch.stoch_signal()
    
    # Volume indicators
    df['OBV'] = ta.volume.on_balance_volume(df['Close'], df['Volume'])
    df['Force_Index'] = ta.volume.force_index(df['Close'], df['Volume'])
    
    return df

def random_forest_prediction(history):
    """
    Predict the stock trend using an enhanced Random Forest classifier.
    
    :param history: pandas DataFrame containing historical stock data
    :return: tuple (prediction, confidence, explanation)
    """
    df = history.copy()
    df['Tomorrow'] = df['Close'].shift(-1)
    df['Target'] = (df['Tomorrow'] > df['Close']).astype(int)
    
    # Add technical indicators
    df = add_technical_indicators(df)
    df = df.dropna()

    features = ['Close', 'Volume', 'SMA5', 'SMA20', 'EMA12', 'EMA26', 
                'MACD', 'MACD_Signal', 'MACD_Hist',
                'BB_High', 'BB_Low', 'BB_Mid',
                'RSI', 'Stoch_K', 'Stoch_D',
                'OBV', 'Force_Index']
    
    X = df[features]
    y = df['Target']

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled = pd.DataFrame(X_scaled, columns=features)

    # Grid Search for optimal parameters
    param_grid = {
        'n_estimators': [200],
        'max_depth': [10, 20],
        'min_samples_split': [5, 10],
        'min_samples_leaf': [2, 4]
    }
    
    rf = RandomForestClassifier(random_state=42)
    grid_search = GridSearchCV(rf, param_grid, cv=5, scoring='accuracy')
    grid_search.fit(X_scaled, y)
    
    best_model = grid_search.best_estimator_
    
    # Cross-validation score
    cv_scores = cross_val_score(best_model, X_scaled, y, cv=5)
    cv_confidence = np.mean(cv_scores) * 100
    
    # Generate prediction
    last_data = X_scaled.iloc[-1].values.reshape(1, -1)
    prediction = best_model.predict(last_data)[0]
    
    # Feature importance and explanation
    feature_importance = dict(zip(features, best_model.feature_importances_))
    current_values = X.iloc[-1]
    explanation = generate_rf_explanation(feature_importance, current_values, df)
    
    return ("increase" if prediction == 1 else "decrease", cv_confidence, explanation)

def generate_rf_explanation(feature_importance, current_values, df):
    """Generate detailed explanation for Random Forest prediction."""
    explanation = []
    
    # Technical Analysis
    if current_values['RSI'] > 70:
        explanation.append("RSI indicates strong overbought conditions (>70)")
    elif current_values['RSI'] < 30:
        explanation.append("RSI indicates strong oversold conditions (<30)")
    
    if current_values['MACD'] > current_values['MACD_Signal']:
        explanation.append("MACD shows bullish crossover")
    else:
        explanation.append("MACD shows bearish crossover")
    
    if current_values['Close'] > current_values['BB_High']:
        explanation.append("Price above upper Bollinger Band (overbought)")
    elif current_values['Close'] < current_values['BB_Low']:
        explanation.append("Price below lower Bollinger Band (oversold)")
    
    # Most important features
    sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
    top_features = sorted_features[:3]
    explanation.append("Top indicators: " + ", ".join([f"{name} ({importance:.2f})" 
                                                     for name, importance in top_features]))
    
    return " | ".join(explanation)

def get_arima_prediction(history):
    """
    Predict the stock trend using ARIMA model with enhanced error handling.
    
    :param history: pandas DataFrame containing historical stock data
    :return: dict containing predictions for different time periods
    """
    try:
        # Resample to daily frequency and handle missing values
        df = history['Close'].resample('D').last().fillna(method='ffill')
        
        # Test for stationarity
        adf_result = adfuller(df)
        is_stationary = adf_result[1] < 0.05
        
        # If not stationary, take first difference
        d = 0 if is_stationary else 1
        if not is_stationary:
            df = df.diff().dropna()
        
        # Fit ARIMA model with optimized parameters
        model = ARIMA(df, order=(2, d, 2))
        results = model.fit()
        
        # Define forecast periods
        periods = [7, 15, 30, 90, 120]
        forecasts = {}
        
        for period in periods:
            # Get forecast with confidence intervals
            forecast = results.get_forecast(steps=period)
            mean_forecast = forecast.predicted_mean
            conf_int = forecast.conf_int(alpha=0.05)
            
            # If we differenced the data, cumsum to get back original scale
            if not is_stationary:
                mean_forecast = np.cumsum(mean_forecast) + history['Close'].iloc[-1]
                conf_int = pd.DataFrame(np.cumsum(conf_int, axis=0), columns=['lower', 'upper'])
                conf_int += history['Close'].iloc[-1]
            
            # Generate dates for the forecast period
            dates = [df.index[-1] + datetime.timedelta(days=i+1) for i in range(period)]
            
            # Create series for the forecast and confidence intervals
            forecast_series = pd.Series(mean_forecast, index=dates)
            lower_bound = pd.Series(conf_int['lower'], index=dates)
            upper_bound = pd.Series(conf_int['upper'], index=dates)
            
            # Calculate trend and confidence
            trend = "increase" if forecast_series.mean() > df.iloc[-1] else "decrease"
            
            # Calculate confidence score based on prediction intervals
            confidence_range = (upper_bound - lower_bound) / forecast_series
            confidence = (100 - np.mean(confidence_range) * 100).clip(0, 100)
            
            forecasts[period] = {
                'prediction': trend,
                'confidence': confidence,
                'daily_forecasts': forecast_series,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'last_price': history['Close'].iloc[-1]
            }
        
        return forecasts
        
    except Exception as e:
        print(f"Error in ARIMA prediction: {str(e)}")
        return None

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator."""
    return ta.momentum.rsi(prices, window=period)
