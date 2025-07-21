from sqlalchemy import update
import os, glob
from pathlib import Path
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, Text, Date, Boolean, TIMESTAMP,
    UniqueConstraint, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://pguser:pgpass@158.160.51.157:5432/tendersdb'
)
SUMMARY_ROOT = os.getenv('SUMMARY_ROOT', 'summary')

# -----------------------------------------------------------------------------
# SQLAlchemy setup
# -----------------------------------------------------------------------------
Base = declarative_base()

class Report(Base):
    __tablename__ = 'reports'
    id          = Column(Integer, primary_key=True)
    client_id   = Column(Text, nullable=False)
    template_id = Column(Text, nullable=False)
    tender_id   = Column(Text, nullable=False)
    report_date = Column(Date, nullable=False)
    report_html = Column(Text, nullable=False)
    viewed      = Column(Boolean, default=False, nullable=False)
    created_at  = Column(TIMESTAMP(timezone=True),
                         server_default=text('now()'))
    __table_args__ = (
        UniqueConstraint('client_id','template_id','tender_id',
                         name='uq_report'),
    )

engine  = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def reset_viewed_status():
    session = Session()
    try:
        # Create an update statement that sets viewed=False for all rows
        stmt = update(Report).values(viewed=False)
        
        # Execute the statement
        session.execute(stmt)
        session.commit()
        print("✅ Successfully reset 'viewed' status for all reports.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error resetting 'viewed' status: {e}")
    finally:
        session.close()

reset_viewed_status()