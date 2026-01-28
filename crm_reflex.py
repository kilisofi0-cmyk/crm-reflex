"""
CRM Mediabuying - Reflex Version
Clean, professional CRM for managing ad campaigns
"""

import reflex as rx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional
import os

# ===========================
# CONFIGURATION
# ===========================

class Config:
    DB_FILE = "crm_data.csv"
    USERS = {
        "admin": {"password": "admin123", "role": "Head"},
        "buyer1": {"password": "buyer123", "role": "Buyer"}
    }

# ===========================
# DATA MODELS
# ===========================

class Campaign(rx.Base):
    name: str
    spend: float
    impressions: int
    clicks: int
    registrations: int
    ftd: int
    deposits: float
    roi: float
    date: str

# ===========================
# HELPER FUNCTIONS
# ===========================

def clean_numeric(series):
    """Clean numeric data"""
    return pd.to_numeric(
        series.astype(str).str.replace(r'[^\d.-]', '', regex=True), 
        errors='coerce'
    ).fillna(0)

def clean_adset_name(name):
    """Clean adset name"""
    if pd.isna(name):
        return "Другое"
    
    name_str = str(name).strip()
    name_lower = name_str.lower()
    
    # Validate
    is_valid = 'adset' in name_lower or (name_str.count('-') >= 5 and len(name_str) >= 30)
    
    if not is_valid:
        return "Другое"
    
    # Clean to -reg
    if '-reg' in name_str:
        reg_pos = name_str.find('-reg')
        name_str = name_str[:reg_pos + 4]
    elif ' ' in name_str:
        name_str = name_str.split(' ')[0]
    
    return name_str.strip() if len(name_str) >= 20 else "Другое"

def read_file(file_path: str, skiprows=0):
    """Read CSV/Excel files"""
    file_name = os.path.basename(file_path).lower()
    
    try:
        if file_name.endswith('.csv'):
            return pd.read_csv(file_path, skiprows=skiprows)
        elif file_name.endswith(('.xlsx', '.xls')):
            if any(kw in file_name for kw in ['отчет', 'звіт', 'report']):
                for skip in [7, 4, 5, 6, skiprows, 0]:
                    try:
                        df = pd.read_excel(file_path, skiprows=skip)
                        if df is not None and len(df) > 0:
                            return df
                    except:
                        continue
            else:
                return pd.read_excel(file_path, skiprows=skiprows)
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

def calculate_metrics(df):
    """Calculate all metrics"""
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
    """Load database"""
    try:
        return pd.read_csv(Config.DB_FILE)
    except:
        return pd.DataFrame()

def save_db(df):
    """Save database"""
    df.to_csv(Config.DB_FILE, index=False)

# ===========================
# STATE MANAGEMENT
# ===========================

class State(rx.State):
    """Main application state"""
    
    # Authentication
    is_authenticated: bool = False
    username: str = ""
    role: str = ""
    login_error: str = ""
    
    # Navigation
    current_page: str = "upload"
    
    # Upload
    upload_date: str = str(datetime.now().date())
    upload_status: str = ""
    upload_success: bool = False
    
    # Analytics
    campaigns: List[Campaign] = []
    selected_date: str = ""
    search_query: str = ""
    total_spend: float = 0
    total_regs: int = 0
    total_ftd: int = 0
    total_deposits: float = 0
    avg_roi: float = 0
    
    def login(self, username: str, password: str):
        """Handle login"""
        if username in Config.USERS and Config.USERS[username]["password"] == password:
            self.is_authenticated = True
            self.username = username
            self.role = Config.USERS[username]["role"]
            self.login_error = ""
            self.current_page = "upload"
        else:
            self.login_error = "Неверный логин или пароль"
    
    def logout(self):
        """Handle logout"""
        self.is_authenticated = False
        self.username = ""
        self.role = ""
        self.current_page = "upload"
    
    def navigate(self, page: str):
        """Navigate to page"""
        self.current_page = page
    
    def load_analytics(self):
        """Load analytics data"""
        db = load_db()
        
        if not db.empty:
            # Filter by date if selected
            if self.selected_date:
                db = db[db['Report_Date'] == self.selected_date]
            
            # Filter by buyer if not head
            if self.role == "Buyer":
                db = db[db['Name'].str.contains(self.username, case=False, na=False)]
            
            # Search filter
            if self.search_query:
                db = db[db['Name'].str.contains(self.search_query, case=False, na=False)]
            
            # Calculate totals
            self.total_spend = float(db['Расход'].sum())
            self.total_regs = int(db['Reg.Panel'].sum())
            self.total_ftd = int(db['Dep.panel'].sum())
            self.total_deposits = float(db['Sum.of.dep'].sum())
            self.avg_roi = float(db['ROI ALL'].mean()) if not db.empty else 0
            
            # Convert to Campaign objects
            self.campaigns = [
                Campaign(
                    name=row['Name'],
                    spend=float(row['Расход']),
                    impressions=int(row['Показы']),
                    clicks=int(row['Клики']),
                    registrations=int(row['Reg.Panel']),
                    ftd=int(row['Dep.panel']),
                    deposits=float(row['Sum.of.dep']),
                    roi=float(row['ROI ALL']),
                    date=row['Report_Date']
                )
                for _, row in db.iterrows()
            ]

# ===========================
# STYLES
# ===========================

style = {
    "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "background": "#f8f9fa",
}

button_style = {
    "background": "#1967d2",
    "color": "white",
    "border_radius": "6px",
    "padding": "0.5rem 1.5rem",
    "border": "none",
    "cursor": "pointer",
    "_hover": {
        "background": "#1557b0"
    }
}

card_style = {
    "background": "white",
    "border": "1px solid #e0e0e0",
    "border_radius": "8px",
    "padding": "1.25rem",
    "box_shadow": "0 1px 3px rgba(0,0,0,0.05)"
}

input_style = {
    "border": "1px solid #dadce0",
    "border_radius": "6px",
    "padding": "0.5rem",
    "width": "100%",
    "_focus": {
        "border_color": "#1967d2",
        "outline": "none"
    }
}

# Will continue in next part...

# ===========================
# COMPONENTS
# ===========================

def metric_card(title: str, value: str, icon: str = "📊"):
    """Metric card component"""
    return rx.box(
        rx.vstack(
            rx.text(icon + " " + title, size="2", color="#5f6368", weight="medium"),
            rx.text(value, size="7", color="#1967d2", weight="bold"),
            spacing="1",
            align="start"
        ),
        **card_style
    )

def navbar():
    """Navigation bar"""
    return rx.box(
        rx.hstack(
            rx.heading("CRM Analytics", size="6", color="#202124"),
            rx.spacer(),
            rx.hstack(
                rx.text(f"👤 {State.username}", size="2", color="#5f6368"),
                rx.text(f"• {State.role}", size="2", color="#1967d2"),
                rx.button(
                    "🚪 Выйти",
                    on_click=State.logout,
                    size="2",
                    variant="outline"
                ),
                spacing="4"
            ),
            width="100%",
            padding="1rem 2rem",
            background="white",
            border_bottom="1px solid #e0e0e0"
        )
    )

def sidebar():
    """Sidebar menu"""
    menu_items = [
        ("upload", "📤", "Загрузка"),
        ("analytics", "📊", "Аналитика"),
        ("ai", "🤖", "AI Помощник"),
    ]
    
    if State.role == "Head":
        menu_items.append(("admin", "⚙️", "Админка"))
    
    return rx.box(
        rx.vstack(
            *[
                rx.button(
                    rx.hstack(
                        rx.text(icon, size="4"),
                        rx.text(label, size="3"),
                        spacing="2"
                    ),
                    on_click=lambda page=page: State.navigate(page),
                    variant="ghost" if State.current_page != page else "solid",
                    width="100%",
                    justify="start"
                )
                for page, icon, label in menu_items
            ],
            spacing="2",
            width="100%",
            padding="1rem"
        ),
        width="250px",
        background="white",
        border_right="1px solid #e0e0e0",
        height="100vh"
    )

# ===========================
# PAGES
# ===========================

def login_page():
    """Login page"""
    return rx.center(
        rx.box(
            rx.vstack(
                rx.heading("🔐 Вход в CRM", size="8", color="#202124"),
                rx.input(
                    placeholder="Логин",
                    id="username",
                    **input_style
                ),
                rx.input(
                    placeholder="Пароль",
                    type="password",
                    id="password",
                    **input_style
                ),
                rx.button(
                    "Войти",
                    on_click=lambda: State.login(
                        rx.get_value("username"),
                        rx.get_value("password")
                    ),
                    width="100%",
                    **button_style
                ),
                rx.cond(
                    State.login_error != "",
                    rx.text(State.login_error, color="red", size="2")
                ),
                spacing="4",
                width="400px"
            ),
            **card_style,
            padding="3rem"
        ),
        height="100vh",
        background="#f8f9fa"
    )

def upload_page():
    """Upload page"""
    return rx.vstack(
        rx.heading("📤 Загрузка данных", size="7", color="#202124"),
        
        rx.hstack(
            rx.text("📅 Дата отчёта:", size="3"),
            rx.input(
                type="date",
                value=State.upload_date,
                on_change=State.set_upload_date,
                **input_style
            ),
            spacing="3"
        ),
        
        rx.divider(),
        
        rx.grid(
            rx.box(
                rx.vstack(
                    rx.heading("🔵 Facebook", size="4"),
                    rx.upload(
                        rx.button("📁 Выбрать файл", **button_style),
                        id="fb_file",
                        accept=".csv,.xlsx,.xls"
                    ),
                    spacing="3"
                ),
                **card_style
            ),
            rx.box(
                rx.vstack(
                    rx.heading("🟢 Panel", size="4"),
                    rx.upload(
                        rx.button("📁 Выбрать файл", **button_style),
                        id="panel_file",
                        accept=".csv,.xlsx,.xls"
                    ),
                    spacing="3"
                ),
                **card_style
            ),
            rx.box(
                rx.vstack(
                    rx.heading("🟡 ColdBet", size="4"),
                    rx.text("Опционально", size="1", color="#5f6368"),
                    rx.upload(
                        rx.button("📁 Выбрать файл", variant="outline"),
                        id="coldbet_file",
                        accept=".csv,.xlsx,.xls"
                    ),
                    spacing="3"
                ),
                **card_style
            ),
            columns="3",
            spacing="4",
            width="100%"
        ),
        
        rx.button(
            "💾 Загрузить и сохранить",
            size="3",
            width="100%",
            **button_style
        ),
        
        rx.cond(
            State.upload_success,
            rx.box(
                rx.text("✅ Данные успешно загружены!", color="green", size="3"),
                **card_style,
                background="#e6f4ea"
            )
        ),
        
        spacing="5",
        width="100%",
        padding="2rem"
    )

def analytics_page():
    """Analytics page"""
    return rx.vstack(
        rx.heading("📊 Аналитика кампаний", size="7", color="#202124"),
        
        # Filters
        rx.hstack(
            rx.select(
                ["2026-01-28", "2026-01-27", "2026-01-26"],
                value=State.selected_date,
                on_change=State.set_selected_date,
                placeholder="Выберите дату"
            ),
            rx.input(
                placeholder="🔍 Поиск по названию",
                value=State.search_query,
                on_change=State.set_search_query,
                **input_style
            ),
            rx.button(
                "Обновить",
                on_click=State.load_analytics,
                **button_style
            ),
            spacing="3",
            width="100%"
        ),
        
        # Dashboard
        rx.heading("📈 Общая статистика", size="5", color="#5f6368", margin_top="2rem"),
        rx.grid(
            metric_card("Расход", f"${State.total_spend:,.0f}", "💰"),
            metric_card("Реги", f"{State.total_regs:,}", "📝"),
            metric_card("FTD", f"{State.total_ftd:,}", "📈"),
            metric_card("Депы", f"${State.total_deposits:,.0f}", "💵"),
            metric_card("Ср. ROI", f"{State.avg_roi:.0f}%", "📊"),
            columns="5",
            spacing="4",
            width="100%"
        ),
        
        rx.divider(),
        
        # Table
        rx.heading("📋 Детальная таблица", size="5", color="#5f6368"),
        rx.box(
            rx.table(
                rx.thead(
                    rx.tr(
                        rx.th("Название"),
                        rx.th("Расход"),
                        rx.th("Клики"),
                        rx.th("Реги"),
                        rx.th("FTD"),
                        rx.th("Депы"),
                        rx.th("ROI"),
                    )
                ),
                rx.tbody(
                    rx.foreach(
                        State.campaigns,
                        lambda c: rx.tr(
                            rx.td(c.name),
                            rx.td(f"${c.spend:,.0f}"),
                            rx.td(f"{c.clicks:,}"),
                            rx.td(f"{c.registrations:,}"),
                            rx.td(f"{c.ftd:,}"),
                            rx.td(f"${c.deposits:,.0f}"),
                            rx.td(f"{c.roi:.0f}%"),
                        )
                    )
                ),
                variant="simple",
                width="100%"
            ),
            **card_style,
            overflow="auto",
            max_height="500px"
        ),
        
        spacing="5",
        width="100%",
        padding="2rem"
    )

def ai_page():
    """AI assistant page"""
    return rx.vstack(
        rx.heading("🤖 AI Ассистент", size="7", color="#202124"),
        rx.text("💡 Задавайте вопросы о ваших кампаниях", color="#5f6368"),
        
        rx.grid(
            rx.button("📉 Убыточные адсеты", variant="outline", width="100%"),
            rx.button("📈 Топ 5 по ROI", variant="outline", width="100%"),
            rx.button("💡 Рекомендации", variant="outline", width="100%"),
            columns="3",
            spacing="3",
            width="100%"
        ),
        
        rx.divider(),
        
        rx.box(
            rx.vstack(
                rx.text("Чат появится здесь", color="#5f6368", size="3"),
                spacing="3"
            ),
            **card_style,
            min_height="400px",
            width="100%"
        ),
        
        spacing="5",
        width="100%",
        padding="2rem"
    )

def admin_page():
    """Admin page"""
    return rx.vstack(
        rx.heading("⚙️ Администрирование", size="7", color="#202124"),
        
        rx.grid(
            rx.box(
                rx.vstack(
                    rx.heading("👥 Пользователи", size="4"),
                    rx.text("admin (Head)", size="2"),
                    rx.text("buyer1 (Buyer)", size="2"),
                    spacing="2"
                ),
                **card_style
            ),
            rx.box(
                rx.vstack(
                    rx.heading("📊 Статистика", size="4"),
                    rx.text("Записей в БД: 0", size="2"),
                    rx.text("Уникальных дат: 0", size="2"),
                    spacing="2"
                ),
                **card_style
            ),
            columns="2",
            spacing="4",
            width="100%"
        ),
        
        spacing="5",
        width="100%",
        padding="2rem"
    )

# ===========================
# MAIN APP
# ===========================

def index():
    """Main application"""
    return rx.cond(
        State.is_authenticated,
        rx.box(
            navbar(),
            rx.hstack(
                sidebar(),
                rx.box(
                    rx.match(
                        State.current_page,
                        ("upload", upload_page()),
                        ("analytics", analytics_page()),
                        ("ai", ai_page()),
                        ("admin", admin_page()),
                        upload_page()  # default
                    ),
                    flex="1",
                    overflow="auto"
                ),
                width="100%",
                height="calc(100vh - 60px)"
            ),
            width="100%",
            height="100vh"
        ),
        login_page()
    )

# Create app
app = rx.App(style=style)
app.add_page(index)

