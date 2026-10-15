"""
Payments Blueprint
Handles simulated payment gateway processing, transaction history,
receipt generation, and revenue auditing.
"""

import io
import csv
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from routes.auth import login_required
from services.payment_service import (
    list_payments, get_payment_by_id, process_demo_payment, get_payment_summary
)

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/payments')
@login_required
def index():
    """Main payment management view with revenue metrics and filterable transactions."""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    payments = list_payments(search=search, status=status, date_from=date_from, date_to=date_to)
    summary = get_payment_summary()

    return render_template(
        'payments.html',
        payments=payments,
        summary=summary,
        search=search,
        selected_status=status,
        date_from=date_from,
        date_to=date_to
    )


@payments_bp.route('/payments/<int:payment_id>/process-demo', methods=['POST'])
@login_required
def process_demo(payment_id):
    """Execute simulated demo gateway payment."""
    payment_method = request.form.get('payment_method', 'Credit Card (Demo)')
    simulate_status = request.form.get('simulate_status', 'paid')

    result = process_demo_payment(payment_id, payment_method=payment_method, simulate_status=simulate_status)
    if result['success']:
        flash(f"{result['message']} Transaction Reference: {result['transaction_ref']}", 'success')
    else:
        flash(result.get('error', result.get('message')), 'danger')

    return redirect(request.referrer or url_for('payments.index'))


@payments_bp.route('/payments/<int:payment_id>/receipt')
@login_required
def receipt(payment_id):
    """Printable receipt view for completed or recorded payment."""
    payment = get_payment_by_id(payment_id)
    if not payment:
        flash('Payment transaction not found.', 'danger')
        return redirect(url_for('payments.index'))

    return render_template('receipt.html', p=payment)


@payments_bp.route('/payments/export/csv')
@login_required
def export_csv():
    """Export payment transactions to CSV."""
    payments = list_payments(limit=1000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Payment Code', 'Reservation Code', 'Customer Name', 'Plate Number',
        'Amount ($)', 'Payment Method', 'Transaction Ref', 'Status', 'Date'
    ])

    for p in payments:
        writer.writerow([
            p['payment_code'],
            p['reservation_code'],
            p['customer_name'],
            p['plate_number'],
            p['amount'],
            p['payment_method'],
            p['transaction_ref'],
            p['status'],
            p['payment_date']
        ])

    csv_data = output.getvalue()
    filename = f"payments_revenue_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
