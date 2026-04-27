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
# ttl=60 = données rafraîchies au max toutes les 60s, évite les appels répétés à chaque widget
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
            col_ed, col_dr, col_px, col_prov, col_ipad = st.columns(5)
            print_ed = col_ed.checkbox("🔵 ED (Définitifs)", value=True, key="p_ed")
            print_dr = col_dr.checkbox("🟡 Drive", value=True, key="p_dr")
            print_px = col_px.checkbox("🟣 Pix", value=True, key="p_px")
            print_prov = col_prov.checkbox("🟠 ED (Provisoires - Rentrée)", value=False, key="p_prov")
            print_ipad = col_ipad.checkbox("📱 Code iPad", value=True, key="p_ipad")

            if st.button(f"📄 Générer la fiche d'impression pour les {classe_choisie}", type="primary"):
                html_content = generer_pdf_html(classe_choisie, df_print, print_ed, print_dr, print_px, print_prov, print_ipad)
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

        st.markdown("**Quels identifiants inclure ?**")
        col_ed, col_dr, col_px, col_prov, col_ipad = st.columns(5)
        print_ed = col_ed.checkbox("🔵 ED (Définitifs)", value=True, key="admin_p_ed")
        print_dr = col_dr.checkbox("🟡 Drive", value=True, key="admin_p_dr")
        print_px = col_px.checkbox("🟣 Pix", value=True, key="admin_p_px")
        print_prov = col_prov.checkbox("🟠 ED (Provisoires)", value=(type_impression == "✨ Tous les NOUVEAUX élèves (Rentrée)"), key="admin_p_prov")
        print_ipad = col_ipad.checkbox("📱 Code iPad", value=True, key="admin_p_ipad")

        if st.button("📄 Générer la fiche à imprimer", type="primary"):
            if not print_ed and not print_dr and not print_px and not print_prov and not print_ipad:
                st.error("❌ Sélectionnez au moins un identifiant.")
            elif df_print.empty:
                st.warning("⚠️ Aucun élève trouvé.")
            else:
                html_content = generer_pdf_html(cible, df_print, print_ed, print_dr, print_px, print_prov, print_ipad)
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
                        orig_rest = str(orig_row['restitution']).strip() if pd.notna(orig_row['restitution']) else ""
                        if new_statut != orig_statut or new_rest != orig_rest:
                            parti_int = 1 if new_statut == 'Parti' else 0
                            supabase.table("eleves").update({
                                "nom": str(row['nom']).upper(), "prenom": str(row['prenom']).capitalize(),
                                "classe": str(row['classe']), "statut_ipad": new_statut,
                                "restitution": new_rest, "est_parti": parti_int
                            }).eq("id", row['id']).execute()
                            modifs_count += 1
                if modifs_count > 0:
                    invalidate_cache()
                    # --- NOUVEAU : On stocke le message avant de recharger ---
                    st.session_state["msg_masse"] = f"✅ {modifs_count} compte(s) mis à jour avec succès !"
                    st.rerun()  # Plus besoin de time.sleep, le rerun est immédiat
                else:
                    st.info("Aucune modification détectée.")


# ==========================================
# 🚛 VUE LOGISTIQUE TOTALE (ADMIN SEUL)
# ==========================================
elif is_admin and menu == "🚛 Vue Logistique Totale":
    st.title("🚛 Vue Logistique & Financière Totale")
    st.info("Ce tableau regroupe les contrats, la casse et les montants financiers pour chaque élève.")
    
    df_e = fetch_table("eleves", eq_col="est_parti", eq_val=0)
    df_i = fetch_table("incidents_ipad")
    
    if df_e.empty:
        st.warning("Aucun élève dans la base.")
    else:
        df_bilan = calculer_bilan_logistique(df_e, df_i)
        
        # Formatage pour l'affichage
        df_disp = df_bilan.rename(columns={
            'nom': 'Nom', 'prenom': 'Prénom', 'classe': 'Classe', 
            'statut_ipad': 'Contrat', 'nb_incidents': 'Nb Incidents',
            'total_sav': 'Total SAV (€)', 'loyer_annuel': 'Loyer Annuel (€)',
            'dette_totale': 'Dette Totale (€)'
        })
        
        st.dataframe(df_disp.drop(columns=['id']), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("### 📥 Export Logistique")
        st.write("Utilisez cet export pour avoir une vision globale de la facturation par élève.")
        
        # Export avec point-virgule pour Excel
        csv_data = df_disp.to_csv(index=False, sep=';').encode('utf-8')
        st.download_button("📥 Exporter le Bilan Logistique (CSV)", csv_data, "bilan_logistique_complet.csv")


# ==========================================
# 💰 COMPTA
# ==========================================
elif (is_admin or is_compta) and menu == "💰 Espace Compta & Logistique":
    st.title("💰 Suivi Comptabilité & Loyers")
    st.warning("⚠️ **RAPPEL :** Les élèves **FRATRIE** paient **15 € / an** (MDM). À leur départ : **16 €** de soulte.")

    df_c = fetch_table("eleves", eq_col="est_parti", eq_val=0, order_col="classe")
    if df_c.empty:
        st.info("Aucun élève actif.")
    else:
        df_c = df_c.sort_values(by=["classe", "nom"])
        niveaux_existants = sorted(list(set([str(c)[0] for c in df_c['classe'] if str(c)[0].isdigit()])), reverse=True)
        options_niveaux = ["Tous les élèves"] + [f"{n}ème" for n in niveaux_existants]
        filtre_niveau = st.selectbox("📂 Filtrer par niveau :", options_niveaux)
        if filtre_niveau != "Tous les élèves":
            chiffre_niveau = filtre_niveau[0]
            df_c = df_c[df_c['classe'].astype(str).str.startswith(chiffre_niveau)]

        df_c['Mensualité (€)'] = df_c.apply(lambda r: calculer_mensualite_ipad(r['classe'], r['statut_ipad'])[0], axis=1)
        df_c['Action Spéciale'] = df_c['statut_ipad'].apply(lambda s: "🚨 PRÉLEVER 15€/AN" if s == "Fratrie" else "-")
        df_c['Solde SI Rendu'] = df_c.apply(lambda r: calculer_solde_depart(r['classe'], True, r['statut_ipad']), axis=1)
        df_c['Solde SI Gardé'] = df_c.apply(lambda r: calculer_solde_depart(r['classe'], False, r['statut_ipad']), axis=1)
        cols_to_show = ["nom", "prenom", "classe", "statut_ipad", "Mensualité (€)", "Action Spéciale", "Solde SI Rendu", "Solde SI Gardé"]
        st.dataframe(df_c[cols_to_show], use_container_width=True, hide_index=True)
        st.download_button("📥 Exporter le tableau", df_c[cols_to_show].to_csv(index=False).encode('utf-8'), "compta_ipads.csv")


# ==========================================
# 📦 RESTITUTIONS (FIN D'ANNÉE)
# ==========================================
elif (is_admin or is_compta) and menu == "📦 Restitutions (Fin d'année)":
    st.title("📦 Restitutions & Sorties MDM (Fin d'année)")
    st.info("📋 Seuls les élèves de **3ème** sont listés ici avec l'action à réaliser avant leur départ.")

    df_rest = fetch_table("eleves", eq_col="est_parti", eq_val=0)
    if not df_rest.empty:
        df_rest = df_rest[df_rest['classe'].astype(str).str.startswith("3")].sort_values(by=["classe", "nom"])

    if df_rest.empty:
        st.success("Aucun élève de 3ème à traiter.")
    else:
        df_rest['Action Requise'] = df_rest['statut_ipad'].apply(
            lambda s: "📥 Récupérer l'iPad" if s == 'Location' else "🔓 Réinitialiser (Sortie MDM)"
        )
        c1, c2 = st.columns(2)
        c1.metric("📥 iPads à récupérer (Locations)", len(df_rest[df_rest['statut_ipad'] == 'Location']))
        c2.metric("🔓 iPads à libérer du MDM", len(df_rest[df_rest['statut_ipad'] != 'Location']))
        cols_to_show = ["nom", "prenom", "classe", "statut_ipad", "Action Requise"]
        st.dataframe(df_rest[cols_to_show], use_container_width=True, hide_index=True)
        st.download_button("📥 Exporter la liste de fin d'année", df_rest[cols_to_show].to_csv(index=False).encode('utf-8'), "actions_ipads_3eme.csv")


# ==========================================
# 🛠️ HISTORIQUE SAV GLOBAL
# ==========================================
elif is_admin and menu == "🛠️ Historique SAV iPad":
    st.title("🛠️ Historique SAV")
    st.info("Cochez la case 'Sélection' pour supprimer un incident de l'historique.")

    df_sav = fetch_table("incidents_ipad", select_cols="*, eleves(nom, prenom)")
    flat_list = []
    for _, i in df_sav.iterrows():
        row = {"sav_id": i["id"], "date_incident": i["date_incident"], "type_incident": i["type_incident"], "montant": i["montant"]}
        if isinstance(i.get("eleves"), dict):
            row["Nom"] = i["eleves"]["nom"]
            row["Prénom"] = i["eleves"]["prenom"]
        flat_list.append(row)

    df_sav_flat = pd.DataFrame(flat_list).fillna("")

    if not df_sav_flat.empty:
        df_sav_flat.insert(0, "🗑️ Sélection", False)
        cols_ordre = ["🗑️ Sélection", "Nom", "Prénom", "date_incident", "type_incident", "montant"]
        df_display = df_sav_flat[cols_ordre]
        edited_sav = st.data_editor(df_display, hide_index=True, use_container_width=True,
                                    disabled=["Nom", "Prénom", "date_incident", "type_incident", "montant"])

        st.markdown("---")
        df_export_sav = df_sav_flat.drop(columns=["🗑️ Sélection", "sav_id"], errors='ignore')
        df_export_sav = df_export_sav.rename(columns={"date_incident": "Date", "type_incident": "Type d'incident", "montant": "Montant"})
        cols_export = [c for c in ["Nom", "Prénom", "Date", "Type d'incident", "Montant"] if c in df_export_sav.columns]
        st.download_button("📥 Exporter l'historique SAV complet (CSV)",
                           df_export_sav[cols_export].to_csv(index=False, sep=';').encode('utf-8'),
                           "historique_sav_complet.csv")
        st.markdown("---")

        sav_a_supprimer = edited_sav[edited_sav["🗑️ Sélection"] == True].index.tolist()
        if sav_a_supprimer:
            st.warning(f"⚠️ Suppression de {len(sav_a_supprimer)} incident(s).")
            if st.button("🗑️ Confirmer la suppression", type="primary"):
                for idx in sav_a_supprimer:
                    sid_to_del = df_sav_flat.iloc[idx]["sav_id"]
                    supabase.table("incidents_ipad").delete().eq("id", sid_to_del).execute()
                invalidate_cache()
                st.success("✅ Incidents supprimés.")
                time.sleep(1.5)
                st.rerun()
    else:
        st.success("L'historique est vide.")


# ==========================================
# ⚙️ MAINTENANCE & NETTOYAGE (ADMIN)
# ==========================================
elif is_admin and menu == "⚙️ Maintenance & Nettoyage":
    st.title("⚙️ Maintenance de la Base Cloud")
    tab_import, tab_import_sav, tab_import_ipad, tab_nettoyage = st.tabs([
        "📥 Importation CSV", "📥 Import SAV", "📥 Import Statuts iPad", "🧹 Nettoyage de la Base"
    ])

    with tab_import:
        st.markdown("""
        ### 📝 Instructions d'importation
        **Format du fichier attendu (.csv avec séparateur `;`) — 8 colonnes dans l'ordre :**
        1. **Classe** | 2. **Nom** | 3. **Prénom** | 4. **Date de Naissance**
        5. **Professeur Principal** | 6. **Date d'entrée** | 7. **ID ED Provisoire** | 8. **MDP ED Provisoire**

        **Modes :**
        - **Décoché (Import classique) :** Ajoute uniquement les nouveaux élèves.
        - **Coché (Mode Rentrée) :** Ajoute les nouveaux, met à jour les anciens, archive les absents en 'Parti'.
        """)
        st.markdown("---")
        mode_rentree = st.checkbox("🎓 Activer le Mode Rentrée")
        up = st.file_uploader("Fichier CSV", type="csv", key="up_import_eleve")

        if up and st.button("🚀 Lancer l'Import vers Supabase"):
            df_new = pd.read_csv(io.StringIO(up.getvalue().decode('utf-8')), sep=None, engine='python')
            eleves_presents_csv = []
            nb_total = len(df_new)
            nb_nouveaux = 0
            repartition = {}

            res_all = supabase.table("eleves").select("id, nom, prenom").execute()
            existing_eleves = {(nettoyeur_identifiant(r['nom']), nettoyeur_identifiant(r['prenom'])): r['id'] for r in res_all.data} if res_all.data else {}

            if mode_rentree and res_all.data:
                for r in res_all.data:
                    supabase.table("eleves").update({"est_nouveau": 0}).eq("id", r['id']).execute()

            with st.spinner("Importation en cours, veuillez patienter..."):
                for _, row in df_new.iterrows():
                    if len(row) < 3:
                        continue
                    cl = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                    n = str(row.iloc[1]).strip().upper() if pd.notna(row.iloc[1]) else ""
                    p = str(row.iloc[2]).strip().capitalize() if pd.notna(row.iloc[2]) else ""
                    dob = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ""
                    pp_val = str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else ""
                    entree_val = str(row.iloc[5]).strip() if len(row) > 5 and pd.notna(row.iloc[5]) else ""
                    id_prov = str(row.iloc[6]).strip() if len(row) > 6 and pd.notna(row.iloc[6]) else ""
                    mdp_prov = str(row.iloc[7]).strip() if len(row) > 7 and pd.notna(row.iloc[7]) else ""

                    repartition[cl] = repartition.get(cl, 0) + 1
                    n_clean = nettoyeur_identifiant(n)
                    p_clean = nettoyeur_identifiant(p)

                    if (n_clean, p_clean) not in existing_eleves:
                        id_ed, id_mail, id_pix = generer_identifiants(p, n, dob, cl)
                        res_ins = supabase.table("eleves").insert({
                            "nom": n, "prenom": p, "classe": cl, "date_naissance": dob, "pp": pp_val,
                            "date_entree": entree_val, "id_ed": id_ed, "mdp_ed": MDP_DEFAUT,
                            "id_mail": id_mail, "mdp_mail": MDP_DEFAUT, "id_pix": id_pix, "mdp_pix": MDP_DEFAUT,
                            "id_ed_prov": id_prov, "mdp_ed_prov": mdp_prov,
                            "statut_ipad": 'Achat', "est_parti": 0, "est_nouveau": 1
                        }).execute()
                        if res_ins.data:
                            eleves_presents_csv.append(res_ins.data[0]['id'])
                        nb_nouveaux += 1
                    else:
                        eleve_id = existing_eleves[(n_clean, p_clean)]
                        eleves_presents_csv.append(eleve_id)
                        supabase.table("eleves").update({"id_ed_prov": id_prov, "mdp_ed_prov": mdp_prov}).eq("id", eleve_id).execute()
                        if mode_rentree:
                            supabase.table("eleves").update({"classe": cl, "pp": pp_val, "date_entree": entree_val}).eq("id", eleve_id).execute()

            if mode_rentree and eleves_presents_csv:
                res_active = supabase.table("eleves").select("id").eq("est_parti", 0).execute()
                if res_active.data:
                    active_ids = [r['id'] for r in res_active.data]
                    ids_to_mark = [aid for aid in active_ids if aid not in eleves_presents_csv]
                    for aid in ids_to_mark:
                        supabase.table("eleves").update({"est_parti": 1, "statut_ipad": 'Parti'}).eq("id", aid).execute()

            invalidate_cache()
            st.success("✅ Importation terminée avec succès !")
            st.markdown("### 📊 Bilan")
            c_tot, c_new = st.columns(2)
            c_tot.metric("Total élèves lus", nb_total)
            c_new.metric("Vrais nouveaux détectés", nb_nouveaux)
            df_rep = pd.DataFrame(list(repartition.items()), columns=['Classe', "Nb élèves"]).sort_values('Classe')
            st.dataframe(df_rep, hide_index=True, use_container_width=True)

    with tab_import_sav:
        st.markdown("""
        ### 📥 Importation Historique SAV
        **5 colonnes :** Nom | Prénom | Date | Type d'incident | Montant
        """)
        st.markdown("---")
        up_sav = st.file_uploader("Fichier CSV (SAV)", type="csv", key="up_sav_import")
        if up_sav and st.button("🚀 Lancer l'Import SAV vers Supabase"):
            df_sav_new = pd.read_csv(io.StringIO(up_sav.getvalue().decode('utf-8')), sep=None, engine='python')
            res_el = supabase.table("eleves").select("id, nom, prenom").execute()
            map_el = {(nettoyeur_identifiant(r['nom']), nettoyeur_identifiant(r['prenom'])): r['id'] for r in res_el.data} if res_el.data else {}
            count = 0
            with st.spinner("Importation SAV en cours..."):
                for _, row in df_sav_new.iterrows():
                    if len(row) < 5:
                        continue
                    n_clean = nettoyeur_identifiant(row.iloc[0])
                    p_clean = nettoyeur_identifiant(row.iloc[1])
                    if (n_clean, p_clean) in map_el:
                        try:
                            supabase.table("incidents_ipad").insert({
                                "eleve_id": map_el[(n_clean, p_clean)],
                                "date_incident": str(row.iloc[2]).strip(),
                                "type_incident": str(row.iloc[3]).strip(),
                                "montant": int(row.iloc[4]), "envoye_compta": 1
                            }).execute()
                            count += 1
                        except Exception:
                            pass
            invalidate_cache()
            st.success(f"✅ {count} incidents SAV importés !")

    with tab_import_ipad:
        st.markdown("""
        ### 📥 Importation Statut iPad
        **3 colonnes :** Nom | Prénom | Statut iPad (Achat / Location / Fratrie / Parti)
        """)
        st.markdown("---")
        up_ipad = st.file_uploader("Fichier CSV (Statut iPad)", type="csv", key="up_ipad_import")
        if up_ipad and st.button("🚀 Lancer la mise à jour des statuts iPad"):
            df_ipad_new = pd.read_csv(io.StringIO(up_ipad.getvalue().decode('utf-8')), sep=None, engine='python')
            res_el = supabase.table("eleves").select("id, nom, prenom").execute()
            map_el = {(nettoyeur_identifiant(r['nom']), nettoyeur_identifiant(r['prenom'])): r['id'] for r in res_el.data} if res_el.data else {}
            count = 0
            with st.spinner("Mise à jour des statuts en cours..."):
                for _, row in df_ipad_new.iterrows():
                    if len(row) < 3:
                        continue
                    n_clean = nettoyeur_identifiant(row.iloc[0])
                    p_clean = nettoyeur_identifiant(row.iloc[1])
                    statut_brut = str(row.iloc[2]).strip().capitalize()
                    statut = "Achat"
                    if "Location" in statut_brut:
                        statut = "Location"
                    elif "Fratrie" in statut_brut:
                        statut = "Fratrie"
                    elif "Parti" in statut_brut:
                        statut = "Parti"
                    if (n_clean, p_clean) in map_el:
                        try:
                            parti_int = 1 if statut == 'Parti' else 0
                            supabase.table("eleves").update({"statut_ipad": statut, "est_parti": parti_int}).eq("id", map_el[(n_clean, p_clean)]).execute()
                            count += 1
                        except Exception:
                            pass
            invalidate_cache()
            st.success(f"✅ {count} statuts iPad mis à jour !")

    with tab_nettoyage:
        st.warning("⚠️ **ZONE DE DANGER :** Suppression définitive de tous les élèves marqués 'Partis' (tickets et SAV inclus).")
        if st.button("🗑️ Supprimer définitivement TOUS les élèves partis", type="primary"):
            res_partis = supabase.table("eleves").select("id").eq("est_parti", 1).execute()
            nb_suppr = len(res_partis.data) if res_partis.data else 0
            if nb_suppr > 0:
                ids = [r['id'] for r in res_partis.data]
                for pid in ids:
                    supabase.table("incidents_ipad").delete().eq("eleve_id", pid).execute()
                    supabase.table("demandes").delete().eq("eleve_id", pid).execute()
                    supabase.table("eleves").delete().eq("id", pid).execute()
                invalidate_cache()
                st.success(f"✅ {nb_suppr} élève(s) supprimés définitivement !")
            else:
                st.info("💡 Aucun élève marqué comme 'Parti'. La base est propre.")
            time.sleep(2.5)
            st.rerun()

        st.markdown("---")
        st.error("🧨 **RESET TOTAL :** Efface la totalité des élèves, tickets et SAV.")
        if st.button("🧨 Vider l'intégralité de la base de données", type="primary"):
            res_all = supabase.table("eleves").select("id").execute()
            if res_all.data:
                ids = [r['id'] for r in res_all.data]
                for pid in ids:
                    supabase.table("incidents_ipad").delete().eq("eleve_id", pid).execute()
                    supabase.table("demandes").delete().eq("eleve_id", pid).execute()
                    supabase.table("eleves").delete().eq("id", pid).execute()
                invalidate_cache()
                st.success(f"✅ Base vidée : {len(res_all.data)} élèves supprimés !")
            else:
                st.info("La base est déjà vide.")
            time.sleep(2.5)
            st.rerun()
