
import sqlite3
from flask import Flask, render_template, request, jsonify
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__)
DATABASE = 'leads.db'

def init_db():
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                budget REAL NOT NULL,
                package TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        db.close()

# Helper function to create a PDF report
def create_pdf_report(email, budget, commission, roi, package, goal):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('Arial', '', 'font/Arial.ttf', uni=True)
    pdf.add_font('Arial', 'B', 'font/arialbd.ttf', uni=True)
    pdf.add_font('Arial', 'I', 'font/ariali.ttf', uni=True)
    pdf.set_font("Arial", size=12)

    # --- NOWA ZMIANA: Używamy "bezpiecznej" szerokości 190 ---
    SAFE_WIDTH = 190

    pdf.cell(SAFE_WIDTH, 10, txt="Spersonalizowany Raport Marketingowy", ln=True, align='C')
    pdf.ln(10)

    pdf.cell(SAFE_WIDTH, 10, txt=f"Raport dla: {email}", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(SAFE_WIDTH, 10, txt="Podsumowanie Twojej Wyceny:", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(SAFE_WIDTH, 10, txt=f"- Wybrany budżet reklamowy: {budget} PLN", ln=True)
    pdf.cell(SAFE_WIDTH, 10, txt=f"- Prowizja agencji (15%): {commission:.2f} PLN", ln=True)
    pdf.cell(SAFE_WIDTH, 10, txt=f"- Szacowany zwrot z inwestycji (ROI): {roi:.2f} PLN", ln=True)
    pdf.cell(SAFE_WIDTH, 10, txt=f"- Rekomendowany pakiet usług: {package}", ln=True)
    pdf.ln(10)

    # Dynamic schedule based on the goal
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(SAFE_WIDTH, 10, txt="Wstępny Harmonogram Działań (Pierwsze 3 miesiące):", ln=True)
    pdf.set_font("Arial", size=12)
    if goal == 'more_calls':
        schedule = [
            "Miesiąc 1: Audyt SEO, optymalizacja on-page, start kampanii Google Ads (Search).",
            "Miesiąc 2: Link building, rozszerzenie kampanii Google Ads o nowe słowa kluczowe.",
            "Miesiąc 3: Analiza i optymalizacja konwersji, raportowanie wyników."
        ]
    elif goal == 'more_sales':
        schedule = [
            "Miesiąc 1: Konfiguracja e-commerce, start kampanii Google Shopping i social media Ads (remarketing).",
            "Miesiąc 2: Optymalizacja kampanii produktowych, testy A/B kreacji reklamowych.",
            "Miesiąc 3: Skalowanie budżetu na najskuteczniejszych kanałach, analiza lejka sprzedażowego."
        ]
    else: # new_brand
        schedule = [
            "Miesiąc 1: Stworzenie strategii komunikacji, start profili w social mediach, content plan.",
            "Miesiąc 2: Regularne publikacje, budowanie zaangażowania, płatne kampanie na zasięg.",
            "Miesiąc 3: Współpraca z influencerami, analiza wizerunku marki, raportowanie."
        ]
    for item in schedule:
        pdf.multi_cell(SAFE_WIDTH, 10, txt=f"- {item}")
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(SAFE_WIDTH, 10, txt="Co Dalej?", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(SAFE_WIDTH, 10, txt="Nasz specjalista skontaktuje się z Tobą w ciągu 24 godzin, aby omówić szczegóły i odpowiedzieć na wszystkie pytania. Przygotuj się na start!")
    pdf.ln(5)
    
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(SAFE_WIDTH, 10, txt="*Powyższe dane są szacunkowe i mogą się różnić w zależności od branży i konkurencji.", ln=True, align='C')

    filename = f"report_{email.replace('@', '_').replace('.', '_')}.pdf"
    pdf.output(filename)
    return filename

# Helper function to send email with attachment
def send_email_with_attachment(to_email, subject, body, filename):
    from_email = "raport@twojaagencja.pl"

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    with open(filename, "rb") as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())

    encoders.encode_base64(part)
    part.add_header(
        'Content-Disposition',
        f"attachment; filename= {filename}",
    )
    msg.attach(part)

    try:
        # Using a local SMTP debugging server on localhost:1025
        server = smtplib.SMTP('localhost', 1025)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        return "Email wysłany pomyślnie!"
    except Exception as e:
        return f"Błąd wysyłania emaila: {e}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate_budget', methods=['POST'])
def calculate_budget():
    budget = float(request.json['budget'])
    commission = budget * 0.15
    roi = budget * 2.5
    return jsonify({
        'commission': commission,
        'roi': roi
    })

@app.route('/select_goal', methods=['POST'])
def select_goal():
    goal = request.json['goal']
    if goal == 'more_calls':
        package = 'SEO + Google Ads'
    elif goal == 'more_sales':
        package = 'Google Ads + Social Media Marketing'
    elif goal == 'new_brand':
        package = 'Social Media Marketing + Content Marketing'
    else:
        package = 'Nie wybrano pakietu'
    return jsonify({
        'package': package
    })

@app.route('/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    email = data['email']
    budget = float(data['budget'])
    goal = data['goal']

    commission = budget * 0.15
    roi = budget * 2.5

    if goal == 'more_calls':
        package = 'SEO + Google Ads'
    elif goal == 'more_sales':
        package = 'Google Ads + Social Media Marketing'
    elif goal == 'new_brand':
        package = 'Social Media Marketing + Content Marketing'
    else:
        package = 'Nie wybrano pakietu'

    try:
        filename = create_pdf_report(email, budget, commission, roi, package, goal)
        
        # Save lead to the database
        db = sqlite3.connect(DATABASE)
        cursor = db.cursor()
        cursor.execute("INSERT OR IGNORE INTO leads (email, budget, package) VALUES (?, ?, ?)", (email, budget, package))
        db.commit()
        db.close()
        
        # Send email with PDF report
        email_subject = "Twoja spersonalizowana wycena - gotowa do pobrania!"
        email_body = f'''Dzień dobry,\n\nDziękujemy za skorzystanie z naszego kalkulatora.\n\nW załączniku przesyłamy spersonalizowany raport z wyceną i wstępnym harmonogramem działań dla Twojej firmy.\n\nNasz specjalista skontaktuje się z Tobą w ciągu 24 godzin, aby omówić szczegóły.\n\nPozdrawiamy,\nZespół Twojej Agencji\n'''
        email_status = send_email_with_attachment(email, email_subject, email_body, filename)


        message = f"Dziękujemy! Raport jest już w drodze na adres {email}. Spodziewaj się kontaktu od nas w ciągu 24h."
    except Exception as e:
        message = f"Wystąpił błąd: {e}"

    return jsonify({
        'message': message
    })

# Initialize the database when the app starts
init_db()

if __name__ == '__main__':
    app.run(debug=True)

         