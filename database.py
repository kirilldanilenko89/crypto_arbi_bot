from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('postgresql://dm_arbi_bot_user:dm_arbi_bot_password@0.0.0.0:5432/dm_arbi_bot', echo=False)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

# db_session = scoped_session(sessionmaker(bind=engine))
# db = sessionmaker(bind=engine)
# db_session = db()

Base = declarative_base()
Base.query = db_session.query_property()