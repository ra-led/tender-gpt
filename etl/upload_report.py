import os, glob
from pathlib import Path
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, Text, Date, Boolean, TIMESTAMP,
    UniqueConstraint, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from meilisearch import Client

MEILI_URL = os.getenv('MEILI_URL', 'http://0.0.0.0:7700')
MEILI_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')
meili = Client(MEILI_URL, MEILI_KEY)

INDEX_NAME = "tenders"
tenders_index = meili.index(INDEX_NAME)


def get_end_by_id(tender_id):
    if not tender_id:
        return None
    docs = tenders_index.get_documents(
        {'filter': f'tender_id IN ["{tender_id}"]', 'limit': 1}
    )
    if docs.results:
        return docs.results[0].end_date
    return None

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://pguser:pgpass@localhost:5432/tendersdb'
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
    end_date    = Column(Date, nullable=False)
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

def init_db_with_models():
    """
    Use SQLAlchemy to create missing tables:
    issues `CREATE TABLE IF NOT EXISTS reports ...`
    """
    Base.metadata.create_all(engine)

def init_db_with_raw_sql():
    """
    If you want to do it manually:
    """
    create_sql = """
    CREATE TABLE IF NOT EXISTS reports (
      id            SERIAL PRIMARY KEY,
      client_id     TEXT NOT NULL,
      template_id   TEXT NOT NULL,
      tender_id     TEXT NOT NULL,
      report_date   DATE NOT NULL,
      end_date      DATE NOT NULL,
      report_html   TEXT NOT NULL,
      viewed        BOOLEAN DEFAULT FALSE,
      created_at    TIMESTAMP WITH TIME ZONE DEFAULT now(),
      UNIQUE (client_id, template_id, tender_id)
    );
    """
    with engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()

# -----------------------------------------------------------------------------
# File parsing & upsert
# -----------------------------------------------------------------------------
def parse_path(path: Path):
    parts = path.parts
    if len(parts) < 6 or parts[-1] != 'report.html':
        return None
    date_str, client_id, template_id, tender_dir = parts[-5:-1]
    if not tender_dir.startswith('tender_'):
        return None
    tender_id = tender_dir.split('_', 1)[1]
    try:
        report_date = datetime.fromisoformat(date_str).date()
    except ValueError:
        report_date = datetime.strptime(date_str, '%d.%m.%Y').date()
    return client_id, template_id, tender_id, report_date

def upsert_reports():
    session = Session()
    files = glob.glob(f'{SUMMARY_ROOT}/**/report.html', recursive=True)
    for fp in files:
        path = Path(fp)
        parsed = parse_path(path)
        if not parsed:
            print("Skipped:", path)
            continue
        client_id, template_id, tender_id, report_date = parsed
        html = path.read_text(encoding='utf-8')

        tender_end_date = get_end_by_id(tender_id)
        
        rpt = session.query(Report).filter_by(
            client_id=client_id,
            template_id=template_id,
            tender_id=tender_id
        ).one_or_none()
        
        if rpt:
            rpt.report_date = report_date
            rpt.end_date = tender_end_date
            rpt.report_html = html
        else:
            session.add(Report(
                client_id=client_id,
                template_id=template_id,
                tender_id=tender_id,
                report_date=report_date,
                end_date=tender_end_date,
                report_html=html
            ))
    session.commit()
    session.close()

if __name__ == '__main__':
    # 1) create table if it doesn't exist:
    init_db_with_models()
    # OR, if you prefer raw SQL:
    # init_db_with_raw_sql()

    # 2) upload all reports
    upsert_reports()
    print("✅ Done uploading reports.")