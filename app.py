from flask import Flask, render_template, request, jsonify, send_file
import openpyxl
from openpyxl.styles import PatternFill
import requests
import time
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
        data = response.json()

        return {
            'valid': data.get('isValid', False),
            'name': data.get('name', ''),
            'address': data.get('address', ''),
            'country': country_code,
            'error': None if data.get('userError') == 'VALID' else data.get('userError')
        }
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

@app.route('/validate', methods=['POST'])
def validate():
    """Validate VAT numbers in the specified column"""
    data = request.json
    filename = secure_filename(data.get('filename'))
    sheet_name = data.get('sheet')
    vat_column = data.get('vatColumn')
    country_column = data.get('countryColumn')

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        wb = openpyxl.load_workbook(filepath)
        sheet = wb[sheet_name]

        # Find column indices
        vat_col_idx = None
        country_col_idx = None

        for idx, cell in enumerate(sheet[1], 1):
            if cell.value == vat_column:
                vat_col_idx = idx
            if cell.value == country_column:
                country_col_idx = idx

        if vat_col_idx is None:
            return jsonify({'error': f'Column "{vat_column}" not found'}), 400

        # Define colors
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
        red_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
        yellow_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")

        results = []

        # Process each row (skip header)
        for row_idx in range(2, sheet.max_row + 1):
            vat_cell = sheet.cell(row_idx, vat_col_idx)
            vat_value = vat_cell.value

            # Skip empty cells
            if not vat_value:
                continue

            # Validate VAT (country code is extracted from VAT number itself)
            result = validate_vat(vat_value)

            # Color code the cell
            if result['valid']:
                vat_cell.fill = green_fill
            elif result.get('country'):
                vat_cell.fill = red_fill
            else:
                # No country code found - yellow
                vat_cell.fill = yellow_fill

            results.append({
                'row': row_idx,
                'vat': str(vat_value),
                'country': result.get('country', ''),
                'valid': result['valid'],
                'name': result.get('name', ''),
                'error': result.get('error')
            })

            # Small delay to be nice to the API
            time.sleep(0.3)

        # Save the modified file
        output_filename = f'validated_{filename}'
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        wb.save(output_path)
        wb.close()

        return jsonify({
            'success': True,
            'results': results,
            'output_file': output_filename
        })

    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/download/<filename>')
def download(filename):
    """Download the validated file"""
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(filepath, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
