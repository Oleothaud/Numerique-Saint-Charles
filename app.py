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


# ==========================================
# 📄 GÉNÉRATEUR PDF HTML
# ==========================================
def generer_pdf_html(cible_titre, df_print, print_ed, print_dr, print_px, print_prov=False, print_ipad=True):
    html_content = f"""
    <html><head>
        <meta charset="utf-8">
        <title>Identifiants - {cible_titre}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1e3a5f; padding: 20px; }}
            .card {{ border: 2px solid #1e3a5f; border-radius: 8px; padding: 15px; margin-bottom: 15px; page-break-inside: avoid; background-color: #f9fbfd; }}
            .header {{ font-size: 16px; font-weight: bold; border-bottom: 2px solid #1e3a5f; padding-bottom: 6px; margin-bottom: 10px; }}
            .cred-row {{ font-size: 14px; margin: 6px 0; padding: 6px; background: #fff; border-radius: 5px; border-left: 4px solid; }}
            .cred-ed {{ border-color: #3498db; }} .cred-dr {{ border-color: #f1c40f; }}
            .cred-px {{ border-color: #9b59b6; }} .cred-ipad {{ border-color: #2ecc71; background-color: #f0fff4; }}
            .cred-prov {{ border-color: #e67e22; background-color: #fff3e0; }}
            .label {{ font-weight: bold; display: inline-block; width: 220px; }}
            .code {{ font-family: monospace; font-size: 15px; background: #eee; padding: 2px 6px; border-radius: 4px; }}
            .warning {{ font-size: 13px; color: #c0392b; margin-bottom: 10px; font-weight: bold; text-decoration: underline; }}
            @media print {{ body {{ padding: 0; margin: 0; }} .no-print {{ display: none; }} .card {{ border: 1px solid #000; box-shadow: none; background-color: white; }} }}
        </style>
    </head><body>
        <div class="no-print" style="background: #e74c3c; color: white; padding: 10px; text-align: center; margin-bottom: 20px; border-radius: 5px;">
            <b>Astuce :</b> Appuyez sur <b>Ctrl + P</b> (ou Cmd + P sur Mac) pour imprimer. Dans destination, choisissez "Enregistrer au format PDF".
        </div>
    """
    for _, row in df_print.iterrows():
        code_ipad = calculer_code_ipad(row['date_naissance'])
        html_content += f"""<div class="card"><div class="header">🎓 {row['nom']} {row['prenom']} - Classe : {row['classe']}</div>"""
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
        menu = st.sidebar.radio("Option :", ["💰 Espace Compta & Logistique", "🛠️ Historique SAV iPad", "📦 Restitutions (Fin d'année)"], key="side_opt_ipad")
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

# ==========================================
# 🪪 DOSSIER 360°
# ==========================================
elif is_admin and menu == "🪪 Dossier 360°":
    st.title("🪪 Dossier Élève 360°")
    search_360 = st.text_input("🔍 Rechercher un élève (Nom ou Prénom) :")
    if not search_360:
        st.info("👆 Saisissez un nom ou prénom.")
    else:
        df_360 = fetch_table("eleves")
        df_incidents_360 = fetch_table("incidents_ipad")
        search_clean = nettoyeur_identifiant(search_360)
        res = df_360[df_360['nom'].apply(nettoyeur_identifiant).str.contains(search_clean) | df_360['prenom'].apply(nettoyeur_identifiant).str.contains(search_clean)] if not df_360.empty else pd.DataFrame()

        for _, el in res.iterrows():
            status_icon = "🚩 (PARTI)" if el['est_parti'] == 1 else "🎓"
            is_expanded = (st.session_state.get("open_el_id") == str(el['id']))
            with st.expander(f"{status_icon} {el['prenom']} {el['nom']} ({el['classe']})", expanded=is_expanded):
                if is_expanded and f"msg_{el['id']}" in st.session_state:
                    st.success(st.session_state.pop(f"msg_{el['id']}"))
                
                tab_profil, tab_mdp, tab_ipad = st.tabs(["📝 Profil", "🔑 Identifiants", "📱 iPad"])
                with tab_profil:
                    with st.form(f"f_p_{el['id']}"):
                        m_nom = st.text_input("Nom", value=el['nom'])
                        m_prenom = st.text_input("Prénom", value=el['prenom'])
                        m_parti = st.checkbox("Parti", value=bool(el['est_parti']))
                        if st.form_submit_button("💾 Sauvegarder"):
                            parti_int = 1 if m_parti else 0
                            supabase.table("eleves").update({"nom": m_nom.upper(), "prenom": m_prenom.capitalize(), "est_parti": parti_int}).eq("id", el['id']).execute()
                            invalidate_cache()
                            st.session_state["open_el_id"] = str(el['id'])
                            st.rerun()
                with tab_mdp:
                    with st.form(f"f_m_{el['id']}"):
                        m_id_ed = st.text_input("ID ED", value=el['id_ed'])
                        m_mdp_ed = st.text_input("MDP ED", value=el['mdp_ed'])
                        if st.form_submit_button("💾 Sauvegarder"):
                            supabase.table("eleves").update({"id_ed": m_id_ed, "mdp_ed": m_mdp_ed}).eq("id", el['id']).execute()
                            invalidate_cache()
                            st.session_state["open_el_id"] = str(el['id'])
                            st.rerun()

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
                "statut_ipad": 'Achat', "est_parti": 0, "est_nouveau": 1
            }).execute()
            invalidate_cache()
            st.success("Ajouté !")

# ==========================================
# 👥 ANNUAIRE, ÉDITION & PDF (ADMIN)
# ==========================================
elif is_admin and menu == "👥 Annuaire, Édition & PDF":
    st.title("👥 Annuaire, Édition & PDF")
    tab_liste, tab_impr, tab_masse = st.tabs(["📋 Liste", "🖨️ Impression PDF", "📝 Édition en Masse"])

    with tab_liste:
        df_all = fetch_table("eleves", eq_col="est_parti", eq_val=0, order_col="classe")
        if not df_all.empty:
            st.dataframe(df_all, use_container_width=True, hide_index=True)

    with tab_impr:
        # Message persistant
        if "msg_integration" in st.session_state:
            st.success(st.session_state.pop("msg_integration"))

        c_choix1, c_choix2 = st.columns(2)
        type_impression = c_choix1.radio("Imprimer pour :", ["Une classe complète", "Un seul élève", "✨ Tous les NOUVEAUX élèves (Rentrée)"])
        
        df_actifs_print = fetch_table("eleves", eq_col="est_parti", eq_val=0)
        df_print = pd.DataFrame()
        cible = ""

        if type_impression == "Une classe complète":
            classes_print = sorted(df_actifs_print['classe'].dropna().unique().tolist()) if not df_actifs_print.empty else []
            cible = c_choix2.selectbox("Choisir la classe :", options=classes_print)
            df_print = df_actifs_print[df_actifs_print['classe'] == cible].sort_values("nom") if not df_actifs_print.empty else pd.DataFrame()
        elif type_impression == "Un seul élève":
            liste_eleves = [f"{r['nom']} {r['prenom']} ({r['classe']})" for _, r in df_actifs_print.iterrows()]
            cible = c_choix2.selectbox("Choisir l'élève :", options=liste_eleves)
            if cible:
                idx = liste_eleves.index(cible)
                df_print = df_actifs_print.iloc[[idx]]
        elif type_impression == "✨ Tous les NOUVEAUX élèves (Rentrée)":
            df_print = fetch_table("eleves", eq_col="est_nouveau", eq_val=1)
            df_print = df_print[df_print['est_parti'] == 0].sort_values(["classe", "nom"]) if not df_print.empty else pd.DataFrame()
            cible = "Nouveaux_Eleves"

        col_ed, col_dr, col_px, col_prov, col_ipad = st.columns(5)
        print_ed = col_ed.checkbox("🔵 ED Définitifs", value=True)
        print_dr = col_dr.checkbox("🟡 Drive", value=True)
        print_px = col_px.checkbox("🟣 Pix", value=True)
        print_prov = col_prov.checkbox("🟠 ED Provisoires", value=False)
        print_ipad = col_ipad.checkbox("📱 Code iPad", value=True)

        if st.button("📄 Générer la fiche à imprimer", type="primary"):
            if df_print.empty:
                st.warning("Aucun élève trouvé.")
            else:
                html_content = generer_pdf_html(cible, df_print, print_ed, print_dr, print_px, print_prov, print_ipad)
                b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
                href = f'<a href="data:text/html;base64,{b64}" download="Identifiants.html" target="_blank" style="padding:10px; background:#2ecc71; color:white; border-radius:5px;">👉 Ouvrir le PDF</a>'
                st.markdown(href, unsafe_allow_html=True)

        # --- LE BOUTON DE VALIDATION (Corrigé au bon endroit !) ---
        if type_impression == "✨ Tous les NOUVEAUX élèves (Rentrée)" and not df_print.empty:
            st.markdown("---")
            st.warning("⚠️ Action finale : Cliquez ci-dessous une fois les fiches imprimées.")
            if st.button("✅ Valider l'intégration (Remise à zéro nouveaux)"):
                ids_a_valider = df_print['id'].tolist()
                for eid in ids_a_valider:
                    supabase.table("eleves").update({"est_nouveau": 0}).eq("id", eid).execute()
                invalidate_cache()
                st.session_state["msg_integration"] = f"✨ {len(ids_a_valider)} élèves intégrés !"
                st.rerun()

    with tab_masse:
        if "msg_masse" in st.session_state:
            st.success(st.session_state.pop("msg_masse"))
        voir_partis = st.checkbox("👁️ Afficher UNIQUEMENT les partis")
        est_p_val = 1 if voir_partis else 0
        df_mass = fetch_table("eleves", eq_col="est_parti", eq_val=est_p_val)
        if not df_mass.empty:
            edited_df = st.data_editor(df_mass[["id", "nom", "prenom", "classe", "statut_ipad", "restitution"]], hide_index=True)
            if st.button("💾 Sauvegarder les modifications en masse"):
                modifs_count = 0
                for i, row in edited_df.iterrows():
                    orig = df_mass.iloc[i]
                    if row['statut_ipad'] != orig['statut_ipad'] or row['restitution'] != orig['restitution']:
                        parti_int = 1 if row['statut_ipad'] == 'Parti' else 0
                        supabase.table("eleves").update({"statut_ipad": row['statut_ipad'], "restitution": row['restitution'], "est_parti": parti_int}).eq("id", row['id']).execute()
                        modifs_count += 1
                if modifs_count > 0:
                    invalidate_cache()
                    st.session_state["msg_masse"] = f"✅ {modifs_count} comptes mis à jour !"
                    st.rerun()

# ==========================================
# ⚙️ MAINTENANCE (Reste du code identique...)
# ==========================================
elif is_admin and menu == "⚙️ Maintenance & Nettoyage":
    # (Tes onglets d'import CSV restent ici tels quels...)
    pass
