from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base, db_session
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, BigInteger, Float, ForeignKey


class ArbiDetectModel(Base):
    __tablename__ = 'arbi_detects'
    # __table_args__ = {'extend_existing': True}

    id            = Column(Integer, primary_key=True)
    symbol        = Column(String, nullable=False)
    base_exchange = Column(String, nullable=False)
    quote_exchange = Column(String, nullable=False)
    trade_state = Column(String, nullable=False)
    buy_datetime   = Column(DateTime, nullable=False)
    buy_base_estimated_price = Column(Float, nullable=False)
    buy_quote_estimated_price = Column(Float, nullable=False)
    buy_base_real_price = Column(Float, nullable=False)
    buy_quote_real_price = Column(Float, nullable=False)
    buy_estimated_spred = Column(Float, nullable=False)
    buy_real_spred = Column(Float, nullable=False)
    sell_datetime = Column(DateTime, nullable=True)
    sell_base_estimated_price = Column(Float, nullable=True)
    sell_quote_estimated_price = Column(Float, nullable=True)
    sell_base_real_price = Column(Float, nullable=True)
    sell_quote_real_price = Column(Float, nullable=True)
    sell_estimated_spred = Column(Float, nullable=True)
    sell_real_spred = Column(Float, nullable=True)

    @staticmethod
    def to_datetime(timestamp_ms):
        utc = datetime.utcfromtimestamp(timestamp_ms // 1000)
        return utc.strftime('%Y-%m-%d %H:%M:%S.%f')[:-6] + "{:03d}".format(int(timestamp_ms) % 1000)

    def db_add(self):
        db_session.add(self)

    @staticmethod
    def db_commit():
        db_session.commit()

    def __init__(self, symbol, base_exchange, quote_exchange):
        self.symbol = symbol
        self.base_exchange = base_exchange
        self.quote_exchange = quote_exchange

    def __repr__(self):
        return '<symbol %r>' % (self.id)

    def to_json(self):
        return '{}'
