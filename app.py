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

# In-memory storage for validation jobs with thread safety
validation_jobs = {}
validation_jobs_lock = threading.Lock()

def update_job(job_id, **kwargs):
    """Thread-safe helper to update job status"""
    with validation_jobs_lock:
        if job_id in validation_jobs:
            validation_jobs[job_id].update(kwargs)
        else:
            print(f"[WARNING] Tried to update non-existent job {job_id}")

def parse_vat_number(vat_input):
    """
    Parse VAT number and extract country code and number.
    Returns (country_code, vat_number) tuple.
    """
    # Valid EU country codes for VAT validation
    VALID_EU_CODES = {
        'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES',
        'FI', 'FR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
        'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK', 'XI'
    }

    vat_str = str(vat_input).strip().replace(' ', '').replace('-', '').replace('.', '')

    # Check if VAT starts with valid 2-letter EU country code
    if len(vat_str) >= 2 and vat_str[:2].isalpha():
        country_code = vat_str[:2].upper()
        # Only extract if it's a valid EU country code
        if country_code in VALID_EU_CODES:
            vat_number = vat_str[2:]
            return country_code, vat_number

    # No valid country code in VAT number
    return None, vat_str

def validate_vat(vat_input, retry_count=0, job_id=None, current_idx=0):
    """
    Validate VAT number using VIES API.
    Automatically extracts country code from VAT number.
    Includes retry logic for rate limiting and timeouts.
    Updates job status to show retry attempts in UI.
    """
    country_code, vat_number = parse_vat_number(vat_input)

    if not country_code:
        return {'valid': False, 'error': 'Nerasta šalies kodo / Country code not found', 'country': None}

    if not vat_number:
        return {'valid': False, 'error': 'Tuščias PVM numeris / Empty VAT number', 'country': country_code}

    try:
        url = f'https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country_code}/vat/{vat_number}'
        response = requests.get(url, timeout=30)

        # Check if response is valid JSON
        if not response.text or response.text.strip() == '':
            return {'valid': False, 'error': 'Empty response from VIES API', 'country': country_code}

        data = response.json()

        # Handle MS_MAX_CONCURRENT_REQ error with retry
        if data.get('userError') == 'MS_MAX_CONCURRENT_REQ':
            # Retry more aggressively for rate limiting (up to 5 retries)
            if retry_count < 5:
                # Update UI to show retry status
                if job_id and current_idx > 0:
                    update_job(job_id, retrying=current_idx)

                # Exponential backoff: 2s, 4s, 6s, 8s, 10s
                time.sleep(2 * (retry_count + 1))
                return validate_vat(vat_input, retry_count + 1, job_id, current_idx)
            else:
                # After 5 retries, still mark as retriable (not invalid)
                return {'valid': False, 'error': 'Pabandysiu vėliau (per daug užklausų)', 'country': country_code, 'retriable': True}

        return {
            'valid': data.get('isValid', False),
            'name': data.get('name', ''),
            'address': data.get('address', ''),
            'country': country_code,
            'error': None if data.get('userError') == 'VALID' else data.get('userError')
        }
    except requests.exceptions.JSONDecodeError as e:
        return {'valid': False, 'error': f'Invalid API response: {str(e)}', 'country': country_code}
    except requests.exceptions.SSLError as e:
        # Retry on SSL errors (including SSL EOF errors)
        # Must be before ConnectionError since SSLError inherits from it
        if retry_count < 3:
            if job_id and current_idx > 0:
                update_job(job_id, retrying=current_idx)
            time.sleep(2 * (retry_count + 1))  # Longer delay for SSL issues
            return validate_vat(vat_input, retry_count + 1, job_id, current_idx)
        return {'valid': False, 'error': 'SSL connection error (VIES API SSL issue)', 'country': country_code}
    except requests.exceptions.Timeout:
        # Retry on timeout
        if retry_count < 2:
            if job_id and current_idx > 0:
                update_job(job_id, retrying=current_idx)
            time.sleep(1 * (retry_count + 1))
            return validate_vat(vat_input, retry_count + 1, job_id, current_idx)
        return {'valid': False, 'error': 'API timeout (server not responding)', 'country': country_code}
    except requests.exceptions.ConnectionError as e:
        # Retry on connection reset/refused errors (catches ConnectionResetError wrapped by requests)
        if retry_count < 3:
            if job_id and current_idx > 0:
                update_job(job_id, retrying=current_idx)
            time.sleep(2 * (retry_count + 1))  # Longer delay for connection issues
            return validate_vat(vat_input, retry_count + 1, job_id, current_idx)
        return {'valid': False, 'error': 'Connection error (VIES API connection lost)', 'country': country_code}
    except Exception as e:
        # Log unexpected errors with full details
        error_msg = f'Unexpected error: {type(e).__name__}: {str(e)}'
        return {'valid': False, 'error': error_msg, 'country': country_code}

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
    print(f"[WORKER] Starting job {job_id}")
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
            update_job(job_id, status='error', error=f'Column "{vat_column}" not found')
            print(f"[WORKER] Job {job_id} error: column not found")
            return

        # Define colors
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
        red_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
        yellow_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")

        # Count total VAT numbers to process FIRST
        vat_rows = []
        for row_idx in range(2, sheet.max_row + 1):
            vat_value = sheet.cell(row_idx, vat_col_idx).value
            if vat_value and str(vat_value).strip():
                vat_rows.append((row_idx, vat_value))

        total = len(vat_rows)

        # Update total immediately so frontend can display it
        update_job(job_id, total=total, status='processing')
        print(f"[WORKER] Job {job_id} found {total} VAT numbers")

        if total == 0:
            update_job(job_id, status='error', error='No VAT numbers found in selected column')
            return

        # Process each VAT number sequentially
        for idx, (row_idx, vat_value) in enumerate(vat_rows, 1):
            vat_cell = sheet.cell(row_idx, vat_col_idx)

            # Update progress before validation
            progress_pct = int((idx / total) * 100)
            update_job(job_id, processed=idx, progress=progress_pct)

            # Clear retry flag before validation
            update_job(job_id, retrying=None)

            # Validate VAT with retry logic (pass job_id and idx for retry tracking)
            result = validate_vat(vat_value, job_id=job_id, current_idx=idx)

            # Clear retry flag after validation completes
            update_job(job_id, retrying=None)

            # Color code the cell
            if result['valid']:
                vat_cell.fill = green_fill
            elif result.get('country'):
                vat_cell.fill = red_fill
            else:
                vat_cell.fill = yellow_fill

            # Parse the VAT to get clean country code and number
            parsed_country, parsed_number = parse_vat_number(vat_value)

            # Add to results (need to append to list safely)
            result_item = {
                'row': row_idx,
                'vat': parsed_number if parsed_country else str(vat_value),
                'country': result.get('country', ''),
                'valid': result['valid'],
                'name': result.get('name', ''),
                'error': result.get('error')
            }

            with validation_jobs_lock:
                if job_id in validation_jobs:
                    validation_jobs[job_id]['results'].append(result_item)

            # Delay between requests to avoid rate limiting
            # Based on research: VIES has undocumented concurrent limits
            # 1 second delay balances speed vs. reliability
            time.sleep(1.0)

        # Save the modified file
        output_filename = f'validated_{filename}'
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        wb.save(output_path)
        wb.close()

        # Mark as complete
        update_job(job_id, status='completed', output_file=output_filename, progress=100)
        print(f"[WORKER] Job {job_id} completed successfully")

    except Exception as e:
        update_job(job_id, status='error', error=str(e))
        print(f"[WORKER] Job {job_id} error: {str(e)}")

@app.route('/validate', methods=['POST'])
def validate():
    """Start VAT validation in background and return job ID"""
    data = request.json
    filename = secure_filename(data.get('filename'))
    sheet_name = data.get('sheet')
    vat_column = data.get('vatColumn')

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Initialize job with thread safety
    with validation_jobs_lock:
        validation_jobs[job_id] = {
            'status': 'initializing',
            'progress': 0,
            'processed': 0,
            'total': 0,
            'results': [],
            'retrying': None,  # Track which VAT is being retried
            'output_file': None,
            'error': None,
            'created_at': time.time()
        }
        print(f"[VALIDATE] Created job {job_id}, total jobs: {len(validation_jobs)}")

    # Start background thread
    thread = threading.Thread(
        target=process_validation_job,
        args=(job_id, filename, sheet_name, vat_column)
    )
    thread.daemon = True
    thread.start()

    # Longer delay to ensure thread has started
    time.sleep(0.2)

    return jsonify({
        'success': True,
        'job_id': job_id
    })

@app.route('/validate-progress/<job_id>')
def validate_progress(job_id):
    """Server-Sent Events endpoint for validation progress"""
    def generate():
        print(f"[PROGRESS] Client connected for job {job_id}")

        # Wait a bit for job to be created if not found immediately
        max_wait = 10  # Increased from 5 to 10 seconds
        waited = 0
        job_found = False

        while waited < max_wait:
            with validation_jobs_lock:
                if job_id in validation_jobs:
                    job_found = True
                    print(f"[PROGRESS] Job {job_id} found after {waited}s")
                    break
                else:
                    print(f"[PROGRESS] Job {job_id} not found, waiting... (total jobs: {len(validation_jobs)})")

            time.sleep(0.2)
            waited += 0.2

        if not job_found:
            print(f"[PROGRESS] Job {job_id} NOT FOUND after {max_wait}s")
            yield f"data: {json.dumps({'status': 'error', 'error': 'Job not found. Please try again.'})}\n\n"
            return

        last_sent_count = 0

        while True:
            with validation_jobs_lock:
                if job_id not in validation_jobs:
                    print(f"[PROGRESS] Job {job_id} disappeared!")
                    yield f"data: {json.dumps({'status': 'error', 'error': 'Job was removed'})}\n\n"
                    return

                job = validation_jobs[job_id].copy()  # Copy to avoid holding lock

            # Send progress update with all results
            update = {
                'status': job['status'],
                'progress': job['progress'],
                'processed': job['processed'],
                'total': job['total'],
                'results': job['results'],
                'retrying': job.get('retrying'),  # Send retry status
                'output_file': job.get('output_file'),
                'error': job.get('error')
            }
            yield f"data: {json.dumps(update)}\n\n"

            last_sent_count = len(job['results'])

            # Stop if completed or errored
            if job['status'] in ['completed', 'error']:
                print(f"[PROGRESS] Job {job_id} finished with status: {job['status']}")
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
    print("=" * 60)
    print("Starting VAT Validator Server")
    print("=" * 60)
    print(f"Server: http://0.0.0.0:8080")
    print("Note: Debug mode is ON - auto-reload enabled")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=8080, threaded=True, use_reloader=True)
