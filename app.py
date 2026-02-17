from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
import openpyxl
from openpyxl.styles import PatternFill
import requests
import time
import os
import json
import uuid
import threading
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# In-memory storage for validation jobs
validation_jobs = {}

def parse_vat_number(vat_input):
    """
    Parse VAT number and extract country code and number.
    Returns (country_code, vat_number) tuple.
    """
    vat_str = str(vat_input).strip().replace(' ', '').replace('-', '').replace('.', '')

    # Check if VAT starts with 2-letter country code
    if len(vat_str) >= 2 and vat_str[:2].isalpha():
        country_code = vat_str[:2].upper()
        vat_number = vat_str[2:]
        return country_code, vat_number

    # No country code in VAT number
    return None, vat_str

def validate_vat(vat_input):
    """
    Validate VAT number using VIES API.
    Automatically extracts country code from VAT number.
    """
    country_code, vat_number = parse_vat_number(vat_input)

    if not country_code:
        return {'valid': False, 'error': 'Nerasta šalies kodo / Country code not found', 'country': None}

    if not vat_number:
        return {'valid': False, 'error': 'Tuščias PVM numeris / Empty VAT number', 'country': country_code}

    try:
        url = f'https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country_code}/vat/{vat_number}'
        response = requests.get(url, timeout=10)

        # Check if response is valid JSON
        if not response.text or response.text.strip() == '':
            return {'valid': False, 'error': 'Empty response from VIES API', 'country': country_code}

        data = response.json()

        return {
            'valid': data.get('isValid', False),
            'name': data.get('name', ''),
            'address': data.get('address', ''),
            'country': country_code,
            'error': None if data.get('userError') == 'VALID' else data.get('userError')
        }
    except requests.exceptions.JSONDecodeError as e:
        return {'valid': False, 'error': f'Invalid API response: {str(e)}', 'country': country_code}
    except requests.exceptions.Timeout:
        return {'valid': False, 'error': 'API timeout', 'country': country_code}
    except Exception as e:
        return {'valid': False, 'error': str(e), 'country': country_code}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and return sheet info"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'Please upload an Excel file (.xlsx or .xls)'}), 400

    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Open workbook and get sheet names
        wb = openpyxl.load_workbook(filepath)
        sheets = wb.sheetnames

        # Get columns from first sheet as example
        first_sheet = wb[sheets[0]]
        columns = []

        # Get header row (assuming first row)
        for cell in first_sheet[1]:
            if cell.value:
                columns.append(str(cell.value))

        wb.close()

        return jsonify({
            'filename': filename,
            'sheets': sheets,
            'columns': columns
        })
    except Exception as e:
        return jsonify({'error': f'Error reading file: {str(e)}'}), 400

@app.route('/get-columns', methods=['POST'])
def get_columns():
    """Get columns for a specific sheet"""
    data = request.json
    filename = secure_filename(data.get('filename'))
    sheet_name = data.get('sheet')

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        wb = openpyxl.load_workbook(filepath)
        sheet = wb[sheet_name]

        columns = []
        for cell in sheet[1]:
            if cell.value:
                columns.append(str(cell.value))

        wb.close()

        return jsonify({'columns': columns})
    except Exception as e:
        return jsonify({'error': f'Error reading sheet: {str(e)}'}), 400

def process_validation_job(job_id, filename, sheet_name, vat_column):
    """Background worker to process VAT validation"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        wb = openpyxl.load_workbook(filepath)
        sheet = wb[sheet_name]

        # Find column index
        vat_col_idx = None
        for idx, cell in enumerate(sheet[1], 1):
            if cell.value == vat_column:
                vat_col_idx = idx
                break

        if vat_col_idx is None:
            validation_jobs[job_id]['status'] = 'error'
            validation_jobs[job_id]['error'] = f'Column "{vat_column}" not found'
            return

        # Define colors
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
        red_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
        yellow_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")

        # Count total VAT numbers to process
        vat_rows = []
        for row_idx in range(2, sheet.max_row + 1):
            vat_value = sheet.cell(row_idx, vat_col_idx).value
            if vat_value:
                vat_rows.append((row_idx, vat_value))

        total = len(vat_rows)
        validation_jobs[job_id]['total'] = total

        # Process each VAT number
        for idx, (row_idx, vat_value) in enumerate(vat_rows, 1):
            vat_cell = sheet.cell(row_idx, vat_col_idx)

            # Validate VAT
            result = validate_vat(vat_value)

            # Color code the cell
            if result['valid']:
                vat_cell.fill = green_fill
            elif result.get('country'):
                vat_cell.fill = red_fill
            else:
                vat_cell.fill = yellow_fill

            # Add to results
            validation_jobs[job_id]['results'].append({
                'row': row_idx,
                'vat': str(vat_value),
                'country': result.get('country', ''),
                'valid': result['valid'],
                'name': result.get('name', ''),
                'error': result.get('error')
            })

            # Update progress
            validation_jobs[job_id]['processed'] = idx
            validation_jobs[job_id]['progress'] = int((idx / total) * 100)

            # Small delay to be nice to the API
            time.sleep(0.3)

        # Save the modified file
        output_filename = f'validated_{filename}'
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        wb.save(output_path)
        wb.close()

        # Mark as complete
        validation_jobs[job_id]['status'] = 'completed'
        validation_jobs[job_id]['output_file'] = output_filename

    except Exception as e:
        validation_jobs[job_id]['status'] = 'error'
        validation_jobs[job_id]['error'] = str(e)

@app.route('/validate', methods=['POST'])
def validate():
    """Start VAT validation in background and return job ID"""
    data = request.json
    filename = secure_filename(data.get('filename'))
    sheet_name = data.get('sheet')
    vat_column = data.get('vatColumn')

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Initialize job
    validation_jobs[job_id] = {
        'status': 'processing',
        'progress': 0,
        'processed': 0,
        'total': 0,
        'results': [],
        'output_file': None,
        'error': None
    }

    # Start background thread
    thread = threading.Thread(
        target=process_validation_job,
        args=(job_id, filename, sheet_name, vat_column)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'job_id': job_id
    })

@app.route('/validate-progress/<job_id>')
def validate_progress(job_id):
    """Server-Sent Events endpoint for validation progress"""
    def generate():
        if job_id not in validation_jobs:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        while True:
            job = validation_jobs[job_id]

            # Send progress update
            yield f"data: {json.dumps(job)}\n\n"

            # Stop if completed or errored
            if job['status'] in ['completed', 'error']:
                break

            time.sleep(0.5)  # Update every 500ms

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/download/<filename>')
def download(filename):
    """Download the validated file"""
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(filepath, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
