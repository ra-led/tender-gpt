from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
from sqlalchemy.sql import func
from datetime import datetime
import json
from pathlib import Path

app = Flask(__name__)

# 1) Configure SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tenders.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 2) Define our Tender model
class Tender(db.Model):
    __tablename__ = 'tenders'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String, index=True, nullable=False)
    tender_id = db.Column(db.String, unique=True, nullable=False)
    url = db.Column(db.String)
    status = db.Column(db.String)
    description = db.Column(db.Text)
    customer = db.Column(db.String)
    start_price = db.Column(db.String)
    result_date = db.Column(db.String)
    public_date = db.Column(db.Date)       # filter by this date
    report_html = db.Column(db.Text)

    def __repr__(self):
        return f'<Tender {self.tender_id}>'

# 3) Initialize DB via CLI command
@app.cli.command("init-db")
def init_db():
    """Create database tables."""
    db.create_all()
    print("✅ Database tables created.")

# 4) Seed data command remains the same
@app.cli.command("seed-db")
def seed_db():
    """Load file-based data into DB."""
    base = Path('data')
    for public_date_dir in base.iterdir():
        try:
            public_date = datetime.strptime(public_date_dir.name, "%Y-%m-%d").date()
        except Exception as ex:
            print(ex)
            continue
        for cli_dir in public_date_dir.iterdir():
            if not cli_dir.is_dir():
                continue
            client_id = cli_dir.name
            for tender_path in cli_dir.glob('tender_*'):
                meta_f = tender_path / 'metadata.json'
                rpt_f = tender_path / 'report.html'
                if not (meta_f.exists() and rpt_f.exists()):
                    continue
    
                with open(meta_f, encoding='utf-8') as mf:
                    meta = json.load(mf)
                with open(rpt_f, encoding='utf-8') as rf:
                    report_html = rf.read()
    
                tender = Tender(
                    client_id   = client_id,
                    tender_id   = meta.get('tender_id'),
                    url         = meta.get('url'),
                    status      = meta.get('status',''),
                    description = meta.get('description',''),
                    customer    = meta.get('customer',''),
                    start_price = meta.get('start_price',''),
                    result_date = meta.get('result_date',''),
                    public_date = public_date,
                    report_html = report_html
                )
                db.session.add(tender)
    db.session.commit()
    print("✅ seed-db done.")


# 5) Fetch from DB with optional date filtering
def load_tenders(client_id, start_date=None, end_date=None):
    q = Tender.query.filter_by(client_id=client_id)
    if start_date:
        q = q.filter(Tender.public_date >= start_date)
    if end_date:
        q = q.filter(Tender.public_date <= end_date)
    return q.order_by(Tender.public_date.desc()).all()

# 6) Routes

@app.route('/')
def landing():
    return render_template('landing.html')

# Helper to get min/max dates for tenders of a client
def get_public_date_range(client_id):
    min_date, max_date = db.session.query(
        func.min(Tender.public_date), func.max(Tender.public_date)
    ).filter(Tender.client_id == client_id).first()
    return min_date, max_date

@app.route('/dashboard/<client_id>')
def dashboard(client_id):
    # read date filters from query string
    start_s = request.args.get('start_date','')
    end_s   = request.args.get('end_date','')
    fmt = '%Y-%m-%d'
    sd = ed = None

    # Get min/max dates for the filter UI
    min_date_obj, max_date_obj = get_public_date_range(client_id)
    min_date = min_date_obj.isoformat() if min_date_obj else ""
    max_date = max_date_obj.isoformat() if max_date_obj else ""

    # Fill sd/ed only if set in the query string
    try:
        if start_s:
            sd = datetime.strptime(start_s, fmt).date()
        if end_s:
            ed = datetime.strptime(end_s, fmt).date()
    except ValueError:
        sd = ed = None

    # If start/end dates are NOT set, and we have min/max, fill for template defaults
    start_s = start_s if start_s else min_date
    end_s = end_s if end_s else max_date

    tenders = load_tenders(client_id, sd, ed)
    return render_template(
        'tender.html',
        tenders    = tenders,
        client_id  = client_id,
        start_date = start_s,
        end_date   = end_s,
        min_date   = min_date,
        max_date   = max_date,
    )

if __name__ == '__main__':
    app.run(debug=True, port=3333)
