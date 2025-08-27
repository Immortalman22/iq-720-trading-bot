#!/usr/bin/env python3
"""
Historical Data Downloader Tool
Downloads historical data from various sources for backtesting purposes
"""
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from tqdm import tqdm
import zipfile
import io

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from src.utils.logger import setup_logger

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Historical Data Downloader")
    
    parser.add_argument(
        "--pairs", 
        type=str, 
        nargs="+", 
        default=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP", "EURJPY", "GBPJPY"],
        help="Currency pairs to download (e.g. EURUSD GBPUSD)"
    )
    
    parser.add_argument(
        "--start-date", 
        type=str, 
        default="2013-01-01",
        help="Start date for data download (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--end-date", 
        type=str, 
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date for data download (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--timeframes", 
        type=str, 
        nargs="+", 
        default=["M5", "M15", "M30", "H1", "H4", "D1"],
        help="Timeframes to download"
    )
    
    parser.add_argument(
        "--source", 
        type=str, 
        default="yahoo",
        choices=["yahoo", "histdata", "dukascopy"],
        help="Data source"
    )
    
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="data/historical",
        help="Directory to save data"
    )
    
    return parser.parse_args()

def download_from_yahoo(pair, start_date, end_date, timeframe, output_dir):
    """
    Download historical data from Yahoo Finance
    
    Args:
        pair: Currency pair (e.g. 'EURUSD')
        start_date: Start date string in YYYY-MM-DD format
        end_date: End date string in YYYY-MM-DD format
        timeframe: Timeframe (e.g. 'H1' for hourly)
        output_dir: Directory to save data
        
    Returns:
        Path to saved CSV file or None if download failed
    """
    # Convert timeframe to yfinance format
    tf_mapping = {
        'M1': '1m',
        'M5': '5m',
        'M15': '15m',
        'M30': '30m',
        'H1': '1h',
        'H4': '4h',
        'D1': '1d',
        'W1': '1wk',
        'MN1': '1mo'
    }
    yf_tf = tf_mapping.get(timeframe, '1h')
    
    # Convert pair to Yahoo Finance format
    yf_pair = f"{pair[:3]}{pair[3:]}=X"
    
    try:
        # Download data
        data = yf.download(
            yf_pair,
            start=start_date,
            end=end_date,
            interval=yf_tf,
            progress=False
        )
        
        # Check if data is empty
        if data.empty:
            logging.warning(f"No data retrieved for {pair} ({timeframe})")
            return None
            
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        file_path = output_path / f"{pair}_{timeframe}_{start_date}_{end_date}.csv"
        data.to_csv(file_path)
        
        return file_path
        
    except Exception as e:
        logging.error(f"Error downloading {pair} from Yahoo Finance: {e}")
        return None

def download_from_histdata(pair, year, month, timeframe, output_dir):
    """
    Download historical data from HistData.com
    Note: HistData requires downloading month by month
    
    Args:
        pair: Currency pair (e.g. 'EURUSD')
        year: Year to download
        month: Month to download (1-12)
        timeframe: Timeframe (e.g. 'M1' for 1-minute)
        output_dir: Directory to save data
        
    Returns:
        Path to saved CSV file or None if download failed
    """
    # HistData uses different pair format
    pair = pair.upper()
    
    # Map timeframe to HistData format
    tf_mapping = {
        'M1': 1,
        'M5': 5,
        'M15': 15,
        'M30': 30,
        'H1': 60,
        'D1': 1440,
        'W1': 10080,
        'MN1': 43200
    }
    histdata_tf = tf_mapping.get(timeframe)
    
    if not histdata_tf:
        logging.error(f"Unsupported timeframe for HistData: {timeframe}")
        return None
    
    try:
        # Format month with leading zero
        month_str = f"{month:02d}"
        
        # Create URL for download
        url = f"https://www.histdata.com/download-free-forex-data/?/{timeframe}_/{pair}/{year}/{month_str}"
        
        # This is a placeholder - actual implementation would need to handle HistData's web interface
        # which requires form submission and cookie handling
        logging.warning("HistData downloads require manual interaction with their website")
        logging.warning(f"Please visit: {url}")
        
        return None
        
    except Exception as e:
        logging.error(f"Error downloading from HistData: {e}")
        return None

def download_from_dukascopy(pair, start_date, end_date, timeframe, output_dir):
    """
    Placeholder for downloading from Dukascopy
    Note: Dukascopy has an API but requires some complex handling
    
    Args:
        pair: Currency pair (e.g. 'EURUSD')
        start_date: Start date string in YYYY-MM-DD format
        end_date: End date string in YYYY-MM-DD format
        timeframe: Timeframe (e.g. 'H1' for hourly)
        output_dir: Directory to save data
        
    Returns:
        Path to saved CSV file or None if download failed
    """
    logging.warning("Dukascopy download is not yet implemented")
    logging.warning(f"You can manually download {pair} data from https://www.dukascopy.com/trading-tools/widgets/quotes/historical_data_feed")
    
    return None

def convert_to_uniform_format(file_path, source, pair, timeframe):
    """
    Convert downloaded data to a uniform format
    
    Args:
        file_path: Path to the downloaded file
        source: Source of the data ('yahoo', 'histdata', 'dukascopy')
        pair: Currency pair
        timeframe: Timeframe
        
    Returns:
        DataFrame with uniform format
    """
    try:
        if not file_path or not file_path.exists():
            return None
            
        if source == 'yahoo':
            # Yahoo data is already in a usable format
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            
            # Rename columns to standard format
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Adj Close': 'adj_close'
            })
            
            # Drop unnecessary columns
            if 'adj_close' in df.columns:
                df = df.drop('adj_close', axis=1)
                
            # Add pair info
            df['pair'] = pair
            
            # Save with uniform format
            df.to_csv(file_path)
            
            return df
            
        elif source == 'histdata':
            # Implementation would depend on HistData format
            pass
            
        elif source == 'dukascopy':
            # Implementation would depend on Dukascopy format
            pass
            
        return None
        
    except Exception as e:
        logging.error(f"Error converting {file_path} to uniform format: {e}")
        return None

def calculate_derived_data(df, timeframe):
    """
    Calculate additional derived data (indicators, etc.)
    
    Args:
        df: DataFrame with OHLCV data
        timeframe: Timeframe
        
    Returns:
        DataFrame with additional columns
    """
    if df is None or df.empty:
        return df
        
    try:
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        
        # Calculate log returns
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Calculate volatility (20-period rolling std of returns)
        df['volatility'] = df['returns'].rolling(20).std()
        
        # Calculate true range
        df['true_range'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                np.abs(df['high'] - df['close'].shift(1)),
                np.abs(df['low'] - df['close'].shift(1))
            )
        )
        
        # Calculate ATR
        df['atr'] = df['true_range'].rolling(14).mean()
        
        return df
        
    except Exception as e:
        logging.error(f"Error calculating derived data: {e}")
        return df

def download_historical_data(args):
    """Download historical data based on provided arguments"""
    # Set up logging
    setup_logger()
    
    print(f"Starting historical data download from {args.source}")
    print(f"Pairs: {', '.join(args.pairs)}")
    print(f"Period: {args.start_date} to {args.end_date}")
    print(f"Timeframes: {', '.join(args.timeframes)}")
    print(f"Output directory: {args.output_dir}")
    print("-" * 80)
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download data for each pair and timeframe
    results = []
    
    for pair in args.pairs:
        for timeframe in args.timeframes:
            print(f"Downloading {pair} {timeframe} data...")
            
            if args.source == 'yahoo':
                file_path = download_from_yahoo(
                    pair=pair,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    timeframe=timeframe,
                    output_dir=args.output_dir
                )
                
                if file_path:
                    df = convert_to_uniform_format(file_path, args.source, pair, timeframe)
                    if df is not None:
                        df = calculate_derived_data(df, timeframe)
                        df.to_csv(file_path)  # Save with derived data
                        results.append({
                            'pair': pair,
                            'timeframe': timeframe,
                            'rows': len(df),
                            'start': df.index.min(),
                            'end': df.index.max(),
                            'file': file_path
                        })
                        print(f"✅ Downloaded {len(df)} rows of {pair} {timeframe} data")
                    else:
                        print(f"❌ Failed to process {pair} {timeframe} data")
                else:
                    print(f"❌ Failed to download {pair} {timeframe} data")
                    
            elif args.source == 'histdata':
                # HistData requires monthly downloads
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
                
                current_date = start_date
                while current_date <= end_date:
                    year = current_date.year
                    month = current_date.month
                    
                    file_path = download_from_histdata(
                        pair=pair,
                        year=year,
                        month=month,
                        timeframe=timeframe,
                        output_dir=args.output_dir
                    )
                    
                    # Move to next month
                    if current_date.month == 12:
                        current_date = datetime(current_date.year + 1, 1, 1)
                    else:
                        current_date = datetime(current_date.year, current_date.month + 1, 1)
                    
            elif args.source == 'dukascopy':
                file_path = download_from_dukascopy(
                    pair=pair,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    timeframe=timeframe,
                    output_dir=args.output_dir
                )
    
    # Print summary
    print("\n" + "=" * 80)
    print("DOWNLOAD SUMMARY")
    print("=" * 80)
    
    if results:
        for r in results:
            print(f"{r['pair']} {r['timeframe']}: {r['rows']} rows ({r['start']} to {r['end']})")
    else:
        print("No data was downloaded successfully")

if __name__ == "__main__":
    args = parse_arguments()
    download_historical_data(args)
