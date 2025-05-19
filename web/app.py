import os
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
from sqlalchemy.sql import func, desc
from datetime import datetime
from openpyxl import Workbook
from io import BytesIO
from meilisearch import Client as MeiliClient

app = Flask(__name__)

# Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://pguser:pgpass@localhost:5432/tendersdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Meili config
MEILI_URL = os.getenv('MEILI_URL', 'http://0.0.0.0:7700')
MEILI_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')
meili = MeiliClient(MEILI_URL, MEILI_KEY)
MEILI_INDEX = 'tenders'
meili_index = meili.index(MEILI_INDEX)

#################################
# MODELS (PostgreSQL only)
#################################
class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Text, nullable=False)
    template_id = db.Column(db.Text, nullable=False)
    tender_id = db.Column(db.Text, nullable=False)
    report_date = db.Column(db.Date, nullable=False)
    report_html = db.Column(db.Text, nullable=False)
    viewed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (db.UniqueConstraint('client_id', 'template_id', 'tender_id'),)

###########################
# HELPERS
###########################

def get_meili_docs_by_ids(ids):
    """Batch fetch (up to 1000) documents from Meilisearch index by tender_id."""
    # For Meilisearch v1+ use get_documents; API batch limit is ~1000
    # If you have to fetch more, split into chunks
    if not ids:
        return {}
    docs = meili_index.get_documents({'filter': f'tender_id IN ["' + '","'.join(ids) + '"]', 'limit': len(ids)})
    # docs['results'] is the list of objects
    # Return a dict {tender_id: doc}
    return {doc['tender_id']: doc for doc in docs.get('results', [])}

def get_min_max_pub_date(client_id):
    """Get min/max report_date for filter UI."""
    min_dt, max_dt = db.session.query(
        func.min(Report.report_date), func.max(Report.report_date)
    ).filter(Report.client_id==client_id).first()
    return min_dt, max_dt

def build_merged_tender(report, doc):
    """Merge Postgres report and meili doc into dict."""
    row = {
        # Core PK fields
        'tender_id': report.tender_id,
        'client_id': report.client_id,
        'template_id': report.template_id,
        'report_date': report.report_date.isoformat(),
        # User
        'viewed': report.viewed,
        'report_html': report.report_html,
        # Meta
    }
    if doc:
        row.update(doc)
    return row

###############
# ROUTES
###############

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/dashboard/<client_id>/data')
def tender_data(client_id):
    # Params
    page    = request.args.get('page', 1, type=int)
    per_page = 10
    start_s = request.args.get('start_date', '')
    end_s   = request.args.get('end_date', '')
    unviewed = (request.args.get('unviewed_only', '0') == '1')
    # parse dates
    sd = ed = None
    fmt = '%Y-%m-%d'
    try:
        if start_s: sd = datetime.strptime(start_s, fmt).date()
        if end_s: ed = datetime.strptime(end_s, fmt).date()
    except ValueError:
        pass

    # Query from Postgres (the "user" subset)
    q = Report.query.filter(Report.client_id == client_id)
    if sd: q = q.filter(Report.report_date >= sd)
    if ed: q = q.filter(Report.report_date <= ed)
    if unviewed: q = q.filter(Report.viewed == False)
    q = q.order_by(desc(Report.report_date))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    reports = pagination.items

    tender_ids = [r.tender_id for r in reports]
    docs_map = get_meili_docs_by_ids(tender_ids)
    tenders = [build_merged_tender(r, docs_map.get(r.tender_id)) for r in reports]

    cards_html = render_template('_cards.html', tenders=tenders)

    return jsonify({
        'html': cards_html,
        'has_next': pagination.has_next
    })

@app.route('/dashboard/<client_id>')
def dashboard(client_id):
    # Filters
    start_s = request.args.get('start_date', '')
    end_s = request.args.get('end_date', '')
    unviewed = (request.args.get('unviewed_only', '0') == '1')
    sd = ed = None
    fmt = '%Y-%m-%d'
    try:
        if start_s: sd = datetime.strptime(start_s, fmt).date()
        if end_s: ed = datetime.strptime(end_s, fmt).date()
    except ValueError:
        pass

    min_date_obj, max_date_obj = get_min_max_pub_date(client_id)
    min_date = min_date_obj.isoformat() if min_date_obj else ""
    max_date = max_date_obj.isoformat() if max_date_obj else ""
    # Fill for defaults
    start_s = start_s if start_s else min_date
    end_s   = end_s if end_s else max_date

    page = request.args.get('page', 1, type=int)
    per_page = 10

    q = Report.query.filter(Report.client_id == client_id)
    if sd: q = q.filter(Report.report_date >= sd)
    if ed: q = q.filter(Report.report_date <= ed)
    if unviewed: q = q.filter(Report.viewed == False)
    q = q.order_by(desc(Report.report_date))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    reports = pagination.items
    tender_ids = [r.tender_id for r in reports]
    docs_map = get_meili_docs_by_ids(tender_ids)
    tenders = [build_merged_tender(r, docs_map.get(r.tender_id)) for r in reports]

    return render_template(
        'tender.html',
        tenders     = tenders,
        client_id   = client_id,
        start_date  = start_s,
        end_date    = end_s,
        min_date    = min_date,
        max_date    = max_date,
        has_next    = pagination.has_next,
        total_count = pagination.total
    )

@app.route('/dashboard/<client_id>/export')
def export_excel(client_id):
    start_s = request.args.get('start_date', '')
    end_s = request.args.get('end_date', '')
    unviewed = (request.args.get('unviewed_only', '0') == '1')
    sd = ed = None
    fmt = '%Y-%m-%d'
    try:
        if start_s: sd = datetime.strptime(start_s, fmt).date()
        if end_s: ed = datetime.strptime(end_s, fmt).date()
    except ValueError:
        pass

    q = Report.query.filter(Report.client_id == client_id)
    if sd: q = q.filter(Report.report_date >= sd)
    if ed: q = q.filter(Report.report_date <= ed)
    if unviewed: q = q.filter(Report.viewed == False)
    q = q.order_by(desc(Report.report_date))
    reports = q.all()
    tender_ids = [r.tender_id for r in reports]
    docs_map = get_meili_docs_by_ids(tender_ids)
    tenders = [build_merged_tender(r, docs_map.get(r.tender_id)) for r in reports]

    wb = Workbook()
    ws = wb.active
    ws.title = "Tenders"
    # Write header
    ws.append([
        "tender_id", "client_id", "template_id", "report_date", "viewed", "customer", "customer_name",
        "description", "public_date", "end_date", "fz", "lot_name", "start_price", "url"
    ])
    for t in tenders:
        ws.append([
            t.get("tender_id"),
            t.get("client_id"),
            t.get("template_id"),
            t.get("report_date"),
            "Yes" if t.get("viewed") else "No",
            t.get("customer"),
            t.get("customer_name"),
            t.get("description"),
            t.get("public_date"),
            t.get("end_date"),
            t.get("fz"),
            t.get("lot_name"),
            t.get("start_price"),
            t.get("url")
        ])
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    fn = f"tenders_{client_id}_{start_s or 'all'}_{end_s or 'all'}.xlsx"
    return send_file(
        bio,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fn
    )

@app.route('/tender/<tender_id>/viewed', methods=['POST'])
def mark_viewed(tender_id):
    # You could add client_id and/or template_id if needed!
    rpt = Report.query.filter_by(tender_id=tender_id).first_or_404()
    if not rpt.viewed:
        rpt.viewed = True
        db.session.commit()
    return ('', 204)

if __name__ == '__main__':
    app.run(debug=True, port=3333)