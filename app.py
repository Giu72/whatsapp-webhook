import os
from flask import Flask, request, jsonify
from pyairtable import Api
import requests as req
import time
from difflib import SequenceMatcher
import base64

app = Flask(__name__)

# ─── CONFIGURAZIONE ───────────────────────────────────────────────────────────
AIRTABLE_TOKEN = "pat5R6Hzz11DFLqkx.37639cb89ca2562dbeca7f837f576c2e916e135eb94712f9ca4d4bc1d7b826f3"
BASE_ID = "app9mXSzgqGOhYtpd"
TABLE_NAME = "Clienti"

VERIFY_TOKEN = "praticaok2024"

META_TOKEN = "EAAV1b680TDABRSbHqdRqjizLcxImyatIj3gTZAZCaeGqYgcQdyVComHrZBQf7kEmZCNWin2DqUxifNhqLemkJvc7Wqw0BxjFeYDZB2FSLQviLFHhcjWMzuGlZBZCnUvpxvDaFRyA2SULWIc94e5ZBzSlxMJ0Rp95krUFPg7G5kBWUtpFhVJ6YvDj92DzxUbJvpWpjj1cgro3WeqAvuA227D0ZCtcUuF39um9sZBFHpqrsr"
PHONE_NUMBER_ID = "1156459807541320"

TELEGRAM_TOKEN = "8555023720:AAEpTP9E9EhfpQBra2oSQCIeaeNYdxapv2I"
TELEGRAM_CHANNEL_ID = "-1003939688675"

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

# ─── GUIDA DOCUMENTI ──────────────────────────────────────────────────────────
GUIDA_DOCUMENTI = {
    "carta d'identità": {
        "sinonimi": ["carta identità", "ci", "documento identità", "documento d'identità", "carta di identità"],
        "guida": """📄 *CARTA D'IDENTITÀ*

*Come ottenerla:*
1. Vai allo sportello anagrafe del tuo Comune
2. Porta una foto tessera recente
3. Porta la vecchia carta d'identità (o denuncia di smarrimento)
4. Paga il bollettino (~16-17€)

*Online:*
Puoi prenotare l'appuntamento su 📲 *prenotazionicie.interno.gov.it*

*Tempi:* 5-7 giorni lavorativi
*Validità:* 10 anni (adulti)

⚠️ Deve essere in corso di validità — fronte e retro"""
    },

    "passaporto": {
        "sinonimi": ["passport"],
        "guida": """📄 *PASSAPORTO*

*Come ottenerlo:*
1. Prenota appuntamento su 📲 *passaportonline.poliziadistato.it*
2. Vai in Questura con:
   • Foto tessera recente
   • Documento d'identità
   • Codice fiscale
   • Marca da bollo da 73,50€
   • Bollettino postale da 42,50€

*Tempi:* 30-90 giorni
*Validità:* 10 anni

⚠️ Deve essere in corso di validità"""
    },

    "codice fiscale": {
        "sinonimi": ["cf", "tessera sanitaria", "codici fiscale", "cod fiscale", "codfiscale"],
        "guida": """📄 *CODICE FISCALE / TESSERA SANITARIA*

*Come ottenerlo:*

🔵 *Online:*
Vai su 📲 *agenziaentrate.gov.it* → Servizi → Codice fiscale
Accedi con SPID o CIE

🔵 *Allo sportello:*
Vai all'Agenzia delle Entrate con documento d'identità

*Tempi:* Immediato online
*Costo:* Gratuito"""
    },

    "permesso di soggiorno": {
        "sinonimi": ["permesso soggiorno", "permesso"],
        "guida": """📄 *PERMESSO DI SOGGIORNO*

*Per il rinnovo:*
1. Scarica il kit postale in ufficio postale
2. Compila il modulo e porta:
   • Passaporto
   • Foto tessera
   • Marca da bollo
   • Ricevuta versamento

*Dove consegnare:*
Ufficio postale abilitato (sportello amico)

*Tempi rinnovo:* 2-6 mesi
⚠️ Se in scadenza, porta anche la ricevuta del rinnovo"""
    },

    "certificato di residenza": {
        "sinonimi": ["residenza", "certificato residenza"],
        "guida": """📄 *CERTIFICATO DI RESIDENZA*

*Come ottenerlo:*

🔵 *Online (gratuito):*
Vai su 📲 *anagrafe.gov.it* → Accedi con SPID → Scarica subito

🔵 *Allo sportello del Comune:*
Vai all'anagrafe con documento d'identità

*Tempi:* Immediato
⚠️ Deve essere rilasciato da non oltre 3 mesi"""
    },

    "stato di famiglia": {
        "sinonimi": ["certificato stato famiglia", "stato famiglia"],
        "guida": """📄 *STATO DI FAMIGLIA*

*Come ottenerlo:*

🔵 *Online (gratuito):*
Vai su 📲 *anagrafe.gov.it* → Accedi con SPID → Scarica subito

🔵 *Allo sportello del Comune:*
Vai all'anagrafe con documento d'identità

*Tempi:* Immediato
*Costo:* Gratuito online
⚠️ Deve essere recente (max 3 mesi)"""
    },

    "busta paga": {
        "sinonimi": ["buste paga", "cedolino", "stipendio", "buste paghe"],
        "guida": """📄 *BUSTE PAGA*

*Come ottenerle:*

🔵 *Dal datore di lavoro:*
Chiedi all'ufficio paghe o HR della tua azienda

🔵 *Per dipendenti pubblici:*
Vai su 📲 *noipa.gov.it* → Accedi con SPID → Cedolini

*Quante servono:* Solitamente le ultime 3
⚠️ Devono essere le più recenti"""
    },

    "cu": {
        "sinonimi": ["cud", "certificazione unica", "certificazione unica redditi", "modello cud"],
        "guida": """📄 *CU / CERTIFICAZIONE UNICA (ex CUD)*

*Come ottenerla:*

🔵 *Dal datore di lavoro:*
Viene consegnata entro il 31 marzo di ogni anno

🔵 *Per dipendenti pubblici:*
Vai su 📲 *noipa.gov.it* → Accedi con SPID → Documenti fiscali

🔵 *Online:*
Vai su 📲 *agenziaentrate.gov.it* → Cassetto fiscale → Accedi con SPID

*Quando è disponibile:* Entro il 31 marzo di ogni anno
⚠️ Serve quella dell'ultimo anno disponibile"""
    },

    "730": {
        "sinonimi": ["modello 730", "dichiarazione redditi 730", "modello redditi"],
        "guida": """📄 *MODELLO 730 / DICHIARAZIONE DEI REDDITI*

*Come ottenerlo:*

🔵 *Se presentato tramite CAF:*
Chiedi una copia al tuo CAF o commercialista

🔵 *Online:*
Vai su 📲 *agenziaentrate.gov.it*
→ Accedi con SPID
→ Cassetto fiscale → Dichiarazioni

*Serve anche:* La ricevuta di presentazione telematica
⚠️ Serve quello dell'ultimo anno"""
    },

    "f24": {
        "sinonimi": ["modello f24", "f 24", "pagamento imposte", "tributi"],
        "guida": """📄 *MODELLO F24*

*Come ottenerlo:*

🔵 *Dal commercialista:*
Chiedi copia dei versamenti effettuati

🔵 *Online:*
Vai su 📲 *agenziaentrate.gov.it*
→ Accedi con SPID → Cassetto fiscale → Versamenti

🔵 *Dalla banca:*
Se hai pagato tramite homebanking, scarica la ricevuta

⚠️ Serve la ricevuta di pagamento con conferma"""
    },

    "estratto conto": {
        "sinonimi": ["estratto conto bancario", "movimenti conto", "conto corrente", "movimenti bancari", "estrato conto"],
        "guida": """📄 *ESTRATTO CONTO BANCARIO*

*Come ottenerlo:*

🔵 *Online (homebanking):*
Accedi alla tua banca online → Estratti conto → Scarica PDF

🔵 *App della banca:*
Apri l'app → Documenti → Estratti conto → Seleziona periodo

🔵 *Allo sportello:*
Vai in filiale e chiedi gli estratti conto cartacei

*Quanti mesi:*
• Mutuo: ultimi 6 mesi
• Prestito: ultimi 3-6 mesi

⚠️ Servono TUTTI i conti correnti intestati a tuo nome"""
    },

    "visura catastale": {
        "sinonimi": ["visura", "catastale", "visura camerale"],
        "guida": """📄 *VISURA CATASTALE*

*Come ottenerla:*

🔵 *Online gratuita:*
Vai su 📲 *agenziaentrate.gov.it*
→ Servizi → Consultazione dati catastali
→ Accedi con SPID

🔵 *Tramite notaio o geometra:*
Può richiederla per te

🔵 *Allo sportello catastale:*
Vai all'Agenzia delle Entrate più vicina

*Costo:* Gratuita online con SPID
*Validità:* Deve essere recente (max 3 mesi)"""
    },

    "planimetria catastale": {
        "sinonimi": ["planimetria", "piantina catastale", "mappa catastale"],
        "guida": """📄 *PLANIMETRIA CATASTALE*

*Come ottenerla:*

🔵 *Online:*
Vai su 📲 *agenziaentrate.gov.it*
→ Consultazione dati catastali
→ Accedi con SPID
→ Cerca immobile → Scarica planimetria

🔵 *Tramite geometra:*
Può richiederla e verificare la conformità (consigliato)

*Costo:* Gratuita online con SPID
⚠️ La banca richiede spesso anche la *dichiarazione di conformità* firmata da un tecnico"""
    },

    "visura ipotecaria": {
        "sinonimi": ["visura ipotecaria", "ipotecaria", "ipoteche"],
        "guida": """📄 *VISURA IPOTECARIA*

*Come ottenerla:*

🔵 *Online:*
Vai su 📲 *agenziaentrate.gov.it*
→ Consultazione dati ipotecari
→ Accedi con SPID

🔵 *Tramite notaio:*
Il notaio la richiede automaticamente in fase di rogito

*Costo:* Gratuita online con SPID
*A cosa serve:* Verifica che l'immobile non abbia ipoteche o pignoramenti"""
    },

    "compromesso": {
        "sinonimi": ["contratto preliminare", "preliminare", "proposta acquisto", "compromeso"],
        "guida": """📄 *COMPROMESSO / CONTRATTO PRELIMINARE*

Il compromesso è il contratto firmato tra acquirente e venditore prima del rogito.

*Ce l'hai già:*
È il documento firmato con il venditore o tramite agenzia immobiliare

*Cosa deve contenere:*
• Dati delle parti
• Dati dell'immobile
• Prezzo concordato
• Caparra versata
• Data prevista del rogito

⚠️ Deve essere firmato da entrambe le parti"""
    },

    "ape": {
        "sinonimi": ["attestato prestazione energetica", "certificazione energetica", "classe energetica"],
        "guida": """📄 *APE — ATTESTATO DI PRESTAZIONE ENERGETICA*

*Come ottenerlo:*

🔵 *Lo fornisce il venditore:*
È obbligatorio che il venditore lo consegni all'acquirente

🔵 *Se non ce l'hai:*
Fai redigere l'APE da un tecnico abilitato (geometra, ingegnere, architetto)

*Costo:* 100-300€
*Validità:* 10 anni
⚠️ Obbligatorio per il rogito"""
    },

    "certificato di agibilità": {
        "sinonimi": ["agibilità", "abitabilità", "certificato agibilità"],
        "guida": """📄 *CERTIFICATO DI AGIBILITÀ*

*Come ottenerlo:*

🔵 *Lo fornisce il venditore:*
È responsabilità del venditore fornirlo

🔵 *Se non esiste:*
Va richiesto al Comune dove si trova l'immobile con l'aiuto di un tecnico abilitato

⚠️ Senza agibilità alcune banche non erogano il mutuo"""
    },

    "piano di ammortamento": {
        "sinonimi": ["piano ammortamento", "ammortamento", "piano rate", "piano di rimborso"],
        "guida": """📄 *PIANO DI AMMORTAMENTO*

*Come ottenerlo:*

🔵 *Dal tuo istituto bancario:*
Accedi all'homebanking → Mutui/Prestiti → Scarica piano di ammortamento

🔵 *Allo sportello:*
Vai in filiale e chiedi una copia del piano di rimborso

*Cosa contiene:*
• Importo di ogni rata
• Quota capitale e interessi
• Debito residuo mese per mese

⚠️ Serve per tutti i mutui o prestiti già in corso"""
    },

    "debito residuo": {
        "sinonimi": ["conteggio residuo", "saldo residuo", "residuo debito", "conteggio estintivo", "estintivo", "debito rimanente"],
        "guida": """📄 *DICHIARAZIONE DEBITO RESIDUO / CONTEGGIO ESTINTIVO*

*Come ottenerlo:*

🔵 *Dalla banca:*
Vai allo sportello o chiama il servizio clienti
Chiedi una "dichiarazione del debito residuo" o "conteggio estintivo"

🔵 *Tramite homebanking:*
Alcuni istituti lo mettono disponibile online nella sezione documenti

*Costo:* Solitamente gratuito
*Tempi:* 2-5 giorni lavorativi
⚠️ Deve essere recente"""
    },

    "liberatoria": {
        "sinonimi": ["liberatorio", "svincolo", "liberazione ipoteca"],
        "guida": """📄 *LIBERATORIA / SVINCOLO IPOTECA*

*Come ottenerla:*

🔵 *Dalla banca che aveva l'ipoteca:*
Dopo aver estinto il mutuo, chiedi formalmente la cancellazione dell'ipoteca

🔵 *Procedura:*
1. Estingui completamente il mutuo
2. La banca invia la quietanza al notaio
3. Il notaio provvede alla cancellazione ipotecaria

*Tempi:* 30-90 giorni dalla estinzione
⚠️ Necessaria per dimostrare che l'immobile è libero da ipoteche"""
    },

    "obis m": {
        "sinonimi": ["obis", "estratto inps", "estratto pensione"],
        "guida": """📄 *OBIS M — ESTRATTO PENSIONE INPS*

*Come ottenerlo:*

🔵 *Online:*
Vai su 📲 *myinps.inps.it*
→ Accedi con SPID
→ Pensione → Cedolino pensione → Estratto

🔵 *Tramite CAF o patronato:*
Possono scaricarlo per te gratuitamente

*Costo:* Gratuito
*A cosa serve:* Dimostra l'importo della pensione percepita"""
    },

    "pa04": {
        "sinonimi": ["modello pa04", "attestazione servizio", "attestazione dipendente pubblico"],
        "guida": """📄 *MODELLO PA04 — DIPENDENTI PUBBLICI*

*Come ottenerlo:*

🔵 *Dall'ufficio del personale:*
Fai richiesta scritta all'ufficio HR del tuo ente pubblico

*Cosa contiene:*
• Anzianità di servizio
• Tipo di contratto
• Stipendio lordo e netto
• TFR accantonato

*Tempi:* 5-15 giorni lavorativi
*Costo:* Gratuito
⚠️ Obbligatorio per dipendenti pubblici"""
    },

    "scia": {
        "sinonimi": ["segnalazione certificata", "scia edilizia", "dia", "concessione edilizia", "permesso costruire"],
        "guida": """📄 *SCIA / DIA / CONCESSIONE EDILIZIA*

*Come ottenerla:*

🔵 *Dal Comune:*
Vai all'ufficio tecnico del Comune dove si trova l'immobile
Chiedi copia della pratica edilizia

🔵 *Dal venditore:*
Il venditore dovrebbe avere copia di tutti i titoli edilizi

🔵 *Tramite geometra:*
Può fare la ricerca in Comune per te

*A cosa serve:*
Dimostra che l'immobile è stato costruito o ristrutturato regolarmente
⚠️ Fondamentale per verificare la regolarità urbanistica"""
    },

    "isee": {
        "sinonimi": ["dichiarazione isee", "attestazione isee", "dsu"],
        "guida": """📄 *ISEE — INDICATORE SITUAZIONE ECONOMICA EQUIVALENTE*

*Come ottenerlo:*

🔵 *Tramite CAF (gratuito):*
Vai al CAF più vicino con:
• Documento d'identità
• Codice fiscale di tutti i componenti del nucleo
• 730 o CU
• Estratti conto

🔵 *Online:*
Vai su 📲 *myinps.inps.it*
→ Accedi con SPID → Compila la DSU precompilata

*Tempi:* Immediato online
*Validità:* 1 anno
*Costo:* Gratuito"""
    },

    "visura camerale": {
        "sinonimi": ["visura camera commercio", "camera di commercio"],
        "guida": """📄 *VISURA CAMERALE*

*Come ottenerla:*

🔵 *Online:*
Vai su 📲 *registroimprese.it*
→ Cerca la tua impresa → Acquista la visura

🔵 *Allo sportello Camera di Commercio:*
Porta documento d'identità e codice fiscale dell'impresa

*Costo:* 5-18€ online
*Validità:* Deve essere recente (max 3 mesi)
⚠️ Serve per lavoratori autonomi e titolari di ditta"""
    },
}

# ─── PAROLE CHIAVE PER RICONOSCERE RICHIESTA DI AIUTO ────────────────────────
PAROLE_AIUTO = ["dove", "come", "trova", "trovo", "ottengo", "ottenere",
                "scaricare", "scarico", "richiedere", "richiedo", "serve",
                "bisogno", "aiuto", "spiegami", "dimmi", "info", "informazioni",
                "recuperare", "recupero", "procurare", "procuro", "avere",
                "reperire", "reperisco", "cerco", "cercare", "trovare",
                "prendere", "prendo", "richiedere", "ho bisogno", "mi serve",
                "dove posso", "come posso", "come faccio", "dove trovo",
                "come trovo", "come ottengo", "come recupero", "come scarico"]

# ─── SINONIMI DOCUMENTI ───────────────────────────────────────────────────────
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
api = Api(AIRTABLE_TOKEN)
table = api.table(BASE_ID, TABLE_NAME)
table_pratiche = api.table(BASE_ID, "Pratiche")


# ─── FUNZIONI HELPER ──────────────────────────────────────────────────────────
def somiglianza(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def cerca_guida_documento(messaggio):
    msg = messaggio.lower().strip()
    ha_parola_aiuto = any(parola in msg for parola in PAROLE_AIUTO)
    if not ha_parola_aiuto:
        return None
    for doc_key, doc_data in GUIDA_DOCUMENTI.items():
        if doc_key.lower() in msg:
            return doc_data["guida"]
        for sinonimo in doc_data["sinonimi"]:
            if sinonimo.lower() in msg:
                return doc_data["guida"]
            if somiglianza(sinonimo, msg) > 0.80:
                return doc_data["guida"]
    return None


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
    print(f"Meta API: {risposta.status_code}")
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


def salva_file_telegram(file_content, nome_file, content_type, mittente):
    try:
        caption = f"📎 Da {mittente} — {nome_file}"
        url_telegram = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        risposta = req.post(url_telegram, data={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "caption": caption
        }, files={
            "document": (nome_file, file_content, content_type)
        })
        risultato = risposta.json()
        if risultato.get("ok"):
            file_id = risultato["result"]["document"]["file_id"]
            url_info = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
            info = req.get(url_info).json()
            if info.get("ok"):
                file_path = info["result"]["file_path"]
                return f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        return None
    except Exception as e:
        print(f"Errore Telegram: {e}")
        return None


def aggiungi_allegato_airtable(cliente_id, url_file, nome_file, content_type):
    try:
        file_content = req.get(url_file).content
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
    lista_ricevuti = [d.strip() for d in ricevuti.split(",") if d.strip()]
    if doc_trovato in lista_mancanti:
        lista_mancanti.remove(doc_trovato)
        lista_ricevuti.append(doc_trovato)
    nuovi_mancanti = ", ".join(lista_mancanti)
    nuovi_ricevuti = ", ".join(lista_ricevuti)
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

    # Prima controlla se è una richiesta di guida
    guida = cerca_guida_documento(messaggio)
    if guida:
        return "richiesta_guida", guida

    doc = trova_documento_nel_testo(messaggio, lista_mancanti)
    if doc:
        return "nome_documento", doc

    for parola in PAROLE_INTENZIONE:
        if parola.lower() in msg:
            return "intenzione", None

    return "testo", None


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verificato!")
        return challenge, 200
    return "Token non valido", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"Ricevuto: {data}")

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "statuses" in value:
            return jsonify({"status": "ok"}), 200

        messages = value.get("messages", [])
        if not messages:
            return jsonify({"status": "ok"}), 200

        message = messages[0]
        mittente = message["from"]
        tipo_msg = message["type"]

        print(f"Da {mittente} | Tipo: {tipo_msg}")

        messaggio = ""
        media_id = None
        ha_file = False

        if tipo_msg == "text":
            messaggio = message["text"]["body"]
        elif tipo_msg in ["image", "document", "audio", "video"]:
            ha_file = True
            media_data = message.get(tipo_msg, {})
            media_id = media_data.get("id")
            messaggio = media_data.get("caption", "")
        elif tipo_msg == "interactive":
            messaggio = message.get("interactive", {}).get("button_reply", {}).get("title", "")

        cliente = trova_o_crea_cliente(mittente)
        cliente_id = cliente["id"]
        fields = cliente["fields"]
        consenso = fields.get("Consenso", "In attesa")

        # ─── GESTIONE CONSENSO PRIVACY ────────────────────────────────────────
        msg_lower = messaggio.lower().strip()

        if msg_lower in ["accetto", "accetta", "si", "sì", "ok", "acconsento"]:
            if consenso != "Accettato":
                table.update(cliente_id, {"Consenso": "Accettato"})
                invia_messaggio_meta(mittente,
                    "✅ Consenso registrato! Grazie.\n\n"
                    "Ora puoi iniziare a mandare i tuoi documenti.\n"
                    "Scrivi 'Ciao' per vedere la lista di cosa serve. 👍\n\n"
                    "💡 Puoi anche chiedermi come trovare qualsiasi documento!\n"
                    "Es: 'Come recupero il CUD?' o 'Dove trovo la visura catastale?'")
                return jsonify({"status": "ok"}), 200

        if msg_lower in ["rifiuto", "rifiuta", "no", "non accetto"]:
            table.update(cliente_id, {"Consenso": "Rifiutato"})
            invia_messaggio_meta(mittente,
                "❌ Hai rifiutato il trattamento dei dati.\n\n"
                "Non potremo procedere con la raccolta documenti.\n"
                "Per maggiori informazioni contatta il tuo mediatore.")
            return jsonify({"status": "ok"}), 200

        if consenso != "Accettato":
            invia_messaggio_meta(mittente, INFORMATIVA_PRIVACY)
            return jsonify({"status": "ok"}), 200

        # ─── DA QUI SOLO CLIENTI CHE HANNO ACCETTATO ─────────────────────────
        mancanti = fields.get("Documenti mancanti", "")
        stato_cliente = fields.get("Stato", "In Attesa")
        tipo_pratica = fields.get("Tipo pratica", "")

        lista_mancanti = [d.strip() for d in mancanti.split(",") if d.strip()]
        tipo, payload = classifica_messaggio(messaggio, ha_file, lista_mancanti)

        print(f"Tipo: {tipo} | Stato: {stato_cliente} | Pratica: {tipo_pratica}")

        # Gestisci file
        if ha_file and media_id:
            file_content, nome_file, content_type = scarica_file_meta(media_id)
            if file_content:
                url_diretto = salva_file_telegram(file_content, nome_file, content_type, mittente)
                if url_diretto:
                    aggiungi_allegato_airtable(cliente_id, url_diretto, nome_file, content_type)

        # ─── RISPOSTE ─────────────────────────────────────────────────────────
        if tipo == "richiesta_guida":
            invia_messaggio_meta(mittente, payload)

        elif tipo == "documento_con_nome":
            lista_rimanenti, stato = aggiorna_documenti(cliente_id, payload, fields)
            if stato == "Completo":
                invia_messaggio_meta(mittente,
                    f"✅ {payload} ricevuto!\n\nPratica COMPLETA! Ti contatteremo a breve. 🎉")
            else:
                invia_messaggio_meta(mittente,
                    f"✅ {payload} ricevuto!\n\nMancano ancora:\n{', '.join(lista_rimanenti)}\n\n"
                    f"💡 Scrivi 'Come recupero [documento]?' per istruzioni su come trovarlo.")

        elif tipo == "documento":
            if lista_mancanti:
                opzioni = "\n".join([f"- {d}" for d in lista_mancanti])
                invia_messaggio_meta(mittente,
                    f"📎 Documento ricevuto!\n\nDi che documento si tratta?\n{opzioni}\n\n"
                    f"💡 Scrivi 'Come recupero [documento]?' per istruzioni su come trovarlo.")
            else:
                invia_messaggio_meta(mittente, "📎 Documento ricevuto! Di che documento si tratta?")

        elif tipo == "nome_documento":
            if not lista_mancanti:
                invia_messaggio_meta(mittente, "Non ho trovato documenti in attesa per la tua pratica.")
            else:
                lista_rimanenti, stato = aggiorna_documenti(cliente_id, payload, fields)
                if stato == "Completo":
                    invia_messaggio_meta(mittente,
                        "✅ Pratica COMPLETA! Hai mandato tutto. Ti contatteremo a breve. 🎉")
                else:
                    invia_messaggio_meta(mittente,
                        f"✅ {payload} registrato!\n\nMancano ancora:\n{', '.join(lista_rimanenti)}\n\n"
                        f"💡 Scrivi 'Come recupero [documento]?' per istruzioni su come trovarlo.")

        elif tipo == "intenzione":
            if stato_cliente == "Completo":
                invia_messaggio_meta(mittente, "✅ La tua pratica è già completa! Ti contatteremo a breve.")
            elif tipo_pratica and not mancanti:
                documenti = get_documenti_per_pratica(tipo_pratica)
                if documenti:
                    table.update(cliente_id, {"Documenti mancanti": documenti})
                    lista = documenti.split(",")
                    opzioni = "\n".join([f"- {d.strip()}" for d in lista])
                    invia_messaggio_meta(mittente,
                        f"Perfetto! 👍 Per la pratica {tipo_pratica} servono:\n{opzioni}\n\n"
                        f"Manda i documenti quando vuoi!\n\n"
                        f"💡 Scrivi 'Come recupero [documento]?' per istruzioni su come trovarlo.")
                else:
                    invia_messaggio_meta(mittente,
                        "Ciao! Il broker non ha ancora configurato la tua pratica. Riprova tra poco.")
            elif mancanti:
                opzioni = "\n".join([f"- {d}" for d in lista_mancanti])
                invia_messaggio_meta(mittente,
                    f"Ciao! 👋 Mancano ancora questi documenti:\n{opzioni}\n\n"
                    f"💡 Scrivi 'Come recupero [documento]?' per istruzioni su come trovarlo.")
            else:
                invia_messaggio_meta(mittente,
                    "Ciao! 👋 Il tuo broker deve prima aprire la pratica. Ti contatteremo a breve.")

        else:
            invia_messaggio_meta(mittente,
                "Ciao! 👋 Sono il sistema di raccolta documenti PraticaOk.\n\n"
                "Posso aiutarti a:\n"
                "📎 Raccogliere i documenti per la tua pratica\n"
                "🔍 Spiegarti come trovare ogni documento\n\n"
                "Scrivi 'Ciao' per iniziare oppure\n"
                "'Come recupero [documento]?' per istruzioni dettagliate!")

    except Exception as e:
        print(f"Errore webhook: {e}")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host="0.0.0.0", port=port)
