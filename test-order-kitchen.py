"""
Receipt printer script for Gruppo Scout VILLAFRANCA DI FORLI' 1
Uses python-escpos library: https://github.com/python-escpos/python-escpos

Install with:
    pip install python-escpos

Usage:
    python print_bill.py
"""

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

    # ── Group header ────────────────────────────────────────────────────────
    p.set(align="center", bold=True, double_height=True, double_width=True)
    p.text("ORDINE 1\n\n")

    # ── Separator ────────────────────────────────────────────────────────────
    p.text("-" * LINE_WIDTH + "\n")

    # ── Column header (double height) ────────────────────────────────────────
    # python-escpos handles the Euro sign natively via the codepage system.
    p.set(align="left", double_height=True)
    p.text("1 MENU CLASSICO\n")

    p.set(normal_textsize=True)

    # ── Total (double height) ────────────────────────────────────────────────
    p.text("-" * LINE_WIDTH + "\n")
    p.set(align="center", bold=True, double_height=True, double_width=True)
    p.text("EAT IN\n")

    # ── Cut ──────────────────────────────────────────────────────────────────
    p.cut()


if __name__ == "__main__":
    print_bill()