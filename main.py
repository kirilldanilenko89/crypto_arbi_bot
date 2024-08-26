import zmq
import json
import asyncio
import telegram
import random
import time
from datetime import timezone
import requests
from uuid import uuid4
import datetime
import argparse
import dateutil.parser
import ccxt.pro as ccxt
from trader import Trader
from models import ArbiDetectModel
from database import db_session

context = zmq.Context()

def send_message(sock, payload):
    message = payload
    sock.send(message)

def symbol_to_ticker(symbol):
    r = symbol.split('/')
    return (r[0].lower() + r[1].lower())

def to_datetime(timestamp_ms):
    return datetime.datetime.fromtimestamp(timestamp_ms // 1000)

coins_blacklist = ['BTC', 'XRP', 'SOL', 'ETH', 'LTC', 'BNB', 'LSK', 'PONKE', 'XMR']

prev_order_id = None
prev_timestamp = None

orders_queue = {}

exchanges = {}

trader_arbi = Trader()

async def initialize_exchanges():

    exchanges['BINANCE'] = ccxt.binance({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['MEXC'] = ccxt.mexc({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['BITGET'] = ccxt.bitget({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['BYBIT'] = ccxt.bybit({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['BINGX'] = ccxt.bingx({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['BITMART'] = ccxt.bitmart({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['PROBIT'] = ccxt.probit({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['XT'] = ccxt.xt({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['BITRUE'] = ccxt.bitrue({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

    exchanges['PHEMEX'] = ccxt.phemex({
        'enableRateLimit': True,
        'apiKey': 'your_key',
        'secret': 'your_key'
    })

class SpredInfo:
    last_bid_price_ex_1 = 0
    last_ask_price_ex_1 = 0
    last_bid_price_ex_2 = 0
    last_ask_price_ex_2 = 0

    last_bid_depth_usdt_ex_1 = 0
    last_ask_depth_usdt_ex_1 = 0
    last_bid_depth_usdt_ex_2 = 0
    last_ask_depth_usdt_ex_2 = 0

    last_bid_depth_pos_ex_1 = 1
    last_ask_depth_pos_ex_1 = 1
    last_bid_depth_pos_ex_2 = 1
    last_ask_depth_pos_ex_2 = 1

    last_bid_pos_price_ex_1 = 0
    last_ask_pos_price_ex_1 = 0
    last_bid_pos_price_ex_2 = 0
    last_ask_pos_price_ex_2 = 0

    last_bids_ex_1 = []
    last_asks_ex_1 = []
    last_bids_ex_1 = []
    last_asks_ex_1 = []

    last_buy_spred_print_time = 0
    last_sell_spred_print_time = 0

spred_infos = {}

async def watch_orderbook(exchange_name, exchange, symbol, ticker, first, trades_count):

    global spred_infos
    global trader_arbi
    global orders_queue

    spred_info = spred_infos[symbol]

    if exchange.has['watchOrderBook']:
        while True:
            try:
                orderbook = await exchange.watch_order_book(ticker, limit=50)

                # print('orderbook')

                msg = {}
                msg['type'] = 'orderbook'
                msg['timestamp'] = orderbook['timestamp']
                msg['bids'] = orderbook['bids']
                msg['asks'] = orderbook['asks']

                if len(orderbook['bids']) == 0 or len(orderbook['asks']) == 0:
                    print(exchange_name + ticker + ' skip')
                    return

                if first:
                    spred_info.last_bid_price_ex_1 = msg['bids'][0][0]
                    spred_info.last_ask_price_ex_1 = msg['asks'][0][0]
                    spred_info.last_bids_ex_1 = []
                    spred_info.last_asks_ex_1 = []
                else:
                    spred_info.last_bid_price_ex_2 = msg['bids'][0][0]
                    spred_info.last_ask_price_ex_2 = msg['asks'][0][0]
                    spred_info.last_bids_ex_2 = []
                    spred_info.last_asks_ex_2 = []

                buy_spred = None
                sell_spred = None

                # print(exchange_name+'2')

                bid_depth_usdt = 0
                bid_depth_position = 0
                first_price = msg['bids'][0][0]
                for order in msg['bids']:
                    percent_length = 100 - ((order[0] / first_price) * 100)
                    if percent_length > 0.001:
                        if first:
                            spred_info.last_bid_depth_usdt_ex_1 = bid_depth_usdt
                            spred_info.last_bids_ex_1.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), bid_depth_position+1])
                        else:
                            spred_info.last_bid_depth_usdt_ex_2 = bid_depth_usdt
                            spred_info.last_bids_ex_2.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), bid_depth_position+1])
                        break

                    if first:
                        spred_info.last_bids_ex_1.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), bid_depth_position])
                        spred_info.last_bid_pos_price_ex_1 = order[0]
                        spred_info.last_bid_depth_pos_ex_1 = bid_depth_position
                    else:
                        spred_info.last_bids_ex_2.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), bid_depth_position])
                        spred_info.last_bid_pos_price_ex_2 = order[0]
                        spred_info.last_bid_depth_pos_ex_2 = bid_depth_position

                    bid_depth_usdt += (order[0] * order[1])
                    bid_depth_position += 1

                    # print('{0} %  price: {1} usdt vol: {2}'.format(percent_length, order[0], usdt_order_volume))

                # print(exchange_name+'3')

                ask_depth_usdt = 0
                ask_depth_position = 0
                first_price = msg['asks'][0][0]
                for order in msg['asks']:
                    percent_length = ((order[0] / first_price) * 100) - 100
                    if percent_length > 0.001:
                        if first:
                            spred_info.last_ask_depth_usdt_ex_1 = ask_depth_usdt
                            spred_info.last_asks_ex_1.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), ask_depth_position+1])
                        else:
                            spred_info.last_ask_depth_usdt_ex_2 = ask_depth_usdt
                            spred_info.last_asks_ex_2.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), ask_depth_position+1])
                        break

                    if first:
                        spred_info.last_asks_ex_1.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), ask_depth_position])
                        spred_info.last_ask_pos_price_ex_1 = order[0]
                        spred_info.last_ask_depth_pos_ex_1 = ask_depth_position
                    else:
                        spred_info.last_asks_ex_2.append([int(order[0] * order[1]), float(format(percent_length, '.3f')), ask_depth_position])
                        spred_info.last_ask_pos_price_ex_2 = order[0]
                        spred_info.last_ask_depth_pos_ex_2 = ask_depth_position

                    ask_depth_usdt += (order[0] * order[1])
                    ask_depth_position += 1

                    # print('{0} %  price: {1} usdt vol: {2}'.format(percent_length, order[0], usdt_order_volume))

                # print(exchange_name+'4')

                if spred_info.last_bid_price_ex_1 != 0 and spred_info.last_ask_price_ex_2 != 0:
                    buy_spred = (spred_info.last_bid_price_ex_1 / spred_info.last_ask_price_ex_2 - 1) * 100
                    # print('{0} {1} buy spred: {2}'.format(datetime.datetime.now(), ticker.split('/')[0], buy_spred))
                    if buy_spred > 0.4 and spred_info.last_bid_depth_usdt_ex_1 > 20 and spred_info.last_ask_depth_usdt_ex_2 > 20:
                        if spred_info.last_ask_price_ex_1 != 0 and spred_info.last_bid_price_ex_2 != 0:
                            sell_spred = (spred_info.last_ask_price_ex_1 / spred_info.last_bid_price_ex_2 - 1) * 100
                        else:
                            sell_spred = None

                        if not trader_arbi.trading() or trader_arbi.trading():
                            print('datetime: {0}; '
                                  'ticker: {1}; '
                                  'buy spred: {2}; '
                                  'last bid price base ex: {3}; '
                                  'last ask price quote ex: {4};'
                                  'base_bid_usdt: {5}; '
                                  'base_bid_pos: {6}; '
                                  'quote_ask_usdt: {7}; '
                                  'quote_ask_pos: {8}; '
                                  'sell_spred: {9}; '
                                  'usdt_24h_volume: {10}; '
                                  'buy_bids: {11}; '
                                  'buy_asks: {12}'.format(datetime.datetime.now(),
                                                                ticker.split('/')[0],
                                                                format(buy_spred, '.3f'),
                                                                spred_info.last_bid_price_ex_1,
                                                                spred_info.last_ask_price_ex_2,
                                                                format(spred_info.last_bid_depth_usdt_ex_1, '.2f'),
                                                                spred_info.last_bid_depth_pos_ex_1,
                                                                format(spred_info.last_ask_depth_usdt_ex_2, '.2f'),
                                                                spred_info.last_ask_depth_pos_ex_2,
                                                                format(sell_spred, '.3f'),
                                                                int(trades_count),
                                                                spred_info.last_bids_ex_1,
                                                                spred_info.last_asks_ex_2))

                        await trader_arbi.buy_spred_notify(symbol, buy_spred, spred_info.last_bid_pos_price_ex_1, spred_info.last_ask_pos_price_ex_2)

                    else:
                        pass
                        # if (time.time() - spred_info.last_buy_spred_print_time) >= 60:
                        #     print('{0} {1} current buy spred: {2}'.format(datetime.datetime.now(), symbol, format(buy_spred, '.3f')))
                        #     spred_info.last_buy_spred_print_time = time.time()


                if spred_info.last_ask_price_ex_1 != 0 and spred_info.last_bid_price_ex_2 != 0:
                    sell_spred = (spred_info.last_ask_price_ex_1 / spred_info.last_bid_price_ex_2 - 1) * 100
                    # print('{0} {1} sell spred: {2}'.format(datetime.datetime.now(), ticker.split('/')[0], sell_spred))
                    if sell_spred < 0.0 and spred_info.last_ask_depth_usdt_ex_1 > 20 and spred_info.last_bid_depth_usdt_ex_2 > 20:
                        await trader_arbi.sell_spred_notify(symbol, sell_spred, spred_info.last_ask_pos_price_ex_1, spred_info.last_bid_pos_price_ex_2)
                        # print('{0} {1} type: sell spred: {2} base_ask: {3}-usdt {4}-pos quote_bid {5}-usdt {6}-pos'.format(datetime.datetime.now(),
                        #         symbol.split('/')[0],
                        #         sell_spred,
                        #         format(last_ask_depth_usdt_ex_1, '.2f'),
                        #         last_ask_depth_pos_ex_1,
                        #         format(last_bid_depth_usdt_ex_2, '.2f'),
                        #         last_bid_depth_pos_ex_2))
                    else:
                        # pass
                        if trader_arbi.trading() and trader_arbi.trading_symbol() == symbol:
                            if (time.time() - spred_info.last_sell_spred_print_time) >= 60:
                                print('{0} {1} current sell spred: {2}'.format(datetime.datetime.now(), symbol, format(sell_spred, '.3f')))
                                spred_info.last_sell_spred_print_time = time.time()

                # pub_socket.send(json.dumps(msg).encode('ascii'))

            except Exception as e:
                print('error {0} watch_orderbook() ex_name: {1} symbol: {2} error_msg: {3}'.format(datetime.datetime.now(), exchange_name, symbol, e))
                telegram.sendMessage('error {0} watch_orderbook() ex_name: {1} symbol: {2} error_msg: {3}'.format(datetime.datetime.now(), exchange_name, symbol, e))
                exit()
                # stop the loop on exception or leave it commented to retry
                # raise e
    else:
        print('error {0} watch_orderbook() ex_name: {1} symbol: {2} error_msg: {3}'.format(datetime.datetime.now(), exchange_name, symbol, '???'))
    return

async def watch_orders(exchange_name, exchange, symbol, first):

    global trader_arbi

    global prev_order_id
    global prev_timestamp

    global orders_queue

    if exchange.has['watchOrders']:
        while True:
            try:
                orders = await exchange.watch_orders(symbol=symbol, limit=1)

                order = orders[0]

                if prev_order_id == order['id'] and prev_timestamp == order['timestamp']:
                    continue

                print('{0} watch_orders() ex_name: {1} symbol: {2} ex_order_datetime: {3} order: {4}'.format(datetime.datetime.now(), exchange_name, symbol, order['datetime'], order))

                orders_queue[order['id']] = order

                # await trader_arbi.handle_order(order)

                prev_order_id = order['id']
                prev_timestamp = order['timestamp']

                # msg = {}
                # msg['type'] = 'order'
                # msg['order_id'] = order['info']['orderId']
                # msg['amount'] = order['info']['cumExecQty']
                # msg['price'] = order['info']['avgPrice']
                # if order['info']['orderStatus'] == 'Filled':
                #     msg['status'] = 'closed'
                # else:
                #     msg['status'] = 'unknown'
                # msg['timestamp'] = order['info']['createdTime']

                # print('broadcaster: info: {0} order {1}'.format(symbol, msg['order_id']))
                #
                # pub_socket.send(json.dumps(msg).encode('ascii'))

            except Exception as e:
                print('error {0} watch_orders() ex_name: {1} symbol: {2} error_msg: {3}'.format(datetime.datetime.now(), exchange_name, symbol, e))
                telegram.sendMessage('error {0} watch_orders() ex_name: {1} symbol: {2} error_msg: {3}'.format(datetime.datetime.now(), exchange_name, symbol, e))
                exit()
                # stop the loop on exception or leave it commented to retry
                # raise e
    else:
        print('error {0} watch_orders() ex_name: {1} symbol: {2} error_msg: {3}'.format(datetime.datetime.now(), exchange_name, symbol, '???'))

    return

async def every_1sec():
    global trader_arbi
    global orders_queue

    try:
        while True:
            orders_to_delete = []
            for order_id, order in orders_queue.items():
                handled = trader_arbi.handle_order(order)
                if handled:
                    orders_to_delete.append(order_id)

            for order_id in orders_to_delete:
                del orders_queue[order_id]

            await asyncio.sleep(1)

    except Exception as e:
        print('error {0} every_1sec() error_msg: {1}'.format(datetime.datetime.now(), e))
        telegram.sendMessage('error {0} every_1sec() error_msg: {1}'.format(datetime.datetime.now(), e))
        exit()

    return

async def sell_all(base_exchange, quote_exchange):
    base_ex_positions = await base_exchange.fetch_positions()
    quote_ex_balance = await quote_exchange.fetch_balance()

    for position in base_ex_positions:
        print('selling base: {0} amount: {1}'.format(position['symbol'], position['contracts']))
        await base_exchange.create_order(position['symbol'], type='market', side='buy', amount=position['contracts'])
    for symbol, amount in quote_ex_balance['free'].items():
        if symbol != 'USDT':
            print('selling quote: {0} amount: {1}'.format(symbol, amount))
            await quote_exchange.create_order(symbol + '/USDT', type='market', side='sell', amount=amount)

def spot_positions(quote_ex_balance):
    count = 0
    for symbol, amount in quote_ex_balance['free'].items():
        if symbol != 'USDT':
            count += 1


    return count

async def recover(base_exchange, quote_exchange):

    global trader_arbi

    print('{0} recover() started'.format(datetime.datetime.now()))
    await sell_all(base_exchange, quote_exchange)
    return

    try:
        last_arbi_detect = db_session.query(ArbiDetectModel).order_by(ArbiDetectModel.id.desc()).first()
        print('{0} recover() started last arbi symbol: {1} last arbi state: {2}'.format(datetime.datetime.now(), last_arbi_detect.symbol, last_arbi_detect.trade_state))

        base_ex_positions = await base_exchange.fetch_positions()
        quote_ex_balance = await quote_exchange.fetch_balance()

        if last_arbi_detect.trade_state == 'done':
            print('{0} recover() condition 1'.format(datetime.datetime.now()))
            await sell_all(base_exchange, quote_exchange)
            return
        elif last_arbi_detect.trade_state == 'trading':
            base_ex_positions_count = len(base_ex_positions)
            quote_ex_positions_count = spot_positions(quote_ex_balance)

            if base_ex_positions_count != 1 or quote_ex_positions_count != 1:
                print('{0} recover() condition 2 base ex pos cnt: {1} quote ex pos cnt: {2}'.format(datetime.datetime.now(), base_ex_positions_count, quote_ex_positions_count))
                await sell_all(base_exchange, quote_exchange)
                return

            base_ex_position_symbol = base_ex_positions[0]['symbol'].split('/')[0]
            base_ex_position_amount = base_ex_positions[0]['contracts']
            quote_ex_position_symbol = None
            quote_ex_position_amount = 0

            for symbol, amount in quote_ex_balance['free'].items():
                if symbol != 'USDT':
                    quote_ex_position_symbol = symbol
                    quote_ex_position_amount = amount

            if base_ex_position_symbol != last_arbi_detect.symbol or quote_ex_position_symbol != last_arbi_detect.symbol:
                print('{0} recover() condition 3 base ex symbol: {1} quote ex symbol: {2}'.format(datetime.datetime.now(), base_ex_position_symbol, quote_ex_position_symbol))
                await sell_all(base_exchange, quote_exchange)
                return

            print('{0} recover() condition 4 base ex amount: {1} quote ex amount: {2}'.format(datetime.datetime.now(), base_ex_position_amount, quote_ex_position_amount))
            trader_arbi.recover(last_arbi_detect.symbol, base_ex_position_amount, quote_ex_position_amount)

        else:
            print('{0} recover() condition 5 ???'.format(datetime.datetime.now()))
            await sell_all(base_exchange, quote_exchange)

    except Exception as e:
        print('error {0} recover() error_msg: {1}'.format(datetime.datetime.now(), e))
        telegram.sendMessage('error {0} recover() error_msg: {1}'.format(datetime.datetime.now(), e))
        exit()


async def main():
    print('CCXT Version:', ccxt.__version__)

    global trader_arbi

    exchange_1_name = 'BYBIT'
    exchange_2_name = 'MEXC'

    print('{0} Bot start'.format(datetime.datetime.now()))
    print('{0} Base exchange: {1}'.format(datetime.datetime.now(), exchange_1_name))
    print('{0} Quote exchange: {1}'.format(datetime.datetime.now(), exchange_2_name))

    await initialize_exchanges()

    try:

        exchange_1 = exchanges[exchange_1_name]
        exchange_1.options['defaultType'] = 'future';
        markets_1 = await exchange_1.load_markets(True)

        ex1_count = 0
        ex_1_coins = []
        for key, value in markets_1.items():
            if value['swap'] and key.endswith('USDT') and key.split('/')[0] not in coins_blacklist and value['active']:
                # print(key)
                ex_1_coins.append(key.split('/')[0])
                ex1_count += 1

        exchange_2 = exchanges[exchange_2_name]
        exchange_2.options['defaultType'] = 'spot';
        # exchange_2.options['defaultType'] = 'future';
        markets_2 = await exchange_2.load_markets(True)

        await trader_arbi.initialize(exchange_1, exchange_2, exchange_1_name, exchange_2_name, markets_1, markets_2)

        await recover(base_exchange=exchange_1, quote_exchange=exchange_2)

        ex2_count = 0
        ex_2_coins = []
        for key, value in markets_2.items():
            if value['spot'] and key.endswith('USDT') and key.split('/')[0] not in coins_blacklist and value['active']:
            # if value['swap'] and key.endswith('USDT') and key.split('/')[0] not in coins_blacklist:
                ex_2_coins.append(key.split('/')[0])
                ex2_count += 1

        common_coins = list(set(ex_1_coins).intersection(ex_2_coins))

        print('{0} Common coins count: {1}'.format(datetime.datetime.now(), len(common_coins)))

        tickers_info = await exchange_2.fetch_tickers()

        final_common_coins_with_trades = {}
        for coin in common_coins:
            try:
                ticker_24h_quote_volume = tickers_info[coin + '/USDT']['quoteVolume']
                if ticker_24h_quote_volume > 200 * 1000:
                # if ticker_24h_quote_volume > 500 * 1000:
                    final_common_coins_with_trades[coin] = ticker_24h_quote_volume
            except Exception as e:
                print('error: tickers_info: {0}'.format(e))
                continue

        # print('final common coins count: {0}'.format(len(final_common_coins_with_trades.keys())))
        #
        # final_common_coins_with_trades_n = dict(sorted(final_common_coins_with_trades.items(), key=lambda item: item[1]))
        # i=1
        # for coin, vol in final_common_coins_with_trades_n.items():
        #     print(str(i) + ' ' + coin + ' ' + str(vol))
        #     i+=1
        #
        # return

        # for coin in common_coins:
        #     try:
        #         since_ms = int((datetime.datetime.now() - datetime.timedelta(minutes=30)).timestamp() * 1000)
        #
        #         # await asyncio.sleep(2)
        #         trades = await exchange_2.fetch_trades(coin + '/USDT', since_ms)
        #
        #         if len(trades) != 200:
        #             print('error: fetch_trades: wrong trades count')
        #             continue
        #
        #         minutes = int(((trades[199]['timestamp'] / 1000) - (trades[0]['timestamp'] / 1000)) / 60)
        #
        #         print('coin: {0} 200 trades in: {1} minutes'.format(coin, minutes))
        #
        #         if minutes <= 60:
        #             del final_common_coins_with_trades[coin]
        #     except Exception as e:
        #         print('error: fetch_trades: {0}'.format(e))
        #         continue


        print('{0} Active common coins count: {1}'.format(datetime.datetime.now(), len(final_common_coins_with_trades.keys())))

        # return

        # final_common_coins_with_trades = ['VET', 'RUNE', 'BLZ', 'NMR', 'TWT', 'APT', 'GNS', 'CRV', 'MAVIA', 'DASH', 'ZETA', 'PORTAL', 'FTT', 'USDC', 'TLM', 'PONKE', 'COMBO', 'BEAM', 'SHIB', 'SAND', 'VELO', 'ZEC', 'HOOK', 'KNC', 'ANT', 'DAR', 'PERP', 'CEEK', 'XVS', 'STRK', 'MATIC', 'ACH', 'NYM', 'ASTR', 'MOBILE', 'DYDX', 'ORDI', 'CVP', 'SUN', 'IOST', 'AR', 'MYRO', 'SSV', 'BEAMX', 'NEO', 'GARI', 'JUP', 'BLAST', 'AXS', 'SPELL', 'JST', 'CETUS', 'SEI', 'REEF', 'ALICE', 'GMT', 'GALA', 'UNI', 'ENJ', 'MANTA', 'GRT', 'MEME', 'AVAX', 'VGX', '1INCH', 'VRA', 'IMX', 'RSS3', 'ARKM', 'REN', 'ATH', 'ZRO', 'ETHW', 'MOVR', 'AAVE', 'LINA', 'ONT', 'VANRY', 'NEXO', 'EDU', 'PYTH', 'ENA', 'FLM', 'CFX', 'PENDLE', 'BSW', 'KSM', 'TOKEN', 'HBAR', 'SAFE', 'RARE', 'CSPR', 'DYM', 'UMA', 'MAGIC', 'OG', 'TAIKO', 'REZ', 'TON', 'OMNI', 'C98', 'TAO', 'STX', 'COMP', 'RENDER', 'LIT', 'APE', 'NYAN', 'SANTOS', 'CREAM', 'STG', 'BB', 'KDA', 'TIA', 'IDEX', 'CORE', 'SC', 'JTO', 'ZEN', 'RAD', 'FTM', 'ALPHA', 'CKB', 'CTC', 'HFT', 'CHESS', 'PYR', 'MOCA', 'CTK', 'EGLD', 'ARPA', 'BENDOG', 'STORJ', 'BLUR', 'ZK', 'LRC', 'SNX', 'YGG', 'BOBA', 'YFII', 'USTC', 'FIL', 'BICO', 'MASA', 'MDT', 'ARB', 'CYBER', 'ALGO', 'MANA', 'CHZ', 'ROSE', 'LPT', 'WAVES', 'MAV', 'SAGA', 'ID', 'ICP', 'PRCL', 'JASMY', 'DEXE', 'XVG', 'PIXEL', 'RSR', 'PENG', 'SKL', 'KLAY', 'FLR', 'A8', 'SLP', 'MULTI', 'SCRT', 'BEL', 'BOME', 'API3', 'POPCAT', 'QTUM', 'FXS', 'AMB', 'UNFI', 'HIVE', 'BSV', 'CANTO', 'OMG', 'LEVER', 'HOT', 'BCH', 'UXLINK', 'NOT', 'BNT', 'ONE', 'OOKI', 'MEW', 'SYN', 'FET', 'LOOM', 'LINK', 'INJ', 'NFP', 'WEMIX', 'HIFI', 'PHA', 'CELR', 'PAXG', 'DEGO', 'ANC', 'ETHFI', 'CAKE', 'CRO', 'BAKE', 'TLOS', 'XCN', 'GTC', 'LUNA', 'POLS', 'OP', 'GFT', 'BAL', 'HIGH', 'EOS', 'GODS', 'AEVO', 'LOOKS', 'XTZ', 'XAI', 'TRX', 'GLMR', 'BADGER', 'MBOX', 'CLV', 'SNT', 'IOTX', 'PSG', 'ATOM', 'MKR', 'T', 'ONDO', 'TNSR', 'AKRO', 'POND', 'GME', 'WAXP', 'NKN', 'FITFI', 'PEOPLE', 'ENS', 'COTI', 'OKB', 'LISTA', 'LQTY', 'ACE', 'WLD', 'IO', 'KAVA', 'XMR', 'NEAR', 'GMX', 'BANANA', 'BTS', 'ILV', 'ALT', 'SXP', 'JOE', 'BTM', 'ACA', 'GST', 'RLC', 'NTRN', 'FIDA', 'QUICK', 'QNT', 'LDO', 'AGLD', 'W', 'OGN', 'LAZIO', 'SWEAT', 'AUCTION', 'MASK', 'DOT', 'DUSK', 'DOG', 'BOND', 'FLUX', 'DRIFT', 'ZKJ', 'ANKR', 'FLOW', 'SUSHI', 'DODO', 'ETC', 'YFI', 'CVX', 'RVN', 'RPL', 'RIF', 'BAT', 'DORA', 'BIGTIME', 'KAS', 'WIF', 'OXT', 'CEL', 'DOGE', 'CELO', 'WOO', 'MAPO', 'AVAIL', 'RDNT', 'ZRX', 'ZIL', 'XCH', 'RAY', 'XLM', 'BNX', 'MINA', 'AGI', 'SFP', 'ADA', 'ALPINE', 'STEEM', 'FRONT', 'TRU', 'AI', 'PHB', 'SUI']

        skip = 0
        tasks = []
        for coin, trades_count in final_common_coins_with_trades.items():

            skip += 1
            # if skip > 2:
            #     continue
            try:
                # print(coin)
                spred_infos[coin] = SpredInfo()
                orderbook_task_1 = watch_orderbook(exchange_1_name, exchange_1, coin, coin + '/USDT:USDT', first=True, trades_count=trades_count)
                orderbook_task_2 = watch_orderbook(exchange_2_name, exchange_2, coin, coin + '/USDT', first=False, trades_count=trades_count)
                orders_task_1 = watch_orders(exchange_1_name, exchange_1, coin + '/USDT:USDT', first=True)
                orders_task_2 = watch_orders(exchange_2_name, exchange_2, coin + '/USDT', first=False)
                tasks.append(orderbook_task_1)
                tasks.append(orderbook_task_2)
                tasks.append(orders_task_1)
                tasks.append(orders_task_2)
            except Exception as e:
                print('error {0} asyncio.gather() error_msg: {1}'.format(datetime.datetime.now(), e))
                continue

        every_1sec_task = every_1sec()
        tasks.append(every_1sec_task)

        print('{0} Started...'.format(datetime.datetime.now()))

        await asyncio.gather(*tasks)

    except Exception as e:
        print('error {0} main() error_msg: {1}'.format(datetime.datetime.now(), e))
        telegram.sendMessage('error {0} main() error_msg: {1}'.format(datetime.datetime.now(), e))
    await exchange_1.close()
    await exchange_2.close()

asyncio.run(main())
