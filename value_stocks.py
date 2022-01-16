from distutils.command.config import config
from lib2to3.pgen2 import token
import numpy as np
import pandas as pd
import requests
from scipy import stats
import math
from statistics import mean
from dotenv import dotenv_values

# initialize IEX sandbox API token
token = dotenv_values('.env')['IEX_CLOUD_API_TOKEN']

# scrape Wikipedia for up-to-date list of S&P500 companies
table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
stocks = table[0][['Symbol','Security']]

# function to split lists into smaller lengths
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]   

# function to get number of shares to buy
def buy_shares(frame, investment):
    position_size = investment / len(frame.index)
    for i in range(0, len(frame)):
        frame.loc[i,'Number of Shares to Buy'] = math.floor(position_size / frame.loc[i, 'Price'])

# function to get portfolio size from user
def portfolio_size(frame):
    while True:
        try:
            portfolio_size = float(input('Portfolio Size: '))
        except ValueError:
            print('Invalid amount, try again!')
            continue

        if portfolio_size < 0:
            print('Cannot have a negative portfolio size')
            continue
        else:
            break
        
    buy_shares(frame, portfolio_size)

# group stocks into lists of 100 elements for batch API call limit
symbol_groups = list(chunks(stocks['Symbol'], 100))
symbol_strings = []
for i in range(0, len(symbol_groups)):
    symbol_strings.append(','.join(symbol_groups[i]))

rv_columns = [
    'Ticker',
    'Price',
    'Number of Shares to Buy',
    'P/E Ratio',
    'P/E Percentile',
    'P/B Ratio',
    'P/B Percentile',
    'P/S Ratio',
    'P/S Percentile',
    'EV/EBITDA',
    'EV/EBITDA Percentile',
    'EV/GP',
    'EV/GP Percentile',
    'PEG Ratio',
    'PEG Percentile',
    'D/E Ratio',
    'D/E Percentile',
    'RV Score'
]

rv_list = []

# extracting metric data from batch API call
for symbol_string in symbol_strings:
    batch_api_call_url = f'https://sandbox.iexapis.com/stable/stock/market/batch?symbols={symbol_string}&types=price,quote,advanced-stats&token={token}'
    data = requests.get(batch_api_call_url).json()
    for symbol in symbol_string.split(','):
        # handle symbols with no API data
        try:
            price = data[symbol]['price']
            pe_ratio = data[symbol]['quote']['peRatio']
            pb_ratio = data[symbol]['advanced-stats']['priceToBook']
            ps_ratio = data[symbol]['advanced-stats']['priceToSales']
            enterprise_value = data[symbol]['advanced-stats']['enterpriseValue']
            ebitda = data[symbol]['advanced-stats']['EBITDA']
            gross_profit = data[symbol]['advanced-stats']['grossProfit']
            peg_ratio = data[symbol]['advanced-stats']['pegRatio']
            de_ratio = data[symbol]['advanced-stats']['debtToEquity']
            
            if enterprise_value == None:
                ev_ebitda = None
                ev_gp = None
            elif ebitda == None:
                ev_ebitda = None
            elif gross_profit == None:
                ev_gp = None
            else:
                ev_ebitda = enterprise_value / ebitda
                ev_gp = enterprise_value / gross_profit

            rv_list.append([
                symbol,
                price,
                None,
                pe_ratio,
                None,
                pb_ratio,
                None,
                ps_ratio,
                None,
                ev_ebitda,
                None,
                ev_gp,
                None,
                peg_ratio,
                None,
                de_ratio,
                None,
                None
            ])
        
        except KeyError:
            rv_list.append([None for i in range(18)])

# initialize dataframe    
rv_df = pd.DataFrame(rv_list, columns=rv_columns)

# fill missing values with the mean of the column
for column in rv_columns[1:16:2]:
    rv_df[column].fillna(rv_df[column].mean(), inplace=True)

metrics = {}
for i in range(3,16,2):
    metrics[rv_columns[i]] = rv_columns[i+1]

# calculate percentile scores for each metric
for metric in metrics.keys():
    for row in rv_df.index:
        percent_score = stats.percentileofscore(rv_df[metric], rv_df.loc[row,metric])
        rv_df.loc[row,metrics[metric]] = percent_score

# calculate RV Score by taking the average of all percentile scores
for row in rv_df.index:
    percentiles = []
    for metric in rv_columns[4:13:2]:
        percentiles.append(rv_df.loc[row, metric])
    rv_df.loc[row, 'RV Score'] = mean(percentiles)

# find 25 stocks of the lowest RV Score
rv_df.sort_values('RV Score', ascending=True,inplace=True)
rv_top_25 = rv_df[:25]
rv_top_25.reset_index(inplace=True, drop=True)

# calculate the number of shares to buy
portfolio_size(rv_top_25)

# export as excel file
rv_top_25.to_excel('ValueStocks.xlsx', sheet_name='Portfolio', index = False)