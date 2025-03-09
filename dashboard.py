import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from textblob import TextBlob
from streamlit_autorefresh import st_autorefresh

###############################
# 0. PAGE & AUTO-REFRESH SETUP
###############################
st.set_page_config(page_title="MarketPulse: Live Finance & Crypto", layout="wide")
st_autorefresh(interval=60_000, limit=None)
st.title("MarketPulse: Live Finance & Crypto")

###################################################
# 1. HELPER FUNCTIONS & STREAMLIT CACHING DECORATORS
###################################################

@st.cache_data(ttl=60)
def fetch_crypto_data(crypto_symbols):
    """Fetch real-time crypto data from Binance."""
    results = []
    for symbol in crypto_symbols:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            results.append({
                "Symbol": data.get("symbol"),
                "Name": crypto_names.get(symbol, "N/A"),
                "Price Change (%)": data.get("priceChangePercent") + "%",
                "Last Price": data.get("lastPrice"),
                "Volume": data.get("volume"),
                "High Price": data.get("highPrice"),
                "Low Price": data.get("lowPrice")
            })
    return pd.DataFrame(results)

@st.cache_data(ttl=60)
def fetch_crypto_historical(symbol, days=30):
    """Fetch historical data (1-day klines) for the last X days from Binance."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={days}"
    resp = requests.get(url)
    if resp.status_code == 200:
        klines = resp.json()
        dates = [datetime.fromtimestamp(k[0]/1000).date() for k in klines]
        closes = [float(k[4]) for k in klines]
        df = pd.DataFrame({"Date": dates, "Close": closes})
        df.set_index("Date", inplace=True)
        return df
    return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_stock_data(stock_symbols):
    """Fetch real-time stock data from yfinance."""
    results = []
    for symbol in stock_symbols:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        results.append({
            "Symbol": symbol,
            "Name": info.get("longName", symbol),
            "Current Price": info.get("regularMarketPrice"),
            "Previous Close": info.get("previousClose"),
            "Market Cap": info.get("marketCap")
        })
    return pd.DataFrame(results)

@st.cache_data(ttl=60)
def fetch_stock_historical(symbol, period="1mo"):
    """Fetch historical data from yfinance."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)
    return hist

@st.cache_data(ttl=120)
def fetch_english_finance_news(api_key, max_articles=5):
    """
    Fetch English news about stocks OR crypto from NewsAPI,
    sort by date, return top articles + sentiment.
    """
    url = (
        "https://newsapi.org/v2/everything?"
        "q=stocks%20OR%20crypto"
        "&language=en"
        "&sortBy=publishedAt"
        f"&apiKey={api_key}"
    )
    resp = requests.get(url)
    articles = []
    avg_sentiment = 0.0

    if resp.status_code == 200:
        data = resp.json()
        raw_articles = data.get("articles", [])
        selected = raw_articles[:max_articles]
        sentiments = []

        for art in selected:
            title = art.get("title", "")
            desc = art.get("description", "")
            content = title + " " + (desc or "")
            polarity = TextBlob(content).sentiment.polarity
            sentiments.append(polarity)

            articles.append({
                "title": title,
                "description": desc,
                "url": art.get("url", ""),
                "source": art["source"]["name"],
                "publishedAt": art.get("publishedAt", ""),
                "sentiment": round(polarity, 3)
            })

        if sentiments:
            avg_sentiment = sum(sentiments) / len(sentiments)
    else:
        st.warning("Error fetching news. Check your API key and try again.")

    return articles, avg_sentiment

##########################
# 2. DEFAULT SYMBOL LISTS #
##########################
default_crypto = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "ADAUSDT", "BNBUSDT"]
crypto_names = {
    "BTCUSDT": "Bitcoin",
    "ETHUSDT": "Ethereum",
    "XRPUSDT": "Ripple",
    "SOLUSDT": "Solana",
    "ADAUSDT": "Cardano",
    "BNBUSDT": "Binance Coin"
}
default_stocks = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA"]

##########################
# 3. INITIAL DATA LOADING #
##########################
if 'crypto_df' not in st.session_state:
    st.session_state.crypto_df = fetch_crypto_data(default_crypto)
if 'stock_df' not in st.session_state:
    st.session_state.stock_df = fetch_stock_data(default_stocks)

###################
# 4. CREATE THE TABS
###################
tabs = st.tabs(["Crypto", "Stocks", "News & Sentiment"])

########### Crypto Tab ###########
with tabs[0]:
    st.header("Cryptocurrency Prices (via Binance)")
    
    # Table Display with Placeholder
    crypto_table_placeholder = st.empty()
    crypto_table_placeholder.dataframe(st.session_state.crypto_df)
    
    # Refresh Table
    with st.spinner("Running: Fetching new crypto data"):
        new_crypto_df = fetch_crypto_data(default_crypto)
        if not new_crypto_df.equals(st.session_state.crypto_df):
            st.session_state.crypto_df = new_crypto_df
            crypto_table_placeholder.dataframe(st.session_state.crypto_df)

    # Chart Section
    selected_crypto = st.selectbox(
        "Select a crypto for historical chart",
        options=default_crypto
    )
    
    if selected_crypto:
        chart_placeholder = st.empty()
        if 'crypto_chart' in st.session_state:
            chart_placeholder.line_chart(st.session_state.crypto_chart.get(selected_crypto, pd.DataFrame()))
        
        with st.spinner("Running: Fetching new crypto chart data"):
            new_hist = fetch_crypto_historical(selected_crypto, days=30)
            if not new_hist.empty:
                if 'crypto_chart' not in st.session_state:
                    st.session_state.crypto_chart = {}
                st.session_state.crypto_chart[selected_crypto] = new_hist
                chart_placeholder.line_chart(new_hist["Close"])

########### Stocks Tab ###########
with tabs[1]:
    st.header("Stock Market Data (via yahoo finance)")
    
    # Table Display with Placeholder
    stock_table_placeholder = st.empty()
    stock_table_placeholder.dataframe(st.session_state.stock_df)
    
    # Refresh Table
    with st.spinner("Running: Fetching new stock data"):
        new_stock_df = fetch_stock_data(default_stocks)
        if not new_stock_df.equals(st.session_state.stock_df):
            st.session_state.stock_df = new_stock_df
            stock_table_placeholder.dataframe(st.session_state.stock_df)

    # Chart Section
    selected_stock = st.selectbox(
        "Select a stock for historical price chart",
        options=default_stocks
    )
    
    if selected_stock:
        chart_placeholder = st.empty()
        if 'stock_chart' in st.session_state:
            chart_placeholder.line_chart(st.session_state.stock_chart.get(selected_stock, pd.DataFrame()))
        
        with st.spinner("Running: Fetching new stock chart data"):
            new_hist = fetch_stock_historical(selected_stock, period="1mo")
            if not new_hist.empty:
                if 'stock_chart' not in st.session_state:
                    st.session_state.stock_chart = {}
                st.session_state.stock_chart[selected_stock] = new_hist
                chart_placeholder.line_chart(new_hist["Close"])

########### News & Sentiment Tab ###########
with tabs[2]:
    st.header("AI-Driven Financial News & Sentiment")
    
    news_placeholder = st.empty()
    sentiment_placeholder = st.empty()
    api_key = st.text_input("Enter your NewsAPI key (required)", type="password")
    
    if api_key:
        with st.spinner("Fetching latest news..."):
            articles, avg_sentiment = fetch_english_finance_news(api_key)
            
            if articles:
                with news_placeholder.container():
                    st.write(f"Top {len(articles)} Latest Articles (English)")
                    for idx, art in enumerate(articles, start=1):
                        st.markdown(f"**{idx}. {art['title']}**")
                        st.write(art["description"])
                        st.write(f"Source: {art['source']}, Published: {art['publishedAt']}")
                        st.markdown(f"[Read full article]({art['url']})")
                        st.write(f"Sentiment: {art['sentiment']}")
                        st.write("---")

                with sentiment_placeholder.container():
                    st.subheader("Overall News Sentiment")
                    st.write("Average Sentiment (from -1 negative to 1 positive):", round(avg_sentiment, 3))
                    if avg_sentiment > 0:
                        st.success("Overall Positive Sentiment")
                    elif avg_sentiment < 0:
                        st.error("Overall Negative Sentiment")
                    else:
                        st.info("Neutral Sentiment")
            else:
                news_placeholder.warning("No news articles found or invalid API key.")
    else:
        news_placeholder.info("Please enter your NewsAPI key to see the latest English financial news (stocks OR crypto).")