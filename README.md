# VAT Number Validator

A simple web application to validate EU VAT numbers from Excel files using the VIES API.

## Features

- 📁 Upload Excel files (.xlsx, .xls)
- 🔍 Auto-detect VAT number columns
- ✅ Validate VAT numbers using official VIES API
- 🎨 Color-coded results (green = valid, red = invalid)
- 📥 Download validated Excel file with color-coded cells

## Quick Start

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser to: `http://localhost:5000`

## Deployment Options

### Option 1: Render.com (Recommended - Free)

1. Create account at [render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repo or upload code
4. Settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - Add `gunicorn==21.2.0` to requirements.txt

### Option 2: Railway.app (Free)

1. Create account at [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway auto-detects Flask and deploys

### Option 3: Fly.io

1. Install Fly CLI: `brew install flyctl`
2. Login: `fly auth login`
3. Deploy: `fly launch`

## Usage

1. **Upload** your Excel file with VAT numbers
2. **Select** the sheet and column containing VAT numbers
3. **Optionally** select a column with country codes (or auto-detect)
4. Click **Validate** and wait for processing
5. **Download** the validated file with color-coded results

## Excel File Format

Your Excel file should have:
- A column with VAT numbers (e.g., "VAT Number", "VAT ID")
- Optionally, a column with country codes (e.g., "Country")

VAT numbers can be in formats:
- `LT100013590314` (with country prefix)
- `100013590314` (without prefix, if country column provided)

## API Rate Limiting

The app includes a 300ms delay between validation requests to be respectful to the VIES API.

## License

MIT
