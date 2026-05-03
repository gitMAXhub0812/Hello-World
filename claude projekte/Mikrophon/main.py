import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import json
import os

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model")
SAMPLERATE = 16000
BLOCKSIZE = 8000


class SpeechApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Live Spracherkennung")
        self.root.geometry("850x620")
        self.root.resizable(True, True)

        self.is_recording = False
        self.audio_thread = None
        self.text_queue = queue.Queue()
        self.confirmed_text = ""
        self.mic_indices = {}

        self._build_ui()
        self._check_dependencies()
        self._poll_queue()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = tk.Frame(self.root, bg="#2c3e50")
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(
            header, text="🎙 Live Spracherkennung",
            font=("Segoe UI", 16, "bold"), bg="#2c3e50", fg="white", pady=10
        ).pack()

        mic_frame = tk.Frame(self.root, pady=8)
        mic_frame.grid(row=1, column=0, sticky="ew", padx=15)
        mic_frame.columnconfigure(1, weight=1)

        tk.Label(mic_frame, text="Mikrofon:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.mic_var = tk.StringVar()
        self.mic_combo = ttk.Combobox(mic_frame, textvariable=self.mic_var, state="readonly", font=("Segoe UI", 10))
        self.mic_combo.grid(row=0, column=1, sticky="ew")
        tk.Button(
            mic_frame, text="↻", font=("Segoe UI", 11), relief=tk.FLAT,
            cursor="hand2", command=self._load_microphones
        ).grid(row=0, column=2, padx=(6, 0))

        text_frame = tk.Frame(self.root)
        text_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 5))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text_area = tk.Text(
            text_frame, font=("Segoe UI", 13), wrap=tk.WORD,
            state=tk.DISABLED, relief=tk.SOLID, bd=1,
            bg="#fafafa", fg="#222222", padx=10, pady=10
        )
        self.text_area.tag_config("partial", foreground="#888888")
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=scrollbar.set)
        self.text_area.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.status_var = tk.StringVar(value="Bereit.")
        self.status_label = tk.Label(
            self.root, textvariable=self.status_var,
            font=("Segoe UI", 9), fg="#666666", anchor="w"
        )
        self.status_label.grid(row=3, column=0, sticky="ew", padx=15)

        btn_frame = tk.Frame(self.root, pady=10)
        btn_frame.grid(row=4, column=0)

        self.record_btn = tk.Button(
            btn_frame, text="▶  Aufnahme starten",
            font=("Segoe UI", 11, "bold"), bg="#27ae60", fg="white",
            activebackground="#219a52", relief=tk.FLAT,
            width=22, pady=6, cursor="hand2",
            command=self._toggle_recording
        )
        self.record_btn.grid(row=0, column=0, padx=6)

        tk.Button(
            btn_frame, text="Löschen",
            font=("Segoe UI", 11), relief=tk.FLAT, bg="#ecf0f1",
            width=10, pady=6, cursor="hand2",
            command=self._clear_text
        ).grid(row=0, column=1, padx=6)

        tk.Button(
            btn_frame, text="💾  Speichern",
            font=("Segoe UI", 11), relief=tk.FLAT, bg="#ecf0f1",
            width=12, pady=6, cursor="hand2",
            command=self._save_text
        ).grid(row=0, column=2, padx=6)

        self._load_microphones()

    def _load_microphones(self):
        if not SD_AVAILABLE:
            return
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()
        mics = []
        self.mic_indices = {}

        # Prefer WASAPI, then DirectSound, then MME
        api_priority = {"Windows WASAPI": 0, "Windows DirectSound": 1, "MME": 2}

        candidates = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                api_name = host_apis[dev["hostapi"]]["name"]
                priority = api_priority.get(api_name, 99)
                candidates.append((priority, dev["name"], i, api_name))

        # Deduplicate: keep only the highest-priority entry per device name
        seen = {}
        for priority, name, idx, api_name in sorted(candidates):
            if name not in seen:
                seen[name] = (idx, api_name)

        for name, (idx, api_name) in seen.items():
            label = f"{name}  [{api_name}]"
            mics.append(label)
            self.mic_indices[label] = idx

        self.mic_combo["values"] = mics

        # Pre-select the system default input device
        try:
            default_idx = sd.default.device[0]
            for label, idx in self.mic_indices.items():
                if idx == default_idx:
                    self.mic_combo.set(label)
                    return
        except Exception:
            pass

        if mics:
            self.mic_combo.current(0)

    def _check_dependencies(self):
        problems = []
        if not SD_AVAILABLE:
            problems.append("sounddevice fehlt")
        if not VOSK_AVAILABLE:
            problems.append("Vosk fehlt")
        if not os.path.isdir(MODEL_PATH):
            problems.append("Modell-Ordner 'model' nicht gefunden")
        if problems:
            self.status_var.set("⚠ " + "  |  ".join(problems))
            self.status_label.config(fg="#c0392b")
            self.record_btn.config(state=tk.DISABLED)

    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self.is_recording = True
        self.record_btn.config(text="⏹  Aufnahme stoppen", bg="#c0392b", activebackground="#a93226")
        self.status_var.set("🔴 Aufnahme läuft …")
        self.status_label.config(fg="#27ae60")
        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()

    def _stop_recording(self):
        self.is_recording = False
        self.record_btn.config(text="▶  Aufnahme starten", bg="#27ae60", activebackground="#219a52")
        self.status_var.set("Aufnahme gestoppt.")
        self.status_label.config(fg="#666666")

    def _audio_loop(self):
        try:
            model = Model(MODEL_PATH)
            rec = KaldiRecognizer(model, SAMPLERATE)

            device_index = self.mic_indices.get(self.mic_var.get())

            def callback(indata, frames, time_info, status):
                data = bytes(indata)
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if text:
                        self.text_queue.put(("final", text))
                else:
                    partial = json.loads(rec.PartialResult())
                    text = partial.get("partial", "").strip()
                    self.text_queue.put(("partial", text))

            with sd.RawInputStream(
                samplerate=SAMPLERATE,
                blocksize=BLOCKSIZE,
                device=device_index,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while self.is_recording:
                    sd.sleep(100)

            final = json.loads(rec.FinalResult()).get("text", "").strip()
            if final:
                self.text_queue.put(("final", final))

        except Exception as exc:
            self.text_queue.put(("error", str(exc)))

    def _poll_queue(self):
        try:
            while True:
                kind, text = self.text_queue.get_nowait()
                if kind == "final":
                    if text:
                        self.confirmed_text += text + " "
                    self._render(self.confirmed_text, partial="")
                elif kind == "partial":
                    self._render(self.confirmed_text, partial=text)
                elif kind == "error":
                    self.status_var.set(f"Fehler: {text}")
                    self.status_label.config(fg="#c0392b")
                    self._stop_recording()
        except Exception:
            pass
        self.root.after(80, self._poll_queue)

    def _render(self, confirmed: str, partial: str):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, confirmed)
        if partial:
            self.text_area.insert(tk.END, partial, "partial")
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def _clear_text(self):
        self.confirmed_text = ""
        self._render("", "")

    def _save_text(self):
        text = self.confirmed_text.strip()
        if not text:
            messagebox.showinfo("Hinweis", "Kein Text zum Speichern vorhanden.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Textdatei", "*.txt"), ("Alle Dateien", "*.*")],
            title="Text speichern als …",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Gespeichert", f"Text gespeichert unter:\n{path}")


if __name__ == "__main__":
    root = tk.Tk()
    SpeechApp(root)
    root.mainloop()
