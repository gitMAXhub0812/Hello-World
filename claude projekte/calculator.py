import tkinter as tk
import math

# ── Farben ───────────────────────────────────────────────────────────────────
BODY      = "#5a5a5e"   # Gehäuse
BTN_NUM   = "#3a3a3c"   # Ziffern-Tasten
BTN_OP    = "#2c2c2e"   # Operator-Tasten
BTN_CLR   = "#7a1e1e"   # Löschen-Tasten
DISP_BG   = "#1c1c1e"   # Display-Hintergrund
DISP_FG   = "#f2f2f7"   # Display-Text (hell)
DISP_HINT = "#8e8e93"   # Zweite Zeile
FG        = "#0a0a0a"   # Schwarze Symbole

FONT      = ("Helvetica", 13, "bold")
FONT_SM   = ("Helvetica", 10, "bold")
BW, BH    = 64, 48      # Standard-Button Pixel
SW, SH    = 64, 38      # Scientific-Button Pixel


def _lighten(c, f=1.75):
    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(
        min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)))


def _darken(c, f=0.35):
    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(
        max(0, int(r * f)), max(0, int(g * f)), max(0, int(b * f)))


# ── 3D-Button via Canvas ─────────────────────────────────────────────────────
class Btn3D(tk.Canvas):
    DEPTH = 6

    def __init__(self, parent, text, command, color,
                 fg=FG, font=FONT, w=BW, h=BH):
        super().__init__(parent, width=w, height=h,
                         bd=0, highlightthickness=0,
                         bg=BODY, cursor="hand2")
        self._text    = text
        self._cmd     = command
        self._color   = color
        self._fg      = fg
        self._font    = font
        self._bw, self._bh = w, h
        self._hi = _lighten(color)
        self._sh = _darken(color)
        self._draw(False)
        self.bind("<ButtonPress-1>",   lambda e: self._draw(True))
        self.bind("<ButtonRelease-1>", self._release)

    def _draw(self, pressed):
        self.delete("all")
        w, h, d = self._bw, self._bh, self.DEPTH
        hi = self._sh if pressed else self._hi
        sh = self._hi if pressed else self._sh
        shift = d // 2 if pressed else 0

        # Schatten-Block (unten rechts)
        self.create_rectangle(d, d, w, h, fill=sh, outline="")
        # Highlight-Block (oben links)
        self.create_rectangle(0, 0, w - d, h - d, fill=hi, outline="")
        # Taste (Fläche)
        self.create_rectangle(
            shift + 2, shift + 2,
            w - d + shift - 2, h - d + shift - 2,
            fill=self._color, outline=""
        )
        # Text
        cx = (shift + 2 + w - d + shift - 2) // 2
        cy = (shift + 2 + h - d + shift - 2) // 2
        self.create_text(cx, cy, text=self._text,
                         fill=self._fg, font=self._font)

    def _release(self, e):
        self._draw(False)
        if self._cmd:
            self._cmd()


# ── Taschenrechner ────────────────────────────────────────────────────────────
class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculator")
        self.root.configure(bg="#8e8e93")
        self.root.resizable(False, False)

        self.current_input  = ""
        self.full_expression = ""
        self.just_evaluated = False

        self._build()

    def _build(self):
        # Äußeres Gehäuse
        outer = tk.Frame(self.root, bg=BODY, bd=6,
                         relief="ridge", padx=14, pady=14)
        outer.pack(padx=18, pady=18)

        self._build_display(outer)
        self._build_standard(outer)
        self._build_scientific(outer)

    # ── Display ───────────────────────────────────────────────────────────────
    def _build_display(self, parent):
        wrap = tk.Frame(parent, bg="#111", bd=5, relief="sunken")
        wrap.pack(fill="x", pady=(0, 12))

        inner = tk.Frame(wrap, bg=DISP_BG, padx=10, pady=8)
        inner.pack(fill="x")

        self.full_expr_var = tk.StringVar(value="")
        self.current_var   = tk.StringVar(value="0")

        tk.Label(inner, textvariable=self.full_expr_var,
                 font=("Helvetica", 10), bg=DISP_BG, fg=DISP_HINT,
                 anchor="e").pack(fill="x")
        tk.Label(inner, textvariable=self.current_var,
                 font=("Helvetica", 30, "bold"), bg=DISP_BG, fg=DISP_FG,
                 anchor="e").pack(fill="x")

    # ── Standard-Tasten ───────────────────────────────────────────────────────
    def _build_standard(self, parent):
        frame = tk.Frame(parent, bg=BODY)
        frame.pack()

        rows = [
            [("C",  self.clear,                     BTN_CLR, FONT),
             ("CE", self.clear_entry,               BTN_CLR, FONT),
             ("±",  self.toggle_sign,               BTN_NUM, FONT),
             ("÷",  lambda: self.add_op("÷"),       BTN_OP,  FONT)],
            [("7",  lambda: self.add_d("7"),         BTN_NUM, FONT),
             ("8",  lambda: self.add_d("8"),         BTN_NUM, FONT),
             ("9",  lambda: self.add_d("9"),         BTN_NUM, FONT),
             ("×",  lambda: self.add_op("×"),       BTN_OP,  FONT)],
            [("4",  lambda: self.add_d("4"),         BTN_NUM, FONT),
             ("5",  lambda: self.add_d("5"),         BTN_NUM, FONT),
             ("6",  lambda: self.add_d("6"),         BTN_NUM, FONT),
             ("-",  lambda: self.add_op("-"),        BTN_OP,  FONT)],
            [("1",  lambda: self.add_d("1"),         BTN_NUM, FONT),
             ("2",  lambda: self.add_d("2"),         BTN_NUM, FONT),
             ("3",  lambda: self.add_d("3"),         BTN_NUM, FONT),
             ("+",  lambda: self.add_op("+"),        BTN_OP,  FONT)],
            [("0",  lambda: self.add_d("0"),         BTN_NUM, FONT),
             (".",  lambda: self.add_d("."),         BTN_NUM, FONT),
             ("%",  self.percent,                   BTN_NUM, FONT),
             ("=",  self.calculate,                 BTN_OP,  FONT)],
        ]
        for r, row in enumerate(rows):
            for c, (txt, cmd, col, fnt) in enumerate(row):
                Btn3D(frame, txt, cmd, col, font=fnt, w=BW, h=BH
                      ).grid(row=r, column=c, padx=3, pady=3)

    # ── Scientific-Tasten ─────────────────────────────────────────────────────
    def _build_scientific(self, parent):
        tk.Frame(parent, bg="#3a3a3c", height=2).pack(fill="x", pady=6)

        frame = tk.Frame(parent, bg=BODY)
        frame.pack()

        sci = [
            [("sin",  lambda: self.sfn(lambda x: math.sin(math.radians(x)))),
             ("cos",  lambda: self.sfn(lambda x: math.cos(math.radians(x)))),
             ("tan",  lambda: self.sfn(lambda x: math.tan(math.radians(x)))),
             ("√",    lambda: self.sfn(math.sqrt))],
            [("log",  lambda: self.sfn(math.log10)),
             ("ln",   lambda: self.sfn(math.log)),
             ("x²",   lambda: self.sfn(lambda x: x ** 2)),
             ("1/x",  lambda: self.sfn(lambda x: 1 / x))],
            [("π",    lambda: self.insert(math.pi)),
             ("e",    lambda: self.insert(math.e)),
             ("(",    lambda: self.bracket("(")),
             (")",    lambda: self.bracket(")"))],
        ]
        for r, row in enumerate(sci):
            for c, (txt, cmd) in enumerate(row):
                Btn3D(frame, txt, cmd, BTN_NUM, font=FONT_SM, w=SW, h=SH
                      ).grid(row=r, column=c, padx=3, pady=3)

    # ── Logik ─────────────────────────────────────────────────────────────────
    def add_d(self, d):
        if self.just_evaluated:
            self.current_input = ""
            self.full_expression = ""
            self.just_evaluated = False
        if d == "." and "." in self.current_input:
            return
        if self.current_input in ("0", "") and d != ".":
            self.current_input = d
        else:
            self.current_input += d
        self.current_var.set(self.current_input)

    def add_op(self, op):
        self.just_evaluated = False
        if self.current_input:
            self.full_expression += self.current_input + " " + op + " "
        elif self.full_expression:
            parts = self.full_expression.rstrip().rsplit(" ", 1)
            self.full_expression = parts[0] + " " + op + " "
        self.full_expr_var.set(self.full_expression)
        self.current_input = ""
        self.current_var.set("0")

    def bracket(self, b):
        self.just_evaluated = False
        self.current_input += b
        self.current_var.set(self.current_input)

    def calculate(self):
        try:
            expr = self.full_expression + self.current_input
            if not expr.strip():
                return
            result = eval(expr.replace("×", "*").replace("÷", "/"))
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self.full_expr_var.set(expr + " =")
            self.current_input = str(result)
            self.current_var.set(self.current_input)
            self.full_expression = ""
            self.just_evaluated = True
        except ZeroDivisionError:
            self.current_var.set("Division durch 0!")
            self.current_input = ""
            self.full_expression = ""
        except Exception:
            self.current_var.set("Fehler")
            self.current_input = ""
            self.full_expression = ""

    def sfn(self, fn):
        try:
            val = float(self.current_input or "0")
            r = fn(val)
            if isinstance(r, float) and r.is_integer():
                r = int(r)
            self.current_input = str(r)
            self.current_var.set(self.current_input)
            self.just_evaluated = False
        except Exception:
            self.current_var.set("Fehler")
            self.current_input = ""

    def insert(self, val):
        self.current_input = str(val)
        self.current_var.set(self.current_input)
        self.just_evaluated = False

    def clear(self):
        self.current_input = ""
        self.full_expression = ""
        self.current_var.set("0")
        self.full_expr_var.set("")
        self.just_evaluated = False

    def clear_entry(self):
        self.current_input = ""
        self.current_var.set("0")
        self.just_evaluated = False

    def toggle_sign(self):
        if self.current_input and self.current_input != "0":
            if self.current_input.startswith("-"):
                self.current_input = self.current_input[1:]
            else:
                self.current_input = "-" + self.current_input
            self.current_var.set(self.current_input)

    def percent(self):
        try:
            val = float(self.current_input or "0") / 100
            self.current_input = str(val)
            self.current_var.set(self.current_input)
        except Exception:
            pass


root = tk.Tk()
Calculator(root)
root.mainloop()
