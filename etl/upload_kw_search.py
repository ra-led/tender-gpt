import os, glob, csv
from pathlib import Path
from datetime import datetime

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Text,
    Date,
    TIMESTAMP,
    Float,
    text,
    Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://pguser:pgpass@localhost:5432/tendersdb'
)
DATA_ROOT = os.getenv('DATA_ROOT', '/Users/yuratomakov/zakupki-gov/tender-gpt/etl/archive/31.05.2025/')

# -----------------------------------------------------------------------------
# SQLAlchemy setup
# -----------------------------------------------------------------------------
Base = declarative_base()

class KWReport(Base):
    __tablename__ = 'kw_report'

    id               = Column(Integer, primary_key=True)
    client_id        = Column(Text,    nullable=False)
    template_id      = Column(Text,    nullable=False)
    tender_id        = Column(Text,    nullable=False)
    public_date      = Column(Date,    nullable=True)
    description      = Column(Text)
    lot_name         = Column(Text)
    url              = Column(Text)
    highlight        = Column(Text)

    # NEW FIELDS
    oker             = Column(Text)
    fz               = Column(Text)
    okpd2            = Column(Text)
    customer_name    = Column(Text)
    start_price      = Column(Float)
    end_date         = Column(Date)
    ets_name         = Column(Text)
    ets_adress       = Column(Text)
    end_datetime     = Column(Text)
    result_date      = Column(Date)
    customer_adress  = Column(Text)

    created_at       = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        # keep your existing index
        Index('ix_kw_client_template_date', 'client_id', 'template_id', 'public_date'),
    )

engine  = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

def parse_csv_filename(path: Path):
    # Format: ./client_data_{date}_{client_id}_{template_id}.csv
    filename = path.name
    if not filename.startswith("client_data_") or not filename.endswith(".csv"):
        return None
    base = filename.removesuffix('.csv')
    date_part, client_id, template_id = base.split("_")[-3:]
    return client_id, template_id

def parse_date(val):
    """Handles date in ISO or dd.mm.yyyy format or returns None"""
    if not val:
        return None
    val = val.strip()
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%d.%m.%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except Exception:
            pass
    return None

def upsert_kw_reports():
    files = glob.glob(f'{DATA_ROOT}/client_data_*.csv')
    session = Session()
    count = 0

    for fp in files:
        path = Path(fp)
        meta = parse_csv_filename(path)
        if not meta:
            print("Skipped:", path)
            continue
        client_id, template_id = meta

        with open(path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tender_id      = row['tender_id']
                public_date    = parse_date(row.get('public_date'))
                end_date       = parse_date(row.get('end_date'))
                result_date    = parse_date(row.get('result_date'))

                # Try to find an existing record
                kw = session.query(KWReport).filter_by(
                    client_id=client_id,
                    template_id=template_id,
                    tender_id=tender_id
                ).one_or_none()

                if kw:
                    # update fields
                    kw.public_date     = public_date
                    kw.description     = row.get('description')
                    kw.lot_name        = row.get('lot_name')
                    kw.url             = row.get('url')
                    kw.highlight       = row.get('highlight')

                    # NEW fields
                    kw.oker            = row.get('oker')
                    kw.fz              = row.get('fz')
                    kw.okpd2           = row.get('okpd2')
                    kw.customer_name   = row.get('customer_name')
                    kw.start_price     = float(row.get('start_price')) if row.get('start_price') else None
                    kw.end_date        = end_date
                    kw.ets_name        = row.get('ets_name')
                    kw.ets_adress      = row.get('ets_adress')
                    kw.end_datetime    = row.get('end_datetime')
                    kw.result_date     = result_date
                    kw.customer_adress = row.get('customer')

                else:
                    # insert new
                    session.add(KWReport(
                        client_id        = client_id,
                        template_id      = template_id,
                        tender_id        = tender_id,
                        public_date      = public_date,
                        description      = row.get('description'),
                        lot_name         = row.get('lot_name'),
                        url              = row.get('url'),
                        highlight        = row.get('highlight'),
                        # new
                        oker             = row.get('oker'),
                        fz               = row.get('fz'),
                        okpd2            = row.get('okpd2'),
                        customer_name    = row.get('customer_name'),
                        start_price      = float(row.get('start_price')) if row.get('start_price') else None,
                        end_date         = end_date,
                        ets_name         = row.get('ets_name'),
                        ets_adress       = row.get('ets_adress'),
                        end_datetime     = row.get('end_datetime'),
                        result_date      = result_date,
                        customer_adress  = row.get('customer'),
                    ))
                count += 1

            session.commit()

    session.close()
    print(f"✅ Uploaded {count} records from {len(files)} files.")

if __name__ == "__main__":
    init_db()
    upsert_kw_reports()

    
# import pandas as pd

# DATABASE_URL="postgresql://pguser:pgpass@158.160.51.157:5432/tendersdb" 

# # Create a session
# session = Session()

# try:
#     # Query all rows from kw_report table using pandas
#     df = pd.read_sql(session.query(KWReport).statement, session.bind)
    
#     print(f"Loaded {len(df)} rows from kw_report table")
#     print(df.head())
    
# finally:
#     # Close the session
#     session.close()
    
    
# from sqlalchemy import update

# # Create a session
# session = Session()

# try:
#     # Update all rows in kw_report table
#     stmt = update(KWReport).values(template_id="1")
#     result = session.execute(stmt)
    
#     # Commit the transaction
#     session.commit()
    
#     print(f"Updated {result.rowcount} rows in kw_report table")
    
# finally:
#     # Close the session
#     session.close()