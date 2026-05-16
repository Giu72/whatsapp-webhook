import schedule
import time
import requests as req
from pyairtable import Api

# ─── CONFIGURAZIONE ───────────────────────────────────────────────────────────
AIRTABLE_TOKEN = "pat5R6Hzz11DFLqkx.37639cb89ca2562dbeca7f837f576c2e916e135eb94712f9ca4d4bc1d7b826f3"
BASE_ID = "app9mXSzgqGOhYtpd"
TABLE_NAME = "Clienti"

META_TOKEN = "EAAV1b680TDABRSbHqdRqjizLcxImyatIj3gTZAZCaeGqYgcQdyVComHrZBQf7kEmZCNWin2DqUxifNhqLemkJvc7Wqw0BxjFeYDZB2FSLQviLFHhcjWMzuGlZBZCnUvpxvDaFRyA2SULWIc94e5ZBzSlxMJ0Rp95krUFPg7G5kBWUtpFhVJ6YvDj92DzxUbJvpWpjj1cgro3WeqAvuA227D0ZCtcUuF39um9sZBFHpqrsr"
PHONE_NUMBER_ID = "1156459807541320"

# ─── AIRTABLE ─────────────────────────────────────────────────────────────────
api = Api(AIRTABLE_TOKEN)
table = api.table(BASE_ID, TABLE_NAME)


def invia_messaggio_meta(numero, testo):
    """Invia messaggio WhatsApp tramite Meta Cloud API"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": testo}
    }
    risposta = req.post(url, json=payload, headers=headers)
    print(f"Reminder inviato a {numero}: {risposta.status_code}")
    return risposta.status_code == 200


def manda_reminder():
    """Controlla Airtable e manda reminder a chi ha documenti mancanti"""
    print("Avvio reminder serale...")

    try:
        # Prendi tutti i clienti con stato Incompleto o In Attesa
        clienti = table.all(formula="OR({Stato}='Incompleto', {Stato}='In Attesa')")

        if not clienti:
            print("Nessun cliente con documenti mancanti. Nessun reminder inviato.")
            return

        contatore = 0
        for cliente in clienti:
            fields = cliente["fields"]
            telefono = fields.get("Telefono", "")
            mancanti = fields.get("Documenti mancanti", "")
            nome = fields.get("Nome", "")
            consenso = fields.get("Consenso", "")

            # Salta se non ha telefono, non ha documenti mancanti o non ha accettato privacy
            if not telefono or not mancanti or consenso != "Accettato":
                continue

            # Costruisci il messaggio
            lista = mancanti.split(",")
            opzioni = "\n".join([f"- {d.strip()}" for d in lista if d.strip()])

            if nome:
                saluto = f"Buonasera {nome}!"
            else:
                saluto = "Buonasera!"

            messaggio = (
                f"{saluto} 👋\n\n"
                f"Ricordiamo che per completare la tua pratica mancano ancora:\n"
                f"{opzioni}\n\n"
                f"Mandali appena puoi! 📎\n\n"
                f"Per qualsiasi info contatta il tuo mediatore."
            )

            # Manda il reminder
            successo = invia_messaggio_meta(telefono, messaggio)
            if successo:
                contatore += 1

        print(f"Reminder completati: {contatore} messaggi inviati.")

    except Exception as e:
        print(f"Errore durante i reminder: {e}")


# ─── SCHEDULER ────────────────────────────────────────────────────────────────
# Pianifica il reminder ogni sera alle 21:00
schedule.every().day.at("21:00").do(manda_reminder)

print("Scheduler reminder avviato. In attesa delle 21:00...")

# Loop principale
while True:
    schedule.run_pending()
    time.sleep(60)  # Controlla ogni minuto