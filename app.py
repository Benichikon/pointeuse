import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import zoneinfo
import io
import os
from supabase import create_client, Client

# --- CONFIGURATION FUSEAU HORAIRE QUEBEC ---
TZ_QUEBEC = zoneinfo.ZoneInfo("America/Toronto")

# --- CONFIGURATION PAGE ---
st.set_page_config(
    page_title="Elliott & Lily - Pointeuse", 
    page_icon="🐾", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- INJECTION CSS AVEC PALETTE ELLIOTT & LILY ---
st.markdown("""
    <style>
    /* Fond principal et typographie */
    .stApp { 
        background-color: #f4f7f6; 
    }
    
    /* Titres principaux */
    h1, h2, h3 { 
        color: #0f4c5c !important; 
        font-weight: 700 !important; 
    }
    
    /* Bannière d'en-tête */
    .banner-img {
        width: 100%;
        max-height: 220px;
        object-fit: cover;
        border-radius: 14px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    
    /* Cartes de statut (Lightspeed) */
    .status-card-in { 
        background-color: #e6f7f5; 
        border-left: 5px solid #169baa; 
        border-radius: 8px; 
        padding: 12px 16px; 
        margin-bottom: 8px; 
        color: #0f4c5c; 
        font-weight: 600; 
        font-size: 15px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }
    .status-card-out { 
        background-color: #ffffff; 
        border-left: 5px solid #cbd5e1; 
        border-radius: 8px; 
        padding: 12px 16px; 
        margin-bottom: 8px; 
        color: #64748b; 
        font-weight: 500; 
        font-size: 15px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }

    /* Bouton principal assorti */
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button {
        background-color: #169baa !important;
        color: white !important;
        border-radius: 10px !important;
        border: none !important;
        font-weight: 600 !important;
        height: 50px !important;
        font-size: 18px !important;
        transition: background-color 0.2s ease !important;
    }
    div.stFormSubmitButton > button:hover {
        background-color: #0f4c5c !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- FONCTIONS UTILITAIRES ---
def arrondir_quart_heure(heures):
    return round(heures * 4) / 4

def get_donnees_pointage():
    emps = supabase.table('employes').select('id, nom, pin').execute().data or []
    punchs = supabase.table('punchs').select('employe_id, type_punch, timestamp').order('timestamp', desc=True).limit(100).execute().data or []
    
    statuts = []
    dernier_statut_map = {}
    
    for emp in emps:
        emp_punchs = [p for p in punchs if p['employe_id'] == emp['id']]
        if emp_punchs:
            dernier = emp_punchs[0]
            try:
                dt_utc = pd.to_datetime(dernier['timestamp'], errors='coerce', utc=True)
                dt_qc = dt_utc.tz_convert(TZ_QUEBEC)
                dt_str = dt_qc.strftime('%H:%M')
            except Exception:
                dt_str = "--:--"
            statuts.append({"nom": emp['nom'], "statut": dernier['type_punch'], "heure": dt_str})
            dernier_statut_map[emp['id']] = dernier['type_punch']
        else:
            statuts.append({"nom": emp['nom'], "statut": "OUT", "heure": "--:--"})
            dernier_statut_map[emp['id']] = "OUT"
            
    return emps, statuts, dernier_statut_map

# --- MENU NAVIGATION & LOGO ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
elif os.path.exists("logo.jpg"):
    st.sidebar.image("logo.jpg", use_container_width=True)

st.sidebar.title("🐾 Elliott & Lily")
menu = st.sidebar.radio("Navigation :", ["⏱️ Pointage (iPad)", "⚙️ Administration"])

# ==========================================
# 1. ÉCRAN DE POINTAGE (IPAD)
# ==========================================
if menu == "⏱️ Pointage (iPad)":
    # Affichage de la bannière si présente
    if os.path.exists("banner.jpg"):
        st.image("banner.jpg", use_container_width=True)
    elif os.path.exists("banner.png"):
        st.image("banner.png", use_container_width=True)

    st.title("⏱️ Poinçonnage de l'Équipe")
    
    emps_data, statuts, dernier_statut_map = get_donnees_pointage()
    
    st.markdown("### 📋 Présences en direct")
    col_in_list, col_out_list = st.columns(2)
    
    with col_in_list:
        st.markdown("**🟢 En poste**")
        en_poste = [e for e in statuts if e['statut'] == 'IN']
        if en_poste:
            for emp in en_poste:
                st.markdown(f'<div class="status-card-in">🐾 {emp["nom"]} <span style="float:right; font-weight:normal; font-size:12px;">Depuis {emp["heure"]}</span></div>', unsafe_allow_html=True)
        else:
            st.caption("Aucun employé en poste.")

    with col_out_list:
        st.markdown("**🔴 Hors poste**")
        absents = [e for e in statuts if e['statut'] == 'OUT']
        if absents:
            for emp in absents:
                st.markdown(f'<div class="status-card-out">🔴 {emp["nom"]} <span style="float:right; font-weight:normal; font-size:12px;">Parti à {emp["heure"]}</span></div>', unsafe_allow_html=True)
        else:
            st.caption("Tout le monde est en poste.")

    st.divider()

    # SAISIE AU CLAVIER
    st.markdown("### 🔑 Saisissez votre PIN")
    with st.form("form_pin_clavier", clear_on_submit=True):
        pin_saisi = st.text_input("Code PIN", type="password", help="Tapez votre PIN et appuyez sur Entrée", placeholder="Code PIN...")
        valider = st.form_submit_button("✅ Valider le poinçonnage", use_container_width=True)
        
        if valider:
            if pin_saisi:
                emp_trouve = next((e for e in emps_data if str(e['pin']) == str(pin_saisi)), None)
                
                if emp_trouve:
                    emp_id = emp_trouve['id']
                    emp_nom = emp_trouve['nom']
                    dernier_type = dernier_statut_map.get(emp_id, "OUT")
                    nouveau_type = "OUT" if dernier_type == "IN" else "IN"
                    
                    now_qc = datetime.now(TZ_QUEBEC)
                    now_iso = now_qc.isoformat()
                    
                    supabase.table('punchs').insert({
                        "employe_id": emp_id,
                        "timestamp": now_iso,
                        "type_punch": nouveau_type
                    }).execute()
                    
                    now_str = now_qc.strftime('%H:%M:%S')
                    if nouveau_type == "IN":
                        st.success(f"🟢 **Bonjour {emp_nom} !** Punch d'entrée enregistré à {now_str}")
                    else:
                        st.info(f"🔴 **Au revoir {emp_nom} !** Punch de sortie enregistré à {now_str}")
                    st.rerun()
                else:
                    st.error("❌ Code PIN incorrect.")

# ==========================================
# 2. PANNEAU D'ADMINISTRATION
# ==========================================
elif menu == "⚙️ Administration":
    st.title("⚙️ Gestion & Rapports")
    
    pwd = st.text_input("Mot de passe administrateur", type="password")
    if pwd == "admin123":
        tab_emp, tab_corr, tab_sup, tab_rep = st.tabs([
            "👥 Employés", 
            "➕ Ajouter un Quart", 
            "🗑️ Gérer Punchs", 
            "📊 Exporter Excel"
        ])
        
        with tab_emp:
            st.subheader("Créer un nouvel employé")
            with st.form("add_emp", clear_on_submit=True):
                nom = st.text_input("Nom complet")
                pin = st.text_input("Code PIN confidentiel", type="password")
                if st.form_submit_button("Créer l'employé"):
                    if nom and pin:
                        try:
                            supabase.table('employes').insert({"nom": nom, "pin": pin}).execute()
                            st.success(f"Employé {nom} ajouté !")
                            st.rerun()
                        except Exception:
                            st.error("Erreur : ce code PIN est déjà attribué.")
            
            st.divider()
            st.subheader("Liste des employés actifs")
            emps = supabase.table('employes').select('id, nom, pin').execute()
            if emps.data:
                st.dataframe(pd.DataFrame(emps.data), use_container_width=True)

        with tab_corr:
            st.subheader("Saisie manuelle d'un quart complet")
            emps = supabase.table('employes').select('id, nom').execute()
            
            if emps.data:
                emp_dict = {e['nom']: e['id'] for e in emps.data}
                emp_choisi = st.selectbox("Employé", list(emp_dict.keys()), key="select_emp_quart")
                date_p = st.date_input("Date du quart", date.today())
                
                col_in, col_out = st.columns(2)
                heure_in = col_in.time_input("Heure d'arrivée (IN)", time(9, 0))
                heure_out = col_out.time_input("Heure de départ (OUT)", time(17, 0))
                
                if st.button("➕ Enregistrer le quart"):
                    dt_in = datetime.combine(date_p, heure_in).replace(tzinfo=TZ_QUEBEC).isoformat()
                    dt_out = datetime.combine(date_p, heure_out).replace(tzinfo=TZ_QUEBEC).isoformat()
                    
                    supabase.table('punchs').insert({"employe_id": emp_dict[emp_choisi], "timestamp": dt_in, "type_punch": "IN", "manuel": 1}).execute()
                    supabase.table('punchs').insert({"employe_id": emp_dict[emp_choisi], "timestamp": dt_out, "type_punch": "OUT", "manuel": 1}).execute()
                    
                    st.success(f"Quart ajouté pour {emp_choisi} !")

        with tab_sup:
            st.subheader("Derniers poinçonnages")
            punch_data = supabase.table('punchs').select('id, timestamp, type_punch, employes(nom)').order('timestamp', desc=True).limit(50).execute()
            
            if punch_data.data:
                records = []
                for row in punch_data.data:
                    try:
                        dt_utc = pd.to_datetime(row['timestamp'], errors='coerce', utc=True)
                        dt_qc = dt_utc.tz_convert(TZ_QUEBEC).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        dt_qc = row['timestamp']

                    records.append({
                        'Supprimer': False,
                        'ID': row['id'],
                        'Employé': row['employes']['nom'] if row.get('employes') else 'Inconnu',
                        'Horodatage': dt_qc,
                        'Action': row['type_punch']
                    })
                
                df_view = pd.DataFrame(records)
                
                edited_df = st.data_editor(
                    df_view,
                    column_config={
                        "Supprimer": st.column_config.CheckboxColumn(
                            "Sélectionner",
                            help="Cochez pour supprimer",
                            default=False,
                        )
                    },
                    disabled=["ID", "Employé", "Horodatage", "Action"],
                    hide_index=True,
                    use_container_width=True
                )
                
                to_delete_ids = edited_df[edited_df['Supprimer'] == True]['ID'].tolist()
                
                if to_delete_ids:
                    st.warning(f"⚠️ {len(to_delete_ids)} ligne(s) sélectionnée(s) : ID {to_delete_ids}")
                    if st.button("🗑️ Confirmer la suppression"):
                        for p_id in to_delete_ids:
                            supabase.table('punchs').delete().eq('id', p_id).execute()
                        st.success("Punch(s) supprimé(s) avec succès !")
                        st.rerun()

        with tab_rep:
            st.subheader("Rapport de paie")
            col1, col2 = st.columns(2)
            d_debut = col1.date_input("Du", date.today())
            d_fin = col2.date_input("Au", date.today())
            
            if st.button("📊 Générer le rapport Excel"):
                data = supabase.table('punchs').select('id, timestamp, type_punch, employes(nom)').gte('timestamp', f"{d_debut}T00:00:00").lte('timestamp', f"{d_fin}T23:59:59").execute()
                
                if data.data:
                    records = []
                    for row in data.data:
                        records.append({
                            'id': row['id'],
                            'nom': row['employes']['nom'] if row.get('employes') else 'Inconnu',
                            'timestamp': row['timestamp'],
                            'type_punch': row['type_punch']
                        })
                    
                    df_p = pd.DataFrame(records)
                    df_p['timestamp'] = pd.to_datetime(df_p['timestamp'], errors='coerce', utc=True).dt.tz_convert(TZ_QUEBEC)
                    df_p = df_p.dropna(subset=['timestamp'])
                    
                    rapport = []
                    for nom, group in df_p.groupby('nom'):
                        group = group.sort_values('timestamp').reset_index(drop=True)
                        i = 0
                        while i < len(group):
                            if group.loc[i, 'type_punch'] == 'IN':
                                in_time = group.loc[i, 'timestamp']
                                out_time = None
                                if i + 1 < len(group) and group.loc[i+1, 'type_punch'] == 'OUT':
                                    out_time = group.loc[i+1, 'timestamp']
                                    i += 1
                                
                                duree_h = (out_time - in_time).total_seconds() / 3600.0 if out_time else 0
                                
                                rapport.append({
                                    "Employé": nom,
                                    "Date": in_time.strftime("%Y-%m-%d"),
                                    "Entrée": in_time.strftime("%H:%M:%S"),
                                    "Sortie": out_time.strftime("%H:%M:%S") if out_time else "MANQUANT",
                                    "Heures Réelles": round(duree_h, 2),
                                    "Heures Arrondies (0.25h)": arrondir_quart_heure(duree_h)
                                })
                            i += 1
                    
                    df_res = pd.DataFrame(rapport)
                    if not df_res.empty:
                        df_summary = df_res.groupby('Employé').agg({
                            'Heures Réelles': 'sum',
                            'Heures Arrondies (0.25h)': 'sum'
                        }).reset_index()

                        st.markdown("### Résumé de la période")
                        st.dataframe(df_summary, use_container_width=True)

                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_summary.to_excel(writer, sheet_name='Résumé', index=False)
                            df_res.to_excel(writer, sheet_name='Détail Punchs', index=False)
                        
                        st.download_button(
                            label="📥 Télécharger le fichier Excel (.xlsx)",
                            data=output.getvalue(),
                            file_name=f"rapport_heures_{d_debut}_au_{d_fin}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("Aucun quart complet trouvé sur cette période.")
                else:
                    st.warning("Aucune donnée sur cette période.")
