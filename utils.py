import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectFromModel
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.arima.model import ARIMA
import datetime
import ta.trend
import ta.momentum
import ta.volatility

def validate_data_quality(df):
    """Check data quality and completeness."""
    if df is None or len(df) < 14:  # Lowered minimum required data points to 14
        print("Insufficient data for analysis")
        return False
    
    # Check for missing values
    missing_pct = df.isnull().sum() / len(df) * 100
    if missing_pct.max() > 20:  # Maximum allowed missing percentage
        print("Too many missing values in the data")
        return False
    
    # Check for data consistency
    if (df['High'] < df['Low']).any():
        print("Inconsistent price data: High < Low")
        return False
    
    if (df['Close'] > df['High']).any() or (df['Close'] < df['Low']).any():
        print("Inconsistent price data: Close price outside High-Low range")
        return False
    
    return True

def add_technical_indicators(df):
    """Add enhanced technical indicators to the dataframe with data length checks."""
    try:
        # Original indicators (require at least 26 periods)
        if len(df) >= 26:
            df['SMA5'] = ta.trend.sma_indicator(df['Close'], window=5)
            df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
            df['EMA12'] = ta.trend.ema_indicator(df['Close'], window=12)
            df['EMA26'] = ta.trend.ema_indicator(df['Close'], window=26)
            
            # MACD
            macd = ta.trend.MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            df['MACD_Hist'] = macd.macd_diff()
        
        # Enhanced Volatility Indicators (require at least 14 periods)
        if len(df) >= 14:
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'])
            df['Volatility_BB'] = ta.volatility.bollinger_pband(df['Close'])
            df['Volatility_KC'] = ta.volatility.keltner_channel_pband(df['High'], df['Low'], df['Close'])
            df['Volatility_DC'] = ta.volatility.donchian_channel_pband(df['High'], df['Low'], df['Close'])
            
            # Enhanced Momentum Indicators
            df['RSI'] = ta.momentum.rsi(df['Close'])
            df['TSI'] = ta.momentum.tsi(df['Close'])
            df['UO'] = ta.momentum.ultimate_oscillator(df['High'], df['Low'], df['Close'])
            df['Stoch_RSI'] = ta.momentum.stochrsi(df['Close'])
            
            # Enhanced Trend Strength Indicators
            df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'])
            df['CCI'] = ta.trend.cci(df['High'], df['Low'], df['Close'])
            df['AROON_IND'] = ta.trend.aroon_indicator(df['Close'], window=25)
            df['MI'] = ta.trend.mass_index(df['High'], df['Low'])
        
        return df
    except Exception as e:
        print(f"Error in technical indicators calculation: {str(e)}")
        return df

def calculate_technical_confidence(current_values):
    """Calculate confidence based on available technical indicators."""
    confidence_factors = []
    
    # RSI
    if 'RSI' in current_values:
        rsi = current_values['RSI']
        if 30 <= rsi <= 70:
            confidence_factors.append(0.7)
        elif 20 <= rsi <= 80:
            confidence_factors.append(0.5)
        else:
            confidence_factors.append(0.3)
    
    # MACD
    if all(indicator in current_values for indicator in ['MACD', 'MACD_Signal']):
        macd_diff = abs(current_values['MACD'] - current_values['MACD_Signal'])
        if macd_diff > 0.5:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.6)
    
    # ADX
    if 'ADX' in current_values:
        adx = current_values['ADX']
        if adx > 25:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)
    
    # Calculate final confidence
    if confidence_factors:
        technical_confidence = (sum(confidence_factors) / len(confidence_factors)) * 100
        # Apply minimum baseline of 35% if we have valid indicators
        return max(technical_confidence, 35)
    
    return 35  # Minimum baseline confidence

def random_forest_prediction(history):
    """Enhanced Random Forest prediction with voting classifier and better validation."""
    try:
        if not validate_data_quality(history):
            return "uncertain", 35, "Insufficient or invalid data"
        
        df = history.copy()
        df['Tomorrow'] = df['Close'].shift(-1)
        df['Target'] = (df['Tomorrow'] > df['Close']).astype(int)
        
        # Add technical indicators
        df = add_technical_indicators(df)
        df = df.dropna()
        
        if len(df) < 14:  # Minimum required for meaningful prediction
            return "uncertain", 35, "Insufficient data after preprocessing"
        
        features = [col for col in df.columns if col not in ['Tomorrow', 'Target']]
        X = df[features]
        y = df['Target']
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=features)
        
        # Feature selection
        base_rf = RandomForestClassifier(n_estimators=100, random_state=42)
        selector = SelectFromModel(base_rf, prefit=False)
        selector.fit(X_scaled, y)
        selected_features = X_scaled.columns[selector.get_support()].tolist()
        X_selected = X_scaled[selected_features]
        
        # Create multiple RF models with different parameters
        rf1 = RandomForestClassifier(n_estimators=500, max_depth=10, min_samples_split=5, random_state=42)
        rf2 = RandomForestClassifier(n_estimators=500, max_depth=20, min_samples_split=10, random_state=43)
        rf3 = RandomForestClassifier(n_estimators=500, max_depth=15, min_samples_split=8, random_state=44)
        
        # Create voting classifier
        voting_clf = VotingClassifier(
            estimators=[('rf1', rf1), ('rf2', rf2), ('rf3', rf3)],
            voting='soft'
        )
        
        # Stratified K-fold cross-validation
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(voting_clf, X_selected, y, cv=skf, scoring='accuracy')
        
        # Fit the final model
        voting_clf.fit(X_selected, y)
        
        # Make prediction
        last_data = X_selected.iloc[-1].values.reshape(1, -1)
        prediction_proba = voting_clf.predict_proba(last_data)[0]
        prediction = 1 if prediction_proba[1] > 0.5 else 0
        
        # Calculate confidence using both model and technical indicators
        model_confidence = max(prediction_proba) * 100
        technical_confidence = calculate_technical_confidence(X.iloc[-1])
        
        # Combine confidences with weights
        confidence = 0.7 * model_confidence + 0.3 * technical_confidence
        
        # Generate explanation
        explanation = generate_rf_explanation(X.iloc[-1], df)
        
        return ("increase" if prediction == 1 else "decrease", confidence, explanation)
        
    except Exception as e:
        print(f"Error in Random Forest prediction: {str(e)}")
        return "uncertain", 35, f"Error in prediction: {str(e)}"

def generate_rf_explanation(current_values, df):
    """Generate enhanced technical analysis explanation."""
    explanation = []
    
    # RSI Analysis
    if 'RSI' in current_values:
        rsi = current_values['RSI']
        if rsi > 70:
            explanation.append(f"Strong overbought conditions (RSI: {rsi:.1f})")
        elif rsi < 30:
            explanation.append(f"Strong oversold conditions (RSI: {rsi:.1f})")
    
    # MACD Analysis
    if all(indicator in current_values for indicator in ['MACD', 'MACD_Signal']):
        if current_values['MACD'] > current_values['MACD_Signal']:
            explanation.append("Bullish MACD crossover")
        else:
            explanation.append("Bearish MACD crossover")
    
    # Trend Strength
    if 'ADX' in current_values:
        adx = current_values['ADX']
        if adx > 25:
            explanation.append(f"Strong trend (ADX: {adx:.1f})")
    
    # Volatility
    if 'Volatility_BB' in current_values and current_values['Volatility_BB'] > 1:
        explanation.append("High volatility indicated by Bollinger Bands")
    
    # Additional Technical Signals
    if 'UO' in current_values:
        uo = current_values['UO']
        if uo > 70:
            explanation.append("Bullish Ultimate Oscillator")
        elif uo < 30:
            explanation.append("Bearish Ultimate Oscillator")
    
    if not explanation:
        explanation.append("Limited technical indicators available")
    
    return " | ".join(explanation)

def get_arima_prediction(history):
    """Enhanced ARIMA prediction with improved confidence calculation."""
    try:
        if not validate_data_quality(history):
            return None
        
        # Resample to daily frequency and handle missing values
        df = history['Close'].resample('D').ffill()
        
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
            
            # Calculate trend
            trend = "increase" if forecast_series.mean() > df.iloc[-1] else "decrease"
            
            # Calculate confidence with minimum baseline
            confidence_range = np.mean((upper_bound - lower_bound) / forecast_series)
            raw_confidence = max(min(100 - (confidence_range * 100), 100), 0)
            confidence = max(raw_confidence, 35)  # Apply minimum baseline
            
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

def predict_stock_trend(history):
    '''Combine Random Forest and ARIMA predictions'''
    try:
        # Get Random Forest predictions
        rf_prediction, rf_confidence, rf_explanation = random_forest_prediction(history)
        
        # Get ARIMA predictions
        arima_predictions = get_arima_prediction(history)
        
        return {
            'Random Forest': (rf_prediction, rf_confidence, rf_explanation),
            'ARIMA': arima_predictions
        }
    except Exception as e:
        print(f"Error in prediction: {str(e)}")
        return {
            'Random Forest': ("uncertain", 35, f"Error: {str(e)}"),
            'ARIMA': None
        }
