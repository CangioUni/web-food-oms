"""
Receipt printer script for Gruppo Scout VILLAFRANCA DI FORLI' 1
Uses python-escpos library: https://github.com/python-escpos/python-escpos

Install with:
    pip install python-escpos

Usage:
    python print_bill.py
"""

import datetime
from escpos.printer import Network

PRINTER_IP   = "10.0.0.200"
PRINTER_PORT = 9100
LINE_WIDTH   = 48       # characters per line at normal font
LOGO_PATH    = "rblogo.png"

_CMD_CP858      = b'\x1b\x74\x13'
EURO_SYMBOL = b'\xd5'

def build_header_row(label: str, value: str, width: int = LINE_WIDTH) -> str:
    """Return a left/right aligned string padded to `width` characters."""
    spaces = width - len(label) - len(value)
    return label + " " * max(spaces, 1) + value


def print_bill(printer_ip: str = PRINTER_IP, port: int = PRINTER_PORT) -> None:
    p = Network(printer_ip, port, profile="KR-306")
    p.codepage = 'cp858'
    p._raw(b'\x1b\x74\x0e')

    # p.charcode('CP858')


    # ── Group header ────────────────────────────────────────────────────────
    p.set(align="center", bold=True, double_height=True)
    p.text("CAMST SOC. COOP. a R.L.\n")
    p.set(align="center", bold=False, normal_textsize=True)
    p.text("MENSA UNIVERSITA' INGEGNERIA\n")
    p.text("VIALE RISORGIMENTO, 2\n")
    p.text("40126 - BOLOGNA (BO)\n")

    p.set(align="center", bold=True, normal_textsize=True)
    p.text("Is. Albo Coop. a M.P. n. A100118\n")
    p.text("P.I. 00501611206 - C.F. 00311310379\n")
    p.text("\n")
    p.text("DOCUMENTO COMMERCIALE\n")
    p.text("di vendita o prestazione\n\n")

    # ── Column header (double height) ────────────────────────────────────────
    # python-escpos handles the Euro sign natively via the codepage system.
    p.set(align="left", bold=True, normal_textsize=True)
    header = build_header_row("DESCRIZIONE", 'IVA     Prezzo (\xd5)') # \u20ac
    p.text(header + "\n")
    p.set(normal_textsize=True)

    # ── Line items ───────────────────────────────────────────────────────────
    p.set(align="left")
    p.text(build_header_row("PASTO CRISTINA", "4,00%          5,00") + "\n")

    # ── Separator ────────────────────────────────────────────────────────────
    p.text("\n")

    # ── Total (double height) ────────────────────────────────────────────────
    p.set(align="left", double_height=True)
    p.text(build_header_row("TOTALE COMPLESSIVO", "5,00") + "\n")
    p.text(build_header_row("di cui IVA", "0,20") + "\n")
    p.set(normal_textsize=True)
    p.text(build_header_row("\nPagamento elettronico", "5,00") + "\n")
    p.text(build_header_row("Importo pagato", "5,00") + "\n")
    p.text("\n")

    p.set(align="center", bold=False, normal_textsize=True)
    p.text("22-04-2026 12:20\n")
    p.text("DOCUMENTO N. 1032-0030\n")
    
    p.text("\n")
    p.set(align="center", bold=True, normal_textsize=True)
    p.text("DETTAGLIO FORME di PAGAMENTO\n")
    p.set(align="left", normal_textsize=True)
    p.text(build_header_row("BANCOMAT CARTE CREDITO", "5,00") + "\n")

    # ── Cut ──────────────────────────────────────────────────────────────────
    p.cut()


if __name__ == "__main__":
    print_bill()