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
import re
from datetime import datetime, timedelta

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

def extract_price_impact(text):
    """Extract specific price impact mentions from article text."""
    price_patterns = [
        r'(?:up|down|rise|fall|drop|jump|surge|plunge|increase|decrease)(?:\s+by\s+)?(\d+(?:\.\d+)?%?)',
        r'(\d+(?:\.\d+)?%?)(?:\s+)?(?:gain|loss|higher|lower)',
        r'price target(?:\s+of\s+)?\$(\d+(?:\.\d+)?)',
    ]
    
    impacts = []
    for pattern in price_patterns:
        matches = re.finditer(pattern, text.lower())
        for match in matches:
            impacts.append(match.group())
    
    return impacts

def calculate_relevance_score(article, current_price):
    """Calculate article relevance score based on content and date."""
    score = 0
    
    # Time relevance (max 40 points)
    pub_time = article.get('providerPublishTime', 0)
    if pub_time:
        hours_ago = (datetime.now() - datetime.fromtimestamp(pub_time)).total_seconds() / 3600
        if hours_ago <= 6:
            score += 40
        elif hours_ago <= 12:
            score += 35
        elif hours_ago <= 24:
            score += 30
        elif hours_ago <= 48:
            score += 20
        else:
            score += 10
    
    # Content relevance (max 60 points)
    text = f"{article.get('title', '')} {article.get('summary', '')}"
    
    # Check for price mentions
    price_impacts = extract_price_impact(text)
    score += len(price_impacts) * 10
    
    # Check for important keywords
    keywords = ['earnings', 'revenue', 'profit', 'guidance', 'forecast', 'analyst', 'upgrade', 'downgrade']
    for keyword in keywords:
        if keyword in text.lower():
            score += 5
    
    # Cap the total score at 100
    return min(score, 100)

def get_stock_news(symbol, limit=15):
    """Fetch and analyze news for a given stock symbol with enhanced credibility scoring"""
    try:
        stock = yf.Ticker(symbol)
        news = stock.news
        
        if not news:
            return None
        
        # Define credible sources with their credibility scores
        CREDIBLE_SOURCES = {
            'Wall Street Journal': 95,
            'WSJ': 95,
            'Financial Times': 95,
            'FT': 95,
            'Reuters': 90,
            'Bloomberg': 90,
            'CNBC': 85,
            'MarketWatch': 80,
            'Barron\'s': 80,
            'Forbes': 75
        }
        
        current_price = stock.info.get('currentPrice', 0)
        analyzed_news = []
        
        for article in news:
            source = article.get('publisher', '')
            credibility_score = 0
            
            # Calculate source credibility score
            for credible_source, score in CREDIBLE_SOURCES.items():
                if credible_source.lower() in source.lower():
                    credibility_score = score
                    break
            
            if credibility_score > 0:  # Only include articles from credible sources
                headline = article.get('title', '')
                summary = article.get('summary', '')
                full_text = f"{headline} {summary}"
                
                # Calculate sentiment
                blob = TextBlob(full_text)
                sentiment_score = blob.sentiment.polarity
                
                # Calculate relevance score
                relevance_score = calculate_relevance_score(article, current_price)
                
                # Extract price impacts
                price_impacts = extract_price_impact(full_text)
                
                analyzed_news.append({
                    'headline': headline,
                    'source': source,
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(article.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                    'sentiment': sentiment_score,
                    'credibility_score': credibility_score,
                    'relevance_score': relevance_score,
                    'summary': summary,
                    'price_impacts': price_impacts
                })
        
        # Sort by weighted score (credibility * relevance * abs(sentiment))
        analyzed_news.sort(key=lambda x: (
            x['credibility_score'] * x['relevance_score'] * (abs(x['sentiment']) + 0.1)
        ), reverse=True)
        
        return analyzed_news[:3]
        
    except Exception as e:
        print(f"Error fetching news: {str(e)}")
        return None

def calculate_news_sentiment_score(news_data):
    """Calculate overall news sentiment score with enhanced analysis"""
    if not news_data:
        return 0.0, []
    
    # Calculate weighted sentiment score
    weighted_sentiments = []
    for article in news_data:
        weight = (article['credibility_score'] * article['relevance_score']) / 10000
        weighted_sentiments.append(article['sentiment'] * weight)
    
    avg_sentiment = sum(weighted_sentiments) / len(weighted_sentiments) if weighted_sentiments else 0
    
    news_impacts = []
    for article in news_data:
        sentiment_str = "positive" if article['sentiment'] > 0 else "negative" if article['sentiment'] < 0 else "neutral"
        impact_strength = "strong" if abs(article['sentiment']) > 0.5 else "moderate" if abs(article['sentiment']) > 0.2 else "slight"
        
        impact = {
            'headline': article['headline'],
            'source': f"{article['source']} (Credibility: {article['credibility_score']}%)",
            'url': article['url'],
            'published': article['published'],
            'impact': (
                f"This {impact_strength} {sentiment_str} news from a highly credible source suggests "
                f"{'upward' if article['sentiment'] > 0 else 'downward'} pressure on the stock price. "
                f"{'Price impacts mentioned: ' + ', '.join(article['price_impacts']) if article['price_impacts'] else ''}"
            )
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
            
    if 'BB_Band' in current_values:
        bb = current_values['BB_Band']
        if bb > 0.8:
            explanation.append("Price near upper Bollinger Band (potential resistance)")
        elif bb < 0.2:
            explanation.append("Price near lower Bollinger Band (potential support)")
            
    if all(x in current_values for x in ['SMA5', 'SMA20']):
        if current_values['SMA5'] > current_values['SMA20']:
            explanation.append("Short-term uptrend (5-day SMA above 20-day)")
        else:
            explanation.append("Short-term downtrend (5-day SMA below 20-day)")
    
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
        
        # Create and train multiple RF models with different configurations
        rf1 = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
        rf2 = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=43)
        rf3 = RandomForestClassifier(n_estimators=200, max_depth=20, random_state=44)
        
        # Create ensemble with voting
        voting_clf = VotingClassifier(
            estimators=[('rf1', rf1), ('rf2', rf2), ('rf3', rf3)],
            voting='soft'
        )
        
        # Train the ensemble
        voting_clf.fit(X_scaled, y)
        
        # Make prediction with probability
        last_data = X_scaled.iloc[-1].values.reshape(1, -1)
        prediction_proba = voting_clf.predict_proba(last_data)[0]
        prediction = "increase" if prediction_proba[1] > 0.5 else "decrease"
        confidence = max(prediction_proba) * 100
        
        # Generate technical analysis explanation
        technical_explanation = generate_technical_explanation(X.iloc[-1])
        
        # Combine technical and news analysis
        final_explanation = {
            'technical_analysis': technical_explanation,
            'news_analysis': news_impacts if news_impacts else None,
            'combined_analysis': (
                f"Based on {'both ' if news_impacts else ''}technical analysis{' and recent news' if news_impacts else ''}, "
                f"the model predicts a {prediction} trend with {confidence:.1f}% confidence. "
                f"{'News sentiment is ' + ('positive' if news_sentiment > 0 else 'negative' if news_sentiment < 0 else 'neutral') + '. ' if news_impacts else ''}"
                f"Technical indicators show: {technical_explanation}."
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
        
        # Prepare data for ARIMA
        df = history['Close'].resample('D').ffill()
        
        # Check stationarity
        adf_result = adfuller(df)
        is_stationary = adf_result[1] < 0.05
        d = 0 if is_stationary else 1
        
        # Make data stationary if needed
        if not is_stationary:
            df = df.diff().dropna()
        
        # Fit ARIMA model
        model = ARIMA(df, order=(2, d, 2))
        results = model.fit()
        
        # Generate forecasts for different periods
        periods = [7, 15, 30, 90, 120]
        forecasts = {}
        
        for period in periods:
            # Get forecast with confidence intervals
            forecast = results.get_forecast(steps=period)
            mean_forecast = forecast.predicted_mean
            conf_int = forecast.conf_int(alpha=0.05)
            
            # Transform back if data was differenced
            if not is_stationary:
                mean_forecast = np.cumsum(mean_forecast) + history['Close'].iloc[-1]
                conf_int = pd.DataFrame(np.cumsum(conf_int, axis=0), columns=['lower', 'upper'])
                conf_int += history['Close'].iloc[-1]
            
            # Create forecast dates
            dates = [df.index[-1] + datetime.timedelta(days=i+1) for i in range(period)]
            
            # Create forecast series
            forecast_series = pd.Series(mean_forecast, index=dates)
            lower_bound = pd.Series(conf_int['lower'], index=dates)
            upper_bound = pd.Series(conf_int['upper'], index=dates)
            
            # Adjust forecasts based on news sentiment
            if news_sentiment != 0:
                sentiment_adjustment = news_sentiment * 0.02  # 2% adjustment per unit of sentiment
                forecast_series *= (1 + sentiment_adjustment)
                lower_bound *= (1 + sentiment_adjustment)
                upper_bound *= (1 + sentiment_adjustment)
            
            # Calculate trend and confidence
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
import re
from datetime import datetime, timedelta

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

def extract_price_impact(text):
    """Extract specific price impact mentions from article text."""
    price_patterns = [
        r'(?:up|down|rise|fall|drop|jump|surge|plunge|increase|decrease)(?:\s+by\s+)?(\d+(?:\.\d+)?%?)',
        r'(\d+(?:\.\d+)?%?)(?:\s+)?(?:gain|loss|higher|lower)',
        r'price target(?:\s+of\s+)?\$(\d+(?:\.\d+)?)',
    ]
    
    impacts = []
    for pattern in price_patterns:
        matches = re.finditer(pattern, text.lower())
        for match in matches:
            impacts.append(match.group())
    
    return impacts

def calculate_relevance_score(article, current_price):
    """Calculate article relevance score based on content and date."""
    score = 0
    
    # Time relevance (max 40 points)
    pub_time = article.get('providerPublishTime', 0)
    if pub_time:
        hours_ago = (datetime.now() - datetime.fromtimestamp(pub_time)).total_seconds() / 3600
        if hours_ago <= 6:
            score += 40
        elif hours_ago <= 12:
            score += 35
        elif hours_ago <= 24:
            score += 30
        elif hours_ago <= 48:
            score += 20
        else:
            score += 10
    
    # Content relevance (max 60 points)
    text = f"{article.get('title', '')} {article.get('summary', '')}"
    
    # Check for price mentions
    price_impacts = extract_price_impact(text)
    score += len(price_impacts) * 10
    
    # Check for important keywords
    keywords = ['earnings', 'revenue', 'profit', 'guidance', 'forecast', 'analyst', 'upgrade', 'downgrade']
    for keyword in keywords:
        if keyword in text.lower():
            score += 5
    
    # Cap the total score at 100
    return min(score, 100)

def get_stock_news(symbol, limit=15):
    """Fetch and analyze news for a given stock symbol with enhanced credibility scoring"""
    try:
        stock = yf.Ticker(symbol)
        news = stock.news
        
        if not news:
            return None
        
        # Define credible sources with their credibility scores
        CREDIBLE_SOURCES = {
            'Wall Street Journal': 95,
            'WSJ': 95,
            'Financial Times': 95,
            'FT': 95,
            'Reuters': 90,
            'Bloomberg': 90,
            'CNBC': 85,
            'MarketWatch': 80,
            'Barron\'s': 80,
            'Forbes': 75
        }
        
        current_price = stock.info.get('currentPrice', 0)
        analyzed_news = []
        
        for article in news:
            source = article.get('publisher', '')
            credibility_score = 0
            
            # Calculate source credibility score
            for credible_source, score in CREDIBLE_SOURCES.items():
                if credible_source.lower() in source.lower():
                    credibility_score = score
                    break
            
            if credibility_score > 0:  # Only include articles from credible sources
                headline = article.get('title', '')
                summary = article.get('summary', '')
                full_text = f"{headline} {summary}"
                
                # Calculate sentiment
                blob = TextBlob(full_text)
                sentiment_score = blob.sentiment.polarity
                
                # Calculate relevance score
                relevance_score = calculate_relevance_score(article, current_price)
                
                # Extract price impacts
                price_impacts = extract_price_impact(full_text)
                
                analyzed_news.append({
                    'headline': headline,
                    'source': source,
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(article.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                    'sentiment': sentiment_score,
                    'credibility_score': credibility_score,
                    'relevance_score': relevance_score,
                    'summary': summary,
                    'price_impacts': price_impacts
                })
        
        # Sort by weighted score (credibility * relevance * abs(sentiment))
        analyzed_news.sort(key=lambda x: (
            x['credibility_score'] * x['relevance_score'] * (abs(x['sentiment']) + 0.1)
        ), reverse=True)
        
        return analyzed_news[:3]
        
    except Exception as e:
        print(f"Error fetching news: {str(e)}")
        return None

def calculate_news_sentiment_score(news_data):
    """Calculate overall news sentiment score with enhanced analysis"""
    if not news_data:
        return 0.0, []
    
    # Calculate weighted sentiment score
    weighted_sentiments = []
    for article in news_data:
        weight = (article['credibility_score'] * article['relevance_score']) / 10000
        weighted_sentiments.append(article['sentiment'] * weight)
    
    avg_sentiment = sum(weighted_sentiments) / len(weighted_sentiments) if weighted_sentiments else 0
    
    news_impacts = []
    for article in news_data:
        sentiment_str = "positive" if article['sentiment'] > 0 else "negative" if article['sentiment'] < 0 else "neutral"
        impact_strength = "strong" if abs(article['sentiment']) > 0.5 else "moderate" if abs(article['sentiment']) > 0.2 else "slight"
        
        impact = {
            'headline': article['headline'],
            'source': f"{article['source']} (Credibility: {article['credibility_score']}%)",
            'url': article['url'],
            'published': article['published'],
            'impact': (
                f"This {impact_strength} {sentiment_str} news from a highly credible source suggests "
                f"{'upward' if article['sentiment'] > 0 else 'downward'} pressure on the stock price. "
                f"{'Price impacts mentioned: ' + ', '.join(article['price_impacts']) if article['price_impacts'] else ''}"
            )
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
            
    if 'BB_Band' in current_values:
        bb = current_values['BB_Band']
        if bb > 0.8:
            explanation.append("Price near upper Bollinger Band (potential resistance)")
        elif bb < 0.2:
            explanation.append("Price near lower Bollinger Band (potential support)")
            
    if all(x in current_values for x in ['SMA5', 'SMA20']):
        if current_values['SMA5'] > current_values['SMA20']:
            explanation.append("Short-term uptrend (5-day SMA above 20-day)")
        else:
            explanation.append("Short-term downtrend (5-day SMA below 20-day)")
    
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
        
        # Create and train multiple RF models with different configurations
        rf1 = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
        rf2 = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=43)
        rf3 = RandomForestClassifier(n_estimators=200, max_depth=20, random_state=44)
        
        # Create ensemble with voting
        voting_clf = VotingClassifier(
            estimators=[('rf1', rf1), ('rf2', rf2), ('rf3', rf3)],
            voting='soft'
        )
        
        # Train the ensemble
        voting_clf.fit(X_scaled, y)
        
        # Make prediction with probability
        last_data = X_scaled.iloc[-1].values.reshape(1, -1)
        prediction_proba = voting_clf.predict_proba(last_data)[0]
        prediction = "increase" if prediction_proba[1] > 0.5 else "decrease"
        confidence = max(prediction_proba) * 100
        
        # Generate technical analysis explanation
        technical_explanation = generate_technical_explanation(X.iloc[-1])
        
        # Combine technical and news analysis
        final_explanation = {
            'technical_analysis': technical_explanation,
            'news_analysis': news_impacts if news_impacts else None,
            'combined_analysis': (
                f"Based on {'both ' if news_impacts else ''}technical analysis{' and recent news' if news_impacts else ''}, "
                f"the model predicts a {prediction} trend with {confidence:.1f}% confidence. "
                f"{'News sentiment is ' + ('positive' if news_sentiment > 0 else 'negative' if news_sentiment < 0 else 'neutral') + '. ' if news_impacts else ''}"
                f"Technical indicators show: {technical_explanation}."
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
        
        # Convert index to UTC and localize timestamps
        df = history['Close'].copy()
        df.index = df.index.tz_localize(None)  # Remove timezone info
        df = df.resample('D').ffill()
        
        # Check stationarity
        adf_result = adfuller(df)
        is_stationary = adf_result[1] < 0.05
        d = 0 if is_stationary else 1
        
        # Make data stationary if needed
        if not is_stationary:
            df = df.diff().dropna()
        
        # Fit ARIMA model
        model = ARIMA(df, order=(2, d, 2))
        results = model.fit()
        
        # Generate forecasts for different periods
        periods = [7, 15, 30, 90, 120]
        forecasts = {}
        
        for period in periods:
            # Get forecast with confidence intervals
            forecast = results.get_forecast(steps=period)
            mean_forecast = forecast.predicted_mean
            conf_int = forecast.conf_int(alpha=0.05)
            
            # Transform back if data was differenced
            if not is_stationary:
                mean_forecast = np.cumsum(mean_forecast) + history['Close'].iloc[-1]
                conf_int = pd.DataFrame(np.cumsum(conf_int, axis=0), columns=['lower', 'upper'])
                conf_int += history['Close'].iloc[-1]
            
            # Create forecast dates
            dates = [df.index[-1] + datetime.timedelta(days=i+1) for i in range(period)]
            
            # Create forecast series
            forecast_series = pd.Series(mean_forecast, index=dates)
            lower_bound = pd.Series(conf_int['lower'], index=dates)
            upper_bound = pd.Series(conf_int['upper'], index=dates)
            
            # Adjust forecasts based on news sentiment
            if news_sentiment != 0:
                sentiment_adjustment = news_sentiment * 0.02  # 2% adjustment per unit of sentiment
                forecast_series *= (1 + sentiment_adjustment)
                lower_bound *= (1 + sentiment_adjustment)
                upper_bound *= (1 + sentiment_adjustment)
            
            # Calculate trend and confidence
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
import re
from datetime import datetime, timedelta

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

def extract_price_impact(text):
    """Extract specific price impact mentions from article text."""
    price_patterns = [
        r'(?:up|down|rise|fall|drop|jump|surge|plunge|increase|decrease)(?:\s+by\s+)?(\d+(?:\.\d+)?%?)',
        r'(\d+(?:\.\d+)?%?)(?:\s+)?(?:gain|loss|higher|lower)',
        r'price target(?:\s+of\s+)?\$(\d+(?:\.\d+)?)',
    ]
    
    impacts = []
    for pattern in price_patterns:
        matches = re.finditer(pattern, text.lower())
        for match in matches:
            impacts.append(match.group())
    
    return impacts

def calculate_relevance_score(article, current_price):
    """Calculate article relevance score based on content and date."""
    score = 0
    
    # Time relevance (max 40 points)
    pub_time = article.get('providerPublishTime', 0)
    if pub_time:
        hours_ago = (datetime.now() - datetime.fromtimestamp(pub_time)).total_seconds() / 3600
        if hours_ago <= 6:
            score += 40
        elif hours_ago <= 12:
            score += 35
        elif hours_ago <= 24:
            score += 30
        elif hours_ago <= 48:
            score += 20
        else:
            score += 10
    
    # Content relevance (max 60 points)
    text = f"{article.get('title', '')} {article.get('summary', '')}"
    
    # Check for price mentions
    price_impacts = extract_price_impact(text)
    score += len(price_impacts) * 10
    
    # Check for important keywords
    keywords = ['earnings', 'revenue', 'profit', 'guidance', 'forecast', 'analyst', 'upgrade', 'downgrade']
    for keyword in keywords:
        if keyword in text.lower():
            score += 5
    
    # Cap the total score at 100
    return min(score, 100)

def get_stock_news(symbol, limit=15):
    """Fetch and analyze news for a given stock symbol with enhanced credibility scoring"""
    try:
        stock = yf.Ticker(symbol)
        news = stock.news
        
        if not news:
            return None
        
        # Define credible sources with their credibility scores
        CREDIBLE_SOURCES = {
            'Wall Street Journal': 95,
            'WSJ': 95,
            'Financial Times': 95,
            'FT': 95,
            'Reuters': 90,
            'Bloomberg': 90,
            'CNBC': 85,
            'MarketWatch': 80,
            'Barron\'s': 80,
            'Forbes': 75
        }
        
        current_price = stock.info.get('currentPrice', 0)
        analyzed_news = []
        
        for article in news:
            source = article.get('publisher', '')
            credibility_score = 0
            
            # Calculate source credibility score
            for credible_source, score in CREDIBLE_SOURCES.items():
                if credible_source.lower() in source.lower():
                    credibility_score = score
                    break
            
            if credibility_score > 0:  # Only include articles from credible sources
                headline = article.get('title', '')
                summary = article.get('summary', '')
                full_text = f"{headline} {summary}"
                
                # Calculate sentiment
                blob = TextBlob(full_text)
                sentiment_score = blob.sentiment.polarity
                
                # Calculate relevance score
                relevance_score = calculate_relevance_score(article, current_price)
                
                # Extract price impacts
                price_impacts = extract_price_impact(full_text)
                
                analyzed_news.append({
                    'headline': headline,
                    'source': source,
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(article.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                    'sentiment': sentiment_score,
                    'credibility_score': credibility_score,
                    'relevance_score': relevance_score,
                    'summary': summary,
                    'price_impacts': price_impacts
                })
        
        # Sort by weighted score (credibility * relevance * abs(sentiment))
        analyzed_news.sort(key=lambda x: (
            x['credibility_score'] * x['relevance_score'] * (abs(x['sentiment']) + 0.1)
        ), reverse=True)
        
        return analyzed_news[:3]
        
    except Exception as e:
        print(f"Error fetching news: {str(e)}")
        return None

def calculate_news_sentiment_score(news_data):
    """Calculate overall news sentiment score with enhanced analysis"""
    if not news_data:
        return 0.0, []
    
    # Calculate weighted sentiment score
    weighted_sentiments = []
    for article in news_data:
        weight = (article['credibility_score'] * article['relevance_score']) / 10000
        weighted_sentiments.append(article['sentiment'] * weight)
    
    avg_sentiment = sum(weighted_sentiments) / len(weighted_sentiments) if weighted_sentiments else 0
    
    news_impacts = []
    for article in news_data:
        sentiment_str = "positive" if article['sentiment'] > 0 else "negative" if article['sentiment'] < 0 else "neutral"
        impact_strength = "strong" if abs(article['sentiment']) > 0.5 else "moderate" if abs(article['sentiment']) > 0.2 else "slight"
        
        impact = {
            'headline': article['headline'],
            'source': f"{article['source']} (Credibility: {article['credibility_score']}%)",
            'url': article['url'],
            'published': article['published'],
            'impact': (
                f"This {impact_strength} {sentiment_str} news from a highly credible source suggests "
                f"{'upward' if article['sentiment'] > 0 else 'downward'} pressure on the stock price. "
                f"{'Price impacts mentioned: ' + ', '.join(article['price_impacts']) if article['price_impacts'] else ''}"
            )
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
            
    if 'BB_Band' in current_values:
        bb = current_values['BB_Band']
        if bb > 0.8:
            explanation.append("Price near upper Bollinger Band (potential resistance)")
        elif bb < 0.2:
            explanation.append("Price near lower Bollinger Band (potential support)")
            
    if all(x in current_values for x in ['SMA5', 'SMA20']):
        if current_values['SMA5'] > current_values['SMA20']:
            explanation.append("Short-term uptrend (5-day SMA above 20-day)")
        else:
            explanation.append("Short-term downtrend (5-day SMA below 20-day)")
    
    if not explanation:
        explanation.append("Limited technical indicators available")
    
    return " | ".join(explanation)

def random_forest_prediction(history, symbol=None):
    """Enhanced Random Forest prediction with news sentiment analysis"""
    try:
        if not validate_data_quality(history):
            return "uncertain", 35, {"technical_analysis": "Insufficient data", "news_analysis": None, "combined_analysis": "Insufficient data for analysis"}
        
        # Convert index to UTC and localize timestamps
        history = history.copy()
        history.index = history.index.tz_localize(None)
        
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
        
        # Create and train multiple RF models with different configurations
        rf1 = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
        rf2 = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=43)
        rf3 = RandomForestClassifier(n_estimators=200, max_depth=20, random_state=44)
        
        # Create ensemble with voting
        voting_clf = VotingClassifier(
            estimators=[('rf1', rf1), ('rf2', rf2), ('rf3', rf3)],
            voting='soft'
        )
        
        # Train the ensemble
        voting_clf.fit(X_scaled, y)
        
        # Make prediction with probability
        last_data = X_scaled.iloc[-1].values.reshape(1, -1)
        prediction_proba = voting_clf.predict_proba(last_data)[0]
        prediction = "increase" if prediction_proba[1] > 0.5 else "decrease"
        confidence = max(prediction_proba) * 100
        
        # Generate technical analysis explanation
        technical_explanation = generate_technical_explanation(X.iloc[-1])
        
        # Combine technical and news analysis
        final_explanation = {
            'technical_analysis': technical_explanation,
            'news_analysis': news_impacts if news_impacts else None,
            'combined_analysis': (
                f"Based on {'both ' if news_impacts else ''}technical analysis{' and recent news' if news_impacts else ''}, "
                f"the model predicts a {prediction} trend with {confidence:.1f}% confidence. "
                f"{'News sentiment is ' + ('positive' if news_sentiment > 0 else 'negative' if news_sentiment < 0 else 'neutral') + '. ' if news_impacts else ''}"
                f"Technical indicators show: {technical_explanation}."
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
        
        # Convert index to UTC and localize timestamps
        df = history['Close'].copy()
        df.index = df.index.tz_localize(None)  # Remove timezone info
        df = df.resample('D').ffill()
        
        # Check stationarity
        adf_result = adfuller(df)
        is_stationary = adf_result[1] < 0.05
        d = 0 if is_stationary else 1
        
        # Make data stationary if needed
        if not is_stationary:
            df = df.diff().dropna()
        
        # Fit ARIMA model
        model = ARIMA(df, order=(2, d, 2))
        results = model.fit()
        
        # Generate forecasts for different periods
        periods = [7, 15, 30, 90, 120]
        forecasts = {}
        
        for period in periods:
            # Get forecast with confidence intervals
            forecast = results.get_forecast(steps=period)
            mean_forecast = forecast.predicted_mean
            conf_int = forecast.conf_int(alpha=0.05)
            
            # Transform back if data was differenced
            if not is_stationary:
                mean_forecast = np.cumsum(mean_forecast) + history['Close'].iloc[-1]
                conf_int = pd.DataFrame(np.cumsum(conf_int, axis=0), columns=['lower', 'upper'])
                conf_int += history['Close'].iloc[-1]
            
            # Create forecast dates
            dates = [df.index[-1] + datetime.timedelta(days=i+1) for i in range(period)]
            
            # Create forecast series
            forecast_series = pd.Series(mean_forecast, index=dates)
            lower_bound = pd.Series(conf_int['lower'], index=dates)
            upper_bound = pd.Series(conf_int['upper'], index=dates)
            
            # Adjust forecasts based on news sentiment
            if news_sentiment != 0:
                sentiment_adjustment = news_sentiment * 0.02  # 2% adjustment per unit of sentiment
                forecast_series *= (1 + sentiment_adjustment)
                lower_bound *= (1 + sentiment_adjustment)
                upper_bound *= (1 + sentiment_adjustment)
            
            # Calculate trend and confidence
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
import re
from datetime import datetime, timedelta

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

def extract_price_impact(text):
    """Extract specific price impact mentions from article text."""
    price_patterns = [
        r'(?:up|down|rise|fall|drop|jump|surge|plunge|increase|decrease)(?:\s+by\s+)?(\d+(?:\.\d+)?%?)',
        r'(\d+(?:\.\d+)?%?)(?:\s+)?(?:gain|loss|higher|lower)',
        r'price target(?:\s+of\s+)?\$(\d+(?:\.\d+)?)',
    ]
    
    impacts = []
    for pattern in price_patterns:
        matches = re.finditer(pattern, text.lower())
        for match in matches:
            impacts.append(match.group())
    
    return impacts

def calculate_relevance_score(article, current_price):
    """Calculate article relevance score based on content and date."""
    score = 0
    
    # Time relevance (max 40 points)
    pub_time = article.get('providerPublishTime', 0)
    if pub_time:
        hours_ago = (datetime.now() - datetime.fromtimestamp(pub_time)).total_seconds() / 3600
        if hours_ago <= 6:
            score += 40
        elif hours_ago <= 12:
            score += 35
        elif hours_ago <= 24:
            score += 30
        elif hours_ago <= 48:
            score += 20
        else:
            score += 10
    
    # Content relevance (max 60 points)
    text = f"{article.get('title', '')} {article.get('summary', '')}"
    
    # Check for price mentions
    price_impacts = extract_price_impact(text)
    score += len(price_impacts) * 10
    
    # Check for important keywords
    keywords = ['earnings', 'revenue', 'profit', 'guidance', 'forecast', 'analyst', 'upgrade', 'downgrade']
    for keyword in keywords:
        if keyword in text.lower():
            score += 5
    
    # Cap the total score at 100
    return min(score, 100)

def get_stock_news(symbol, limit=15):
    """Fetch and analyze news for a given stock symbol with enhanced credibility scoring"""
    try:
        stock = yf.Ticker(symbol)
        news = stock.news
        
        if not news:
            return None
        
        # Define credible sources with their credibility scores
        CREDIBLE_SOURCES = {
            'Wall Street Journal': 95,
            'WSJ': 95,
            'Financial Times': 95,
            'FT': 95,
            'Reuters': 90,
            'Bloomberg': 90,
            'CNBC': 85,
            'MarketWatch': 80,
            'Barron\'s': 80,
            'Forbes': 75
        }
        
        current_price = stock.info.get('currentPrice', 0)
        analyzed_news = []
        
        for article in news:
            source = article.get('publisher', '')
            credibility_score = 0
            
            # Calculate source credibility score
            for credible_source, score in CREDIBLE_SOURCES.items():
                if credible_source.lower() in source.lower():
                    credibility_score = score
                    break
            
            if credibility_score > 0:  # Only include articles from credible sources
                headline = article.get('title', '')
                summary = article.get('summary', '')
                full_text = f"{headline} {summary}"
                
                # Calculate sentiment
                blob = TextBlob(full_text)
                sentiment_score = blob.sentiment.polarity
                
                # Calculate relevance score
                relevance_score = calculate_relevance_score(article, current_price)
                
                # Extract price impacts
                price_impacts = extract_price_impact(full_text)
                
                analyzed_news.append({
                    'headline': headline,
                    'source': source,
                    'url': article.get('link', ''),
                    'published': datetime.fromtimestamp(article.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                    'sentiment': sentiment_score,
                    'credibility_score': credibility_score,
                    'relevance_score': relevance_score,
                    'summary': summary,
                    'price_impacts': price_impacts
                })
        
        # Sort by weighted score (credibility * relevance * abs(sentiment))
        analyzed_news.sort(key=lambda x: (
            x['credibility_score'] * x['relevance_score'] * (abs(x['sentiment']) + 0.1)
        ), reverse=True)
        
        return analyzed_news[:3]
        
    except Exception as e:
        print(f"Error fetching news: {str(e)}")
        return None

def calculate_news_sentiment_score(news_data):
    """Calculate overall news sentiment score with enhanced analysis"""
    if not news_data:
        return 0.0, []
    
    # Calculate weighted sentiment score
    weighted_sentiments = []
    for article in news_data:
        weight = (article['credibility_score'] * article['relevance_score']) / 10000
        weighted_sentiments.append(article['sentiment'] * weight)
    
    avg_sentiment = sum(weighted_sentiments) / len(weighted_sentiments) if weighted_sentiments else 0
    
    news_impacts = []
    for article in news_data:
        sentiment_str = "positive" if article['sentiment'] > 0 else "negative" if article['sentiment'] < 0 else "neutral"
        impact_strength = "strong" if abs(article['sentiment']) > 0.5 else "moderate" if abs(article['sentiment']) > 0.2 else "slight"
        
        impact = {
            'headline': article['headline'],
            'source': f"{article['source']} (Credibility: {article['credibility_score']}%)",
            'url': article['url'],
            'published': article['published'],
            'impact': (
                f"This {impact_strength} {sentiment_str} news from a highly credible source suggests "
                f"{'upward' if article['sentiment'] > 0 else 'downward'} pressure on the stock price. "
                f"{'Price impacts mentioned: ' + ', '.join(article['price_impacts']) if article['price_impacts'] else ''}"
            )
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
            
    if 'BB_Band' in current_values:
        bb = current_values['BB_Band']
        if bb > 0.8:
            explanation.append("Price near upper Bollinger Band (potential resistance)")
        elif bb < 0.2:
            explanation.append("Price near lower Bollinger Band (potential support)")
            
    if all(x in current_values for x in ['SMA5', 'SMA20']):
        if current_values['SMA5'] > current_values['SMA20']:
            explanation.append("Short-term uptrend (5-day SMA above 20-day)")
        else:
            explanation.append("Short-term downtrend (5-day SMA below 20-day)")
    
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
        
        # Create and train multiple RF models with different configurations
        rf1 = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
        rf2 = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=43)
        rf3 = RandomForestClassifier(n_estimators=200, max_depth=20, random_state=44)
        
        # Create ensemble with voting
        voting_clf = VotingClassifier(
            estimators=[('rf1', rf1), ('rf2', rf2), ('rf3', rf3)],
            voting='soft'
        )
        
        # Train the ensemble
        voting_clf.fit(X_scaled, y)
        
        # Make prediction with probability
        last_data = X_scaled.iloc[-1].values.reshape(1, -1)
        prediction_proba = voting_clf.predict_proba(last_data)[0]
        prediction = "increase" if prediction_proba[1] > 0.5 else "decrease"
        confidence = max(prediction_proba) * 100
        
        # Generate technical analysis explanation
        technical_explanation = generate_technical_explanation(X.iloc[-1])
        
        # Combine technical and news analysis
        final_explanation = {
            'technical_analysis': technical_explanation,
            'news_analysis': news_impacts if news_impacts else None,
            'combined_analysis': (
                f"Based on {'both ' if news_impacts else ''}technical analysis{' and recent news' if news_impacts else ''}, "
                f"the model predicts a {prediction} trend with {confidence:.1f}% confidence. "
                f"{'News sentiment is ' + ('positive' if news_sentiment > 0 else 'negative' if news_sentiment < 0 else 'neutral') + '. ' if news_impacts else ''}"
                f"Technical indicators show: {technical_explanation}."
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
        
        # Convert index to UTC and localize timestamps
        df = history['Close'].copy()
        df.index = df.index.tz_localize(None)  # Remove timezone info
        df = df.resample('D').ffill()
        
        # Check stationarity
        adf_result = adfuller(df)
        is_stationary = adf_result[1] < 0.05
        d = 0 if is_stationary else 1
        
        # Make data stationary if needed
        if not is_stationary:
            df = df.diff().dropna()
        
        # Fit ARIMA model
        model = ARIMA(df, order=(2, d, 2))
        results = model.fit()
        
        # Generate forecasts for different periods
        periods = [7, 15, 30, 90, 120]
        forecasts = {}
        
        for period in periods:
            # Get forecast with confidence intervals
            forecast = results.get_forecast(steps=period)
            mean_forecast = forecast.predicted_mean
            conf_int = forecast.conf_int(alpha=0.05)
            
            # Transform back if data was differenced
            if not is_stationary:
                mean_forecast = np.cumsum(mean_forecast) + history['Close'].iloc[-1]
                conf_int = pd.DataFrame(np.cumsum(conf_int, axis=0), columns=['lower', 'upper'])
                conf_int += history['Close'].iloc[-1]
            
            # Create forecast dates
            dates = [df.index[-1] + datetime.timedelta(days=i+1) for i in range(period)]
            
            # Create forecast series
            forecast_series = pd.Series(mean_forecast, index=dates)
            lower_bound = pd.Series(conf_int['lower'], index=dates)
            upper_bound = pd.Series(conf_int['upper'], index=dates)
            
            # Adjust forecasts based on news sentiment
            if news_sentiment != 0:
                sentiment_adjustment = news_sentiment * 0.02  # 2% adjustment per unit of sentiment
                forecast_series *= (1 + sentiment_adjustment)
                lower_bound *= (1 + sentiment_adjustment)
                upper_bound *= (1 + sentiment_adjustment)
            
            # Calculate trend and confidence
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

