"""
CRM Mediabuying - Reflex Final Version
Professional, clean, working CRM
"""

import reflex as rx
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List
import os
import glob

# ===========================
# CONFIG
# ===========================

DB_FILE = "crm_data.csv"
USERS = {
    "admin": {"password": "admin123", "role": "Head"},
    "buyer1": {"password": "buyer123", "role": "Buyer"}
}

# ===========================
# HELPERS
# ===========================

def clean_numeric(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r'[^\d.-]', '', regex=True), 
        errors='coerce'
    ).fillna(0)

def clean_adset_name(name):
    if pd.isna(name):
        return "Другое"
    
    name_str = str(name).strip()
    name_lower = name_str.lower()
    
    is_valid = 'adset' in name_lower or (name_str.count('-') >= 5 and len(name_str) >= 30)
    
    if not is_valid:
        return "Другое"
    
    if '-reg' in name_str:
        reg_pos = name_str.find('-reg')
        name_str = name_str[:reg_pos + 4]
    elif ' ' in name_str:
        name_str = name_str.split(' ')[0]
    
    return name_str.strip() if len(name_str) >= 20 else "Другое"

def read_file(file_path: str):
    file_name = os.path.basename(file_path).lower()
    
    try:
        if file_name.endswith('.csv'):
            return pd.read_csv(file_path)
        elif file_name.endswith(('.xlsx', '.xls')):
            if any(kw in file_name for kw in ['отчет', 'звіт', 'report']):
                for skip in [7, 4, 5, 6, 0]:
                    try:
                        df = pd.read_excel(file_path, skiprows=skip)
                        if df is not None and len(df) > 0:
                            return df
                    except:
                        continue
            else:
                return pd.read_excel(file_path)
    except Exception as e:
        print(f"Error: {e}")
        return None

def calculate_metrics(df):
    df = df.copy()
    
    df['CPM'] = np.where(df['Показы'] > 0, (df['Расход'] / df['Показы']) * 1000, 0)
    df['CPC'] = np.where(df['Клики'] > 0, df['Расход'] / df['Клики'], 0)
    df['CTR'] = np.where(df['Показы'] > 0, (df['Клики'] / df['Показы']) * 100, 0)
    df['CPL'] = np.where(df['Reg.Panel'] > 0, df['Расход'] / df['Reg.Panel'], 0)
    df['CR%'] = np.where(df['Клики'] > 0, (df['Reg.Panel'] / df['Клики']) * 100, 0)
    df['Appr%'] = np.where(df['Reg.Panel'] > 0, (df['Dep.panel'] / df['Reg.Panel']) * 100, 0)
    df['ROAS FTD'] = np.where(df['Расход'] > 0, (df['Sum.FTD'] / df['Расход']) * 100, 0)
    df['ROAS ALL'] = np.where(df['Расход'] > 0, (df['Sum.of.dep'] / df['Расход']) * 100, 0)
    df['ROI FTD'] = df['ROAS FTD'] - 100
    df['ROI ALL'] = df['ROAS ALL'] - 100
    
    return df

def load_db():
    try:
        return pd.read_csv(DB_FILE)
    except:
        return pd.DataFrame()

def save_db(df):
    df.to_csv(DB_FILE, index=False)

# ===========================
# STATE
# ===========================

class State(rx.State):
    # Auth
    is_authenticated: bool = False
    username: str = ""
    role: str = ""
    login_error: str = ""
    
    # Nav
    current_page: str = "upload"
    
    # Upload
    upload_date: str = str(datetime.now().date())
    fb_uploaded: bool = False
    panel_uploaded: bool = False
    cb_uploaded: bool = False
    upload_success: bool = False
    upload_error: str = ""
    stats: dict = {}
    
    # Analytics
    campaigns: List[dict] = []
    dates: List[str] = []
    selected_date: str = ""
    search: str = ""
    total_spend: float = 0
    total_regs: int = 0
    total_ftd: int = 0
    total_dep: float = 0
    avg_roi: float = 0
    
    def login(self, form_data: dict):
        username = form_data.get("username", "")
        password = form_data.get("password", "")
        
        if username in USERS and USERS[username]["password"] == password:
            self.is_authenticated = True
            self.username = username
            self.role = USERS[username]["role"]
            self.login_error = ""
        else:
            self.login_error = "Неверный логин или пароль"
    
    def logout(self):
        self.is_authenticated = False
        self.username = ""
        self.role = ""
    
    def navigate(self, page: str):
        self.current_page = page
        if page == "analytics":
            self.load_analytics()
    
    async def handle_fb(self, files: List[rx.UploadFile]):
        os.makedirs("./uploads", exist_ok=True)
        for file in files:
            data = await file.read()
            with open(f"./uploads/fb_{file.filename}", "wb") as f:
                f.write(data)
            self.fb_uploaded = True
    
    async def handle_panel(self, files: List[rx.UploadFile]):
        os.makedirs("./uploads", exist_ok=True)
        for file in files:
            data = await file.read()
            with open(f"./uploads/panel_{file.filename}", "wb") as f:
                f.write(data)
            self.panel_uploaded = True
    
    async def handle_cb(self, files: List[rx.UploadFile]):
        os.makedirs("./uploads", exist_ok=True)
        for file in files:
            data = await file.read()
            with open(f"./uploads/cb_{file.filename}", "wb") as f:
                f.write(data)
            self.cb_uploaded = True
    
    def process(self):
        if not self.fb_uploaded or not self.panel_uploaded:
            self.upload_error = "Загрузите FB и Panel"
            return
        
        try:
            fb = glob.glob("./uploads/fb_*")[0] if glob.glob("./uploads/fb_*") else None
            panel = glob.glob("./uploads/panel_*")[0] if glob.glob("./uploads/panel_*") else None
            cb = glob.glob("./uploads/cb_*")[0] if glob.glob("./uploads/cb_*") else None
            
            if not fb or not panel:
                self.upload_error = "Файлы не найдены"
                return
            
            # Process
            df_fb = read_file(fb)
            df_panel = read_file(panel)
            
            # FB
            fb_col = next((c for c in df_fb.columns if 'адсет' in c.lower() or 'adset' in c.lower()), df_fb.columns[0])
            df_fb_clean = pd.DataFrame()
            df_fb_clean['Name'] = df_fb[fb_col].apply(clean_adset_name)
            
            spend_col = next((c for c in df_fb.columns if any(k in c.lower() for k in ['расход', 'spend'])), None)
            impr_col = next((c for c in df_fb.columns if 'показ' in c.lower()), None)
            click_col = next((c for c in df_fb.columns if 'клик' in c.lower()), None)
            
            df_fb_clean['Расход'] = clean_numeric(df_fb[spend_col]) if spend_col else 0
            df_fb_clean['Показы'] = clean_numeric(df_fb[impr_col]) if impr_col else 0
            df_fb_clean['Клики'] = clean_numeric(df_fb[click_col]) if click_col else 0
            
            # Panel
            panel_col = next((c for c in df_panel.columns if 'subid' in str(c).lower()), df_panel.columns[0])
            df_panel_clean = pd.DataFrame()
            df_panel_clean['Name'] = df_panel[panel_col].apply(clean_adset_name)
            
            reg_col = next((c for c in df_panel.columns if 'регистрац' in str(c).lower()), None)
            ftd_col = next((c for c in df_panel.columns if 'депозит' in str(c).lower() and '$' not in str(c)), None)
            dep_col = next((c for c in df_panel.columns if 'сумма депозит' in str(c).lower() or 'сума депозит' in str(c).lower()), None)
            
            df_panel_clean['Reg.Panel'] = clean_numeric(df_panel[reg_col]) if reg_col else 0
            df_panel_clean['Dep.panel'] = clean_numeric(df_panel[ftd_col]) if ftd_col else 0
            df_panel_clean['Sum.FTD'] = 0
            df_panel_clean['Sum.of.dep'] = clean_numeric(df_panel[dep_col]) if dep_col else 0
            
            # Merge
            merged = pd.merge(df_fb_clean, df_panel_clean, on='Name', how='outer')
            merged['Report_Date'] = self.upload_date
            merged['Install'] = 0
            
            for col in ['Расход', 'Показы', 'Клики', 'Reg.Panel', 'Dep.panel', 'Sum.FTD', 'Sum.of.dep', 'Install']:
                merged[col] = merged[col].fillna(0)
            
            merged = calculate_metrics(merged)
            
            # Save
            db = load_db()
            db = pd.concat([db, merged], ignore_index=True)
            save_db(db)
            
            self.stats = {
                "campaigns": len(merged),
                "spend": float(merged['Расход'].sum()),
                "regs": int(merged['Reg.Panel'].sum()),
                "ftd": int(merged['Dep.panel'].sum()),
                "deposits": float(merged['Sum.of.dep'].sum())
            }
            
            self.upload_success = True
            self.upload_error = ""
            
            # Cleanup
            for f in glob.glob("./uploads/*"):
                os.remove(f)
            
            self.fb_uploaded = False
            self.panel_uploaded = False
            self.cb_uploaded = False
            
        except Exception as e:
            self.upload_error = f"Ошибка: {str(e)}"
            self.upload_success = False
    
    def load_analytics(self):
        db = load_db()
        
        if db.empty:
            return
        
        self.dates = sorted(db['Report_Date'].unique().tolist(), reverse=True)
        
        if not self.selected_date and self.dates:
            self.selected_date = self.dates[0]
        
        if self.selected_date:
            db = db[db['Report_Date'] == self.selected_date]
        
        if self.role == "Buyer":
            db = db[db['Name'].str.contains(self.username, case=False, na=False)]
        
        if self.search:
            db = db[db['Name'].str.contains(self.search, case=False, na=False)]
        
        db = db.sort_values('ROI ALL', ascending=False)
        
        self.total_spend = float(db['Расход'].sum())
        self.total_regs = int(db['Reg.Panel'].sum())
        self.total_ftd = int(db['Dep.panel'].sum())
        self.total_dep = float(db['Sum.of.dep'].sum())
        self.avg_roi = float(db['ROI ALL'].mean()) if not db.empty else 0
        
        self.campaigns = db[['Name', 'Расход', 'Показы', 'Клики', 'Reg.Panel', 'Dep.panel', 'Sum.of.dep', 'ROI ALL']].to_dict('records')

# ===========================
# STYLES
# ===========================

button_style = {
    "background": "#1967d2",
    "color": "white",
    "border_radius": "6px",
    "padding": "0.5rem 1.5rem",
    "_hover": {"background": "#1557b0"}
}

card_style = {
    "background": "white",
    "border": "1px solid #e0e0e0",
    "border_radius": "8px",
    "padding": "1.25rem"
}

# ===========================
# COMPONENTS
# ===========================

def metric_card(title: str, value: str):
    return rx.box(
        rx.vstack(
            rx.text(title, size="2", color="#5f6368"),
            rx.text(value, size="6", color="#1967d2", weight="bold"),
            spacing="1"
        ),
        **card_style
    )

def navbar():
    return rx.box(
        rx.hstack(
            rx.heading("CRM Analytics", size="6"),
            rx.spacer(),
            rx.text(f"{State.username} • {State.role}", size="2"),
            rx.button("Выйти", on_click=State.logout, variant="outline"),
            width="100%",
            padding="1rem 2rem"
        ),
        background="white",
        border_bottom="1px solid #e0e0e0"
    )

def sidebar():
    items = [
        ("upload", "📤", "Загрузка"),
        ("analytics", "📊", "Аналитика"),
    ]
    
    return rx.box(
        rx.vstack(
            *[
                rx.button(
                    f"{icon} {label}",
                    on_click=lambda p=page: State.navigate(p),
                    variant="solid" if State.current_page == page else "ghost",
                    width="100%"
                )
                for page, icon, label in items
            ],
            spacing="2",
            padding="1rem"
        ),
        width="200px",
        background="white",
        border_right="1px solid #e0e0e0",
        height="100vh"
    )

# ===========================
# PAGES
# ===========================

def login():
    return rx.center(
        rx.box(
            rx.vstack(
                rx.heading("🔐 CRM Login"),
                rx.form(
                    rx.vstack(
                        rx.input(name="username", placeholder="Логин"),
                        rx.input(name="password", type="password", placeholder="Пароль"),
                        rx.button("Войти", type="submit", width="100%", **button_style),
                        spacing="3"
                    ),
                    on_submit=State.login
                ),
                rx.cond(
                    State.login_error != "",
                    rx.text(State.login_error, color="red")
                ),
                spacing="4",
                width="350px"
            ),
            **card_style,
            padding="2rem"
        ),
        height="100vh",
        background="#f8f9fa"
    )

def upload():
    return rx.vstack(
        rx.heading("📤 Загрузка", size="7"),
        
        rx.input(
            type="date",
            value=State.upload_date,
            on_change=State.set_upload_date
        ),
        
        rx.grid(
            rx.box(
                rx.vstack(
                    rx.text("🔵 Facebook"),
                    rx.upload(
                        rx.button(
                            rx.cond(State.fb_uploaded, "✅ Загружен", "Выбрать"),
                            **button_style
                        ),
                        on_drop=State.handle_fb,
                        border="2px dashed #dadce0",
                        padding="1rem"
                    ),
                    spacing="2"
                ),
                **card_style
            ),
            rx.box(
                rx.vstack(
                    rx.text("🟢 Panel"),
                    rx.upload(
                        rx.button(
                            rx.cond(State.panel_uploaded, "✅ Загружен", "Выбрать"),
                            **button_style
                        ),
                        on_drop=State.handle_panel,
                        border="2px dashed #dadce0",
                        padding="1rem"
                    ),
                    spacing="2"
                ),
                **card_style
            ),
            columns="2",
            spacing="4"
        ),
        
        rx.button(
            "Обработать",
            on_click=State.process,
            **button_style,
            width="100%"
        ),
        
        rx.cond(
            State.upload_success,
            rx.box(
                rx.text("✅ Загружено!"),
                rx.text(f"Адсетов: {State.stats.get('campaigns', 0)}"),
                rx.text(f"Расход: ${State.stats.get('spend', 0):,.0f}"),
                **card_style,
                background="#e6f4ea"
            )
        ),
        
        rx.cond(
            State.upload_error != "",
            rx.text(State.upload_error, color="red")
        ),
        
        spacing="4",
        padding="2rem"
    )

def analytics():
    return rx.vstack(
        rx.heading("📊 Аналитика", size="7"),
        
        rx.hstack(
            rx.select(State.dates, value=State.selected_date, on_change=State.set_selected_date),
            rx.input(placeholder="Поиск", value=State.search, on_change=State.set_search),
            rx.button("Обновить", on_click=State.load_analytics),
            spacing="3"
        ),
        
        rx.grid(
            metric_card("Расход", f"${State.total_spend:,.0f}"),
            metric_card("Реги", f"{State.total_regs:,}"),
            metric_card("FTD", f"{State.total_ftd:,}"),
            metric_card("Депы", f"${State.total_dep:,.0f}"),
            metric_card("ROI", f"{State.avg_roi:.0f}%"),
            columns="5",
            spacing="4"
        ),
        
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Spend"),
                        rx.table.column_header_cell("Regs"),
                        rx.table.column_header_cell("FTD"),
                        rx.table.column_header_cell("ROI"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        State.campaigns,
                        lambda c: rx.table.row(
                            rx.table.cell(c["Name"]),
                            rx.table.cell(f"${c['Расход']:,.0f}"),
                            rx.table.cell(f"{c['Reg.Panel']:,}"),
                            rx.table.cell(f"{c['Dep.panel']:,}"),
                            rx.table.cell(f"{c['ROI ALL']:.0f}%"),
                        )
                    )
                )
            ),
            **card_style,
            overflow="auto",
            max_height="600px"
        ),
        
        spacing="4",
        padding="2rem",
        on_mount=State.load_analytics
    )

def index():
    return rx.cond(
        State.is_authenticated,
        rx.box(
            navbar(),
            rx.hstack(
                sidebar(),
                rx.match(
                    State.current_page,
                    ("upload", upload()),
                    ("analytics", analytics()),
                    upload()
                ),
                height="calc(100vh - 60px)"
            )
        ),
        login()
    )

app = rx.App()
app.add_page(index)

