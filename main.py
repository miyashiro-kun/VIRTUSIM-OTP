import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import StringVar, messagebox, Label
from PIL import Image, ImageTk
import tkinter as tk
import requests
import threading
import time
import json
import io
import customtkinter
import pyttsx3
import os
import sys
from tkinter import Entry
from tkinter import ttk as tkttk  # for Treeview in log viewer
from gtts import gTTS
from playsound import playsound
import tempfile
import pystray
from PIL import Image as PILImage
from plyer import notification
from ttkbootstrap.toast import ToastNotification
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from ttkwidgets.autocomplete import AutocompleteCombobox

def resource_path(filename):
    """
    Mengembalikan path absolut ke file, baik saat dijalankan dari .py atau dari .exe (PyInstaller).
    """
    if getattr(sys, 'frozen', False):  # Jika dijalankan sebagai .exe
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)

API_KEY = " ISI API KEY MU "
BASE_URL = "https://virtusim.com/api/v2/json.php"

class VirtusimApp(ttk.Window):
    def __init__(self):
        super().__init__(title="Virtusim OTP App", themename="flatly")
        self.geometry("1390x580")
        self.resizable(False, False)

        self.service_list = []
        self.selected_service = StringVar()
        self.username = StringVar(value="Memuat...")
        self.balance = StringVar(value="Memuat...")
        self.operator_list = []
        self.selected_operator = StringVar()
        self.row_index = 0
        self.deposit_popup = None
        self.log_popup = None

        self.themes = self.style.theme_names()
        self.current_theme = StringVar(value=self.style.theme_use())

        self.style.configure("Header.TFrame", background="#e1e1e1")
        self.style.configure("Header.TLabel", background="#e1e1e1", font=("Segoe UI", 10, "bold"))
        self.style.configure("Treeview.Heading", anchor="w")

        self.create_widgets()
        threading.Thread(target=self.get_balance, daemon=True).start()
        threading.Thread(target=self.get_service_list, daemon=True).start()
        threading.Thread(target=self.get_operator_list, daemon=True).start()
        
        threading.Thread(target=self.create_tray_icon, daemon=True).start()
    
    def speak_notification(self, text):
        def run_speech():
            try:
                tts = gTTS(text=text, lang='id')
                temp_path = resource_path("otp_tts.mp3")  # Simpan di folder aplikasi

                tts.save(temp_path)
                time.sleep(0.5)  # Waktu tunggu agar file siap dibuka
                playsound(temp_path)

                # Opsional: hapus file setelah selesai
                try:
                    os.remove(temp_path)
                except:
                    pass
            except Exception as e:
                print(f"TTS Error: {e}")

        threading.Thread(target=run_speech, daemon=True).start()


		
    def create_widgets(self):
        ttk.Button(self, text="Log Aktivitas", bootstyle=INFO, command=self.show_log_history).place(x=10, y=10)

        ttk.Label(self, text="Virtusim OTP Manager", font=("Segoe UI", 18, "bold")).pack(pady=(10, 5))

        info_frame = ttk.Frame(self)
        info_frame.pack(pady=5)
        ttk.Label(info_frame, text="User :", font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))
        ttk.Label(info_frame, textvariable=self.username, font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(info_frame, text="   Saldo :", font=("Segoe UI", 10)).pack(side="left", padx=(20, 5))
        ttk.Label(info_frame, textvariable=self.balance, font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(info_frame, text="Deposit", bootstyle=SUCCESS, command=self.open_deposit_popup).pack(side="left", padx=(20, 5))
        ttk.Button(info_frame, text="Refresh Saldo", bootstyle=WARNING, command=lambda: threading.Thread(target=self.get_balance, daemon=True).start()).pack(side="left", padx=(5, 0))
        
        control_frame = ttk.Frame(self)
        control_frame.pack(pady=10)
        ttk.Label(control_frame, text="Pilih Operator:", font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 10))
        self.operator_menu = ttk.Combobox(control_frame, textvariable=self.selected_operator, state="readonly")
        self.operator_menu.pack(side="left", padx=(0, 10), ipadx=30)
        
        ttk.Label(control_frame, text="Layanan:", font=("Segoe UI", 13, "bold")).pack(side="left", padx=(10, 10))
        self.service_menu = AutocompleteCombobox(control_frame,textvariable=self.selected_service,completevalues=[f"{item['name']} - Rp{item['price']} (ID: {item['id']})" for item in self.service_list],width=40)
        self.service_menu.pack(side="left", padx=(0, 10))
        self.service_menu.set_completion_list([f"{item['name']} - Rp{item['price']} (ID: {item['id']})"for item in self.service_list])
        self.service_menu.bind('<KeyRelease>', self.delayed_filter)
        
        ttk.Button(control_frame, text="Order OTP", bootstyle=PRIMARY, command=self.order_otp).pack(side="left")
        header = ttk.Frame(self, style="Header.TFrame") 
        header.pack(fill='x', padx=10, pady=(3, 3))

        for i in range(7):
            header.grid_columnconfigure(i, weight=1, uniform="col")

        for i, text in enumerate(["ID","Layanan", "Nomor", "SIM", "Status", "SMS", "Aksi"]):
            ttk.Label(header, text=text, style="Header.TLabel").grid(row=0, column=i, sticky="w", padx=5, pady=(3, 3))

        self.order_container = ttk.Frame(self)
        self.order_container.pack(padx=10, pady=5, fill='both', expand=True)
        
        ttk.Label(self, text="Tema:", font=("Segoe UI", 10)).place(x=10, y=550)
        self.theme_combo = ttk.Combobox(self, values=self.themes, state="readonly", textvariable=self.current_theme, width=15)
        self.theme_combo.place(x=50, y=548)
        self.theme_combo.bind("<<ComboboxSelected>>", self.change_theme)
    
    def clear_service_entry(self, event):
        event.widget.delete(0, tk.END)
    def delayed_filter(self, event):
        if hasattr(self, "_filter_after_id"):
            self.after_cancel(self._filter_after_id)
        self._filter_after_id = self.after(1300, lambda: self.filter_service_list(event))
    
    def on_keyrelease(self, event):
        value = self.selected_service.get().lower()
    
    # Filter data list
        filtered = [item for item in self.services_list if value in item.lower()]

        self.service_menu['values'] = filtered

    # Kalau ada hasil, munculkan dropdown
        if filtered:
            self.service_menu.event_generate('<Down>')

    # Jangan hapus isi input, biarkan tetap ada

    
    def get_service_list(self):
        url = f"{BASE_URL}?api_key={API_KEY}&action=services&country=Indonesia&service="
        try:
            r = requests.get(url)
            data = r.json()
            if data.get("status"):
                self.service_list = sorted(data["data"], key=lambda item: item["name"].lower())
                service_names = [f"{item['name']} - Rp{item['price']} (ID: {item['id']})" for item in self.service_list]
                self.service_menu["values"] = service_names
                if service_names:
                    self.selected_service.set(service_names[449])
 
                    
        except Exception as e:
            print(f"Error loading services: {e}")
    
    def filter_service_list(self, event):
        typed = self.service_menu.get().lower()

    # Filter layanan berdasarkan teks
        filtered = [
            f"{item['name']} - Rp{item['price']} (ID: {item['id']})"
            for item in self.service_list
            if typed in item['name'].lower()
        ]

    # Update isi dropdown
        self.service_menu['values'] = filtered

    # Tampilkan dropdown tanpa mengganggu input focus
        if filtered:
        # Tampilkan dropdown *setelah idle* (supaya tidak ganggu focus)
            self.after_idle(lambda: self.service_menu.event_generate('<Down>'))

   
    
    def change_theme(self, event):
        new_theme = self.current_theme.get()
        self.style.theme_use(new_theme)

    def get_balance(self):
        url = f"{BASE_URL}?api_key={API_KEY}&action=balance"
        try:
            r = requests.get(url)
            data = r.json()
            if data.get("status"):
                self.username.set(data["username"])
                self.balance.set(f'Rp. {data["balance"]}')
            else:
                self.username.set("Gagal")
                self.balance.set("Gagal")
        except:
            self.username.set("Error")
            self.balance.set("Error")

    def get_operator_list(self):
        url = f"{BASE_URL}?api_key={API_KEY}&action=list_operator&country=Indonesia"
        try:
            r = requests.get(url)
            data = r.json()
            if data.get("status"):
                self.operator_list = data["data"]
                self.operator_menu["values"] = self.operator_list
                self.selected_operator.set(self.operator_list[0])
        except:
            self.operator_list = []
            self.selected_operator.set("")

    def log_activity(self, filename, data):
        filepath = resource_path(filename)
        logs = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except:
                pass
        logs.insert(0, data)  # data terbaru di awal
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
            
    def show_notification(self, title, message):
        # Gunakan plyer untuk notifikasi desktop
        notification.notify(
            title=title,
            message=message,
            app_name="Virtusim OTP",
            timeout=5
        )
    
    def create_tray_icon(self):
        # Load icon tray (gunakan icon di folder resource)
        icon_path = resource_path("icon.png")
        try:
            image = PILImage.open(icon_path)
        except:
            # Jika icon gagal load, buat icon kosong 64x64
            image = PILImage.new('RGBA', (64, 64), (255, 0, 0, 0))

        def on_show(icon, item):
            self.after(0, self.deiconify)
            self.after(0, self.lift)
            self.after(0, self.focus_force)

        def on_hide(icon, item):
            self.after(0, self.withdraw)

        def on_quit(icon, item):
            icon.stop()
            self.after(0, self.destroy)

        menu = pystray.Menu(
            pystray.MenuItem('Tampilkan', on_show),
            pystray.MenuItem('Sembunyikan', on_hide),
            pystray.MenuItem('Keluar', on_quit)
        )

        icon = pystray.Icon("Virtusim OTP", image, "Virtusim OTP", menu)
        icon.run()

    def order_otp(self):
        
        service_name = self.selected_service.get()
        if not service_name:
            messagebox.showerror("Error", "Pilih layanan terlebih dahulu.")
            return

        # Ekstrak ID dari pilihan, misal: "Telegram - Rp800 (ID: 1234)"
        try:
            service_id = service_name.split("ID:")[1].strip(" )")
        except:
            messagebox.showerror("Error", "Gagal membaca ID layanan.")
            return

        operator = self.selected_operator.get()
        if not operator:
            messagebox.showerror("Error", "Pilih operator terlebih dahulu.")
            return

        url = f"{BASE_URL}?api_key={API_KEY}&action=order&service={service_id}&operator={operator}"
        try:
            r = requests.get(url)
            data = r.json()
            if data.get("status"):
                order = data["data"]
                self.add_order_row(order)

                # Log order dengan status awal "processing" dan SMS "-"
                self.log_activity("log_order.json", {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": order["id"],
                    "service_name": self.selected_service.get(), 
                    "number": order["number"],
                    "operator": order["operator"],
                    "status": "processing",
                    "sms": "-"
                })
                
                self.show_notification("Order OTP", f"Order {order['id']} berhasil dibuat!")
                self.speak_notification(f"Order berhasil di buat pakai {operator} , jangan lupa klik ready ya.")

            else:
                messagebox.showerror("Gagal Order", data.get("msg", "Gagal melakukan order."))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_order_row(self, order):
        bg_color = "#a3cdf0" if self.row_index % 2 == 0 else "#00ffff"
        row = tk.Frame(self.order_container,bg=bg_color )
        row.pack(fill='x', pady=1)

        for i in range(7):
            row.grid_columnconfigure(i, weight=1, uniform="col")

        def make_label(text, col, bold=False):
            font = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
            label = Label(row, text=text, font=font, bg=bg_color)
            label.grid(row=0, column=col, sticky="w", padx=5)
            return label

        def make_copyable_entry(text, col):
            entry_var = StringVar(value=text)
            entry = Entry(row, textvariable=entry_var, font=("Segoe UI", 10),  bg=bg_color)
            entry.grid(row=0, column=col, sticky="we", padx=5, ipady=1)
            return entry_var, entry

        make_label(order["id"], 0)
        make_label(self.selected_service.get(), 1)
        number_var = make_copyable_entry(order["number"], 2)
        make_label(order["operator"], 3)
        lbl_status = make_label("⏳ Pending", 4)
        sms_var, _ = make_copyable_entry("-", 5)

        action_frame = ttk.Frame(row)
        action_frame.grid(row=0, column=6, sticky="w", padx=5)

        btn_ready = ttk.Button(action_frame, text="READY", bootstyle=SUCCESS)
        btn_cancel = ttk.Button(action_frame, text="BATAL", bootstyle=DANGER)
        
        btn_ready.pack(side="left", padx=2)
        btn_cancel.pack(side="left", padx=2)

        def ready_action():
            url = f"{BASE_URL}?api_key={API_KEY}&action=set_status&id={order['id']}&status=1"
            try:
                r = requests.get(url)
                data = r.json()
                if data.get("status"):
                    btn_ready.config(state="disabled")
                    lbl_status.config(text="✅ READY")
                    ToolTip(btn_cancel, text="NOMOR READY SIAP DI GUNAKAN", bootstyle=(SUCCESS, INVERSE))
                    # Update log status menjadi "sukses" saat READY ditekan (bisa diubah sesuai kebutuhan)
                    self.update_log_order_status(order['id'], "sukses", sms_var.get())
                    
                    self.show_notification("Order READY", f"Order {order['id']} telah READY.")

                    messagebox.showinfo("READY", f"Order {order['id']} ditandai READY.")
                else:
                    messagebox.showerror("Gagal", "Tidak bisa set READY.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def cancel_action():
            url = f"{BASE_URL}?api_key={API_KEY}&action=set_status&id={order['id']}&status=2"
            try:
                r = requests.get(url)
                data = r.json()
                if data.get("status"):
                    row.destroy()

                    # Update log status menjadi "batal" dan sms "-"
                    self.update_log_order_status(order['id'], "batal", "-")
                    
                    self.show_notification("Order Batal", f"Order {order['id']} dibatalkan.")
                    self.speak_notification(f"Order berhasil di batalkan , saldo sudah di kembalikan")
                    messagebox.showinfo("Batal", f"Order {order['id']} dibatalkan.")
                        
                else:
                    self.speak_notification(f"Tunggu 3 menit dulu kalau mau membatalkan orderan")
                    messagebox.showerror("Gagal", "Tidak bisa membatalkan order. Tunggu 3 menit.")
                    
            except Exception as e:
                messagebox.showerror("Error", str(e))

        btn_ready.config(command=ready_action)
        btn_cancel.config(command=cancel_action)

        threading.Thread(target=self.poll_status, args=(order["id"], lbl_status, sms_var, btn_cancel), daemon=True).start()
        self.row_index += 1

    def update_log_order_status(self, order_id, status, sms):
        filepath = resource_path("log_order.json")
        logs = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except:
                pass

        # Update log order berdasar order_id
        for log in logs:
            if str(log.get("order_id")) == str(order_id):
                log["status"] = status
                log["sms"] = sms

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    def poll_status(self, order_id, lbl_status, sms_var, btn_cancel):
        url = f"{BASE_URL}?api_key={API_KEY}&action=status&id={order_id}"
        timeout = 3000
        interval = 5
        elapsed = 0

        while elapsed < timeout:
            try:
                r = requests.get(url)
                data = r.json()
                # Debug print untuk cek data API
                

                if data.get("status"):
                    detail = data.get("data", {})
                    sms = detail.get("sms", "").strip()
                    status = detail.get("status", "").strip()

                    # Update label status text di UI thread
                    def update_ui():
                        lbl_status.config(text=f"⏳ {status}")
                    lbl_status.after(0, update_ui)

                    # Jika status sukses dan sms valid
                    if sms and sms != "-" and "success" in status.lower():
                        def update_success_ui():
                            lbl_status.config(text="✅ SUCCESS")
                            sms_var.set(sms)
                            btn_cancel.config(text="SELESAI", bootstyle=SECONDARY, command=lambda: None)
                            ToolTip(btn_cancel, text="Orderan Selesai , Bisa Cek Log", bootstyle=(SECONDARY, INVERSE))
                        lbl_status.after(0, update_success_ui)

                        # Update log order status sukses dan sms ke file log
                        self.update_log_order_status(order_id, "sukses", sms)
                        
                        digits = ' '.join(sms)
                        self.speak_notification(f"OTP masuk, Kode nyaa: {digits} ")                      
                        self.show_notification("Order Sukses", f"Order {order_id} berhasil dengan SMS:\n{sms}")
                        toast = ToastNotification(title="OTP VIRTUSIM",message=f"OTP masuk, Kode nyaa: {digits} ",duration=30000)
                        toast.show_toast()
                        return

                time.sleep(interval)
                elapsed += interval
            except Exception as e:
                print("Polling error:", e)
                break

        # Jika timeout, set status batal
        try:
            cancel_url = f"{BASE_URL}?api_key={API_KEY}&action=set_status&id={order_id}&status=2"
            requests.get(cancel_url)
        except:
            pass

        def update_timeout_ui():
            lbl_status.config(text="❌ TIMEOUT")
            btn_cancel.config(text="SELESAI", bootstyle=SECONDARY, command=lambda: None)
            ToolTip(btn_cancel, text="ORDERAN DI BATALKAN KARENA TIMEOUT", bootstyle=(DANGER, INVERSE))
            sms_var.set("-")

        lbl_status.after(0, update_timeout_ui)
        self.update_log_order_status(order_id, "batal", "-")

    def show_log_history(self):
        if self.log_popup and self.log_popup.winfo_exists():
            self.log_popup.lift()
            return

        try:
            with open(resource_path("log_order.json"), "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = []

        self.log_popup = ttk.Toplevel(self)
        self.log_popup.title("Riwayat Log Order")
        self.log_popup.geometry("1200x400")
        self.log_popup.resizable(False, False)

        tree = tkttk.Treeview(
            self.log_popup,
            columns=("order_id","service_name", "number", "operator", "status", "sms", "timestamp"),
            show="headings"
        )

        tree.heading("order_id", text="Order ID")
        tree.heading("service_name", text="Layanan")
        tree.heading("number", text="Nomor")
        tree.heading("operator", text="Operator")
        tree.heading("status", text="Status")
        tree.heading("sms", text="SMS")
        tree.heading("timestamp", text="Timestamp")

        tree.column("order_id", width=90, anchor="center")
        tree.column("service_name", width=160, anchor="center")
        tree.column("number", width=140, anchor="center")
        tree.column("operator", width=90, anchor="center")
        tree.column("status", width=90, anchor="center")
        tree.column("sms", width=220, anchor="center")
        tree.column("timestamp", width=160, anchor="center")

        for log in logs:
            tree.insert("", "end", values=(
                log.get("order_id", ""),
                log.get("service_name", ""), 
                log.get("number", ""),
                log.get("operator", ""),
                log.get("status", ""),
                log.get("sms", ""),
                log.get("timestamp", "")
            ))

        tree.pack(fill="both", expand=True, padx=10, pady=10)


    def open_deposit_popup(self):
        if self.deposit_popup and self.deposit_popup.winfo_exists():
            self.deposit_popup.lift()
            return

        self.deposit_popup = ttk.Toplevel(self)
        self.deposit_popup.title("Deposit Saldo")
        self.deposit_popup.geometry("300x250")
        self.deposit_popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (self.deposit_popup.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (self.deposit_popup.winfo_height() // 2)
        self.deposit_popup.geometry(f"+{x}+{y}")
        self.deposit_popup.resizable(False, False)
        self.deposit_popup.transient(self)

        ttk.Label(self.deposit_popup, text="Nominal", font=("Segoe UI", 11)).pack(pady=(15, 0))
        entry_nominal = ttk.Entry(self.deposit_popup)
        entry_nominal.pack(pady=5, padx=20, fill='x')

        ttk.Label(self.deposit_popup, text="Metode", font=("Segoe UI", 11)).pack(pady=(10, 0))
        metode_combo = ttk.Combobox(self.deposit_popup, state="readonly")
        metode_combo["values"] = ["QRIS", "Transfer Bank", "DANA", "OVO", "Gopay"]
        metode_combo.current(0)
        metode_combo.pack(pady=5, padx=20, fill='x')

        def show_deposit_popup(data):
            nominal_res = data.get("balance_pay", "")
            metode_res = data.get("method", "")
            qr_url = data.get("qr", "")
            note = data.get("note", "")

            info_popup = ttk.Toplevel(self)
            info_popup.title("Informasi Pembayaran")
            info_popup.geometry("450x620")
            info_popup.resizable(False, False)
            info_popup.transient(self)
            info_popup.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - (info_popup.winfo_width() // 2)
            y = self.winfo_y() + (self.winfo_height() // 2) - (info_popup.winfo_height() // 2)
            info_popup.geometry(f"+{x}+{y}")

            ttk.Label(info_popup, text=f"Nominal: Rp. {nominal_res}", font=("Segoe UI", 11)).pack(pady=(10, 5))
            ttk.Label(info_popup, text=f"Metode: {metode_res}", font=("Segoe UI", 11)).pack(pady=5)
            ttk.Label(info_popup, text="Scan QR untuk bayar:", font=("Segoe UI", 11, "bold")).pack(pady=(15, 10))

            try:
                qr_response = requests.get(qr_url)
                img_data = Image.open(io.BytesIO(qr_response.content))
                img_resized = img_data.resize((300, 300))
                photo = ImageTk.PhotoImage(img_resized)
                img_label = ttk.Label(info_popup, image=photo)
                img_label.image = photo
                img_label.pack(pady=(10, 10))
            except Exception as e:
                ttk.Label(info_popup, text=f"Gagal memuat gambar: {e}", foreground="red").pack(pady=10)

            if note:
                ttk.Label(info_popup, text="Catatan:", font=("Segoe UI", 11, "bold")).pack(pady=(10, 2))
                ttk.Label(info_popup, text=note, wraplength=400, justify="left").pack(pady=5)

            ttk.Button(info_popup, text="Tutup", bootstyle=SECONDARY, command=info_popup.destroy).pack(pady=10)

        def bayar_action():
            nominal = entry_nominal.get()
            hp = "0850000011"
            metode_text = metode_combo.get()

            metode_map = {"QRIS": 20, "Transfer Bank": 21, "DANA": 23, "OVO": 24, "Gopay": 25}
            metode_code = metode_map.get(metode_text, 20)

            url = f"{BASE_URL}?api_key={API_KEY}&action=deposit&method={metode_code}&amount={nominal}&phone={hp}"
            try:
                response = requests.get(url)
                result = response.json()

                filename = "deposit_sukses.json" if result.get("status") else "deposit_gagal.json"
                filepath = resource_path(filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)

                if not result.get("status"):
                    self.speak_notification(f"Kamu belum membayar deposit yang sebelumnya , bayar dulu kalau mau deposit lagi ya")
                    messagebox.showerror("Deposit Gagal", result.get("msg", "Gagal melakukan deposit."))
    
                    sukses_path = resource_path("deposit_sukses.json")
                    if os.path.exists(sukses_path):
                        try:
                            with open(sukses_path, "r", encoding="utf-8") as f:
                                last_data = json.load(f)
                            if last_data.get("status"):
                                show_deposit_popup(last_data.get("data", {}))
                        except:
                            pass
                    return

                show_deposit_popup(result.get("data", {}))
                self.deposit_popup.destroy()
                self.deposit_popup = None
                
            except Exception as e:
                messagebox.showerror("Error", f"Gagal koneksi: {e}")

        ttk.Button(self.deposit_popup, text="Bayar", bootstyle=PRIMARY, command=bayar_action).pack(pady=20)
        self.deposit_popup.protocol("WM_DELETE_WINDOW", lambda: self.deposit_popup.destroy())

if __name__ == "__main__":
    app = VirtusimApp()
    app.mainloop()
