# PDFlex
PDFlex je webová aplikácia na prácu s PDF súbormi – umožňuje ich ochranu heslom, konverziu do DOCX a OCR rozpoznávanie textu.
Projekt je postavený na FastAPI (Python) s využitím SQLAlchemy, PostgreSQL, a obsahuje aj základnú fakturačnú logiku s podporou charity.

 Funkcionality

	Ochrana PDF heslom (AES 128-bit)
	Konverzia PDF → DOCX (s pdf2docx)
	OCR rozpoznávanie textu (s Tesseract)
	Transakčný systém – každý úkon sa zapisuje do DB
	Charita – možnosť venovať časť ceny charity podľa plánu

 Použité technológie

		FastAPI – backend framework
		SQLAlchemy – ORM vrstva
		PostgreSQL – databáza
		pdfplumber, pdf2docx, PyPDF2 – PDF spracovanie
		pytesseract, pdf2image – OCR

  # 1. Naklonuj repo
git clone https://github.com/Dzan21/PDFlex.git
cd PDFlex/backend

# 2. Vytvor virtuálne prostredie
python3 -m venv .venv
source .venv/bin/activate

# 3. Nainštaluj závislosti
pip install -r requirements.txt

# 4. Spusti server
uvicorn app.main:app --reload --port 8001

docker-compose up --build
