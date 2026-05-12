import os
import threading
from flask import Flask, request, jsonify
from pyairtable import Api
import requests as req
import time
from difflib import SequenceMatcher
import base64

app = Flask(__name__)

# ─── CONFIGURAZIONE (da variabili d'ambiente Render) ─────────────────────────
AIRTABLE_TOKEN   = os.environ.get("AIRTABLE_TOKEN")
BASE_ID          = os.environ.get("AIRTABLE_BASE_ID")
TABLE_NAME       = "Clienti"

VERIFY_TOKEN     = os.environ.get("VERIFY_TOKEN", "praticaok2024")

META_TOKEN       = os.environ.get("META_TOKEN")
PHONE_NUMBER_ID  = os.environ.get("PHONE_NUMBER_ID")


# ─── TESTO INFORMATIVA PRIVACY ────────────────────────────────────────────────
INFORMATIVA_PRIVACY = """👋 Benvenuto nel sistema di raccolta documenti *PraticaOk*.

📋 *INFORMATIVA SULLA PRIVACY*
Ai sensi del GDPR (Reg. UE 2016/679), ti informiamo che:

• I tuoi dati e documenti saranno trattati esclusivamente per la gestione della tua pratica finanziaria
• I documenti saranno condivisi solo con il mediatore creditizio incaricato
• I dati saranno conservati in modo sicuro e cancellati al termine della pratica
• Hai diritto di accedere, modificare o cancellare i tuoi dati in qualsiasi momento

Per esercitare i tuoi diritti: praticaok@gmail.com

✅ Per procedere, rispondi *ACCETTO*
❌ Per rifiutare, rispondi *RIFIUTO*"""

# ─── SINONIMI ─────────────────────────────────────────────────────────────────
SINONIMI = {
    "CU": ["cu", "certificazione unica", "busta paga", "redditi", "lavoro"],
    "F24": ["f24", "modello f24", "pagamento", "tributi"],
    "Documento identità": ["documento identità", "carta identità", "carta d'identità", "patente", "passaporto", "identità"],
    "Codice fiscale": ["codice fiscale", "codici fiscale", "cf", "tessera sanitaria", "codfiscale", "cod fiscale"],
    "Buste paga ultime 3": ["busta paga", "buste paga", "cedolino", "stipendio", "buste paghe"],
    "CUD": ["cud", "modello cud"],
    "Estratto conto 6 mesi": ["estratto conto", "conto corrente", "movimenti", "estrato conto"],
    "Estratto Conto": ["estratto conto", "estrato conto", "estratto"],
    "Certificato di Stipendio": ["certificato di stipendio", "certificato stipendio", "cert stipendio", "certificato salario"],
    "Lista movimenti": ["lista movimenti", "lista dei movimenti", "movimenti bancari", "movimenti conto"],
    "Conteggio estintivo": ["conteggio estintivo", "conteggio estinzione", "estintivo"],
    "Piano di Ammortamento": ["piano di ammortamento", "piano ammortamento", "ammortamento", "piano rate"],
    "Conteggio Residuo": ["conteggio residuo", "residuo", "debito residuo", "saldo residuo"],
    "Visura": ["visura", "visura catastale", "visura camerale", "catastale"],
    "Scia": ["scia", "segnalazione certificata", "scia edilizia"],
    "Debito residuo": ["debito residuo", "residuo debito", "saldo debitore", "debito rimanente"],
    "Liberatoria": ["liberatoria", "liberatorio", "svincolo", "liberazione ipoteca"],
    "Compromesso": ["compromesso", "preliminare", "proposta acquisto", "compromeso"]
}

PAROLE_INTENZIONE = ["mando", "invio", "allego", "mandare", "inviare", "mutuo",
                     "prestito", "pratica", "documentazione", "buongiorno",
                     "buon", "salve", "ciao", "iniziare", "iniziamo", "ho bisogno"]

# ─── AIRTABLE ─────────────────────────────────────────────────────────────────
api_at       = Api(AIRTABLE_TOKEN)
table        = api_at.table(BASE_ID, TABLE_NAME)
table_pratiche = api_at.table(BASE_ID, "Pratiche")


# ─── FUNZIONI HELPER ──────────────────────────────────────────────────────────
def somiglianza(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def trova_documento_nel_testo(testo, lista_mancanti):
    msg = testo.lower().strip()
    for doc in lista_mancanti:
        sinonimi_doc = SINONIMI.get(doc, [doc.lower()])
        for sinonimo in sinonimi_doc:
            if sinonimo.lower() in msg:
                return doc
            if somiglianza(sinonimo, msg) > 0.75:
                return doc
            parole_sinonimo = sinonimo.lower().split()
            parole_msg = msg.split()
            if all(any(somiglianza(p, pm) > 0.8 for pm in parole_msg) for p in parole_sinonimo):
                return doc
    return None


def get_documenti_per_pratica(tipo_pratica):
    risultati = table_pratiche.all(formula=f"{{Tipo pratica}}='{tipo_pratica}'")
    if risultati:
        return risultati[0]["fields"].get("Documenti richiesti", "")
    return ""


def trova_o_crea_cliente(telefono):
    risultati = table.all(formula=f"{{Telefono}}='{telefono}'")
    if risultati:
        return risultati[0]
    nuovo = table.create({
        "Telefono": telefono,
        "Stato": "In Attesa",
        "Consenso": "In attesa",
        "Documenti mancanti": ""
    })
    return nuovo


def invia_messaggio_meta(numero, testo):
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
    print(f"Meta API risposta: {risposta.status_code} — {risposta.text[:200]}")
    return risposta.status_code == 200


def scarica_file_meta(media_id):
    try:
        url_info = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {META_TOKEN}"}
        info = req.get(url_info, headers=headers).json()
        url_file = info.get("url")
        content_type = info.get("mime_type", "application/octet-stream")
        if not url_file:
            return None, None, None
        file_content = req.get(url_file, headers=headers).content
        if "pdf" in content_type:
            estensione = ".pdf"
        elif "jpeg" in content_type or "jpg" in content_type:
            estensione = ".jpg"
        elif "png" in content_type:
            estensione = ".png"
        else:
            estensione = ".bin"
        nome_file = f"doc_{int(time.time())}{estensione}"
        return file_content, nome_file, content_type
    except Exception as e:
        print(f"Errore download Meta: {e}")
        return None, None, None


def aggiungi_allegato_airtable(cliente_id, file_content, nome_file, content_type):
    try:
        upload_url = f"https://content.airtable.com/v0/{BASE_ID}/{cliente_id}/Link%20documenti/uploadAttachment"
        headers = {
            "Authorization": f"Bearer {AIRTABLE_TOKEN}",
            "Content-Type": "application/json"
        }
        file_b64 = base64.b64encode(file_content).decode("utf-8")
        payload = {
            "filename": nome_file,
            "contentType": content_type,
            "file": file_b64
        }
        risposta = req.post(upload_url, json=payload, headers=headers)
        print(f"Upload Airtable: {risposta.status_code}")
        return risposta.status_code == 200
    except Exception as e:
        print(f"Errore upload Airtable: {e}")
        return False


def aggiorna_documenti(cliente_id, doc_trovato, fields):
    mancanti = fields.get("Documenti mancanti", "")
    ricevuti = fields.get("Documenti ricevuti", "")
    lista_mancanti = [d.strip() for d in mancanti.split(",") if d.strip()]
    lista_ricevuti  = [d.strip() for d in ricevuti.split(",")  if d.strip()]
    if doc_trovato in lista_mancanti:
        lista_mancanti.remove(doc_trovato)
        lista_ricevuti.append(doc_trovato)
    nuovi_mancanti = ", ".join(lista_mancanti)
    nuovi_ricevuti  = ", ".join(lista_ricevuti)
    stato = "Completo" if not lista_mancanti else "Incompleto"
    table.update(cliente_id, {
        "Documenti mancanti": nuovi_mancanti,
        "Documenti ricevuti": nuovi_ricevuti,
        "Stato": stato
    })
    return lista_mancanti, stato


def classifica_messaggio(messaggio, ha_file, lista_mancanti):
    msg = messaggio.lower().strip() if messaggio else ""
    if ha_file:
        if messaggio and messaggio.strip():
            doc = trova_documento_nel_testo(messaggio, lista_mancanti)
            if doc:
                return "documento_con_nome", doc
        return "documento", None
    if not messaggio:
        return "testo", None
    doc = trova_documento_nel_testo(messaggio, lista_mancanti)
    if doc:
        return "nome_documento", doc
    for parola in PAROLE_INTENZIONE:
        if parola.lower() in msg:
            return "intenzione", None
    return "testo", None


# ─── ELABORAZIONE IN BACKGROUND ───────────────────────────────────────────────
# Meta Cloud API richiede risposta entro 20 secondi.
# Tutta la logica viene eseguita in un thread separato,
# così il webhook risponde subito 200 e Meta non fa retry.

def elabora_messaggio(data):
    try:
        entry   = data["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]

        if "statuses" in value:
            return

        messages = value.get("messages", [])
        if not messages:
            return

        message  = messages[0]
        mittente = message["from"]
        tipo_msg = message["type"]

        print(f"Da {mittente} | Tipo: {tipo_msg}")

        messaggio = ""
        media_id  = None
        ha_file   = False

        if tipo_msg == "text":
            messaggio = message["text"]["body"]
        elif tipo_msg in ["image", "document", "audio", "video"]:
            ha_file   = True
            media_data = message.get(tipo_msg, {})
            media_id   = media_data.get("id")
            messaggio  = media_data.get("caption", "")
        elif tipo_msg == "interactive":
            messaggio = message.get("interactive", {}).get("button_reply", {}).get("title", "")

        # Carica cliente (rilegge sempre dati freschi da Airtable)
        cliente    = trova_o_crea_cliente(mittente)
        cliente_id = cliente["id"]
        fields     = cliente["fields"]
        consenso   = fields.get("Consenso", "In attesa")

        # ─── GESTIONE CONSENSO PRIVACY ────────────────────────────────────────
        msg_lower = messaggio.lower().strip() if messaggio else ""

        # Cliente risponde ACCETTO
        if msg_lower in ["accetto", "accetta", "si", "sì", "ok", "acconsento"]:
            if consenso != "Accettato":
                table.update(cliente_id, {"Consenso": "Accettato"})
                invia_messaggio_meta(mittente,
                    "✅ Consenso registrato! Grazie.\n\n"
                    "Ora puoi iniziare a mandare i tuoi documenti.\n"
                    "Scrivi 'Ciao' per vedere la lista di cosa serve. 👍")
            return  # ← IMPORTANTE: esce sempre, evita di mandare anche l'informativa

        # Cliente risponde RIFIUTO
        if msg_lower in ["rifiuto", "rifiuta", "no", "non accetto"]:
            table.update(cliente_id, {"Consenso": "Rifiutato"})
            invia_messaggio_meta(mittente,
                "❌ Hai rifiutato il trattamento dei dati.\n\n"
                "Non potremo procedere con la raccolta documenti.\n"
                "Per maggiori informazioni contatta il tuo mediatore.")
            return

        # Cliente NON ha ancora accettato → manda informativa
        if consenso != "Accettato":
            invia_messaggio_meta(mittente, INFORMATIVA_PRIVACY)
            return

        # ─── DA QUI IN POI SOLO CLIENTI CHE HANNO ACCETTATO ──────────────────
        mancanti       = fields.get("Documenti mancanti", "")
        stato_cliente  = fields.get("Stato", "In Attesa")
        tipo_pratica   = fields.get("Tipo pratica", "")

        lista_mancanti = [d.strip() for d in mancanti.split(",") if d.strip()]
        tipo, doc_trovato = classifica_messaggio(messaggio, ha_file, lista_mancanti)

        print(f"Tipo: {tipo} | Doc: {doc_trovato} | Stato: {stato_cliente} | Pratica: {tipo_pratica}")

        # Gestisci file — scarica da Meta e carica direttamente su Airtable
        if ha_file and media_id:
            file_content, nome_file, content_type = scarica_file_meta(media_id)
            if file_content:
                aggiungi_allegato_airtable(cliente_id, file_content, nome_file, content_type)

        # Rispondi
        if tipo == "documento_con_nome":
            lista_rimanenti, stato = aggiorna_documenti(cliente_id, doc_trovato, fields)
            if stato == "Completo":
                invia_messaggio_meta(mittente, f"✅ {doc_trovato} ricevuto!\n\nPratica COMPLETA! Ti contatteremo a breve.")
            else:
                invia_messaggio_meta(mittente, f"✅ {doc_trovato} ricevuto!\n\nMancano ancora:\n{', '.join(lista_rimanenti)}")

        elif tipo == "documento":
            if lista_mancanti:
                opzioni = "\n".join([f"- {d}" for d in lista_mancanti])
                invia_messaggio_meta(mittente, f"📎 Documento ricevuto!\n\nDi che documento si tratta?\n{opzioni}")
            else:
                invia_messaggio_meta(mittente, "📎 Documento ricevuto! Di che documento si tratta?")

        elif tipo == "nome_documento":
            if not lista_mancanti:
                invia_messaggio_meta(mittente, "Non ho trovato documenti in attesa per la tua pratica.")
            else:
                lista_rimanenti, stato = aggiorna_documenti(cliente_id, doc_trovato, fields)
                if stato == "Completo":
                    invia_messaggio_meta(mittente, "✅ Pratica COMPLETA! Hai mandato tutto. Ti contatteremo a breve.")
                else:
                    invia_messaggio_meta(mittente, f"✅ {doc_trovato} registrato!\n\nMancano ancora:\n{', '.join(lista_rimanenti)}")

        elif tipo == "intenzione":
            if stato_cliente == "Completo":
                invia_messaggio_meta(mittente, "✅ La tua pratica è già completa! Ti contatteremo a breve.")
            elif tipo_pratica and not mancanti:
                documenti = get_documenti_per_pratica(tipo_pratica)
                if documenti:
                    table.update(cliente_id, {"Documenti mancanti": documenti})
                    lista = documenti.split(",")
                    opzioni = "\n".join([f"- {d.strip()}" for d in lista])
                    invia_messaggio_meta(mittente, f"Perfetto! 👍 Per la pratica {tipo_pratica} servono:\n{opzioni}\n\nManda i documenti quando vuoi!")
                else:
                    invia_messaggio_meta(mittente, "Ciao! Il broker non ha ancora configurato la tua pratica. Riprova tra poco.")
            elif mancanti:
                opzioni = "\n".join([f"- {d}" for d in lista_mancanti])
                invia_messaggio_meta(mittente, f"Ciao! 👋 Mancano ancora questi documenti:\n{opzioni}")
            else:
                invia_messaggio_meta(mittente, "Ciao! 👋 Il tuo broker deve prima aprire la pratica. Ti contatteremo a breve.")

        else:
            invia_messaggio_meta(mittente, "Ciao! 👋 Sono il sistema di raccolta documenti. Manda i tuoi documenti quando sei pronto!")

    except Exception as e:
        print(f"Errore elaborazione: {e}")


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verificato!")
        return challenge, 200
    return "Token non valido", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"Ricevuto: {data}")

    # Risponde subito 200 a Meta, poi elabora in background
    t = threading.Thread(target=elabora_messaggio, args=(data,))
    t.daemon = True
    t.start()

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health_check():
    return "PraticaOk attivo ✅", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host="0.0.0.0", port=port)
