import tkinter as tk
from tkinter import messagebox

def berechnen(operation):
    try:
        a = float(eingabe1.get())
        b = float(eingabe2.get())
    except ValueError:
        messagebox.showerror("Fehler", "Bitte gültige Zahlen eingeben!")
        return

    if operation == "/" and b == 0:
        messagebox.showerror("Fehler", "Division durch 0 nicht möglich!")
        return

    ergebnisse = {
        "+": a + b,
        "-": a - b,
        "*": a * b,
        "/": a / b,
    }

    ergebnis = ergebnisse[operation]
    ergebnis_label.config(text=f"Ergebnis: {ergebnis:g}")

fenster = tk.Tk()
fenster.title("Taschenrechner")
fenster.resizable(False, False)
fenster.configure(bg="#f0f0f0")

FONT = ("Segoe UI", 14)
BTN_FONT = ("Segoe UI", 16, "bold")

tk.Label(fenster, text="Erste Zahl:", font=FONT, bg="#f0f0f0").grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")
eingabe1 = tk.Entry(fenster, font=FONT, width=15, justify="center")
eingabe1.grid(row=0, column=1, padx=20, pady=(20, 5))

tk.Label(fenster, text="Zweite Zahl:", font=FONT, bg="#f0f0f0").grid(row=1, column=0, padx=20, pady=5, sticky="w")
eingabe2 = tk.Entry(fenster, font=FONT, width=15, justify="center")
eingabe2.grid(row=1, column=1, padx=20, pady=5)

btn_frame = tk.Frame(fenster, bg="#f0f0f0")
btn_frame.grid(row=2, column=0, columnspan=2, pady=15)

farben = {"+" : "#4CAF50", "-": "#2196F3", "*": "#FF9800", "/": "#F44336"}
for symbol, farbe in farben.items():
    tk.Button(
        btn_frame, text=symbol, font=BTN_FONT,
        width=4, bg=farbe, fg="white", activebackground=farbe,
        relief="flat", cursor="hand2",
        command=lambda op=symbol: berechnen(op)
    ).pack(side="left", padx=8)

ergebnis_label = tk.Label(fenster, text="Ergebnis: —", font=("Segoe UI", 16, "bold"), bg="#f0f0f0", fg="#333")
ergebnis_label.grid(row=3, column=0, columnspan=2, pady=(0, 20))

fenster.mainloop()
