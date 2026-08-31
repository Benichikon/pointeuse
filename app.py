import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import io

# --- INITIALISATION DE LA BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('pointeuse.db')
    c = conn.cursor()
    # Table des employés
    c.execute('''
        CREATE TABLE IF NOT EXISTS employes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            pin TEXT UNIQUE NOT NULL
        )
    ''')
    # Table des punchs
    c.execute('''
        CREATE TABLE IF NOT EXISTS punchs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employe_id INTEGER,
            timestamp DATETIME NOT NULL,
            type_punch TEXT NOT NULL,
            manuel INTEGER DEFAULT 0,
            FOREIGN KEY(employe_id) REFERENCES employes(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FONCTIONS UTILITAIRES ---
def arrondir_quart_heure(heures):
    """Arrondit au 0.25 d'heure le plus proche (ex: 7.13 -> 7.25)"""
    return round(heures * 4) / 4

def get_dernier_punch(employe_id):
    conn = sqlite3.connect('pointeuse.db')
    c = conn.cursor()
    c.execute('SELECT type_punch FROM punchs WHERE employe_id = ? ORDER BY timestamp DESC LIMIT 1', (employe_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

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

    # Affichage du code masqué
    st.markdown(f"### Code PIN : `{'*' * len(st.session_state.pin_input)}`")

    # Clavier numérique
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
        
        conn = sqlite3.connect('pointeuse.db')
        c = conn.cursor()
        c.execute('SELECT id, nom FROM employes WHERE pin = ?', (pin,))
        emp = c.fetchone()
        
        if emp:
            emp_id, emp_nom = emp
            dernier_type = get_dernier_punch(emp_id)
            nouveau_type = "OUT" if dernier_type == "IN" else "IN"
            
            now = datetime.now()
            c.execute('INSERT INTO punchs (employe_id, timestamp, type_punch) VALUES (?, ?, ?)',
                      (emp_id, now.strftime("%Y-%m-%d %H:%M:%S"), nouveau_type))
            conn.commit()
            
            if nouveau_type == "IN":
                st.success(f"🟢 Bonjour {emp_nom} ! Punch d'ENTRÉE enregistré à {now.strftime('%H:%M:%S')}")
            else:
                st.info(f"🔴 Au revoir {emp_nom} ! Punch de SORTIE enregistré à {now.strftime('%H:%M:%S')}")
        else:
            st.error("❌ Code PIN invalide.")
        conn.close()

# ==========================================
# 2. PANNEAU D'ADMINISTRATION
# ==========================================
elif menu == "⚙️ Administration":
    st.title("⚙️ Administration")
    
    pwd = st.text_input("Mot de passe Admin", type="password")
    if pwd == "admin123":  # Mot de passe par défaut
        tab_emp, tab_corr, tab_rep = st.tabs(["👥 Employés", "✏️ Corriger Punchs", "📊 Rapports XLSX"])
        
        # TAB 1 : GESTION EMPLOYÉS
        with tab_emp:
            st.subheader("Ajouter un employé")
            with st.form("add_emp"):
                nom = st.text_input("Nom de l'employé")
                pin = st.text_input("Code PIN unique (chiffres)", type="password")
                if st.form_submit_button("Ajouter"):
                    if nom and pin:
                        try:
                            conn = sqlite3.connect('pointeuse.db')
                            c = conn.cursor()
                            c.execute('INSERT INTO employes (nom, pin) VALUES (?, ?)', (nom, pin))
                            conn.commit()
                            conn.close()
                            st.success(f"Employé {nom} ajouté !")
                        except:
                            st.error("Ce PIN est déjà utilisé.")
            
            st.subheader("Liste des employés")
            conn = sqlite3.connect('pointeuse.db')
            df_emp = pd.read_sql_query('SELECT id, nom, pin FROM employes', conn)
            conn.close()
            st.dataframe(df_emp, use_container_width=True)

        # TAB 2 : CORRECTION MANUELLE
        with tab_corr:
            st.subheader("Ajouter un punch manuel")
            conn = sqlite3.connect('pointeuse.db')
            emps = pd.read_sql_query('SELECT id, nom FROM employes', conn)
            
            if not emps.empty:
                emp_choisi = st.selectbox("Employé", emps['nom'].tolist())
                emp_id = int(emps[emps['nom'] == emp_choisi]['id'].values[0])
                date_p = st.date_input("Date", date.today())
                heure_p = st.time_input("Heure", datetime.now().time())
                type_p = st.selectbox("Type", ["IN", "OUT"])
                
                if st.button("Enregistrer le punch manuel"):
                    dt = datetime.combine(date_p, heure_p).strftime("%Y-%m-%d %H:%M:%S")
                    c = conn.cursor()
                    c.execute('INSERT INTO punchs (employe_id, timestamp, type_punch, manuel) VALUES (?, ?, ?, 1)',
                              (emp_id, dt, type_p))
                    conn.commit()
                    st.success("Punch manuel ajouté !")
            conn.close()

        # TAB 3 : RAPPORTS EXCEL (XLSX)
        with tab_rep:
            st.subheader("Générer le rapport")
            col1, col2 = st.columns(2)
            d_debut = col1.date_input("Date de début", date.today())
            d_fin = col2.date_input("Date de fin", date.today())
            
            if st.button("📊 Calculer et Générer XLSX"):
                conn = sqlite3.connect('pointeuse.db')
                query = '''
                    SELECT p.id, e.nom, p.timestamp, p.type_punch 
                    FROM punchs p 
                    JOIN employes e ON p.employe_id = e.id
                    WHERE date(p.timestamp) BETWEEN ? AND ?
                    ORDER BY e.nom, p.timestamp ASC
                '''
                df_p = pd.read_sql_query(query, conn, params=(d_debut, d_fin))
                conn.close()
                
                if not df_p.empty:
                    df_p['timestamp'] = pd.to_datetime(df_p['timestamp'])
                    
                    # Calcul des paires IN / OUT
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
                    
                    # Résumé par employé
                    df_summary = df_res.groupby('Employé').agg({
                        'Heures Réelles': 'sum',
                        'Heures Arrondies (0.25h)': 'sum'
                    }).reset_index()

                    st.markdown("### Résumé des Heures")
                    st.dataframe(df_summary, use_container_width=True)

                    # Export Excel
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
                    st.warning("Aucun punch trouvé pour cette période.")