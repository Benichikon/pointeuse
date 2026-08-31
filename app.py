import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import io
from supabase import create_client, Client

# --- CONNEXION SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- FONCTIONS UTILITAIRES ---
def arrondir_quart_heure(heures):
    """Arrondit au 0.25 d'heure le plus proche (ex: 7.13 -> 7.25)"""
    return round(heures * 4) / 4

def get_dernier_punch(employe_id):
    res = supabase.table('punchs').select('type_punch').eq('employe_id', employe_id).order('timestamp', desc=True).limit(1).execute()
    return res.data[0]['type_punch'] if res.data else None

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="Système de Pointage", page_icon="⏱️", layout="centered")

menu = st.sidebar.radio("Navigation", ["⏱️ Pointage (PIN)", "⚙️ Administration"])

# ==========================================
# 1. ÉCRAN DE POINTAGE (EMPLOYÉS)
# ==========================================
if menu == "⏱️ Pointage (PIN)":
    st.title("⏱️ Poinçonnage")
    
    if "pin_input" not in st.session_state:
        st.session_state.pin_input = ""

    st.markdown(f"### Code PIN : `{'*' * len(st.session_state.pin_input)}`")

    col1, col2, col3 = st.columns(3)
    for i in range(1, 10):
        col = [col1, col2, col3][(i - 1) % 3]
        if col.button(str(i), key=f"btn_{i}", use_container_width=True):
            if len(st.session_state.pin_input) < 6:
                st.session_state.pin_input += str(i)
                st.rerun()

    c_eff, c_zero, c_val = st.columns(3)
    if c_eff.button("❌ Effacer", use_container_width=True):
        st.session_state.pin_input = ""
        st.rerun()
        
    if c_zero.button("0", use_container_width=True):
        if len(st.session_state.pin_input) < 6:
            st.session_state.pin_input += "0"
            st.rerun()

    if c_val.button("✅ Valider", use_container_width=True):
        pin = st.session_state.pin_input
        st.session_state.pin_input = ""
        
        emp_res = supabase.table('employes').select('id, nom').eq('pin', pin).execute()
        
        if emp_res.data:
            emp_id = emp_res.data[0]['id']
            emp_nom = emp_res.data[0]['nom']
            dernier_type = get_dernier_punch(emp_id)
            nouveau_type = "OUT" if dernier_type == "IN" else "IN"
            
            now_iso = datetime.now().isoformat()
            supabase.table('punchs').insert({
                "employe_id": emp_id,
                "timestamp": now_iso,
                "type_punch": nouveau_type
            }).execute()
            
            now_str = datetime.now().strftime('%H:%M:%S')
            if nouveau_type == "IN":
                st.success(f"🟢 Bonjour {emp_nom} ! Punch d'ENTRÉE enregistré à {now_str}")
            else:
                st.info(f"🔴 Au revoir {emp_nom} ! Punch de SORTIE enregistré à {now_str}")
        else:
            st.error("❌ Code PIN invalide.")

# ==========================================
# 2. PANNEAU D'ADMINISTRATION
# ==========================================
elif menu == "⚙️ Administration":
    st.title("⚙️ Administration")
    
    pwd = st.text_input("Mot de passe Admin", type="password")
    if pwd == "admin123":
        tab_emp, tab_corr, tab_sup, tab_rep = st.tabs(["👥 Employés", "➕ Ajouter un Quart", "🗑️ Gérer / Supprimer", "📊 Rapports XLSX"])
        
        # TAB 1 : EMPLOIÉS
        with tab_emp:
            st.subheader("Ajouter un employé")
            with st.form("add_emp"):
                nom = st.text_input("Nom de l'employé")
                pin = st.text_input("Code PIN unique (chiffres)", type="password")
                if st.form_submit_button("Ajouter"):
                    if nom and pin:
                        try:
                            supabase.table('employes').insert({"nom": nom, "pin": pin}).execute()
                            st.success(f"Employé {nom} ajouté !")
                        except Exception as e:
                            st.error("Erreur ou PIN déjà utilisé.")
            
            st.subheader("Liste des employés")
            emps = supabase.table('employes').select('id, nom, pin').execute()
            if emps.data:
                st.dataframe(pd.DataFrame(emps.data), use_container_width=True)

        # TAB 2 : AJOUTER UN QUART COMPLET (ENTRÉE + SORTIE)
        with tab_corr:
            st.subheader("Ajouter un quart de travail manuel")
            emps = supabase.table('employes').select('id, nom').execute()
            
            if emps.data:
                emp_dict = {e['nom']: e['id'] for e in emps.data}
                emp_choisi = st.selectbox("Employé", list(emp_dict.keys()), key="select_emp_quart")
                date_p = st.date_input("Date du quart", date.today())
                
                col_in, col_out = st.columns(2)
                heure_in = col_in.time_input("Heure d'entrée (IN)", time(9, 0))
                heure_out = col_out.time_input("Heure de sortie (OUT)", time(17, 0))
                
                if st.button("➕ Enregistrer le quart complet"):
                    dt_in = datetime.combine(date_p, heure_in).isoformat()
                    dt_out = datetime.combine(date_p, heure_out).isoformat()
                    
                    supabase.table('punchs').insert({
                        "employe_id": emp_dict[emp_choisi],
                        "timestamp": dt_in,
                        "type_punch": "IN",
                        "manuel": 1
                    }).execute()
                    
                    supabase.table('punchs').insert({
                        "employe_id": emp_dict[emp_choisi],
                        "timestamp": dt_out,
                        "type_punch": "OUT",
                        "manuel": 1
                    }).execute()
                    
                    st.success(f"Quart enregistré de {heure_in.strftime('%H:%M')} à {heure_out.strftime('%H:%M')} !")

        # TAB 3 : SUPPRIMER OU ÉPURER DES PUNCHS
        with tab_sup:
            st.subheader("Historique et suppression des punchs")
            punch_data = supabase.table('punchs').select('id, timestamp, type_punch, employes(nom)').order('timestamp', desc=True).limit(50).execute()
            
            if punch_data.data:
                records = []
                for row in punch_data.data:
                    records.append({
                        'ID': row['id'],
                        'Employé': row['employes']['nom'] if row.get('employes') else 'Inconnu',
                        'Date/Heure': row['timestamp'],
                        'Type': row['type_punch']
                    })
                df_view = pd.DataFrame(records)
                st.dataframe(df_view, use_container_width=True)
                
                st.markdown("---")
                id_to_delete = st.number_input("Entrer l'ID du punch à supprimer", min_value=1, step=1)
                if st.button("🗑️ Supprimer ce punch"):
                    supabase.table('punchs').delete().eq('id', id_to_delete).execute()
                    st.success(f"Punch #{id_to_delete} supprimé !")
                    st.rerun()

        # TAB 4 : EXPORTATION EXCEL
        with tab_rep:
            st.subheader("Générer le rapport")
            col1, col2 = st.columns(2)
            d_debut = col1.date_input("Date de début", date.today())
            d_fin = col2.date_input("Date de fin", date.today())
            
            if st.button("📊 Calculer et Générer XLSX"):
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
                    df_p['timestamp'] = pd.to_datetime(df_p['timestamp'], utc=True)
                    
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
                                
                                duree_h = 0
                                if out_time:
                                    duree_h = (out_time - in_time).total_seconds() / 3600.0
                                
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

                        st.markdown("### Résumé des Heures")
                        st.dataframe(df_summary, use_container_width=True)

                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_summary.to_excel(writer, sheet_name='Résumé', index=False)
                            df_res.to_excel(writer, sheet_name='Détail Punchs', index=False)
                        
                        st.download_button(
                            label="📥 Télécharger le rapport Excel (.xlsx)",
                            data=output.getvalue(),
                            file_name=f"rapport_heures_{d_debut}_au_{d_fin}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("Aucune paire de punchs complète (IN/OUT) trouvée pour générer des heures calculables.")
                else:
                    st.warning("Aucun punch trouvé pour cette période.")
