import telegram
import asyncio
import datetime
from models import ArbiDetectModel
from database import db_session

class TradingState:
    NoneState = 1
    BuyWaitingState = 2
    BuyState = 3
    SellWaitingState = 4
    SellState = 5
    BuyTimeoutState = 6
    AfterTradeState = 7
    SleepAfterTradeState = 8

class Trader:
    def __init__(self):
        self.base_exchange = None
        self.quote_exchange = None
        self.base_exchange_name = None
        self.quote_exchange_name = None

        self.base_market = None
        self.quote_market = None

        self.deposit_usdt = 12

        self._done_callback = None

        self.base_ex_last_order_id = None
        self.quote_ex_last_order_id = None

        self.last_symbol = None

        self.last_buy_estimated_spred = 0
        self.last_sell_estimated_spred = 0

        self.base_ex_last_amount = 0
        self.quote_ex_last_amount = 0

        self.base_ex_buy_cost = 0
        self.base_ex_sell_cost = 0
        self.quote_ex_buy_cost = 0
        self.quote_ex_sell_cost = 0

        self.base_ex_buy_price = 0
        self.base_ex_sell_price = 0
        self.quote_ex_buy_price = 0
        self.quote_ex_sell_price = 0

        self.base_ex_buy_fee = None
        self.base_ex_sell_fee = None
        self.quote_ex_buy_fee = None
        self.quote_ex_sell_fee = None

        self.base_ex_buy_average_price = 0
        self.base_ex_sell_average_price = 0
        self.quote_ex_buy_average_price = 0
        self.quote_ex_sell_average_price = 0

        self._last_timestamp = None
        self._last_amount = None
        self._last_price = -1
        self.trading_state = TradingState.NoneState

    async def initialize(self, base_exchange, quote_exchange, base_exchange_name, quote_exchange_name, base_market, quote_market):
        self.base_exchange = base_exchange
        self.quote_exchange = quote_exchange
        self.base_exchange_name = base_exchange_name
        self.quote_exchange_name = quote_exchange_name
        self.base_market = base_market
        self.quote_market = quote_market

        self.flush_trading_state()

    def flush_trading_state(self):
        # print('>>>> flush')

        self.base_ex_last_amount = 0
        self.base_ex_buy_cost = 0
        self.base_ex_buy_price = 0
        self.base_ex_buy_average_price = 0
        self.base_ex_sell_cost = 0
        self.base_ex_sell_price = 0
        self.base_ex_sell_average_price = 0

        self.quote_ex_last_amount = 0
        self.quote_ex_buy_cost = 0
        self.quote_ex_buy_price = 0
        self.quote_ex_buy_average_price = 0
        self.quote_ex_sell_cost = 0
        self.quote_ex_sell_price = 0
        self.quote_ex_sell_average_price = 0

        self.base_ex_buy_fee = None
        self.base_ex_sell_fee = None
        self.quote_ex_buy_fee = None
        self.quote_ex_sell_fee = None

        self.base_ex_last_order_id = None
        self.quote_ex_last_order_id = None

        self.base_ex_last_amount = 0
        self.quote_ex_last_amount = 0

        self.last_symbol = None

        self.last_buy_estimated_spred = 0
        self.last_sell_estimated_spred = 0

        self.trading_state = TradingState.NoneState

    def last_amount(self):
        return self._last_amount

    def trading(self):
        return (self.trading_state != TradingState.NoneState)

    def trading_symbol(self):
        return self.last_symbol

    def precision(self, ticker, market):
        base_precision = float(market[ticker]['precision']['amount'])
        precision_length = 0
        if base_precision < 1:
            precision_length = (format(base_precision, 'f')).split('.')[1].find('1') + 1

        return base_precision, precision_length

    def recover(self, symbol, base_ex_amount, quote_ex_amount):
        self.trading_state = TradingState.BuyState
        self.last_symbol = symbol
        self.base_ex_last_amount = base_ex_amount
        self.quote_ex_last_amount = quote_ex_amount

    async def buy_spred_notify(self, symbol, estimated_spred, last_bid_pos_price_base_ex, last_ask_pos_price_quote_ex):

        if self.trading():
            return

        try:

            self.trading_state = TradingState.BuyWaitingState

            self.last_symbol = symbol
            self.last_buy_estimated_spred = estimated_spred
            self.base_ex_buy_price = last_bid_pos_price_base_ex
            self.quote_ex_buy_price = last_ask_pos_price_quote_ex

            base_precision, precision_length = self.precision(symbol + '/USDT:USDT', self.base_market)

            amount = self.deposit_usdt / last_bid_pos_price_base_ex
            amount -= (amount % base_precision)
            base_amount = round(amount, precision_length)

            base_precision, precision_length = self.precision(symbol + '/USDT', self.quote_market)

            amount = self.deposit_usdt / last_ask_pos_price_quote_ex
            amount -= (amount % base_precision)
            quote_amount = round(amount, precision_length)

            print('{0} buy_spred_notify() sending orders'.format(datetime.datetime.now()))
            orders = await asyncio.gather(self.base_exchange.create_order(symbol + '/USDT:USDT', type='market', side='sell', amount=base_amount, price=last_bid_pos_price_base_ex)
                                        , self.quote_exchange.create_order(symbol + '/USDT', type='market', side='buy', amount=quote_amount, price=last_ask_pos_price_quote_ex))

            self.base_ex_last_order_id = orders[0]['id']
            self.quote_ex_last_order_id = orders[1]['id']

            print('{0} buy_spred_notify() base ex buy order id {1} order {2}'.format(datetime.datetime.now(), self.base_ex_last_order_id, orders[0]))
            print('{0} buy_spred_notify() quote ex buy order id {1} order {2}'.format(datetime.datetime.now(), self.quote_ex_last_order_id, orders[1]))

        except Exception as e:
            print('error {0} buy_spred_notify() symbol: {1} error_msg: {2}'.format(datetime.datetime.now(), symbol, e))
            telegram.sendMessage('error {0} buy_spred_notify() symbol: {1} error_msg: {2}'.format(datetime.datetime.now(), symbol, e))
            exit()

        return

    async def sell_spred_notify(self, symbol, estimated_spred, last_ask_pos_price_base_ex, last_bid_pos_price_quote_ex):

        if self.trading_state != TradingState.BuyState:
            return

        if self.last_symbol != symbol:
            return

        try:

            self.trading_state = TradingState.SellWaitingState
            self.last_sell_estimated_spred = estimated_spred
            self.base_ex_sell_price = last_ask_pos_price_base_ex
            self.quote_ex_sell_price = last_bid_pos_price_quote_ex

            print('{0} sell_spred_notify() sending orders'.format(datetime.datetime.now()))
            orders = await asyncio.gather(self.base_exchange.create_order(symbol + '/USDT:USDT', type='market', side='buy', amount=self.base_ex_last_amount, price=last_ask_pos_price_base_ex)
                                        , self.quote_exchange.create_order(symbol+'/USDT', type='market', side='sell', amount=self.quote_ex_last_amount, price=last_bid_pos_price_quote_ex))

            self.base_ex_last_order_id = orders[0]['id']
            self.quote_ex_last_order_id = orders[1]['id']

            print('{0} sell_spred_notify() base ex sell order id {1} order {2}'.format(datetime.datetime.now(), self.base_ex_last_order_id, orders[0]))
            print('{0} sell_spred_notify() quote ex sell order id {1} order {2}'.format(datetime.datetime.now(), self.quote_ex_last_order_id, orders[1]))

        except Exception as e:
            print('error {0} sell_spred_notify() symbol: {1} error_msg: {2}'.format(datetime.datetime.now(), symbol, e))
            telegram.sendMessage('error {0} sell_spred_notify() symbol: {1} error_msg: {2}'.format(datetime.datetime.now(), symbol, e))
            exit()

        return

    def handle_order(self, order):

        try:

            if order['id'] != self.base_ex_last_order_id and order['id'] != self.quote_ex_last_order_id:
                # print('error {0} handle_order() wrong order id'.format(datetime.datetime.now()))
                return False

            if float(order['remaining']) > 0 and order['status'] != 'closed':
                print('error {0} handle_order() wrong order status'.format(datetime.datetime.now()))
                exit()

            if self.trading_state == TradingState.BuyWaitingState:
                if order['id'] == self.base_ex_last_order_id:
                    self.base_ex_last_amount = order['filled']
                    self.base_ex_buy_cost = order['cost']
                    self.base_ex_buy_average_price = order['average']
                    self.base_ex_buy_fee = order['fee']
                elif order['id'] == self.quote_ex_last_order_id:
                    self.quote_ex_last_amount = order['filled']
                    # if order['fee']['currency'] != 'USDT':
                    #     self.quote_ex_last_amount -= float(order['fee']['cost'])
                    self.quote_ex_buy_cost = order['cost']
                    self.quote_ex_buy_average_price = order['average']
                    self.quote_ex_buy_fee = order['fee']

                if self.base_ex_buy_average_price > 0 and self.quote_ex_buy_average_price > 0:
                    self.trading_state = TradingState.BuyState
                    self.base_ex_last_order_id = None
                    self.quote_ex_last_order_id = None
                    print('Buy DONE\n'
                          '- symbol: {0}\n'
                          '- base amount: {1}\n'
                          '- quote amount: {2}\n'
                          '- base price: {3}\n'
                          '- quote price: {4}\n'
                          '- estimated spred: {5}\n'
                          '- base average price: {6}\n'
                          '- quote average price: {7}\n'
                          '- real spred: {8}\n'
                          '- base fee: {9}\n'
                          '- quote fee: {10}'.format(self.last_symbol,
                                                     self.base_ex_last_amount,
                                                     self.quote_ex_last_amount,
                                                    self.base_ex_buy_price,
                                                    self.quote_ex_buy_price,
                                                    format(self.last_buy_estimated_spred, '.3f'),
                                                    self.base_ex_buy_average_price,
                                                    self.quote_ex_buy_average_price,
                                                    format((self.base_ex_buy_average_price / self.quote_ex_buy_average_price - 1) * 100, '.3f'),
                                                    self.base_ex_buy_fee,
                                                    self.quote_ex_buy_fee)
                          )

                    arbi_detect = ArbiDetectModel(self.last_symbol, self.base_exchange_name, self.quote_exchange_name)
                    arbi_detect.trade_state = 'trading'
                    arbi_detect.buy_datetime = datetime.datetime.now()
                    arbi_detect.buy_base_estimated_price = self.base_ex_buy_price
                    arbi_detect.buy_quote_estimated_price = self.quote_ex_buy_price
                    arbi_detect.buy_base_real_price = self.base_ex_buy_average_price
                    arbi_detect.buy_quote_real_price = self.quote_ex_buy_average_price
                    arbi_detect.buy_estimated_spred = self.last_buy_estimated_spred
                    arbi_detect.buy_real_spred = float(format((self.base_ex_buy_average_price / self.quote_ex_buy_average_price - 1) * 100, '.3f'))

                    arbi_detect.db_add()
                    ArbiDetectModel.db_commit()

            elif self.trading_state == TradingState.SellWaitingState:
                if order['id'] == self.base_ex_last_order_id:
                    self.base_ex_last_amount = order['filled']
                    self.base_ex_sell_cost = order['cost']
                    self.base_ex_sell_average_price = order['average']
                elif order['id'] == self.quote_ex_last_order_id:
                    self.quote_ex_last_amount = order['filled']
                    self.quote_ex_sell_cost = order['cost']
                    self.quote_ex_sell_average_price = order['average']

                if self.base_ex_sell_average_price > 0 and self.quote_ex_sell_average_price > 0:
                    sell_buy_base_cost = self.base_ex_sell_cost - self.base_ex_buy_cost
                    sell_buy_quote_cost = self.quote_ex_sell_cost - self.quote_ex_buy_cost
                    final_cost = sell_buy_base_cost + sell_buy_quote_cost
                    print('Sell DONE\n'
                          '- symbol: {0}\n'
                          '- base price: {1}\n'
                          '- quote price: {2}\n'
                          '- estimated spred: {3}\n'
                          '- base average price: {4}\n'
                          '- quote average price: {5}\n'
                          '- real spred: {6}\n'
                          '- base fee: {7}\n'
                          '- quote fee: {8}\n'
                          '- sell-buy base cost: {9}\n'
                          '- sell-buy quote cost: {10}\n'
                          '- final cost: {11}'.format(self.last_symbol,
                                                    self.base_ex_sell_price,
                                                    self.quote_ex_sell_price,
                                                    format(self.last_sell_estimated_spred, '.3f'),
                                                    self.base_ex_sell_average_price,
                                                    self.quote_ex_sell_average_price,
                                                    format((self.base_ex_sell_average_price / self.quote_ex_sell_average_price - 1) * 100, '.3f'),
                                                    self.base_ex_sell_fee,
                                                    self.quote_ex_sell_fee,
                                                    format(sell_buy_base_cost, '.3f'),
                                                    format(sell_buy_quote_cost, '.3f'),
                                                    format(final_cost, '.3f')
                                                      )
                          )

                    arbi_detect = db_session.query(ArbiDetectModel).order_by(ArbiDetectModel.id.desc()).first()
                    arbi_detect.trade_state = 'done'
                    arbi_detect.sell_datetime = datetime.datetime.now()
                    arbi_detect.sell_base_estimated_price = self.base_ex_sell_price
                    arbi_detect.sell_quote_estimated_price = self.quote_ex_sell_price
                    arbi_detect.sell_base_real_price = self.base_ex_sell_average_price
                    arbi_detect.sell_quote_real_price = self.quote_ex_sell_average_price
                    arbi_detect.sell_estimated_spred = self.last_sell_estimated_spred
                    arbi_detect.sell_real_spred = float(format((self.base_ex_sell_average_price / self.quote_ex_sell_average_price - 1) * 100, '.3f'))

                    telegram.sendMessage('Trade DONE\n'
                                         '- symbol: {0}\n'
                                         '- estimated buy spred: {1}\n'
                                         '- real buy spred: {2}\n'
                                         '- estimated sell spred: {3}\n'
                                         '- real sell spred: {4}\n'
                                         '- result: {5}\n'
                                         .format(arbi_detect.symbol,
                                                 arbi_detect.buy_estimated_spred,
                                                 arbi_detect.buy_real_spred,
                                                 arbi_detect.sell_estimated_spred,
                                                 arbi_detect.sell_real_spred,
                                                 (arbi_detect.buy_real_spred - arbi_detect.sell_real_spred) - 0.2))

                    arbi_detect.db_add()
                    ArbiDetectModel.db_commit()

                    self.flush_trading_state()

        except Exception as e:
            print('error {0} handle_order() error_msg: {1}'.format(datetime.datetime.now(), e))
            telegram.sendMessage('error {0} handle_order() error_msg: {1}'.format(datetime.datetime.now(), e))
            exit()

        return True

