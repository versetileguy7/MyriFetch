import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import requests
from bs4 import BeautifulSoup
import os
import json
import threading
import time
from urllib.parse import unquote, quote
from PIL import Image
import urllib3
import shutil
import traceback
import subprocess # Added for opening folders on Linux
import platform   # Added for OS detection

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Silence SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PATH FIX FOR LINUX/WINDOWS/APPIMAGE ---
APP_NAME = "MyriFetch"
if os.name == 'nt':
    APP_DATA = os.path.join(os.environ['APPDATA'], APP_NAME)
else:
    APP_DATA = os.path.join(os.path.expanduser("~"), ".config", APP_NAME)

if not os.path.exists(APP_DATA):
    try:
        os.makedirs(APP_DATA, exist_ok=True)
    except Exception as e:
        print(f"Failed to create config folder: {e}")

CONFIG_FILE = os.path.join(APP_DATA, "myrient_ultimate.json")
ICON_DIR = os.path.join(APP_DATA, "icons")
# -----------------------------------

BASE_URL = "https://myrient.erista.me/files/"
NUM_THREADS = 4  # Hydra Heads

# FIXED HEADERS: Referer must match the source domain to bypass hotlink protection
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',  # Accept binary files
    'Referer': 'https://myrient.erista.me/',
    'Origin': 'https://myrient.erista.me',
    'Connection': 'keep-alive'
}

LB_NAMES = {
    "PlayStation 3": "Sony Playstation 3",
    "PlayStation 2": "Sony Playstation 2",
    "GameCube": "Nintendo GameCube",
    "Wii": "Nintendo Wii",
    "Dreamcast": "Sega Dreamcast",
    "Xbox": "Microsoft Xbox",
    "PSP": "Sony PSP",
    "PlayStation 1": "Sony Playstation",
    "SNES": "Super Nintendo (SNES)",
    "GBA": "Nintendo Game Boy Advance",
    "Nintendo DS": "Nintendo DS",
    "Nintendo 3DS": "Nintendo 3DS"
}

CONSOLES = {
    "PlayStation 3": "Redump/Sony - PlayStation 3/",
    "PlayStation 2": "Redump/Sony - PlayStation 2/",
    "GameCube": "Redump/Nintendo - GameCube - NKit RVZ [zstd-19-128k]/",
    "Wii": "Redump/Nintendo - Wii - NKit RVZ [zstd-19-128k]/",
    "Dreamcast": "Redump/Sega - Dreamcast/",
    "Xbox": "Redump/Microsoft - Xbox/",
    "PSP": "Redump/Sony - PlayStation Portable/",
    "PlayStation 1": "Redump/Sony - PlayStation/",
    "SNES": "No-Intro/Nintendo - Super Nintendo Entertainment System/",
    "GBA": "No-Intro/Nintendo - Game Boy Advance/",
    "Nintendo DS": "No-Intro/Nintendo - Nintendo DS (Decrypted)/",
    "Nintendo 3DS": "No-Intro/Nintendo - Nintendo 3DS (Decrypted)/"
}

# --- THEME DEFINITIONS ---
THEMES = {
    "Cyber Dark": {
        "bg": "#09090b", "card": "#18181b", "cyan": "#00f2ff",
        "pink": "#ff0055", "text": "#ffffff", "dim": "#71717a", "success": "#00e676"
    },
    "Dracula": {
        "bg": "#282a36", "card": "#44475a", "cyan": "#8be9fd",
        "pink": "#ff79c6", "text": "#f8f8f2", "dim": "#6272a4", "success": "#50fa7b"
    },
    "Matrix": {
        "bg": "#000000", "card": "#111111", "cyan": "#00ff41",
        "pink": "#008f11", "text": "#e0e0e0", "dim": "#333333", "success": "#003b00"
    },
    "Nord": {
        "bg": "#2e3440", "card": "#3b4252", "cyan": "#88c0d0",
        "pink": "#bf616a", "text": "#eceff4", "dim": "#4c566a", "success": "#a3be8c"
    }
}

# Default global color dictionary (will be updated in __init__)
C = THEMES["Cyber Dark"].copy()

class UltimateApp(ctk.CTk):
    def __init__(self):
        # 1. Load Config FIRST to apply theme before building UI
        self.folder_mappings = self.load_config()
        self.apply_saved_theme()

        super().__init__()
        self.title("MYRIFETCH // ROM MANAGER")
        self.geometry("1100x850") # Slightly taller for storage bar
        self.configure(fg_color=C["bg"])

        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.current_path = ""
        self.file_cache = []
        self.filtered_cache = []

        # REFACTOR: Changed from Queue to List for management capability
        self.download_list = []
        self.is_downloading = False
        self.cancel_download = False
        self.console_icons = {}
        self.current_page = 0
        self.items_per_page = 100

        self.home_widgets = []
        self.browser_widgets = []
        self.queue_widgets = []
        self.settings_widgets = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.setup_sidebar()
        self.setup_main()

        threading.Thread(target=self.icon_manager, daemon=True).start()
        self.show_home()
        self.status_txt.configure(text="Ready")
        self.net_log("System Initialized")
        try:
            self.refresh_dir("")
        except:
            pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try: return json.load(open(CONFIG_FILE, 'r'))
            except: return {}
        return {}

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f: json.dump(self.folder_mappings, f)

    def apply_saved_theme(self):
        """Checks config for saved theme and updates global C dict"""
        saved_theme = self.folder_mappings.get("app_theme", "Cyber Dark")
        if saved_theme in THEMES:
            C.update(THEMES[saved_theme])

    def change_theme(self, new_theme):
        self.folder_mappings["app_theme"] = new_theme
        self.save_config()
        messagebox.showinfo("Theme Changed", "Please restart MyriFetch to fully apply the new theme.")

    def change_default_region(self, new_region):
        self.folder_mappings["default_region"] = new_region
        self.save_config()
        # Update the browser dropdown to match the new setting immediately
        try:
            self.region_var.set(new_region)
            self.filter_list() # Re-filter list if currently viewing files
        except:
            pass

    def net_log(self, msg):
        try:
            self.after(0, lambda: self.net_status.configure(text=f"Net: {msg}"))
        except: pass

    def icon_manager(self):
        if os.path.exists(ICON_DIR):
            try: shutil.rmtree(ICON_DIR)
            except: pass

        time.sleep(0.5)
        try:
            os.makedirs(ICON_DIR, exist_ok=True)
        except: pass

        self.net_log("Connecting to LaunchBox DB...")
        lb_urls = {}
        try:
            icon_headers = HEADERS.copy()
            icon_headers['Referer'] = 'https://gamesdb.launchbox-app.com/'

            r = requests.get("https://gamesdb.launchbox-app.com/platforms/index", headers=icon_headers, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                cards = soup.find_all('div', class_='white-card')
                for card in cards:
                    title_tag = card.find('a', class_='list-item-title')
                    if not title_tag: continue
                    lb_name = title_tag.text.strip()
                    img_tag = card.find('img')
                    if img_tag and 'src' in img_tag.attrs:
                        img_url = img_tag['src']
                        for my_name, target_lb_name in LB_NAMES.items():
                            if lb_name.lower() == target_lb_name.lower():
                                lb_urls[my_name] = img_url
        except Exception as e:
            print(f"LaunchBox Scrape Error: {e}")

        for name in CONSOLES.keys():
            safe_name = "".join(x for x in name if x.isalnum()) + ".png"
            local_path = os.path.join(ICON_DIR, safe_name)
            if name in lb_urls:
                self.net_log(f"Downloading: {name}")
                try:
                    r = requests.get(lb_urls[name], headers=HEADERS, stream=True, timeout=10)
                    if r.status_code == 200:
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(1024): f.write(chunk)
                except: pass

        for name in CONSOLES.keys():
            safe_name = "".join(x for x in name if x.isalnum()) + ".png"
            local_path = os.path.join(ICON_DIR, safe_name)
            if os.path.exists(local_path) and os.path.getsize(local_path) > 500:
                try:
                    pil_img = Image.open(local_path)
                    self.console_icons[name] = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(100, 100))
                except: pass

        self.net_log("Icons Loaded")
        self.after(0, self.render_home_grid)
        self.after(3000, lambda: self.net_log("Idle"))

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#101014")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self.sidebar, text="👾 MYRIFETCH", font=("Arial", 22, "bold"), text_color="white").grid(row=0, column=0, padx=20, pady=30)

        self.btn_home = self.nav_btn("Home", 1, self.show_home)
        self.btn_browser = self.nav_btn("Browser", 2, lambda: self.show_browser())
        self.btn_queue = self.nav_btn("Downloads", 3, self.show_queue)
        self.btn_settings = self.nav_btn("Settings", 4, self.show_settings)

        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color=C["card"])
        self.status_frame.grid(row=6, column=0, padx=10, pady=(20, 5), sticky="ew")
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", text_color=C["success"], font=("Arial", 16))
        self.status_dot.pack(side="left", padx=10)
        self.status_txt = ctk.CTkLabel(self.status_frame, text="Online", text_color=C["dim"])
        self.status_txt.pack(side="left")

        self.net_status = ctk.CTkLabel(self.sidebar, text="Net: Idle", text_color=C["dim"], font=("Consolas", 10), anchor="w")
        self.net_status.grid(row=7, column=0, padx=15, pady=(0, 10), sticky="ew")

    def nav_btn(self, text, row, cmd):
        btn = ctk.CTkButton(self.sidebar, text=text, height=40, fg_color="transparent",
                            anchor="w", font=("Arial", 13, "bold"), hover_color="#27272a", command=cmd)
        btn.grid(row=row, column=0, padx=10, pady=5, sticky="ew")
        return btn

    def setup_main(self):
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # --- SEARCH & FILTER CONTAINER ---
        self.search_container = ctk.CTkFrame(self.main_area, fg_color="transparent", height=40)
        self.search_container.grid_columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()

        self.entry_search = ctk.CTkEntry(
            self.search_container,
            placeholder_text="Search (Press Enter)...",
            height=40,
            fg_color=C["card"],
            border_width=2,
            border_color=C["cyan"],
            corner_radius=20,
            text_color="white",
            textvariable=self.search_var
        )
        self.entry_search.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.entry_search.bind("<Return>", self.filter_list)

        # LOAD DEFAULT REGION FROM CONFIG
        default_region = self.folder_mappings.get("default_region", "All Regions")
        self.region_var = ctk.StringVar(value=default_region)

        self.region_filter = ctk.CTkOptionMenu(
            self.search_container,
            variable=self.region_var,
            values=["All Regions", "USA", "Europe", "Japan", "World"],
            command=self.filter_list,
            fg_color=C["card"],
            button_color=C["cyan"],
            button_hover_color=C["pink"],
            text_color="white",
            width=140,
            height=40,
            corner_radius=20
        )
        self.region_filter.grid(row=0, column=1, sticky="e")
        # ---------------------------------

        self.frame_home = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.frame_browser = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.frame_queue = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.frame_settings = ctk.CTkFrame(self.main_area, fg_color="transparent")

        # HOME TAB
        ctk.CTkLabel(self.frame_home, text="QUICK JUMP", font=("Arial", 16, "bold"), text_color=C["dim"]).pack(anchor="w", pady=10)
        self.grid_consoles = ctk.CTkScrollableFrame(self.frame_home, fg_color="transparent")
        self.grid_consoles.pack(fill="both", expand=True)
        self.bind_scroll(self.grid_consoles, self.grid_consoles)
        self.render_home_grid()

        # BROWSER TAB
        self.frame_browser.grid_rowconfigure(1, weight=1)
        self.frame_browser.grid_columnconfigure(0, weight=1)
        nav = ctk.CTkFrame(self.frame_browser, fg_color="transparent")
        nav.pack(fill="x", pady=5)
        ctk.CTkButton(nav, text="⬅ Back", width=60, fg_color=C["card"], command=self.go_up).pack(side="left")
        self.lbl_path = ctk.CTkLabel(nav, text="/", text_color=C["dim"], padx=10)
        self.lbl_path.pack(side="left")

        # --- NEW NAV BUTTONS (Open & Set) ---
        self.btn_open = ctk.CTkButton(nav, text="↗ Open", width=60, fg_color=C["card"],
                                      hover_color=C["dim"], command=self.open_current_folder)
        self.btn_open.pack(side="right", padx=(5, 0))

        self.btn_map = ctk.CTkButton(nav, text="📂 Set Folder", fg_color="transparent", border_width=1,
                                     border_color=C["cyan"], text_color=C["cyan"], command=self.set_mapping)
        self.btn_map.pack(side="right")
        # ------------------------------------

        # --- STORAGE VISUALIZER ---
        self.storage_frame = ctk.CTkFrame(self.frame_browser, fg_color="transparent", height=20)
        self.storage_frame.pack(fill="x", padx=10)
        self.storage_label = ctk.CTkLabel(self.storage_frame, text="Storage: Checking...", font=("Arial", 10), text_color=C["dim"])
        self.storage_label.pack(side="left")
        self.storage_bar = ctk.CTkProgressBar(self.storage_frame, height=8, progress_color=C["dim"])
        self.storage_bar.set(0)
        self.storage_bar.pack(side="left", fill="x", expand=True, padx=10)
        # --------------------------

        self.list_frame = ctk.CTkScrollableFrame(self.frame_browser, fg_color=C["card"])
        self.list_frame.pack(fill="both", expand=True, pady=10)
        self.bind_scroll(self.list_frame, self.list_frame)

        self.loading_frame = ctk.CTkFrame(self.frame_browser, fg_color="transparent")
        self.loading_label = ctk.CTkLabel(self.loading_frame, text="ACCESSING DATABANK...", font=("Arial", 18, "bold"), text_color=C["cyan"])
        self.loading_label.place(relx=0.5, rely=0.4, anchor="center")
        self.loading_bar = ctk.CTkProgressBar(self.loading_frame, width=300, height=20, progress_color=C["pink"], mode="indeterminate")
        self.loading_bar.place(relx=0.5, rely=0.5, anchor="center")

        self.page_controls = ctk.CTkFrame(self.frame_browser, fg_color="transparent", height=40)
        self.page_controls.pack(fill="x", pady=5)
        self.btn_prev = ctk.CTkButton(self.page_controls, text="< Previous", width=100, fg_color=C["card"], command=self.prev_page)
        self.btn_prev.pack(side="left")
        self.lbl_page = ctk.CTkLabel(self.page_controls, text="Page 1", text_color=C["dim"])
        self.lbl_page.pack(side="left", expand=True)
        self.btn_next = ctk.CTkButton(self.page_controls, text="Next >", width=100, fg_color=C["card"], command=self.next_page)
        self.btn_next.pack(side="right")

        self.btn_dl = ctk.CTkButton(self.frame_browser, text="DOWNLOAD SELECTED", height=50,
                                    fg_color=C["cyan"], text_color="black", font=("Arial", 14, "bold"),
                                    command=self.add_to_queue)
        self.btn_dl.pack(fill="x")

        # QUEUE TAB (Updated with List for Management)
        ctk.CTkLabel(self.frame_queue, text="ACTIVE DOWNLOAD", font=("Arial", 20, "bold")).pack(anchor="w", pady=10)
        self.queue_controls = ctk.CTkFrame(self.frame_queue, fg_color="transparent")
        self.queue_controls.pack(fill="x", pady=5)
        self.lbl_speed = ctk.CTkLabel(self.queue_controls, text="IDLE", font=("Consolas", 14), text_color=C["cyan"])
        self.lbl_speed.pack(side="left")
        self.btn_cancel = ctk.CTkButton(self.queue_controls, text="Cancel Download", fg_color=C["pink"],
                                        width=120, height=30, command=self.cancel_current, state="disabled")
        self.btn_cancel.pack(side="right")
        self.progress_bar = ctk.CTkProgressBar(self.frame_queue, height=15, progress_color=C["cyan"])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=10)

        self.log_box = ctk.CTkTextbox(self.frame_queue, fg_color=C["card"], font=("Consolas", 12), height=100)
        self.log_box.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(self.frame_queue, text="PENDING QUEUE", font=("Arial", 20, "bold"), text_color=C["dim"]).pack(anchor="w", pady=10)
        self.queue_list_frame = ctk.CTkScrollableFrame(self.frame_queue, fg_color=C["card"])
        self.queue_list_frame.pack(fill="both", expand=True)
        self.bind_scroll(self.queue_list_frame, self.queue_list_frame)

        # SETTINGS TAB
        ctk.CTkLabel(self.frame_settings, text="SETTINGS & PATHS", font=("Arial", 20, "bold")).pack(anchor="w", pady=10)
        self.settings_scroll = ctk.CTkScrollableFrame(self.frame_settings, fg_color=C["card"])
        self.settings_scroll.pack(fill="both", expand=True, pady=10)
        self.bind_scroll(self.settings_scroll, self.settings_scroll)

    def render_home_grid(self):
        for widget in self.home_widgets:
            try:
                widget.grid_forget()
                widget.destroy()
            except: pass
        self.home_widgets = []
        self.update_idletasks()

        MAX_COLS = 3
        self.grid_consoles.grid_columnconfigure((0,1,2), weight=1)

        GROUPS = [
            ("SONY", ["PlayStation 1", "PlayStation 2", "PSP", "PlayStation 3"]),
            ("NINTENDO", ["SNES", "GBA", "GameCube", "Nintendo DS", "Wii", "Nintendo 3DS"]),
            ("SEGA", ["Dreamcast"]),
            ("MICROSOFT", ["Xbox"])
        ]

        current_row = 0

        for group_name, console_list in GROUPS:
            header = ctk.CTkLabel(self.grid_consoles, text=group_name, font=("Arial", 14, "bold"), text_color=C["cyan"], anchor="w")
            header.grid(row=current_row, column=0, columnspan=MAX_COLS, sticky="w", padx=10, pady=(20, 5))
            self.bind_scroll(header, self.grid_consoles)
            self.home_widgets.append(header)
            current_row += 1

            col = 0
            for name in console_list:
                if name not in CONSOLES: continue
                path = CONSOLES[name]

                card = ctk.CTkButton(
                    self.grid_consoles,
                    text=f"\n{name}",
                    image=self.console_icons.get(name),
                    compound="top",
                    width=150,
                    height=150,
                    fg_color=C["card"],
                    font=("Arial", 14, "bold"),
                    hover_color=C["pink"],
                    command=lambda p=path: self.jump_to(p)
                )
                card.grid(row=current_row, column=col, padx=10, pady=10, sticky="nsew")
                self.bind_scroll(card, self.grid_consoles)
                self.home_widgets.append(card)

                col += 1
                if col >= MAX_COLS:
                    col = 0
                    current_row += 1

            if col > 0: current_row += 1

    def show_loader(self):
        self.list_frame.pack_forget()
        self.page_controls.pack_forget()
        self.btn_dl.pack_forget()
        self.loading_frame.pack(fill="both", expand=True, pady=10)
        self.loading_bar.start()

    def hide_loader(self):
        self.loading_bar.stop()
        self.loading_frame.pack_forget()
        self.list_frame.pack(fill="both", expand=True, pady=10)
        self.page_controls.pack(fill="x", pady=5)
        self.btn_dl.pack(fill="x")

    def hide_all(self):
        self.frame_home.grid_forget()
        self.frame_browser.grid_forget()
        self.frame_queue.grid_forget()
        self.frame_settings.grid_forget()
        self.search_container.grid_forget()
        self.btn_home.configure(fg_color="transparent", text_color="white")
        self.btn_browser.configure(fg_color="transparent", text_color="white")
        self.btn_queue.configure(fg_color="transparent", text_color="white")
        self.btn_settings.configure(fg_color="transparent", text_color="white")

    def show_home(self):
        self.hide_all()
        self.frame_home.grid(row=1, column=0, sticky="nsew")
        self.btn_home.configure(fg_color=C["cyan"], text_color="black")

    def show_browser(self):
        self.hide_all()
        self.search_container.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.frame_browser.grid(row=1, column=0, sticky="nsew")
        self.btn_browser.configure(fg_color=C["cyan"], text_color="black")
        # Update storage stats when entering browser
        self.update_storage_stats()

    def show_queue(self):
        self.hide_all()
        self.frame_queue.grid(row=1, column=0, sticky="nsew")
        self.btn_queue.configure(fg_color=C["cyan"], text_color="black")
        self.render_queue_list() # Update visual list

    def show_settings(self):
        self.hide_all()
        self.frame_settings.grid(row=1, column=0, sticky="nsew")
        self.btn_settings.configure(fg_color=C["cyan"], text_color="black")
        self.render_settings()

    def cancel_current(self):
        if self.is_downloading:
            self.cancel_download = True
            self.btn_cancel.configure(state="disabled", text="Stopping...")
            self.log("⚠ CANCELLATION REQUESTED...")

    def jump_to(self, path):
        self.refresh_dir(path)
        self.show_browser()

    def render_settings(self):
        for widget in self.settings_widgets:
            try: widget.destroy()
            except: pass
        self.settings_widgets = []

        # --- THEME SELECTOR ---
        theme_row = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        theme_row.pack(fill="x", pady=10)
        self.settings_widgets.append(theme_row)
        self.bind_scroll(theme_row, self.settings_scroll)

        lbl = ctk.CTkLabel(theme_row, text="APP THEME", width=150, anchor="w", font=("Arial", 13, "bold"), text_color=C["cyan"])
        lbl.pack(side="left", padx=10)
        self.bind_scroll(lbl, self.settings_scroll)

        current_theme_name = self.folder_mappings.get("app_theme", "Cyber Dark")
        self.theme_var = ctk.StringVar(value=current_theme_name)

        theme_dropdown = ctk.CTkOptionMenu(
            theme_row,
            variable=self.theme_var,
            values=list(THEMES.keys()),
            command=self.change_theme,
            fg_color=C["bg"],
            button_color=C["cyan"],
            button_hover_color=C["pink"],
            text_color="white",
            corner_radius=20
        )
        theme_dropdown.pack(side="left", padx=10)
        self.bind_scroll(theme_dropdown, self.settings_scroll)

        hint = ctk.CTkLabel(theme_row, text="(Restart Required)", text_color=C["dim"], font=("Arial", 10))
        hint.pack(side="left", padx=5)
        self.bind_scroll(hint, self.settings_scroll)

        # --- DEFAULT REGION SELECTOR ---
        region_row = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
        region_row.pack(fill="x", pady=10)
        self.settings_widgets.append(region_row)
        self.bind_scroll(region_row, self.settings_scroll)

        lbl_reg = ctk.CTkLabel(region_row, text="DEFAULT REGION", width=150, anchor="w", font=("Arial", 13, "bold"), text_color=C["cyan"])
        lbl_reg.pack(side="left", padx=10)
        self.bind_scroll(lbl_reg, self.settings_scroll)

        current_region = self.folder_mappings.get("default_region", "All Regions")
        self.default_region_var = ctk.StringVar(value=current_region)

        region_dropdown = ctk.CTkOptionMenu(
            region_row,
            variable=self.default_region_var,
            values=["All Regions", "USA", "Europe", "Japan", "World"],
            command=self.change_default_region,
            fg_color=C["bg"],
            button_color=C["cyan"],
            button_hover_color=C["pink"],
            text_color="white",
            corner_radius=20
        )
        region_dropdown.pack(side="left", padx=10)
        self.bind_scroll(region_dropdown, self.settings_scroll)

        sep = ctk.CTkFrame(self.settings_scroll, fg_color=C["dim"], height=1)
        sep.pack(fill="x", pady=10, padx=10)
        self.settings_widgets.append(sep)
        self.bind_scroll(sep, self.settings_scroll)

        for name, path in CONSOLES.items():
            row = ctk.CTkFrame(self.settings_scroll, fg_color="transparent")
            row.pack(fill="x", pady=5)
            self.settings_widgets.append(row)
            self.bind_scroll(row, self.settings_scroll)

            l1 = ctk.CTkLabel(row, text=name, width=150, anchor="w", font=("Arial", 13, "bold"))
            l1.pack(side="left", padx=10)
            self.bind_scroll(l1, self.settings_scroll)

            current = self.folder_mappings.get(path)
            path_text = current if current else "Default (Ask)"
            path_color = "white" if current else C["dim"]

            l2 = ctk.CTkLabel(row, text=path_text, text_color=path_color, anchor="w")
            l2.pack(side="left", fill="x", expand=True)
            self.bind_scroll(l2, self.settings_scroll)

            btn = ctk.CTkButton(row, text="Change", width=80, fg_color=C["bg"], border_width=1,
                          border_color=C["cyan"], text_color=C["cyan"],
                          command=lambda p=path: self.change_console_path(p))
            btn.pack(side="right", padx=10)
            self.bind_scroll(btn, self.settings_scroll)

    def change_console_path(self, path):
        d = filedialog.askdirectory(title=f"Select folder for {path}")
        if d:
            self.folder_mappings[path] = d
            self.save_config()
            self.render_settings()

    def bind_scroll(self, widget, target_frame):
        widget.bind("<Button-4>", lambda e: self._on_mouse_scroll(e, target_frame, -1))
        widget.bind("<Button-5>", lambda e: self._on_mouse_scroll(e, target_frame, 1))
        widget.bind("<MouseWheel>", lambda e: self._on_mouse_scroll(e, target_frame, 0))

    def _on_mouse_scroll(self, event, widget, direction):
        try:
            if direction == 0:
                widget._parent_canvas.yview_scroll(-1 * (event.delta // 120), "units")
            else:
                widget._parent_canvas.yview_scroll(direction, "units")
        except: pass

    def refresh_dir(self, path=None):
        self.show_loader()
        target = path if path is not None else self.current_path

        def _work():
            try:
                self.after(0, lambda: self.status_txt.configure(text="Loading..."))
                self.net_log(f"Listing: {target[:20]}...")

                clean_path = unquote(target)
                url = BASE_URL + clean_path

                try: r = self.session.get(url, timeout=15)
                except: r = self.session.get(url, timeout=15, verify=False)
                r.raise_for_status()

                soup = BeautifulSoup(r.text, 'html.parser')
                parsed = []
                for row in soup.find_all('tr'):
                    links = row.find_all('a')
                    if not links: continue
                    href = links[0].get('href')
                    name = links[0].text.strip()
                    if href in ['../', '/'] or name == "Parent Directory" or '?' in href: continue

                    is_dir = href.endswith('/')
                    size_text = ""
                    cols = row.find_all('td')
                    if len(cols) >= 2 and not is_dir:
                         for c in cols:
                             txt = c.text.strip()
                             if any(x in txt for x in ['M', 'G', 'K', 'B']) and len(txt) < 10 and txt != name:
                                 size_text = txt
                                 break

                    parsed.append({"name": unquote(name).strip('/'), "href": href, "type": "dir" if is_dir else "file", "size": size_text})

                self.current_path = target
                self.file_cache = parsed
                self.after(0, self.filter_list)
                self.after(0, self.update_map_btn)
                self.after(0, self.update_storage_stats) # Update storage when path changes
                self.after(0, lambda: self.status_txt.configure(text="Online"))
                self.net_log("Idle")

            except Exception as e:
                self.after(0, self.hide_loader)
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to load: {e}"))
                self.after(0, lambda: self.status_txt.configure(text="Error"))
                self.net_log("Network Error")

        threading.Thread(target=_work, daemon=True).start()

    def filter_list(self, *args):
        search = self.search_var.get().lower()
        try:
            region = self.region_var.get().lower()
        except:
            region = "all regions"

        filtered = []
        for i in self.file_cache:
            name_lower = i['name'].lower()

            if search and search not in name_lower:
                continue

            if i['type'] != 'dir' and region != "all regions":
                if region not in name_lower:
                    continue

            filtered.append(i)

        self.filtered_cache = filtered
        self.current_page = 0
        self.render_page()

    def render_page(self):
        self.hide_loader()
        for widget in self.browser_widgets:
            try:
                widget.pack_forget()
                widget.destroy()
            except: pass
        self.browser_widgets = []
        self.update_idletasks()

        self.lbl_path.configure(text=f"/{self.current_path}")
        self.checkboxes = []

        # --- ALREADY DOWNLOADED CHECK ---
        local_path = self.folder_mappings.get(self.current_path)

        sorted_items = sorted(self.filtered_cache, key=lambda x: (x['type'] != 'dir', x['name']))
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = sorted_items[start:end]

        total_pages = (len(sorted_items) + self.items_per_page - 1) // self.items_per_page
        if total_pages == 0: total_pages = 1
        self.lbl_page.configure(text=f"Page {self.current_page + 1} / {total_pages}")
        self.btn_prev.configure(state="normal" if self.current_page > 0 else "disabled")
        self.btn_next.configure(state="normal" if end < len(sorted_items) else "disabled")

        for item in page_items:
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            self.browser_widgets.append(row)
            self.bind_scroll(row, self.list_frame)

            if item['type'] == 'dir':
                btn = ctk.CTkButton(row, text=f"📁 {item['name']}", fg_color="transparent", anchor="w",
                              hover_color=C["pink"], command=lambda h=item['href']: self.refresh_dir(self.current_path+h))
                btn.pack(fill="x")
                self.bind_scroll(btn, self.list_frame)
            else:
                # CHECK IF FILE EXISTS LOCALLY
                is_owned = False
                if local_path:
                    if os.path.exists(os.path.join(local_path, item['name'])):
                        is_owned = True

                var = ctk.IntVar()
                text_col = C["success"] if is_owned else "white"
                display_text = f"✔ {item['name']}" if is_owned else item['name']

                chk = ctk.CTkCheckBox(row, text=display_text, variable=var, font=("Arial", 12),
                                      text_color=text_col, # Green if owned
                                      fg_color=C["cyan"], hover_color=C["pink"])
                chk.pack(side="left")
                self.bind_scroll(chk, self.list_frame)
                self.checkboxes.append((item['name'], var, item['href']))

                lbl = ctk.CTkLabel(row, text=item['size'], text_color=C["dim"])
                lbl.pack(side="right", padx=10)
                self.bind_scroll(lbl, self.list_frame)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.render_page()

    def next_page(self):
        if (self.current_page + 1) * self.items_per_page < len(self.filtered_cache):
            self.current_page += 1
            self.render_page()

    def go_up(self):
        if not self.current_path: return
        parts = self.current_path.rstrip('/').split('/')
        if len(parts) <= 1: self.refresh_dir("")
        else: self.refresh_dir("/".join(parts[:-1]) + "/")

    def get_local_folder(self):
        return self.folder_mappings.get(self.current_path)

    def update_map_btn(self):
        path = self.get_local_folder()
        if path:
            self.btn_map.configure(text=f"📂 {os.path.basename(path)}", fg_color=C["cyan"], text_color="black")
        else:
            self.btn_map.configure(text="📂 Set Save Folder", fg_color="transparent", text_color=C["cyan"])

    def set_mapping(self):
        d = filedialog.askdirectory()
        if d:
            self.folder_mappings[self.current_path] = d
            self.save_config()
            self.update_map_btn()
            self.update_storage_stats() # Update storage on new path

    def open_current_folder(self):
        path = self.get_local_folder()
        if not path or not os.path.exists(path):
            messagebox.showerror("Error", "No valid local folder set for this console.")
            return

        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def update_storage_stats(self):
        path = self.get_local_folder()
        if not path or not os.path.exists(path):
            self.storage_label.configure(text="Storage: No Folder Set")
            self.storage_bar.set(0)
            return

        try:
            total, used, free = shutil.disk_usage(path)
            # Calculate percentages
            total_gb = total / (1024**3)
            free_gb = free / (1024**3)
            used_pct = used / total

            self.storage_label.configure(text=f"Storage: {free_gb:.1f} GB Free (of {total_gb:.1f} GB)")
            self.storage_bar.set(used_pct)

            # Color logic
            if free_gb < 10: # Less than 10GB red
                self.storage_bar.configure(progress_color=C["pink"])
            elif free_gb < 50: # Less than 50GB yellow/dim
                self.storage_bar.configure(progress_color="orange")
            else:
                self.storage_bar.configure(progress_color=C["success"])
        except:
            self.storage_label.configure(text="Storage: Unknown")
            self.storage_bar.set(0)

    def add_to_queue(self):
        targets = [(n, h) for n, v, h in self.checkboxes if v.get() == 1]
        if not targets: return

        local_dir = self.get_local_folder()
        if not local_dir:
            local_dir = filedialog.askdirectory()
            if not local_dir: return

        if not os.access(local_dir, os.W_OK):
            messagebox.showerror("Permission Error", f"Cannot write to:\n{local_dir}")
            return

        for name, href in targets:
            clean_path_for_url = self.current_path + href
            url = BASE_URL + clean_path_for_url
            dest = os.path.join(local_dir, name)

            size_mb = 0
            for i in self.file_cache:
                if i['name'] == name:
                    try:
                        s_str = i['size'].replace('G', '').replace('M', '').replace('K', '')
                        if 'G' in i['size']: size_mb = float(s_str) * 1024
                        elif 'M' in i['size']: size_mb = float(s_str)
                    except: pass
                    break

            # Add to LIST instead of Queue
            self.download_list.append({"url": url, "path": dest, "name": name, "size_mb": size_mb})
            self.log(f"QUEUED: {name}")

        self.show_queue()
        # Update UI List
        self.render_queue_list()

        if not self.is_downloading:
            threading.Thread(target=self.process_queue, daemon=True).start()

    def remove_from_queue(self, index):
        if 0 <= index < len(self.download_list):
            item = self.download_list.pop(index)
            self.log(f"REMOVED: {item['name']}")
            self.render_queue_list()

    def render_queue_list(self):
        # Clear existing
        for widget in self.queue_widgets:
            try: widget.destroy()
            except: pass
        self.queue_widgets = []

        if not self.download_list:
            lbl = ctk.CTkLabel(self.queue_list_frame, text="Queue is empty", text_color=C["dim"])
            lbl.pack(pady=10)
            self.queue_widgets.append(lbl)
            return

        for i, item in enumerate(self.download_list):
            row = ctk.CTkFrame(self.queue_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            self.queue_widgets.append(row)
            self.bind_scroll(row, self.queue_list_frame)

            name_lbl = ctk.CTkLabel(row, text=f"{i+1}. {item['name']}", anchor="w", text_color="white")
            name_lbl.pack(side="left", padx=5, fill="x", expand=True)
            self.bind_scroll(name_lbl, self.queue_list_frame)

            # Remove Button
            del_btn = ctk.CTkButton(row, text="❌", width=30, fg_color=C["bg"], hover_color=C["pink"],
                                    command=lambda idx=i: self.remove_from_queue(idx))
            del_btn.pack(side="right", padx=5)
            self.bind_scroll(del_btn, self.queue_list_frame)

    def log(self, msg):
        self.log_box.insert("end", f"{msg}\n")
        self.log_box.see("end")

    def play_notification(self):
        if os.name == 'nt':
            try:
                import winsound
                winsound.MessageBeep()
            except:
                print('\a')
        else:
            try: os.system('paplay /usr/share/sounds/freedesktop/stereo/complete.oga &')
            except: print('\a')

    def dl_part(self, url, start, end, fname):
        h = self.session.headers.copy()
        h['Range'] = f"bytes={start}-{end}"
        try:
            with self.session.get(url, headers=h, stream=True, timeout=30) as r:
                if 'text/html' in r.headers.get('Content-Type', '') or r.status_code == 403:
                    raise Exception("Blocked/HTML Response")

                r.raise_for_status()
                with open(fname, 'wb') as f:
                    for c in r.iter_content(65536):
                        if self.cancel_download: return
                        f.write(c)
                        self.download_stats['bytes'] += len(c)
        except Exception as e:
            if not self.cancel_download:
                print(f"Hydra Thread Failed: {e}")
            if os.path.exists(fname): os.remove(fname)

    def process_queue(self):
        self.is_downloading = True
        self.btn_cancel.configure(state="normal", text="Cancel Download")

        while self.download_list:
            if self.cancel_download:
                break

            # Pop from list
            task = self.download_list.pop(0)

            # Update UI to reflect removal from pending list
            self.after(0, self.render_queue_list)

            self.log(f"HYDRA ACTIVE: {task['name']}")
            self.net_log(f"DL: {task['name'][:15]}...")

            try:
                head = self.session.head(task['url'], timeout=10, allow_redirects=True)

                if 'text/html' in head.headers.get('Content-Type', ''):
                     self.log(f"❌ ERROR: Server returned HTML (Hotlink blocked?)")
                     self.log(f"   Try checking your IP or VPN.")
                     continue

                try: total_length = int(head.headers.get('content-length', 0))
                except: total_length = 0
                if total_length == 0 and task['size_mb'] > 0: total_length = int(task['size_mb'] * 1024 * 1024)

                save_folder = os.path.dirname(task['path'])
                try:
                    total, used, free = shutil.disk_usage(save_folder)
                    if total_length > 0 and free < total_length:
                        self.log(f"❌ ERROR: Disk Full")
                        continue
                except: pass

                part_size = total_length // NUM_THREADS
                threads, parts = [], []
                self.download_stats = {'bytes': 0}
                start_t = time.time()

                for i in range(NUM_THREADS):
                    s = i * part_size
                    e = s + part_size - 1 if i < NUM_THREADS - 1 else total_length - 1
                    fname = f"{task['path']}.part{i}"
                    parts.append(fname)
                    t = threading.Thread(target=self.dl_part, args=(task['url'], s, e, fname))
                    threads.append(t)
                    t.start()

                while any(t.is_alive() for t in threads):
                    if self.cancel_download:
                        break

                    time.sleep(0.5)
                    now = time.time()
                    if now - start_t > 0:
                        spd = self.download_stats['bytes'] / (now - start_t)
                        pct = self.download_stats['bytes'] / total_length if total_length > 0 else 0
                        self.after(0, lambda p=pct, s=spd: (
                            self.progress_bar.set(p),
                            self.lbl_speed.configure(text=f"{s/1024/1024:.2f} MB/s")
                        ))

                if self.cancel_download:
                    self.log("🛑 CANCELLED BY USER")
                    for p in parts:
                         if os.path.exists(p):
                            try: os.remove(p)
                            except: pass
                    break

                self.log("Stitching...")
                if all(os.path.exists(p) for p in parts):
                    with open(task['path'], 'wb') as f_out:
                        for p in parts:
                            with open(p, 'rb') as f_in:
                                while chunk := f_in.read(1024*1024): f_out.write(chunk)
                            os.remove(p)

                    if os.path.getsize(task['path']) < 2048:
                         self.log(f"❌ FAILED: File too small (likely HTML error)")
                    else:
                        self.log("✔ COMPLETED")
                        self.play_notification()
                else:
                    self.log("❌ ERROR: Download failed (Missing parts)")

            except Exception as e:
                self.log(f"❌ ERROR: {e}")

        self.is_downloading = False
        self.cancel_download = False
        self.btn_cancel.configure(state="disabled", text="Cancel Download")
        self.progress_bar.set(0)
        self.after(0, lambda: self.lbl_speed.configure(text="IDLE"))
        self.net_log("Idle")

if __name__ == "__main__":
    try:
        app = UltimateApp()
        app.mainloop()
    except Exception as e:
        error_msg = traceback.format_exc()
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Critical Error", f"MyriFetch Crashed:\n\n{error_msg}")
        except:
            print("CRITICAL ERROR:")
            print(error_msg)
            input("Press Enter to exit...")
