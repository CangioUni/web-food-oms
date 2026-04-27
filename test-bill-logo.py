import socket
from PIL import Image, ImageOps

# General commands
init = b'\x1B\x40'          # Init bill
cut = b'\x1D\x56\x42\x00'   # Cut bill
text_center = b'\x1b\x61\x01'  # Center text
text_left = b'\x1b\x61\x00'    # Left text

# Select Code Table (Example: n=19 for PC858 which includes Euro)
SELECT_TABLE = b'\x1b\x74\x13' 

# The Euro symbol byte in PC858 is 0xD5
INIT = b'\x1b\x40'
CODE_PAGE_858 = b'\x1b\x74\x13' # PC858
EURO_SYMBOL = b'\xd5'              # Euro symbol in PC858
DBL_HEIGHT = b'\x1d\x21\x01'     # Double height
NORMAL_SIZE = b'\x1d\x21\x00'    # Reset size

header_gruppo = text_center + b"\n\x1B\x45\x01Gruppo Scout\nVILLAFRANCA DI FORLI' 1\x1B\x45\x00\nVia Lughese 269\n47122, FORLI' (FC)\n\n"
footer_text = text_center + b"\nSCONTRINO NON FISCALE\n\n"

def get_logo_data(image_path, printer_width=576):
    """
    Converts image to monochrome ESC/POS raster format with scaling and centering.
    
    Pixel Width Reference:
    - 80mm paper: ~576 pixels (Standard 203 DPI)
    - 58mm (57mm) paper: ~384 pixels
    """

    img = Image.open(image_path).convert('L')
    width, height = img.size

    # Scale down if image exceeds printer width
    if width > printer_width:
        ratio = printer_width / float(width)
        new_height = int(float(height) * float(ratio))
        img = img.resize((printer_width, new_height), Image.Resampling.LANCZOS)
        width, height = img.size

    # Invert and convert to 1-bit monochrome
    img = ImageOps.invert(img)
    img = img.convert('1')
    
    width_bytes = (width + 7) // 8
    
    # Calculate centering offset
    offset = max(0, (printer_width - width) // 2)
    
    # GS L: Set left margin
    margin_header = bytes([0x1D, 0x4C, offset & 0xFF, (offset >> 8) & 0xFF])
    
    # GS v 0: Raster image header
    raster_header = bytes([
        0x1D, 0x76, 0x30, 0x00, 
        width_bytes & 0xFF, (width_bytes >> 8) & 0xFF, 
        height & 0xFF, (height >> 8) & 0xFF
    ])
    
    # GS L 0 0: Reset margin to zero
    reset_margin = bytes([0x1D, 0x4C, 0x00, 0x00])
    
    return margin_header + raster_header + img.tobytes() + reset_margin

def get_header(width=48):
    left = "DESCRIZIONE"
    # Construct "PREZZO (€)" using the Euro byte
    right = b"Prezzo (" + EURO_SYMBOL + b")"
    
    # Calculate padding based on character count
    # Note: Double height does not change character width/count per line
    current_len = len(left) + len(right)
    spaces = width - current_len
    
    line = left.encode('ascii') + (b' ' * spaces) + right + b'\n\n'
    return DBL_HEIGHT + line + NORMAL_SIZE

def text_left_right(text_l, text_r, width=48):
    # Print two strings with left and right alignemnt in same line

    # Calculate padding based on character count
    current_len = len(text_l) + len(text_r)
    spaces = width - current_len
    
    line = text_l.encode('ascii') + (b' ' * spaces) + text_r.encode('ascii') + b'\n'
    return line

def print_bill(printer_ip, port=9100):
    
    # Commands
    logo = get_logo_data("rblogo.png")
    # text = b"Order #1\n"
    # text2 = b"Item: CAFFE' - EUR 1,00\n\n"
    
    bill_text = init + logo + CODE_PAGE_858 + header_gruppo
    bill_text = bill_text + get_header(width=48)
    bill_text = bill_text + text_left_right("MENU CLASSICO", "9,00")
    bill_text = bill_text + (b'-' * 48)
    bill_text = bill_text + DBL_HEIGHT + text_left_right("TOTALE COMPLESSIVO", "9,00") + NORMAL_SIZE
    bill_text = bill_text + footer_text + cut

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((printer_ip, port))
            
            # s.sendall(init + logo + header_gruppo + footer_text + cut)
            s.sendall(bill_text)
            # s.sendall(init + logo + CODE_PAGE_858 + header_gruppo + get_header(width=48) + text_left_right("", text_r, width=48) + footer_text + cut)
            
            print(f"Sent to {printer_ip}")
    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    print_bill("10.0.0.200")
