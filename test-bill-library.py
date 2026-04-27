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


def build_header_row(label: str, value: str, width: int = LINE_WIDTH) -> str:
    """Return a left/right aligned string padded to `width` characters."""
    spaces = width - len(label) - len(value)
    return label + " " * max(spaces, 1) + value


def print_bill(printer_ip: str = PRINTER_IP, port: int = PRINTER_PORT) -> None:
    p = Network(printer_ip, port, profile="KR-306")
    p._raw(_CMD_CP858)

    # ── Logo ────────────────────────────────────────────────────────────────
    p.image(LOGO_PATH, center=True)

    # ── Group header ────────────────────────────────────────────────────────
    p.set(align="center", bold=True, normal_textsize=True)
    p.text("Gruppo Scout\n")
    p.text("VILLAFRANCA DI FORLI' 1\n")
    p.set(align="center", bold=False)
    p.text("Via Lughese 269\n")
    p.text("47122, FORLI' (FC)\n")
    p.text("\n")

    # ── Group header ────────────────────────────────────────────────────────
    p.set(align="center", bold=True, double_height=True, double_width=True)
    p.text("ORDINE 1\n")

    # ── Column header (double height) ────────────────────────────────────────
    # python-escpos handles the Euro sign natively via the codepage system.
    p.set(align="left", double_height=True)
    header = build_header_row("DESCRIZIONE", "Prezzo (\xd5)") # \u20ac
    p.text(header + "\n\n")
    p.set(normal_textsize=True)

    # ── Line items ───────────────────────────────────────────────────────────
    p.set(align="left")
    p.text(build_header_row("MENU CLASSICO", "9,00") + "\n")

    # ── Separator ────────────────────────────────────────────────────────────
    p.text("-" * LINE_WIDTH + "\n")

    # ── Total (double height) ────────────────────────────────────────────────
    p.set(align="left", double_height=True)
    p.text(build_header_row("TOTALE COMPLESSIVO", "9,00") + "\n")
    p.set(normal_textsize=True)

    # ── Footer ───────────────────────────────────────────────────────────────
    p.set(align="center")
    doc_number = 1
    now = datetime.datetime.now()
    p.text(f"\n{now.strftime('%d-%m-%Y  %H:%M')}\n")
    p.text(f"DOCUMENTO N. {doc_number:03d}\n")
    p.text("\nSCONTRINO NON FISCALE\n\n")

    # ── Cut ──────────────────────────────────────────────────────────────────
    p.cut()


if __name__ == "__main__":
    print_bill()