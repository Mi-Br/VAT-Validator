# PVM (VAT) Number Validator / PVM Numerių Tikrinimas

A simple web application to validate EU VAT numbers from Excel files using the VIES API.

Paprasta žiniatinklio programa PVM numeriams iš Excel failų tikrinti naudojant VIES API.

## Features / Funkcijos

- 📁 Upload Excel files (.xlsx, .xls) / Įkelkite Excel failus
- 🔍 Auto-detect VAT number columns / Automatiškai aptinka PVM stulpelius
- ✅ Validate VAT numbers using official VIES API / Tikrina PVM numerius naudojant oficialią VIES API
- 🎨 Color-coded results (green = valid, red = invalid) / Spalvomis pažymėti rezultatai
- 📥 Download validated Excel file with color-coded cells / Atsisiųskite patikrintą Excel failą
- 🇱🇹 Lithuanian language UI / Lietuviška sąsaja

## Quick Deploy to Render / Greitas Diegimas į Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Manual Render Deployment / Rankinis Diegimas

1. Fork or clone this repository / Nukopijuokite šią saugyklą
2. Create account at [render.com](https://render.com)
3. Click "New +" → "Web Service"
4. Connect your GitHub repository / Prijunkite GitHub saugyklą
5. Render will auto-detect settings from `render.yaml`
6. Click "Create Web Service"
7. Done! Your app will be live in ~2 minutes / Atlikta! Jūsų programa veiks per ~2 minutes

## Local Development / Vietinis Paleidimas

1. Install dependencies / Įdiekite priklausomybes:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run the application / Paleiskite programą:
```bash
python app.py
```

3. Open your browser to / Atidarykite naršyklėje: `http://localhost:8080`

## How to Use / Kaip Naudotis

1. **Upload** your Excel file with VAT numbers / **Įkelkite** Excel failą su PVM numeriais
2. **Select** the sheet and column containing VAT numbers / **Pasirinkite** lapą ir stulpelį su PVM numeriais
3. Click **Validate** and wait for processing / Spauskite **Tikrinti** ir palaukite
4. **Download** the validated file with color-coded results / **Atsisiųskite** patikrintą failą su spalvomis pažymėtais rezultatais

## Excel File Format / Excel Failo Formatas

Your Excel file should have / Jūsų Excel failas turėtų turėti:
- A column with VAT numbers / Stulpelį su PVM numeriais
- VAT numbers **must start with 2-letter country code** / PVM numeriai **turi prasidėti 2 raidžių šalies kodu**

VAT number formats / PVM numerių formatai:
- ✅ `LT100013590314` (with country prefix / su šalies kodu)
- ✅ `DE811569869`
- ✅ `FR40303265045`
- ❌ `100013590314` (missing country code / trūksta šalies kodo)

### Supported Country Codes / Palaikomi Šalių Kodai

AT (Austria), BE (Belgium), BG (Bulgaria), CY (Cyprus), CZ (Czech Republic),
DE (Germany), DK (Denmark), EE (Estonia), EL (Greece), ES (Spain),
FI (Finland), FR (France), HR (Croatia), HU (Hungary), IE (Ireland),
IT (Italy), LT (Lithuania), LU (Luxembourg), LV (Latvia), MT (Malta),
NL (Netherlands), PL (Poland), PT (Portugal), RO (Romania), SE (Sweden),
SI (Slovenia), SK (Slovakia)

## API Information / API Informacija

This application uses the official European Commission VIES API:
- REST API: `https://ec.europa.eu/taxation_customs/vies/rest-api/`
- Rate limiting: 300ms delay between requests
- Free to use, no API key required

Ši programa naudoja oficialią Europos Komisijos VIES API.

## Technical Stack / Technologijos

- **Backend**: Python 3.11 + Flask
- **Excel Processing**: openpyxl
- **API**: VIES REST API
- **Deployment**: Render.com

## License / Licencija

MIT

## Support / Pagalba

For issues or questions, please open an issue on GitHub.

Klausimams ar problemoms, prašome sukurti GitHub issue.
