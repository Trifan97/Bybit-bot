from pybit.unified_trading import HTTP
import pandas as pd
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# API Credentials
API_KEY = "YRXRe1T4bOi3STvB6Y"
API_SECRET = "C6l4QPsA4lcQn61286HbT0HILu8CDDhOkzM0"

# Initialize Bybit REST client
client = HTTP(testnet=True, api_key=API_KEY, api_secret=API_SECRET)

# Constants
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # Multiple pairs
INTERVAL = "1m"  # Candle interval
POSITION_SIZE = 0.01  # Adjust based on your risk management
SLEEP_TIME = 60  # Time to wait between cycles (in seconds)

# Fetch OHLCV data
def fetch_candlestick(symbol, interval, limit=100):
    try:
        response = client.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        df = pd.DataFrame(response['result']['list'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')  # Convert timestamp
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df
    except Exception as e:
        logging.error(f"Error fetching candlestick data for {symbol}: {e}")
        return pd.DataFrame()

# Calculate Fair Value Gaps
def calculate_fvg(df):
    fvg_list = []
    for i in range(1, len(df) - 1):
        if df['high'][i - 1] < df['low'][i + 1]:
            fvg_list.append({'type': 'bullish', 'top': df['low'][i + 1], 'bottom': df['high'][i - 1], 'index': i})
        elif df['low'][i - 1] > df['high'][i + 1]:
            fvg_list.append({'type': 'bearish', 'top': df['high'][i - 1], 'bottom': df['low'][i + 1], 'index': i})
    return pd.DataFrame(fvg_list)

# Identify Swing Highs and Lows
def identify_swing_highs_and_lows(df, swing_length=3):
    swing_data = []
    for i in range(swing_length, len(df) - swing_length):
        if df['high'].iloc[i] == max(df['high'].iloc[i-swing_length:i+swing_length+1]):
            swing_data.append({'index': i, 'type': 'high', 'level': df['high'].iloc[i]})
        elif df['low'].iloc[i] == min(df['low'].iloc[i-swing_length:i+swing_length+1]):
            swing_data.append({'index': i, 'type': 'low', 'level': df['low'].iloc[i]})
    return pd.DataFrame(swing_data)

# Identify Order Blocks
def identify_order_blocks(df):
    order_blocks = []
    for i in range(1, len(df) - 1):
        if df['close'].iloc[i] > df['close'].iloc[i - 1] and df['close'].iloc[i] > df['close'].iloc[i + 1]:
            order_blocks.append({'index': i, 'type': 'bullish', 'level': df['close'].iloc[i]})
        elif df['close'].iloc[i] < df['close'].iloc[i - 1] and df['close'].iloc[i] < df['close'].iloc[i + 1]:
            order_blocks.append({'index': i, 'type': 'bearish', 'level': df['close'].iloc[i]})
    return pd.DataFrame(order_blocks)

# Trading Logic
def trading_logic(df, fvg_df, swing_df, ob_df):
    for _, fvg in fvg_df.iterrows():
        if fvg['type'] == 'bullish' and df['close'].iloc[-1] < fvg['bottom']:
            return 'buy'
        elif fvg['type'] == 'bearish' and df['close'].iloc[-1] > fvg['top']:
            return 'sell'

    for _, swing in swing_df.iterrows():
        if swing['type'] == 'high' and df['close'].iloc[-1] > swing['level']:
            return 'sell'
        elif swing['type'] == 'low' and df['close'].iloc[-1] < swing['level']:
            return 'buy'

    for _, ob in ob_df.iterrows():
        if ob['type'] == 'bullish' and df['close'].iloc[-1] < ob['level']:
            return 'buy'
        elif ob['type'] == 'bearish' and df['close'].iloc[-1] > ob['level']:
            return 'sell'
    return None

# Place Order
def place_order(symbol, side, qty):
    try:
        response = client.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=qty,
            timeInForce="GoodTillCancel"
        )
        logging.info(f"Order placed for {symbol}: {response}")
    except Exception as e:
        logging.error(f"Error placing order for {symbol}: {e}")

# Main Bot Loop
def main():
    while True:
        for symbol in SYMBOLS:  # Loop through all symbols
            try:
                logging.info(f"Fetching data for {symbol}...")
                ohlcv = fetch_candlestick(symbol, INTERVAL)

                if ohlcv.empty:
                    logging.warning(f"No data fetched for {symbol}. Retrying...")
                    continue

                logging.info(f"Calculating Fair Value Gaps for {symbol}...")
                fvg_df = calculate_fvg(ohlcv)

                logging.info(f"Identifying Swing Highs and Lows for {symbol}...")
                swing_df = identify_swing_highs_and_lows(ohlcv)

                logging.info(f"Identifying Order Blocks for {symbol}...")
                ob_df = identify_order_blocks(ohlcv)

                logging.info(f"Applying trading logic for {symbol}...")
                signal = trading_logic(ohlcv, fvg_df, swing_df, ob_df)

                if signal == 'buy':
                    logging.info(f"Bullish signal detected for {symbol}. Placing buy order...")
                    place_order(symbol, 'Buy', POSITION_SIZE)
                elif signal == 'sell':
                    logging.info(f"Bearish signal detected for {symbol}. Placing sell order...")
                    place_order(symbol, 'Sell', POSITION_SIZE)
                else:
                    logging.info(f"No trade signal for {symbol}. Waiting for the next cycle...")

            except Exception as e:
                logging.error(f"Error in main loop for {symbol}: {e}")
                continue  # Move to the next symbol if an error occurs

        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()

