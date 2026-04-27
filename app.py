import streamlit as st
import pandas as pd
import urllib.parse
import unicodedata
import io
import os
import datetime
import time
import plotly.express as px
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client

# ==========================================
# 📍 CONFIGURATIONS INITIALES & PAGE
# ==========================================
st.set_page_config(page_title="Numérique Saint Charles", page_icon="☁️", layout="wide")

DOSSIER_COURANT = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 🔐 CONFIGURATION EMAIL & SÉCURITÉ CLOUD (SECRETS)
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# --- OPTIMISATION 1 : Client Supabase en singleton (une seule connexion pour toute la session) ---
@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"❌ Erreur de connexion Supabase : {e}")
    st.stop()

SMTP_USER = st.secrets["SMTP_USER"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_ADMIN = "o.leothaud2@saintcharles71.fr"
EMAIL_TEST_CIBLE = "o.leothaud@gmail.com"

PASSWORD_ADMIN = st.secrets["PASSWORD_ADMIN"]
PASSWORD_COMPTA = st.secrets["PASSWORD_COMPTA"]
PASSWORD_PROF = st.secrets["PASSWORD_PROF"]
MDP_DEFAUT = st.secrets["MDP_DEFAUT"]


# ==========================================
# 🛡️ FONCTIONS DATA SUPABASE AVEC CACHE
# ==========================================

# --- OPTIMISATION 2 : Cache avec TTL court pour les lectures fréquentes ---
@st.cache_data(ttl=60, show_spinner=False)
def fetch_table(table_name, eq_col=None, eq_val=None, order_col=None, select_cols="*"):
    query = get_supabase_client().table(table_name).select(select_cols)
    if eq_col is not None:
        query = query.eq(eq_col, eq_val)
    if order_col is not None:
        query = query.order(order_col)
    try:
        res = query.execute()
        df = pd.DataFrame(res.data)
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        schemas = {
            "eleves": ["id", "nom", "prenom", "classe", "date_naissance", "id_ed", "mdp_ed",
                       "id_mail", "mdp_mail", "id_pix", "mdp_pix", "statut_ipad", "mensualite",
                       "restitution", "solde", "incident", "est_parti", "pp", "date_entree",
                       "id_ed_prov", "mdp_ed_prov", "est_nouveau"],
            "incidents_ipad": ["id", "eleve_id", "date_incident", "type_incident", "montant", "envoye_compta"],
            "demandes": ["id", "eleve_id", "prof", "plateforme", "statut", "date_demande"],
        }
        df = pd.DataFrame(columns=schemas.get(table_name, []))
    return df.fillna("")


def invalidate_cache():
    """Vide le cache de données après toute écriture Supabase."""
    fetch_table.clear()


# ==========================================
# 🎨 STYLE FINAL ST CHARLES
# ==========================================
st.markdown("""
    <style>
        button[title="View fullscreen"] { display: none !important; }
        [data-testid="StyledFullScreenButton"] { display: none !important; }
        [data-testid="collapsedControl"] { opacity: 1 !important; }
        [data-testid="stSidebar"] { background-color: #1e3a5f !important; }
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
            color: #f0f4f8 !important;
        }
        [data-testid="stSidebar"] input {
            background-color: #ffffff !important;
            color: #1e3a5f !important;
            -webkit-text-fill-color: #1e3a5f !important;
        }
        [data-testid="stSidebar"] input::placeholder { color: #1e3a5f !important; opacity: 0.7; }
        .stApp { background-color: #f0f4f8 !important; }
        h1, h2, h3, [data-testid="stHeader"] { color: #1e3a5f !important; }
        [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 { color: #1e3a5f !important; }
        input, select, div[data-baseweb="select"] > div {
            color: #1e3a5f !important;
            background-color: #ffffff !important;
            -webkit-text-fill-color: #1e3a5f !important;
        }
        div[role="listbox"] { background-color: #ffffff !important; color: #1e3a5f !important; }
        label p { color: #1e3a5f !important; }
        div[data-baseweb="tooltip"], div[data-testid="stTooltipContent"] {
            display: none !important; opacity: 0 !important; visibility: hidden !important;
        }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 📧 EMAIL
# ==========================================
def envoyer_email_reel(sujet, corps_html, destinataire=EMAIL_TEST_CIBLE):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Numérique Saint Charles <{SMTP_USER}>"
        msg['To'] = destinataire
        msg['Cc'] = EMAIL_ADMIN
        msg['Subject'] = sujet
        msg.attach(MIMEText(corps_html, 'html'))
        tous_destinataires = [destinataire, EMAIL_ADMIN]
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, tous_destinataires, msg.as_string())
        server.quit()
        st.toast(f"🚀 Email envoyé à {destinataire} (copie à l'admin)")
        return True
    except Exception as e:
        st.error(f"❌ Erreur technique email : {e}")
        return False


# ==========================================
# 🧠 LOGIQUE CALCULS & GÉNÉRATION
# ==========================================
def nettoyeur_identifiant(texte):
    if pd.isna(texte) or str(texte).strip() == "":
        return ""
    s = ''.join(c for c in unicodedata.normalize('NFD', str(texte)) if unicodedata.category(c) != 'Mn')
    return s.lower().replace(' ', '').replace('-', '')


def generer_identifiants(prenom, nom, date_naiss, classe):
    p_clean = nettoyeur_identifiant(prenom)
    n_clean = nettoyeur_identifiant(nom)
    try:
        jjmm = "".join(str(date_naiss).split('/')[:2]).zfill(4)
    except Exception:
        jjmm = "0000"
    mail = f"{p_clean}.{n_clean}@saintcharles71.fr"
    if "6G" in str(classe).upper():
        return f"{p_clean}.{n_clean}", mail, mail
    return f"{p_clean.capitalize()[:2]}.{n_clean.capitalize()}", mail, f"{p_clean}.{n_clean}{jjmm}"


def calculer_code_ipad(date_naiss):
    try:
        parts = str(date_naiss).split('/')
        jjmm = parts[0].zfill(2) + parts[1].zfill(2)
        return f"{jjmm}71"
    except Exception:
        return "000071"


def calculer_mensualite_ipad(classe, statut):
    if statut == "Parti":
        return 0, 0
    if statut == "Fratrie":
        return 0, 15
    mensualite = 14 if str(classe).strip().startswith("3") else 16
    return mensualite, mensualite * 10

def calculer_solde_depart(classe, rend_ipad, statut):
    if statut == "Parti":
        return "0 €"
    if statut == "Fratrie":
        return "N/A (Garde l'iPad)" if rend_ipad else "16 € (Soulte MDM)"
    mois_actuel = datetime.datetime.now().month
    if 9 <= mois_actuel <= 12:
        mois_restants = 10 - (mois_actuel - 9)
    elif 1 <= mois_actuel <= 6:
        mois_restants = 6 - mois_actuel + 1
    else:
        mois_restants = 0
    classe_str = str(classe).strip()
    mensualite = 14 if classe_str.startswith("3") else 16
    solde_annee_courante = mois_restants * mensualite
    if rend_ipad:
        return f"{solde_annee_courante} €"
    annees_suivantes = 0
    if classe_str.startswith("6"):
        annees_suivantes = 160 + 160 + 140
    elif classe_str.startswith("5"):
        annees_suivantes = 160 + 140
    elif classe_str.startswith("4"):
        annees_suivantes = 140
    return f"{solde_annee_courante + annees_suivantes + 16} €"

def calculer_bilan_logistique(df_eleves, df_incidents):
    if df_eleves.empty:
        return pd.DataFrame()
    
    # On prépare le bilan
    bilan = df_eleves[['id', 'nom', 'prenom', 'classe', 'statut_ipad']].copy()
    
    # Calcul du nombre d'incidents et montant SAV par élève
    if not df_incidents.empty:
        sav_stats = df_incidents.groupby('eleve_id')['montant'].agg(['count', 'sum']).reset_index()
        sav_stats.columns = ['id', 'nb_incidents', 'total_sav']
        bilan = pd.merge(bilan, sav_stats, on='id', how='left')
    else:
        bilan['nb_incidents'] = 0
        bilan['total_sav'] = 0
        
    bilan = bilan.fillna(0)
    
    # Calcul du loyer annuel théorique
    def get_loyer(row):
        mens, annuel = calculer_mensualite_ipad(row['classe'], row['statut_ipad'])
        return annuel
    
    bilan['loyer_annuel'] = bilan.apply(get_loyer, axis=1)
    bilan['dette_totale'] = bilan['total_sav'] + bilan['loyer_annuel']
    
    return bilan.sort_values(['classe', 'nom'])


# ==========================================
# 📄 GÉNÉRATEUR PDF HTML
# ==========================================
def generer_pdf_html(cible_titre, df_print, print_ed, print_dr, print_px, print_prov, print_ipad, print_conv=False):
    html_content = """
    <html><head><meta charset="utf-8">
    <title>Documents - """ + cible_titre + """</title>
    <style>
        @media print { .page-break { page-break-after: always; } .no-print { display: none; } }
        body { font-family: "Arial", sans-serif; color: #333; margin: 0; padding: 0; }
        
        /* Styles pour la Fiche Identifiants (Card) */
        .card { border: 2px solid #1e3a5f; border-radius: 8px; padding: 15px; margin-bottom: 15px; page-break-inside: avoid; background-color: #f9fbfd; font-size: 14px; }
        .header-card { font-size: 16px; font-weight: bold; border-bottom: 2px solid #1e3a5f; padding-bottom: 6px; margin-bottom: 10px; color: #1e3a5f; }
        .cred-row { font-size: 14px; margin: 6px 0; padding: 6px; background: #fff; border-radius: 5px; border-left: 4px solid; color: #1e3a5f; }
        .cred-ed { border-color: #3498db; } .cred-dr { border-color: #f1c40f; }
        .cred-px { border-color: #9b59b6; } .cred-ipad { border-color: #2ecc71; background-color: #f0fff4; }
        .cred-prov { border-color: #e67e22; background-color: #fff3e0; }
        .label { font-weight: bold; display: inline-block; width: 220px; }
        .code { font-family: monospace; font-size: 15px; background: #eee; padding: 2px 6px; border-radius: 4px; }
        .warning { font-size: 13px; color: #c0392b; margin-bottom: 10px; font-weight: bold; text-decoration: underline; }
        
        /* Styles pour la Convention A4 */
        .convention-page { padding: 20px; position: relative; line-height: 1.15; font-size: 10px; color: #000; }
        .header-conv { text-align: center; margin-bottom: 10px; }
        .title-conv { font-weight: bold; font-size: 12px; margin-bottom: 2px; text-decoration: underline; }
        .subtitle-conv { font-weight: bold; font-size: 11px; margin-bottom: 8px; }
        .convention-page h3 { font-size: 11px; margin-top: 8px; margin-bottom: 2px; text-decoration: underline; color: #000; font-weight: bold; }
        .convention-page p, .convention-page li { text-align: justify; margin: 2px 0; }
        .convention-page ul { margin: 2px 0; padding-left: 20px; }
        .info-block { margin-bottom: 10px; }
        .footer-sigs { margin-top: 15px; width: 100%; border-collapse: collapse; }
        .footer-sigs td { border: 1px solid #000; width: 50%; height: 50px; vertical-align: top; padding: 5px; font-size: 10px; }
        .st-charles-footer { text-align: center; font-size: 9px; margin-top: 10px; color: #444; }
    </style>
    </head><body>
    <div class="no-print" style="background: #e74c3c; color: white; padding: 10px; text-align: center; margin-bottom: 20px; border-radius: 5px;">
        <b>Astuce :</b> Appuyez sur <b>Ctrl + P</b> (ou Cmd + P sur Mac) pour imprimer. Dans destination, choisissez "Enregistrer au format PDF".
    </div>"""

    for _, row in df_print.iterrows():
        classe = str(row['classe']).upper()
        nom = str(row['nom']).upper()
        prenom = str(row['prenom'])
        date_entree = str(row.get('date_entree', ''))
        if not date_entree: 
            date_entree = "........................"
        code_ipad = calculer_code_ipad(row['date_naissance'])

        # ==========================================
        # PARTIE 1 : LA CONVENTION (Si demandée)
        # ==========================================
        if print_conv:
            if classe.startswith("6"):
                niveau, duree = "6ÈME", "4 ans"
                art8_texte = """La tablette numérique est financée sur la durée de la scolarité selon le cycle.<br>
                <b>Nombre de mensualités : 40 | Montant mensuel : 16 € | Coût total : 640 €</b><br>
                Un dernier loyer de 16 € sera appliqué pour lever l’option d’achat.<br>
                Ces loyers couvrent l’achat de la tablette, ses accessoires, les applications installées par l’établissement, ainsi que l’assurance souscrite par l’établissement.<br>
                Lors du départ définitif de l’élève, que ce soit de manière anticipée (réorientation, déménagement…) ou à l’issue du cycle scolaire :<br>
                Soit la famille décide d’acquérir la tablette, sous réserve de son paiement intégral et de la signature d’une attestation de cession de propriété. Toutes les restrictions d’utilisation seront alors levées.<br>
                Soit la famille ne souhaite pas l’acquérir. Dans ce cas, toute année commencée est due. La tablette et ses accessoires doivent être restitués à l’établissement en parfait état de marche. Dans le cas contraire, la caution sera immédiatement encaissée."""
            elif classe.startswith("5"):
                niveau, duree = "5ÈME", "3 ans"
                art8_texte = """La tablette numérique est financée sur la durée de la scolarité selon le cycle.<br>
                Un élève arrivant en cours de cycle se verra attribuer une tablette d’occasion.<br>
                <b>Nombre de mensualités : 30 | Montant mensuel : 16 € | Coût total : 480 €</b><br>
                Un dernier loyer de 16 € sera appliqué pour lever l’option d’achat.<br>
                Ces loyers couvrent l’achat de la tablette, ses accessoires, les applications installées par l’établissement, ainsi que l’assurance souscrite par l’établissement.<br>
                Lors du départ définitif de l’élève, que ce soit de manière anticipée (réorientation, déménagement…) ou à l’issue du cycle scolaire :<br>
                Soit la famille décide d’acquérir la tablette, sous réserve de son paiement intégral et de la signature d’une attestation de cession de propriété. Toutes les restrictions d’utilisation seront alors levées.<br>
                Soit la famille ne souhaite pas l’acquérir. Dans ce cas, toute année commencée est due. La tablette et ses accessoires doivent être restitués à l’établissement en parfait état de marche. Dans le cas contraire, la caution sera immédiatement encaissée."""
            elif classe.startswith("4"):
                niveau, duree = "4ÈME", "2 ans"
                art8_texte = """La tablette numérique est en location sur la durée des deux années scolaires.<br>
                L’élève arrivant en classe de 4ème se verra attribuer une tablette d’occasion.<br>
                Le montant du loyer de 16€ sera prélevé chaque mois de l’année scolaire (de septembre à juin).<br>
                Ces loyers couvrent la location globale de la tablette (y compris ses accessoires, les applications installées par l’établissement, ainsi que l’assurance souscrite par l’établissement).<br>
                En cas de départ anticipé (réorientation, déménagement…), toute année commencée est due.<br>
                La tablette et ses accessoires doivent être restitués en parfait état de marche.<br>
                À l’issue du cycle scolaire la tablette sera récupérée par l’établissement avec une attestation de restitution."""
            else:
                niveau, duree = "3ÈME", "1 an"
                art8_texte = """La tablette numérique est en location sur la durée de l'année scolaire.<br>
                L’élève arrivant en classe de 3ème se verra attribuer une tablette d’occasion.<br>
                Le montant du loyer de 14€ sera prélevé chaque mois de l’année scolaire (de septembre à juin).<br>
                Ces loyers couvrent la location globale de la tablette (y compris ses accessoires, les applications installées par l’établissement, ainsi que l’assurance souscrite par l’établissement).<br>
                En cas de départ anticipé (réorientation, déménagement…), toute année commencée est due.<br>
                La tablette et ses accessoires doivent être restitués en parfait état de marche.<br>
                À l’issue du cycle scolaire la tablette sera récupérée par l’établissement avec une attestation de restitution."""

            html_content += f"""
            <div class="convention-page page-break">
                <div class="header-conv">
                    <div class="title-conv">CONVENTION DE MISE A DISPOSITION D’UN IPAD / TABLETTE NUMERIQUE EDUCATIVE A DESTINATION DES ELEVES</div>
                    <div class="subtitle-conv">ANNEE SCOLAIRE 2025-26 - ÉLÈVES DE {niveau}</div>
                </div>

                <div class="info-block">
                    <b>Etablissement :</b> Collège Saint Charles<br>
                    <b>Classe :</b> {classe}<br>
                    <b>Nom élève :</b> {nom}<br>
                    <b>Prénom :</b> {prenom}<br>
                    <b>Date entrée dans l’établissement :</b> {date_entree}<br><br>
                    Entre le groupe scolaire St Charles représenté par Mr Bruno AUBRIET, chef d’établissement coordinateur,<br>
                    Et (noms et prénoms des parents) ....................................................................................................<br>
                    Représentants légaux de l’élève {prenom} {nom} en classe de {classe}<br>
                    Il est convenu ce qui suit :
                </div>

                <h3>Article 1 : Objet de la convention</h3>
                <p>La présente convention régit les conditions de mise à disposition d’une tablette numérique par l’établissement à l’élève, pour la durée de sa scolarité dans l’établissement cité ci-dessus.</p>

                <h3>Article 2 : Le matériel mis à disposition</h3>
                <ul>
                    <li>Une tablette tactile Ipad de la marque Apple</li>
                    <li>Une housse de protection</li>
                    <li>Un adaptateur secteur et un câble d'alimentation marque IPAD pour la tablette</li>
                    <li>Des applications préinstallées et préconfigurées</li>
                </ul>

                <h3>Article 3 : Propriété</h3>
                <p>La tablette et les accessoires mis à disposition font partie des outils pédagogiques, et restent la propriété de l’établissement Saint Charles{' jusqu’à ce que ces derniers soient cédés aux élèves en fin de cycle scolaire' if classe.startswith('6') or classe.startswith('5') else ''}.<br>
                La revente, la cession, même à titre gratuit, l'échange, le prêt, la location, de la tablette et de ses accessoires sont donc strictement interdits.<br>
                Au moment du départ, le référent indiquera la procédure de sauvegarde des fichiers sur un outil de stockage personnel.</p>

                <h3>Article 4 : Conditions de mise à disposition et durée</h3>
                <p>L’Etablissement procède à la remise de la tablette à l'élève à la rentrée scolaire ou à la date d’arrivée dans l’établissement.<br>
                La durée de mise à disposition est de {duree}.<br>
                La mise à disposition reste conditionnée aux étapes suivantes :</p>
                <ul>
                    <li>Acceptation sans réserve de la présente convention de prêt et d'utilisation de la tablette tactile numérique datée, signée, et paraphée avec la mention manuscrite « lu et accepté » par le ou les représentants légaux et l'élève.</li>
                    <li>Versement d'une caution de 500 € par chèque uniquement et non daté (non encaissé, à l'ordre de « OGEC Saint Charles »).</li>
                </ul>
                <p>Cette caution sera détruite par l’établissement lors de la remise de la tablette en fin de cycle.{' Pour toute tablette non restituée, la caution sera immédiatement encaissée.' if classe.startswith('3') or classe.startswith('4') else ''}</p>

                <h3>Article 5 : Les engagements des élèves et des responsables</h3>
                <p>La tablette est mise à disposition de l'élève à titre individuel et nominatif. L'usage du matériel est réservé à l'élève dont l'identité figure sur la présente convention.<br>
                Les usages hors enceinte de l’Etablissement relèvent de l'autorité et de la responsabilité du ou des représentants légaux.<br>
                La signature de la présente convention par l'un des représentants légaux et de l'élève constitue l'acceptation de la remise de la tablette et de la détention de la tablette et des accessoires par l'élève.<br>
                <b>L’élève et ses représentant légaux s’engagent à :</b></p>
                <ul>
                    <li>Conserver et à prendre le plus grand soin de la tablette et des accessoires confiés</li>
                    <li>Garder la tablette dans la housse de protection et à l’abri des regards notamment dans les transports scolaires</li>
                    <li>Ne pas dégrader le matériel (pas d’inscription, pas d’autocollant)</li>
                    <li>Charger la tablette à 100% tous les soirs</li>
                    <li>Ne pas modifier la configuration initiale, respecter les réglages installés</li>
                    <li>Ne pas modifier ou détruire des fichiers sans autorisation</li>
                    <li>Ne pas prêter la tablette ou la mettre à la disposition d’autres personnes</li>
                </ul>
                <p><b>En classe :</b></p>
                <ul>
                    <li>Rester sur l’application demandée par le professeur et bien classer ses cours</li>
                    <li>Ne pas naviguer sur internet sans autorisation : ni jeux, ni réseaux sociaux, ne rien publier</li>
                    <li>Ne pas prendre de photos, ni vidéo sans autorisation</li>
                    <li>Ne pas utiliser l’Apple TV ni l’air Drop sans autorisation</li>
                </ul>
                <p>L'intégrité du système d'exploitation est contrôlée par l’établissement afin d'empêcher des fonctionnements non autorisés de la tablette.<br>
                Pour garantir l'utilisation de la tablette, l’Établissement met en œuvre un système de supervision de chaque tablette permettant son contrôle grâce à un logiciel de gestion de terminaux mobiles. Ce système de supervision permet d'appliquer des actions à distance telles que la réinitialisation du code de verrouillage, les réglages sur la tablette et de mettre à disposition des applications sélectionnées par l’Etablissement. Il permet aussi de géo localiser la tablette en cas de perte ou de vol.<br>
                Les enseignants ou le personnel de direction peuvent accéder aux dossiers de l'élève pour vérifier le travail accompli ou en cours.</p>

                <h3>Article 6 : Protection des données</h3>
                <p>À toutes fins utiles, il est rappelé que les données collectées auprès des élèves sont obligatoires aux fins de bonne gestion, d'organisation et de sécurisation des systèmes d'information et de communication. Les données stockées sont supprimées à la fin de la scolarité et le compte désactivé.</p>

                <h3>Article 7 : Pannes, bris, perte ou vol</h3>
                <p><b>En cas de panne ou de bris</b><br>
                La maintenance de la tablette, des accessoires et des logiciels et applications associés est de la compétence de l’Etablissement et de son prestataire. Aucune intervention externe n'est autorisée sur la tablette et ses accessoires. L'élève et son ou ses représentants légaux ne devront en aucun cas faire réparer ou remplacer un élément de la tablette.<br>
                Tout problème, incident, panne ou casse relatifs à la tablette, aux accessoires, aux applications installées doit être immédiatement signalé au référent numérique. Le remplacement éventuel du matériel se fera par l’établissement.<br>
                En cas de bris, une franchise sera appliquée de la manière suivante : 100€ pour un premier envoi, 200€ pour un deuxième, 300€ pour un troisième…</p>
                <p><b>En cas de perte ou de vol</b><br>
                En cas de vol ou de perte, une plainte ou une main courante (uniquement en cas de perte) devra obligatoirement être déposée immédiatement auprès des services de Police ou de Gendarmerie compétents territorialement par le ou les représentants légaux. Le récépissé devra être envoyé soit par courrier postal, soit par voie électronique à l’Etablissement, et ce, dans un délai de 48 heures à compter de la date indiquée sur le récépissé.<br>
                Le dispositif de géolocalisation à distance pourra être activé de manière exceptionnelle et ponctuelle afin de la retrouver. Les données relatives à la géolocalisation, susceptibles d'être enregistrées ne le seront donc, qu'à partir de la déclaration de perte, de vol ou d'abus de confiance.<br>
                En cas de perte ou vol, une franchise sera appliquée de la manière suivante : 100€ pour un premier envoi, 200€ pour un deuxième, 300€ pour un troisième…</p>

                <h3>Article 8 : Conditions financières</h3>
                <p>{art8_texte}</p>

                <h3>Article 9 : Sanctions</h3>
                <p>En cas de manquement à la présente convention et de violation d'une disposition réglementaire, l'élève s'expose à une confiscation de la tablette par l’Etablissement ainsi qu'à des sanctions disciplinaires.<br>
                En cas de mauvais usage, de revente, cession, échange, prêt ou location de la tablette et des accessoires, le matériel sera repris et des sanctions pouvant aller jusqu’à l’exclusion seront prises.<br>
                Les accessoires et la tablette de marque Apple sont la propriété de l’ensemble St Charles. Toute casse ou perte entraine la refacturation de ceux-ci. Le remplacement par des accessoires standards est interdit.<br>
                En cas de dégradation, la refacturation suivante sera opérée : Vitre de protection 15 € | Câble Apple 25 € | Bloc alimentation Apple 25 € | Coque 25 €.</p>

                <table class="footer-sigs">
                    <tr>
                        <td>Le : ........................................<br><br><b>Elève</b><br><span style="font-size:9px;">(noter lu et accepté + signature)</span></td>
                        <td><br><br><b>Représentants légaux</b><br><span style="font-size:9px;">(noter lu et accepté + signature)</span></td>
                    </tr>
                </table>
                <div class="st-charles-footer">Collège Saint Charles - Chalon-sur-Saône - Pôle Numérique</div>
            </div>
            """

        # ==========================================
        # PARTIE 2 : LA FICHE CARTONNÉE DES CODES
        # ==========================================
        
        # Si on imprime la convention, on force un saut de page APRÈS la fiche carton pour le prochain élève
        page_break_class = "page-break" if print_conv else ""
        
        html_content += f"""
        <div class="card {page_break_class}">
            <div class="header-card">🎓 {row['nom']} {row['prenom']} - Classe : {row['classe']}</div>"""
        
        if print_prov and 'id_ed_prov' in row and str(row['id_ed_prov']).strip() != "":
            html_content += "<div class='warning'>⚠️ ATTENTION : Les codes 'PROVISOIRE' sont à usage unique. Ils doivent obligatoirement être modifiés lors de la première connexion.</div>"
            html_content += f"<div class='cred-row cred-prov'><span class='label'>🟠 Ecole Directe (PROVISOIRE) :</span> ID : <span class='code'>{row['id_ed_prov']}</span> &nbsp;|&nbsp; Mdp : <span class='code'>{row['mdp_ed_prov']}</span></div>"
        if print_ipad:
            html_content += f"<div class='cred-row cred-ipad'><span class='label'>📱 Code déverrouillage iPad :</span> <span class='code'>{code_ipad}</span></div>"
        if print_ed:
            html_content += f"<div class='cred-row cred-ed'><span class='label'>🔵 Ecole Directe (Définitifs) :</span> ID : <span class='code'>{row['id_ed']}</span> &nbsp;|&nbsp; Mdp : <span class='code'>{row['mdp_ed']}</span></div>"
        if print_dr:
            html_content += f"<div class='cred-row cred-dr'><span class='label'>🟡 Drive :</span> ID : <span class='code'>{row['id_mail']}</span> &nbsp;|&nbsp; Mdp : <span class='code'>{row['mdp_mail']}</span></div>"
        if print_px:
            html_content += f"<div class='cred-row cred-px'><span class='label'>🟣 Pix :</span> ID : <span class='code'>{row['id_pix']}</span> &nbsp;|&nbsp; Mdp : <span class='code'>{row['mdp_pix']}</span></div>"
        
        html_content += "</div>"

    html_content += "<script>setTimeout(function() { window.print(); }, 500);</script></body></html>"
    return html_content


# ==========================================
# 🧭 BARRE LATÉRALE & SÉCURITÉ
# ==========================================
chemin_logo = os.path.join(DOSSIER_COURANT, "logo.jpg")
if os.path.exists(chemin_logo):
    st.sidebar.image(chemin_logo, use_container_width=True)
else:
    st.sidebar.title("🌱 Numérique Saint Charles")

# --- OPTIMISATION 3 : Comptage des demandes en attente avec cache court ---
@st.cache_data(ttl=30, show_spinner=False)
def get_nb_demandes_en_attente():
    try:
        res = get_supabase_client().table("demandes").select("id", count="exact").eq("statut", "En attente").execute()
        return res.count or 0
    except Exception:
        return 0


pwd_input = st.sidebar.text_input("🔑 Code d'accès (Prof / Admin / Compta)", type="password")
is_admin = (pwd_input == PASSWORD_ADMIN)
is_compta = (pwd_input == PASSWORD_COMPTA)
is_prof = (pwd_input == PASSWORD_PROF)

# ==========================================
# 🛑 BLOCAGE DE SÉCURITÉ (PAGE D'ACCUEIL)
# ==========================================
if not (is_admin or is_compta or is_prof):
    st.markdown("<h1 style='text-align: center; color: #1e3a5f; margin-bottom: 0;'>Bienvenue sur Numérique Saint Charles</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #1e3a5f; opacity: 0.7; margin-top: 0;'>Plateforme centralisée de gestion numérique</h4>", unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_spacer_l, col_image, col_spacer_r = st.columns([1, 2, 1])
    with col_image:
        chemin_accueil = os.path.join(DOSSIER_COURANT, "welcome.jpg")
        if os.path.exists(chemin_accueil):
            st.image(chemin_accueil, use_container_width=True)
        else:
            st.markdown("<div style='text-align: center; font-size: 130px; margin-top: -20px;'>🏫</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    col_t_spacer_l, col_text, col_t_spacer_r = st.columns([1, 8, 1])
    with col_text:
        st.markdown("""
            <div style='background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; border-radius: 0.25rem; padding: 1.5rem; margin-bottom: 2rem; text-align: center;'>
                🔒 <strong>Accès Restreint</strong><br><br>
                Cet espace est strictement réservé au personnel de l'établissement. Veuillez saisir votre <strong>code d'accès</strong> dans le menu latéral à gauche pour déverrouiller la plateforme.
            </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style='text-align: center; color: #1e3a5f;'>
            <p style='font-size: 18px;'><strong>Que retrouverez-vous sur cette plateforme ?</strong></p>
            <p style='margin-bottom: 8px;'>👩‍🏫 <strong>Portail Professeurs :</strong> Accès immédiat aux identifiants des élèves (Ecole Directe, Pix, Drive...) et création de tickets d'assistance.</p>
            <p style='margin-bottom: 8px;'>💼 <strong>Pôle Administration :</strong> Gestion à 360° des dossiers numériques, annuaires complets et éditions des fiches mots de passe.</p>
            <p>💰 <strong>Pôle Comptabilité :</strong> Suivi automatisé des contrats matériels, locations iPad, facturation SAV et restitutions.</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("<br><br><hr>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 13px; color: grey;'>© 2026 - Collège Saint Charles - Pôle Numérique & Informatique</p>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 🔄 ROUTAGE DES MENUS
# ==========================================
menu = "👩‍🏫 Portail Professeurs"

if "jump_ticket" not in st.session_state:
    st.session_state.jump_ticket = False


def trigger_jump():
    st.session_state.jump_ticket = True


if is_admin:
    st.sidebar.success("Mode Admin activé (Cloud)")
    nb_demandes = get_nb_demandes_en_attente()
    if nb_demandes > 0:
        st.sidebar.button(f"🚨 {nb_demandes} ticket(s) en attente !", on_click=trigger_jump, type="primary", use_container_width=True)
    else:
        st.sidebar.info("✅ Aucun ticket en attente.")
    st.sidebar.markdown("---")
    sections = ["📊 Tableau de bord", "👤 Dossier Élève", "🧑‍🏫 Gestion MdP", "📱 Gestion iPad", "⚙️ Base de Données"]
    if st.session_state.jump_ticket:
        st.session_state.side_sec = "🧑‍🏫 Gestion MdP"
        st.session_state.side_opt_mdp = "🛎️ Tickets"
        st.session_state.jump_ticket = False
    section = st.sidebar.selectbox("📂 Catégorie d'outils :", sections, key="side_sec")
    if section == "📊 Tableau de bord":
        menu = "📊 Tableau de Bord"
    elif section == "👤 Dossier Élève":
        menu = st.sidebar.radio("Option :", ["🪪 Dossier 360°", "➕ Nouvel Arrivant"], key="side_opt_eleve")
    elif section == "🧑‍🏫 Gestion MdP":
        menu = st.sidebar.radio("Option :", ["👩‍🏫 Portail Profs", "🛎️ Tickets", "🗄️ Historique des MdP"], key="side_opt_mdp")
    elif section == "📱 Gestion iPad":
        # L'admin voit une option en plus : "🚛 Vue Logistique Totale"
        options_ipad = ["🚛 Vue Logistique Totale", "💰 Espace Compta & Logistique", "🛠️ Historique SAV iPad", "📦 Restitutions (Fin d'année)"]
        menu = st.sidebar.radio("Option :", options_ipad, key="side_opt_ipad")
    elif section == "⚙️ Base de Données":
        menu = st.sidebar.radio("Option :", ["👥 Annuaire, Édition & PDF", "⚙️ Maintenance & Nettoyage"], key="side_opt_db")

elif is_compta:
    st.sidebar.success("Mode Comptabilité activé (Cloud)")
    menu = st.sidebar.radio("Navigation :", ["📊 Tableau de Bord", "💰 Espace Compta & Logistique", "📦 Restitutions (Fin d'année)"])


# ==========================================
# 📊 TABLEAU DE BORD
# ==========================================
if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord & Statistiques")

    # --- OPTIMISATION 4 : Chargement des deux tables en parallèle (via cache) ---
    df_eleves = fetch_table("eleves", eq_col="est_parti", eq_val=0)
    df_incidents = fetch_table("incidents_ipad")

    if df_eleves.empty:
        st.warning("La base de données est vide.")
    else:
        st.markdown("### 📌 Indicateurs Clés")
        df_eleves['statut_ipad'] = df_eleves['statut_ipad'].replace("", "Achat")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Effectif Total", len(df_eleves))
        c2.metric("iPads en Location", len(df_eleves[df_eleves['statut_ipad'] == 'Location']))
        c3.metric("iPads en Fratrie", len(df_eleves[df_eleves['statut_ipad'] == 'Fratrie']))
        c4.metric("Incidents Déclarés", len(df_incidents))
        montant_total = pd.to_numeric(df_incidents['montant'], errors='coerce').sum() if not df_incidents.empty else 0
        c5.metric("Facturation SAV", f"{montant_total} €")

        col_list1, col_list2, col_list3 = st.columns(3)
        with col_list1:
            with st.expander("📄 Voir la liste des iPads en Location"):
                st.dataframe(df_eleves[df_eleves['statut_ipad'] == 'Location'][['nom', 'prenom', 'classe']], hide_index=True)
        with col_list2:
            with st.expander("👨‍👩‍👧‍👦 Voir la liste des iPads Fratrie"):
                st.dataframe(df_eleves[df_eleves['statut_ipad'] == 'Fratrie'][['nom', 'prenom', 'classe']], hide_index=True)
        with col_list3:
            with st.expander("🛠️ Voir le détail des incidents SAV"):
                if not df_incidents.empty:
                    st.dataframe(df_incidents[['date_incident', 'type_incident', 'montant']], hide_index=True)
                else:
                    st.info("Aucun incident déclaré.")

        st.markdown("---")
        st.markdown("### 📈 Pilotage Financier & Matériel")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # Graphique 1 : Répartition existante
            fig_parc = px.pie(df_eleves, names='statut_ipad', hole=0.4, title="Répartition des Contrats iPad")
            st.plotly_chart(fig_parc, use_container_width=True)
            
        with col_chart2:
            # Graphique 2 : Top Incidents par Classe
            if not df_incidents.empty and not df_eleves.empty:
                # On fusionne les incidents avec les élèves pour récupérer la classe
                df_merge = pd.merge(df_incidents, df_eleves[['id', 'classe']], left_on='eleve_id', right_on='id', how='left')
                df_casse = df_merge['classe'].value_counts().reset_index()
                df_casse.columns = ['Classe', "Nombre d'incidents"]
                
                fig_casse = px.bar(df_casse, x='Classe', y="Nombre d'incidents", 
                                   title="Alerte Casse : Incidents par Classe", 
                                   color="Nombre d'incidents", color_continuous_scale="Reds")
                st.plotly_chart(fig_casse, use_container_width=True)
            else:
                st.info("📊 Pas assez de données pour afficher le graphique des incidents.")

        # --- Calcul du Revenu Prévisionnel ---
        st.markdown("---")
        df_loc = df_eleves[df_eleves['statut_ipad'] == 'Location']
        total_annuel = sum(calculer_mensualite_ipad(row['classe'], 'Location')[1] for _, row in df_loc.iterrows())
        
        st.success(f"💶 **Projection Financière :** D'après le parc actuel ({len(df_loc)} iPads en location), le revenu annuel prévisionnel généré par les loyers s'élève à **{total_annuel} €**.")


# ==========================================
# 🪪 DOSSIER 360° (ADMIN SEUL)
# ==========================================
elif is_admin and menu == "🪪 Dossier 360°":
    st.title("🪪 Dossier Élève 360°")
    search_360 = st.text_input("🔍 Rechercher un élève (Nom ou Prénom) :")

    if not search_360:
        st.info("👆 Saisissez un nom ou prénom dans la barre ci-dessus pour ouvrir un dossier.")
        st.markdown("""
            <div style='text-align: center; margin-top: 40px; margin-bottom: 30px; color: #1e3a5f; opacity: 0.6;'>
                <h1 style='font-size: 80px;'>🪪</h1>
                <h3>Vue à 360 degrés</h3>
                <p>Recherchez un élève pour accéder à l'intégralité de son profil, mettre à jour ses mots de passe, gérer son contrat iPad ou déclarer un incident SAV.</p>
            </div>
        """, unsafe_allow_html=True)
        res = pd.DataFrame()
        df_incidents_360 = pd.DataFrame()
    else:
        # --- OPTIMISATION 5 : Fetch depuis le cache, filtrage local côté Python ---
        df_360 = fetch_table("eleves")
        df_incidents_360 = fetch_table("incidents_ipad")
        search_clean = nettoyeur_identifiant(search_360)
        if not df_360.empty:
            res = df_360[
                df_360['nom'].apply(nettoyeur_identifiant).str.contains(search_clean) |
                df_360['prenom'].apply(nettoyeur_identifiant).str.contains(search_clean)
            ]
        else:
            res = pd.DataFrame()

    if res.empty and search_360:
        st.warning("Aucun élève trouvé à ce nom.")
    else:
        for _, el in res.iterrows():
            status_icon = "🚩 (PARTI)" if el['est_parti'] == 1 else "🎓"
            is_expanded = (st.session_state.get("open_el_id") == str(el['id']))

            with st.expander(f"{status_icon} {el['prenom']} {el['nom']} ({el['classe']})", expanded=is_expanded):
                if is_expanded and f"msg_{el['id']}" in st.session_state:
                    st.success(st.session_state.pop(f"msg_{el['id']}"))

                tab_profil, tab_mdp, tab_ipad = st.tabs(["📝 Profil & Scolarité", "🔑 Identifiants", "📱 Matériel & SAV"])

                with tab_profil:
                    with st.form(f"form_profil_{el['id']}"):
                        c1, c2, c3 = st.columns(3)
                        m_nom = c1.text_input("Nom", value=el['nom'])
                        m_prenom = c2.text_input("Prénom", value=el['prenom'])
                        m_dob = c3.text_input("Date de Naissance", value=el['date_naissance'])
                        c4, c5, c6 = st.columns(3)
                        m_classe = c4.text_input("Classe", value=el['classe'])
                        m_pp = c5.text_input("Professeur Principal", value=el['pp'])
                        m_entree = c6.text_input("Date d'entrée", value=el['date_entree'])
                        m_parti = st.checkbox("🚩 Cet élève a définitivement quitté l'établissement",
                                              value=bool(el['est_parti']), key=f"f_x_{el['id']}_{el['est_parti']}")

                        if st.form_submit_button("💾 Enregistrer le profil"):
                            parti_int = 1 if m_parti else 0
                            if parti_int == 1:
                                statut_ipad_up = 'Parti'
                            else:
                                statut_ipad_up = 'Achat' if el['statut_ipad'] == 'Parti' else (el['statut_ipad'] if el['statut_ipad'] != "" else "Achat")
                            supabase.table("eleves").update({
                                "nom": m_nom.upper(), "prenom": m_prenom.capitalize(),
                                "date_naissance": m_dob, "classe": m_classe, "pp": m_pp,
                                "date_entree": m_entree, "est_parti": parti_int, "statut_ipad": statut_ipad_up
                            }).eq("id", el['id']).execute()
                            invalidate_cache()
                            st.session_state["open_el_id"] = str(el['id'])
                            st.session_state[f"msg_{el['id']}"] = "✅ Profil et scolarité mis à jour avec succès !"
                            st.rerun()

                with tab_mdp:
                    with st.form(f"form_mdp_{el['id']}"):
                        st.markdown("**Identifiants Actifs**")
                        c1, c2 = st.columns(2)
                        m_id_ed = c1.text_input("Identifiant ED (Définitif)", value=el['id_ed'])
                        m_mdp_ed = c2.text_input("Mot de passe ED", value=el['mdp_ed'])
                        c3, c4 = st.columns(2)
                        m_id_mail = c3.text_input("Compte Drive", value=el['id_mail'])
                        m_mdp_mail = c4.text_input("MDP Drive", value=el['mdp_mail'])
                        c5, c6 = st.columns(2)
                        m_id_pix = c5.text_input("ID Pix", value=el['id_pix'])
                        m_mdp_pix = c6.text_input("MDP Pix", value=el['mdp_pix'])
                        st.markdown("---")
                        st.info(f"📱 **Code déverrouillage iPad** : {calculer_code_ipad(el['date_naissance'])}")
                        st.markdown("---")
                        st.markdown("**Identifiants Provisoires (Rentrée)**")
                        c7, c8 = st.columns(2)
                        m_id_prov = c7.text_input("ID ED Provisoire", value=el.get('id_ed_prov', ''))
                        m_mdp_prov = c8.text_input("MDP ED Provisoire", value=el.get('mdp_ed_prov', ''))

                        if st.form_submit_button("💾 Enregistrer les identifiants"):
                            supabase.table("eleves").update({
                                "id_ed": m_id_ed, "mdp_ed": m_mdp_ed, "id_mail": m_id_mail,
                                "mdp_mail": m_mdp_mail, "id_pix": m_id_pix, "mdp_pix": m_mdp_pix,
                                "id_ed_prov": m_id_prov, "mdp_ed_prov": m_mdp_prov
                            }).eq("id", el['id']).execute()
                            invalidate_cache()
                            st.session_state["open_el_id"] = str(el['id'])
                            st.session_state[f"msg_{el['id']}"] = "✅ Identifiants mis à jour avec succès !"
                            st.rerun()

                with tab_ipad:
                    with st.form(f"form_ipad_{el['id']}"):
                        st.markdown("#### 📄 Contrat & Solde")
                        c_stat, c_mens, c_tot = st.columns(3)
                        statut_actuel = el['statut_ipad'] if el['statut_ipad'] != "" else "Achat"
                        idx = ["Achat", "Location", "Fratrie", "Parti"].index(statut_actuel) if statut_actuel in ["Achat", "Location", "Fratrie", "Parti"] else 0
                        nouveau_statut = c_stat.selectbox("Statut du matériel", ["Achat", "Location", "Fratrie", "Parti"],
                                                          index=idx, key=f"s_st_{el['id']}_{statut_actuel}")
                        mens_calc, tot_calc = calculer_mensualite_ipad(el['classe'], nouveau_statut)
                        c_mens.text_input("Mensualité (€)", value=f"{mens_calc} €", disabled=True, key=f"s_ms_{el['id']}_{statut_actuel}")
                        c_tot.text_input("Total Annuel", value=f"{tot_calc} €", disabled=True, key=f"s_tt_{el['id']}_{statut_actuel}")
                        rend_box = st.checkbox("L'élève REND l'iPad", key=f"rend_360_{el['id']}")
                        solde_calc = calculer_solde_depart(el['classe'], rend_box, nouveau_statut)
                        st.info(f"💰 **Solde départ : {solde_calc}**")

                        if st.form_submit_button("💾 Mettre à jour le contrat"):
                            parti_int = 1 if nouveau_statut == 'Parti' else (0 if el['est_parti'] == 1 else el['est_parti'])
                            supabase.table("eleves").update({"statut_ipad": nouveau_statut, "est_parti": parti_int}).eq("id", el['id']).execute()
                            invalidate_cache()
                            st.session_state["open_el_id"] = str(el['id'])
                            st.session_state[f"msg_{el['id']}"] = "✅ Contrat mis à jour !"
                            st.rerun()

                    st.markdown("#### ➕ Déclarer un nouvel incident")
                    with st.form(f"form_new_sav_{el['id']}"):
                        type_inc = st.selectbox("Nature du sinistre",
                            ["Écran de protection (15€)", "Chargeur (25€)", "Câble (25€)", "Coque (25€)",
                             "iPad cassé (50€/100€)", "Écran HS SAV", "Batterie HS SAV"],
                            key=f"type_inc_{el['id']}")
                        prix_facture = 15 if "protection" in type_inc else \
                                       25 if any(x in type_inc for x in ["Chargeur", "Câble", "Coque"]) else \
                                       50 if (str(el['classe']).startswith("3") or str(el['classe']).startswith("4")) else 100
                        st.warning(f"🧾 Facturation : **{prix_facture} €**")
                        submit_sav = st.form_submit_button("🚀 Valider & Envoyer EMAIL")

                    if submit_sav:
                        corps_sav = f"""<html><body style="font-family: Arial, sans-serif; color: #1e3a5f;">
                            <h2 style="color: #1e3a5f; border-bottom: 2px solid #1e3a5f; padding-bottom: 10px;">📄 Notification de Facturation SAV iPad</h2>
                            <p>Bonjour,</p><p>Un nouvel incident a été déclaré sur le parc iPad :</p>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Élève :</td><td style="padding: 8px; border: 1px solid #ddd;">{el['nom'].upper()} {el['prenom']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Classe :</td><td style="padding: 8px; border: 1px solid #ddd;">{el['classe']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Motif :</td><td style="padding: 8px; border: 1px solid #ddd;">{type_inc}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; color: #d9534f;">Montant :</td><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; color: #d9534f;">{prix_facture} €</td></tr>
                            </table>
                            <p style="margin-top: 20px;">Enregistré le {datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")}.</p>
                            <br><p>Cordialement,<br><b>L'équipe Numérique - Saint Charles</b></p>
                        </body></html>"""
                        if envoyer_email_reel(f"SAV iPad - {el['nom'].upper()} ({el['classe']})", corps_sav, EMAIL_TEST_CIBLE):
                            supabase.table("incidents_ipad").insert({
                                "eleve_id": el['id'],
                                "date_incident": datetime.datetime.now().strftime("%d/%m/%Y"),
                                "type_incident": type_inc, "montant": prix_facture, "envoye_compta": 1
                            }).execute()
                            invalidate_cache()
                            st.success(f"✅ Incident déclaré ({prix_facture}€) !")

                    st.markdown("#### 🛠️ Historique SAV")
                    # Filtrage local depuis le cache (pas de nouvelle requête)
                    if not df_incidents_360.empty:
                        eleve_incidents = df_incidents_360[df_incidents_360['eleve_id'] == el['id']].copy()
                        if not eleve_incidents.empty:
                            eleve_incidents['Email Compta'] = eleve_incidents['envoye_compta'].apply(lambda x: '✅ Oui' if x == 1 else '❌ Non')
                            el_disp = eleve_incidents[['date_incident', 'type_incident', 'montant', 'Email Compta']]
                            el_disp.index = [""] * len(el_disp)
                            st.table(el_disp)
                            with st.form(f"del_sav_form_{el['id']}"):
                                if st.form_submit_button("🗑️ Effacer tout l'historique SAV de cet élève"):
                                    supabase.table("incidents_ipad").delete().eq("eleve_id", el['id']).execute()
                                    invalidate_cache()
                                    st.session_state["open_el_id"] = str(el['id'])
                                    st.session_state[f"msg_{el['id']}"] = "✅ Historique SAV effacé."
                                    st.rerun()
                        else:
                            st.success("Aucun incident.")
                    else:
                        st.success("Aucun incident.")


# ==========================================
# ➕ NOUVEL ARRIVANT
# ==========================================
elif is_admin and menu == "➕ Nouvel Arrivant":
    st.title("➕ Nouvel Arrivant")
    with st.form("form_ajout"):
        f_nom = st.text_input("Nom").upper()
        f_prenom = st.text_input("Prénom").capitalize()
        f_classe = st.text_input("Classe")
        f_dob = st.text_input("Date Naissance")
        f_pp = st.text_input("PP")
        f_entree = st.text_input("Entrée")
        if st.form_submit_button("✅ Créer la fiche"):
            id_ed, id_mail, id_pix = generer_identifiants(f_prenom, f_nom, f_dob, f_classe)
            supabase.table("eleves").insert({
                "nom": f_nom, "prenom": f_prenom, "classe": f_classe, "date_naissance": f_dob,
                "pp": f_pp, "date_entree": f_entree, "id_ed": id_ed, "mdp_ed": MDP_DEFAUT,
                "id_mail": id_mail, "mdp_mail": MDP_DEFAUT, "id_pix": id_pix, "mdp_pix": MDP_DEFAUT,
                "statut_ipad": 'Achat', "est_parti": 0, "est_nouveau": 1 # 👈 Ajoute bien le 1 ici
            }).execute()
            invalidate_cache()
            st.success("Ajouté !")


# ==========================================
# 👩‍🏫 PORTAIL PROFESSEURS
# ==========================================
elif menu == "👩‍🏫 Portail Professeurs" or menu == "👩‍🏫 Portail Profs":
    st.title("👩‍🏫 Portail Enseignants")
    tab_recherche, tab_masse = st.tabs(["🔍 Recherche", "👁️ Vue Classe"])

    with tab_recherche:
        recherche = st.text_input("🔍 Rechercher les identifiants d'un élève (Nom ou Prénom) :")
        if not recherche:
            st.info("👆 Saisissez le nom ou le prénom d'un élève pour trouver ses codes.")
            st.markdown("""
                <div style='text-align: center; margin-top: 20px; margin-bottom: 30px; color: #1e3a5f; opacity: 0.6;'>
                    <h1 style='font-size: 60px;'>🧑‍🎓</h1><h3>Dossiers Individuels</h3>
                    <p>Consultez les mots de passe d'un élève spécifique et demandez rapidement une réinitialisation en cas de problème.</p>
                </div>""", unsafe_allow_html=True)
            res = pd.DataFrame()
        else:
            # --- OPTIMISATION 6 : Filtrage local sur les données en cache ---
            df = fetch_table("eleves", eq_col="est_parti", eq_val=0)
            if not df.empty:
                search_clean = nettoyeur_identifiant(recherche)
                res = df[
                    df['nom'].apply(nettoyeur_identifiant).str.contains(search_clean, na=False) |
                    df['prenom'].apply(nettoyeur_identifiant).str.contains(search_clean, na=False)
                ]
            else:
                res = pd.DataFrame()

        if res.empty and recherche:
            st.warning("Aucun élève trouvé à ce nom.")
        else:
            for _, el in res.iterrows():
                with st.expander(f"🎓 {el['nom']} {el['prenom']} ({el['classe']})", expanded=False):
                    st.markdown(f":blue[**ED :**] `{el['id_ed']}` / `{el['mdp_ed']}`")
                    st.markdown(f":yellow[**Drive :**] `{el['id_mail']}` / `{el['mdp_mail']}`")
                    st.markdown(f":violet[**Pix :**] `{el['id_pix']}` / `{el['mdp_pix']}`")
                    st.markdown(f":green[**Code iPad :**] `{calculer_code_ipad(el['date_naissance'])}`")
                    st.markdown("---")
                    st.markdown("**🛎️ Signaler un problème de mot de passe**")
                    with st.form(f"form_ticket_prof_{el['id']}"):
                        email_prof = st.text_input("Votre e-mail :", key=f"prof_{el['id']}")
                        plateforme = st.selectbox("Plateforme concernée :", ["Ecole Directe", "Compte Drive", "Pix"], key=f"plat_{el['id']}")
                        
                        # --- NOUVEAUTÉ : Checkbox obligatoire ---
                        a_ete_teste = st.checkbox("✅ Je certifie avoir testé ce mot de passe avec l'élève et il ne fonctionne pas.", key=f"check_{el['id']}")
                        
                        if st.form_submit_button("Envoyer la demande à l'Admin"):
                            if not a_ete_teste:
                                st.error("❌ Vous devez certifier avoir testé le code avant d'envoyer la demande.")
                            elif not email_prof or "@" not in email_prof:
                                st.error("❌ Veuillez saisir une adresse e-mail valide.")
                            else:
                                df_verif = fetch_table("demandes", eq_col="eleve_id", eq_val=el['id'])
                                if not df_verif.empty:
                                    df_verif = df_verif[(df_verif['plateforme'] == plateforme) & (df_verif['statut'] == 'En attente')]
                                if not df_verif.empty:
                                    st.warning(f"⚠️ Une réinitialisation est déjà en cours pour {plateforme}.")
                                else:
                                    corps_alerte = f"""<html><body style="font-family: Arial, sans-serif;">
                                        <h2 style="color: #d9534f;">🚨 Nouveau Ticket MdP à traiter</h2>
                                        <p>Bonjour Olivier,</p>
                                        <ul>
                                            <li><b>Email Professeur :</b> {email_prof}</li>
                                            <li><b>Élève :</b> {el['nom']} {el['prenom']} ({el['classe']})</li>
                                            <li><b>Plateforme :</b> {plateforme}</li>
                                        </ul>
                                    </body></html>"""
                                    if envoyer_email_reel(f"🚨 ALERTE : Nouveau ticket de {email_prof}", corps_alerte, EMAIL_ADMIN):
                                        supabase.table("demandes").insert({"eleve_id": el['id'], "prof": email_prof, "plateforme": plateforme}).execute()
                                        invalidate_cache()
                                        st.success("✅ Demande envoyée ! L'administration a été prévenue.")

    with tab_masse:
        # --- OPTIMISATION 7 : Liste des classes depuis le cache élèves déjà chargé ---
        df_all_actifs = fetch_table("eleves", eq_col="est_parti", eq_val=0)
        classes_disponibles = sorted(df_all_actifs['classe'].dropna().unique().tolist()) if not df_all_actifs.empty else []
        classe_choisie = st.selectbox("Classe :", options=["--"] + classes_disponibles)

        if classe_choisie != "--":
            cacher_mdp = st.toggle("👁️ Cacher les mots de passe", value=True)
            cols = "nom, prenom, date_naissance, id_ed, mdp_ed, id_mail, mdp_mail, id_pix, mdp_pix, id_ed_prov, mdp_ed_prov, est_parti"
            df_c = fetch_table("eleves", eq_col="classe", eq_val=classe_choisie, order_col="nom", select_cols=cols)
            df_c = df_c[df_c['est_parti'] == 0] if not df_c.empty else df_c

            df_print = df_c.copy()
            if not df_print.empty:
                df_print['classe'] = classe_choisie

            c_eff1, c_eff2 = st.columns([1, 3])
            c_eff1.metric("Effectif de la classe", len(df_c))
            with c_eff2:
                st.info(f"💡 Identifiants pour la **{classe_choisie}**.")

            if not df_c.empty:
                df_c = df_c.drop(columns=[c for c in ['id_ed_prov', 'mdp_ed_prov', 'est_parti'] if c in df_c.columns])
                df_c.insert(3, 'Code iPad', df_c['date_naissance'].apply(calculer_code_ipad))

                if cacher_mdp:
                    for col in ['mdp_ed', 'mdp_mail', 'mdp_pix', 'Code iPad']:
                        df_c[col] = "••••••••"

                df_c = df_c.drop(columns=['date_naissance']).rename(columns={
                    'nom': 'Nom', 'prenom': 'Prénom', 'Code iPad': '📱 Code iPad',
                    'id_ed': '🔵 ID ED', 'mdp_ed': '🔵 MDP ED',
                    'id_mail': '🟡 ID Drive', 'mdp_mail': '🟡 MDP Drive',
                    'id_pix': '🟣 ID Pix', 'mdp_pix': '🟣 MDP Pix'
                })
                df_c.index = [""] * len(df_c)
                st.table(df_c)

            st.markdown("---")
            st.markdown("### 🖨️ Impression des identifiants de la classe")
            
            # --- NOUVEAUTÉ : Checkbox pour imprimer la convention format A4 ---
            print_conv = st.checkbox("📄 Imprimer la Convention de prêt iPad (Format A4)", value=False, key="p_conv")
            st.write("")
            st.markdown("**Quels identifiants inclure sur la fiche cartonnée ?**")
            
            col_ed, col_dr, col_px, col_prov, col_ipad = st.columns(5)
            print_ed = col_ed.checkbox("🔵 ED (Définitifs)", value=True, key="p_ed")
            print_dr = col_dr.checkbox("🟡 Drive", value=True, key="p_dr")
            print_px = col_px.checkbox("🟣 Pix", value=True, key="p_px")
            print_prov = col_prov.checkbox("🟠 ED (Provisoires)", value=False, key="p_prov")
            print_ipad = col_ipad.checkbox("📱 Code iPad", value=True, key="p_ipad")

            if st.button(f"📄 Générer la fiche d'impression pour les {classe_choisie}", type="primary"):
                html_content = generer_pdf_html(classe_choisie, df_print, print_ed, print_dr, print_px, print_prov, print_ipad, print_conv)
                b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
                href = f'<a href="data:text/html;base64,{b64}" download="Identifiants_{classe_choisie}.html" target="_blank" style="display: inline-block; padding: 12px 24px; background-color: #2ecc71; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; margin-top: 10px;">👉 Ouvrir la fiche pour l\'impression PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("👆 Sélectionnez une classe dans le menu déroulant ci-dessus.")


# ==========================================
# 🛎️ TICKETS (ADMIN)
# ==========================================
elif is_admin and menu == "🛎️ Tickets":
    st.title("🛎️ Tickets de réinitialisation")

    df_d = fetch_table("demandes", eq_col="statut", eq_val="En attente", select_cols="*, eleves(*)")
    flat_data = []
    for _, d in df_d.iterrows():
        row = {"id_demande": d["id"], "eleve_id": d["eleve_id"], "prof": d["prof"],
               "plateforme": d["plateforme"], "statut": d["statut"], "date_demande": d["date_demande"]}
        if isinstance(d.get("eleves"), dict):
            row.update(d["eleves"])
        flat_data.append(row)

    df_tickets = pd.DataFrame(flat_data).fillna("")

    if df_tickets.empty:
        st.success("Tout est traité. Aucun ticket en attente.")
    else:
        for _, req in df_tickets.iterrows():
            with st.expander(f"🚨 Demande de {req['prof']} - {req['prenom']} {req['nom']} ({req['plateforme']})", expanded=True):
                c_info, c_del = st.columns([4, 1])
                c_info.warning(f"⚠️ **ACTION REQUISE :** Réinitialiser le compte **{req['plateforme'].upper()}**.")
                if c_del.button("🗑️ Supprimer", key=f"del_ticket_{req['id_demande']}"):
                    supabase.table("demandes").delete().eq("id", req['id_demande']).execute()
                    invalidate_cache()
                    st.rerun()

                with st.form(f"ticket_edit_form_{req['id_demande']}"):
                    c1, c2 = st.columns(2)
                    new_id_ed = c1.text_input("Identifiant ED", value=req['id_ed'], key=f"t_ie_{req['id_demande']}")
                    new_mdp_ed = c2.text_input("Mot de passe ED", value=req['mdp_ed'], key=f"t_me_{req['id_demande']}")
                    c3, c4 = st.columns(2)
                    new_id_mail = c3.text_input("Compte Drive", value=req['id_mail'], key=f"t_im_{req['id_demande']}")
                    new_mdp_mail = c4.text_input("MDP Drive", value=req['mdp_mail'], key=f"t_mm_{req['id_demande']}")
                    c5, c6 = st.columns(2)
                    new_id_pix = c5.text_input("ID Pix", value=req['id_pix'], key=f"t_ip_{req['id_demande']}")
                    new_mdp_pix = c6.text_input("MDP Pix", value=req['mdp_pix'], key=f"t_mp_{req['id_demande']}")

                    if st.form_submit_button("💾 Enregistrer & Envoyer les codes au professeur"):
                        codes_envoyes = new_mdp_ed if req['plateforme'] == "Ecole Directe" else \
                                        new_mdp_mail if "Drive" in req['plateforme'] else new_mdp_pix
                        ident_envoyes = new_id_ed if req['plateforme'] == "Ecole Directe" else \
                                        new_id_mail if "Drive" in req['plateforme'] else new_id_pix
                        corps_mdp = f"""<html><body style="font-family: Arial, sans-serif; color: #1e3a5f;">
                            <h2>🔑 Nouveaux identifiants numériques</h2>
                            <p>Le mot de passe <b>{req['plateforme']}</b> a été réinitialisé :</p>
                            <ul>
                                <li><b>Élève :</b> {req['nom'].upper()} {req['prenom']}</li>
                                <li><b>Classe :</b> {req['classe']}</li>
                                <li><b>Identifiant :</b> {ident_envoyes}</li>
                                <li><b>Mot de passe :</b> <code style="background:#f4f4f4;padding:2px 5px;border-radius:4px;">{codes_envoyes}</code></li>
                            </ul>
                            <br><p>Cordialement,<br><b>L'équipe Numérique - Saint Charles</b></p>
                        </body></html>"""
                        if envoyer_email_reel(f"Codes {req['plateforme']} - {req['nom'].upper()}", corps_mdp, req['prof']):
                            supabase.table("eleves").update({
                                "id_ed": new_id_ed, "mdp_ed": new_mdp_ed, "id_mail": new_id_mail,
                                "mdp_mail": new_mdp_mail, "id_pix": new_id_pix, "mdp_pix": new_mdp_pix
                            }).eq("id", req['eleve_id']).execute()
                            supabase.table("demandes").update({"statut": "Traité"}).eq("id", req['id_demande']).execute()
                            invalidate_cache()
                            st.rerun()


# ==========================================
# 🗄️ HISTORIQUE MDP
# ==========================================
elif is_admin and menu == "🗄️ Historique des MdP":
    st.title("🗄️ Historique MdP")
    st.info("Cochez la case 'Sélection' pour supprimer un vieux ticket de l'historique.")

    df_h = fetch_table("demandes", select_cols="*, eleves(nom, prenom)", order_col="id")
    df_h = df_h.sort_values("id", ascending=False) if not df_h.empty else df_h

    flat_list = []
    for _, d in df_h.iterrows():
        row = {"ticket_id": d["id"], "date_demande": d["date_demande"], "prof": d["prof"], "plateforme": d["plateforme"]}
        if isinstance(d.get("eleves"), dict):
            row["nom"] = d["eleves"]["nom"]
            row["prenom"] = d["eleves"]["prenom"]
        flat_list.append(row)

    df_hist = pd.DataFrame(flat_list).fillna("")

    if not df_hist.empty:
        df_hist.insert(0, "🗑️ Sélection", False)
        edited_h = st.data_editor(df_hist, hide_index=True, use_container_width=True,
                                  disabled=["ticket_id", "date_demande", "nom", "prenom", "prof", "plateforme"])
        tickets_a_supprimer = edited_h[edited_h["🗑️ Sélection"] == True]["ticket_id"].tolist()
        if tickets_a_supprimer:
            st.warning(f"⚠️ Vous êtes sur le point de supprimer {len(tickets_a_supprimer)} ticket(s).")
            if st.button("🗑️ Confirmer la suppression", type="primary"):
                for tid in tickets_a_supprimer:
                    supabase.table("demandes").delete().eq("id", tid).execute()
                invalidate_cache()
                st.success("✅ Tickets supprimés.")
                time.sleep(1.5)
                st.rerun()
    else:
        st.success("L'historique est vide.")


# ==========================================
# 👥 ANNUAIRE, ÉDITION & PDF (ADMIN)
# ==========================================
elif is_admin and menu == "👥 Annuaire, Édition & PDF":
    st.title("👥 Annuaire, Édition & PDF")
    tab_liste, tab_impr, tab_masse = st.tabs(["📋 Liste des élèves", "🖨️ Impression des codes PDF", "📝 Édition en Masse (Départs & iPad)"])

    with tab_liste:
        df_all = fetch_table("eleves", eq_col="est_parti", eq_val=0, order_col="classe")
        if not df_all.empty:
            df_all = df_all.sort_values(by=["classe", "nom"])
            df_all.insert(5, 'Code iPad', df_all['date_naissance'].apply(calculer_code_ipad))
            cols_to_show = ["id", "nom", "prenom", "classe", "Code iPad", "pp", "date_entree",
                            "id_ed", "mdp_ed", "id_mail", "mdp_mail", "id_pix", "mdp_pix"]
            existing_cols = [c for c in cols_to_show if c in df_all.columns]
            st.dataframe(df_all[existing_cols], use_container_width=True, hide_index=True)
            st.download_button("📥 Exporter l'annuaire complet (CSV)", df_all.to_csv(index=False).encode('utf-8'), "annuaire_eleves.csv")

    with tab_impr:
        # --- NOUVEAU : Message de succès après validation ---
        if "msg_integration" in st.session_state:
            st.success(st.session_state.pop("msg_integration"))
            
        st.markdown("### 🖨️ Générateur de fiches d'identifiants")
        st.info("💡 Le document généré s'ouvrira automatiquement pour impression (enregistrable en PDF).")
        c_choix1, c_choix2 = st.columns(2)
        type_impression = c_choix1.radio("Imprimer pour :", ["Une classe complète", "Un seul élève", "✨ Tous les NOUVEAUX élèves (Rentrée)"])

        df_print = pd.DataFrame()
        cible = ""

        # --- OPTIMISATION 8 : Réutilisation du cache élèves plutôt que nouvelles requêtes ---
        df_actifs_print = fetch_table("eleves", eq_col="est_parti", eq_val=0)

        if type_impression == "Une classe complète":
            classes_print = sorted(df_actifs_print['classe'].dropna().unique().tolist()) if not df_actifs_print.empty else []
            cible = c_choix2.selectbox("Choisir la classe :", options=classes_print)
            df_print = df_actifs_print[df_actifs_print['classe'] == cible].sort_values("nom") if not df_actifs_print.empty else pd.DataFrame()

        elif type_impression == "Un seul élève":
            if not df_actifs_print.empty:
                df_e = df_actifs_print.sort_values("nom")
                liste_eleves = [f"{r['nom']} {r['prenom']} ({r['classe']})" for _, r in df_e.iterrows()]
                cible = c_choix2.selectbox("Choisir l'élève :", options=liste_eleves)
                idx = liste_eleves.index(cible)
                eleve_id = int(df_e.iloc[idx]['id'])
                df_print = df_e[df_e['id'] == eleve_id]

        elif type_impression == "✨ Tous les NOUVEAUX élèves (Rentrée)":
            c_choix2.success("Sélectionne tous les nouveaux arrivants détectés.")
            cible = "Nouveaux_Eleves_Rentree"
            df_print_raw = fetch_table("eleves", eq_col="est_nouveau", eq_val=1)
            df_print = df_print_raw[df_print_raw['est_parti'] == 0].sort_values(["classe", "nom"]) if not df_print_raw.empty else pd.DataFrame()

        st.markdown("---")
        # --- NOUVEAUTÉ : Checkbox pour imprimer la convention format A4 ---
        print_conv = st.checkbox("📄 Imprimer la Convention de prêt iPad (Format A4)", value=(type_impression == "✨ Tous les NOUVEAUX élèves (Rentrée)"), key="admin_p_conv")
        
        st.write("")
        st.markdown("**Quels identifiants inclure sur la fiche cartonnée ?**")
        col_ed, col_dr, col_px, col_prov, col_ipad = st.columns(5)
        print_ed = col_ed.checkbox("🔵 ED (Définitifs)", value=True, key="admin_p_ed")
        print_dr = col_dr.checkbox("🟡 Drive", value=True, key="admin_p_dr")
        print_px = col_px.checkbox("🟣 Pix", value=True, key="admin_p_px")
        print_prov = col_prov.checkbox("🟠 ED (Provisoires)", value=(type_impression == "✨ Tous les NOUVEAUX élèves (Rentrée)"), key="admin_p_prov")
        print_ipad = col_ipad.checkbox("📱 Code iPad", value=True, key="admin_p_ipad")

        if st.button("📄 Générer la fiche à imprimer", type="primary"):
            if not print_ed and not print_dr and not print_px and not print_prov and not print_ipad and not print_conv:
                st.error("❌ Sélectionnez au moins un document ou identifiant à imprimer.")
            elif df_print.empty:
                st.warning("⚠️ Aucun élève trouvé.")
            else:
                html_content = generer_pdf_html(cible, df_print, print_ed, print_dr, print_px, print_prov, print_ipad, print_conv)
                b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
                href = f'<a href="data:text/html;base64,{b64}" download="Identifiants_{cible.replace(" ", "_")}.html" target="_blank" style="display: inline-block; padding: 12px 24px; background-color: #2ecc71; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; margin-top: 10px;">👉 Ouvrir la fiche pour l\'impression PDF</a>'
                st.markdown(href, unsafe_allow_html=True)

        # --- AJOUT : Bouton de validation (Uniquement pour le mode Nouveaux) ---
        if type_impression == "✨ Tous les NOUVEAUX élèves (Rentrée)" and not df_print.empty:
            st.markdown("---")
            st.warning("⚠️ **Action de fin de traitement :**")
            st.write("Si vous avez terminé d'imprimer vos fiches, cliquez sur le bouton ci-dessous. Cela enlèvera le marqueur 'Nouveau' de ces élèves pour qu'ils ne polluent plus vos prochains exports.")
            
            if st.button("✅ Valider l'intégration des nouveaux (Remise à zéro)"):
                with st.spinner("Mise à jour des dossiers en cours..."):
                    # Récupère la liste des IDs affichés
                    ids_a_valider = df_print['id'].tolist()
                    # Met à jour est_nouveau à 0 pour chacun
                    for eid in ids_a_valider:
                        supabase.table("eleves").update({"est_nouveau": 0}).eq("id", eid).execute()
                
                invalidate_cache()
                st.session_state["msg_integration"] = f"✨ Terminé ! {len(ids_a_valider)} élèves sont maintenant intégrés officiellement."
                st.rerun()

    with tab_masse:
        st.markdown("### 📝 Édition Masse (Statut Matériel & Restitution)")
        
        # --- NOUVEAU : Affichage persistant du message après le rerun ---
        if "msg_masse" in st.session_state:
            st.success(st.session_state.pop("msg_masse"))
            
        voir_partis = st.checkbox("👁️ Afficher UNIQUEMENT les élèves partis")
        est_p_val = 1 if voir_partis else 0
        df_mass = fetch_table("eleves", eq_col="est_parti", eq_val=est_p_val)

        if not df_mass.empty:
            df_mass = df_mass.sort_values(by=["classe", "nom"])
            cols = ["id", "nom", "prenom", "classe", "statut_ipad", "restitution"]
            existing_cols = [c for c in cols if c in df_mass.columns]
            edited_df = st.data_editor(
                df_mass[existing_cols],
                column_config={
                    "id": None,
                    "statut_ipad": st.column_config.SelectboxColumn("Contrat", options=["Achat", "Location", "Fratrie", "Parti"]),
                    "restitution": st.column_config.TextColumn("Notes Restitution")
                },
                use_container_width=True, hide_index=True
            )
            if st.button("💾 Sauvegarder"):
                modifs_count = 0
                with st.spinner("Enregistrement en cours..."):
                    for i, row in edited_df.iterrows():
                        orig_row = df_mass.iloc[i]
                        new_statut = str(row['statut_ipad']).strip() if pd.notna(row['statut_ipad']) else ""
                        orig_statut = str(orig_row['statut_ipad']).strip() if pd.notna(orig_row['statut_ipad']) else ""
                        new_rest = str(row['restitution']).strip() if pd.notna(row['restitution']) else ""
                        orig_rest = str(orig_row['restitution']).strip() if pd.notna(orig_row['re
