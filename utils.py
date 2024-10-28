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
from textblob import TextBlob
import yfinance as yf

def validate_data_quality(df):
    """Check data quality and completeness."""
    if df is None or len(df) < 14:
        print("Insufficient data for analysis")
        return False
    
    # Check for missing values
    missing_pct = df.isnull().sum() / len(df) * 100
    if missing_pct.max() > 20:
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
    """Add enhanced technical indicators to the dataframe."""
    try:
        # Trend Indicators
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
        
        # Enhanced Indicators
        if len(df) >= 14:
            # Volatility
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'])
            df['BB_Band'] = ta.volatility.bollinger_pband(df['Close'])
            
            # Momentum
            df['RSI'] = ta.momentum.rsi(df['Close'])
            df['Stoch_RSI'] = ta.momentum.stochrsi(df['Close'])
            
            # Trend Strength
            df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'])
        
        return df
    except Exception as e:
        print(f"Error in technical indicators calculation: {str(e)}")
        return df

def get_stock_news(symbol, limit=10):
    """Fetch and analyze news for a given stock symbol"""
    try:
        stock = yf.Ticker(symbol)
        news = stock.news
        
        if not news:
            return None
        
        CREDIBLE_SOURCES = ['Wall Street Journal', 'Financial Times', 'Reuters', 'Bloomberg', 
                           'CNBC', 'MarketWatch', 'Barron\'s', 'Forbes', 'WSJ', 'FT']
        
        analyzed_news = []
        for article in news[:limit]:
            source = article.get('publisher', '')
            if any(src.lower() in source.lower() for src in CREDIBLE_SOURCES):
                headline = article.get('title', '')
                blob = TextBlob(headline)
                sentiment_score = blob.sentiment.polarity
                
                analyzed_news.append({
                    'headline': headline,
                    'source': source,
                    'url': article.get('link', ''),
                    'published': article.get('providerPublishTime', ''),
                    'sentiment': sentiment_score,
                    'summary': article.get('summary', '')
                })
        
        analyzed_news.sort(key=lambda x: (abs(x['sentiment']), x['published']), reverse=True)
        return analyzed_news[:3]
        
    except Exception as e:
        print(f"Error fetching news: {str(e)}")
        return None

def calculate_news_sentiment_score(news_data):
    """Calculate overall news sentiment score"""
    if not news_data:
        return 0.0, []
    
    total_sentiment = sum(article['sentiment'] for article in news_data)
    avg_sentiment = total_sentiment / len(news_data)
    
    news_impacts = []
    for article in news_data:
        sentiment_str = "positive" if article['sentiment'] > 0 else "negative" if article['sentiment'] < 0 else "neutral"
        impact = {
            'headline': article['headline'],
            'source': article['source'],
            'url': article['url'],
            'impact': f"This {sentiment_str} news suggests {'upward' if article['sentiment'] > 0 else 'downward'} pressure on the stock price"
        }
        news_impacts.append(impact)
    
    return avg_sentiment, news_impacts

def generate_technical_explanation(current_values):
    """Generate technical analysis explanation."""
    explanation = []
    
    if 'RSI' in current_values:
        rsi = current_values['RSI']
        if rsi > 70:
            explanation.append(f"Strong overbought conditions (RSI: {rsi:.1f})")
        elif rsi < 30:
            explanation.append(f"Strong oversold conditions (RSI: {rsi:.1f})")
    
    if all(x in current_values for x in ['MACD', 'MACD_Signal']):
        macd_diff = current_values['MACD'] - current_values['MACD_Signal']
        if macd_diff > 0:
            explanation.append("Bullish MACD crossover")
        else:
            explanation.append("Bearish MACD crossover")
    
    if 'ADX' in current_values:
        adx = current_values['ADX']
        if adx > 25:
            explanation.append(f"Strong trend strength (ADX: {adx:.1f})")
    
    if not explanation:
        explanation.append("Limited technical indicators available")
    
    return " | ".join(explanation)

def random_forest_prediction(history, symbol=None):
    """Enhanced Random Forest prediction with news sentiment analysis"""
    try:
        if not validate_data_quality(history):
            return "uncertain", 35, {"technical_analysis": "Insufficient data", "news_analysis": None, "combined_analysis": "Insufficient data for analysis"}
        
        news_data = get_stock_news(symbol) if symbol else None
        news_sentiment, news_impacts = calculate_news_sentiment_score(news_data)
        
        df = history.copy()
        df['Tomorrow'] = df['Close'].shift(-1)
        df['Target'] = (df['Tomorrow'] > df['Close']).astype(int)
        
        df = add_technical_indicators(df)
        df = df.dropna()
        
        if len(df) < 14:
            return "uncertain", 35, {"technical_analysis": "Insufficient data", "news_analysis": None, "combined_analysis": "Insufficient data after preprocessing"}
        
        if news_sentiment != 0:
            df['NewsSentiment'] = news_sentiment
        
        features = [col for col in df.columns if col not in ['Tomorrow', 'Target']]
        X = df[features]
        y = df['Target']
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=features)
        
        # Create and train multiple RF models
        rf1 = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
        rf2 = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=43)
        rf3 = RandomForestClassifier(n_estimators=200, max_depth=20, random_state=44)
        
        voting_clf = VotingClassifier(
            estimators=[('rf1', rf1), ('rf2', rf2), ('rf3', rf3)],
            voting='soft'
        )
        
        voting_clf.fit(X_scaled, y)
        
        last_data = X_scaled.iloc[-1].values.reshape(1, -1)
        prediction_proba = voting_clf.predict_proba(last_data)[0]
        prediction = "increase" if prediction_proba[1] > 0.5 else "decrease"
        confidence = max(prediction_proba) * 100
        
        technical_explanation = generate_technical_explanation(X.iloc[-1])
        
        final_explanation = {
            'technical_analysis': technical_explanation,
            'news_analysis': news_impacts if news_impacts else None,
            'combined_analysis': (
                f"Based on {'both ' if news_impacts else ''}technical analysis{' and recent news' if news_impacts else ''}, "
                f"the model predicts a {prediction} trend. "
                f"{'News sentiment is ' + ('positive' if news_sentiment > 0 else 'negative' if news_sentiment < 0 else 'neutral') + '.' if news_impacts else ''}"
            )
        }
        
        return prediction, confidence, final_explanation
        
    except Exception as e:
        print(f"Error in Random Forest prediction: {str(e)}")
        return "uncertain", 35, {"technical_analysis": f"Error: {str(e)}", "news_analysis": None, "combined_analysis": "Error in prediction"}

def get_arima_prediction(history, symbol=None):
    """Enhanced ARIMA prediction with news sentiment integration"""
    try:
        if not validate_data_quality(history):
            return None
        
        news_data = get_stock_news(symbol) if symbol else None
        news_sentiment, news_impacts = calculate_news_sentiment_score(news_data)
        
        df = history['Close'].resample('D').ffill()
        
        adf_result = adfuller(df)
        is_stationary = adf_result[1] < 0.05
        d = 0 if is_stationary else 1
        
        if not is_stationary:
            df = df.diff().dropna()
        
        model = ARIMA(df, order=(2, d, 2))
        results = model.fit()
        
        periods = [7, 15, 30, 90, 120]
        forecasts = {}
        
        for period in periods:
            forecast = results.get_forecast(steps=period)
            mean_forecast = forecast.predicted_mean
            conf_int = forecast.conf_int(alpha=0.05)
            
            if not is_stationary:
                mean_forecast = np.cumsum(mean_forecast) + history['Close'].iloc[-1]
                conf_int = pd.DataFrame(np.cumsum(conf_int, axis=0), columns=['lower', 'upper'])
                conf_int += history['Close'].iloc[-1]
            
            dates = [df.index[-1] + datetime.timedelta(days=i+1) for i in range(period)]
            
            forecast_series = pd.Series(mean_forecast, index=dates)
            lower_bound = pd.Series(conf_int['lower'], index=dates)
            upper_bound = pd.Series(conf_int['upper'], index=dates)
            
            if news_sentiment != 0:
                sentiment_adjustment = news_sentiment * 0.02
                forecast_series *= (1 + sentiment_adjustment)
                lower_bound *= (1 + sentiment_adjustment)
                upper_bound *= (1 + sentiment_adjustment)
            
            trend = "increase" if forecast_series.mean() > df.iloc[-1] else "decrease"
            confidence_range = np.mean((upper_bound - lower_bound) / forecast_series)
            confidence = max(min(100 - (confidence_range * 100), 100), 35)
            
            forecasts[period] = {
                'prediction': trend,
                'confidence': confidence,
                'daily_forecasts': forecast_series,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'last_price': history['Close'].iloc[-1],
                'news_analysis': news_impacts if news_impacts else None
            }
        
        return forecasts
        
    except Exception as e:
        print(f"Error in ARIMA prediction: {str(e)}")
        return None

def predict_stock_trend(history, symbol=None):
    """Combine Random Forest and ARIMA predictions with news integration"""
    try:
        rf_prediction, rf_confidence, rf_explanation = random_forest_prediction(history, symbol)
        arima_predictions = get_arima_prediction(history, symbol)
        
        return {
            'Random Forest': (rf_prediction, rf_confidence, rf_explanation),
            'ARIMA': arima_predictions
        }
    except Exception as e:
        print(f"Error in prediction: {str(e)}")
        return {
            'Random Forest': ("uncertain", 35, {"technical_analysis": f"Error: {str(e)}", "news_analysis": None, "combined_analysis": "Error in prediction"}),
            'ARIMA': None
        }
