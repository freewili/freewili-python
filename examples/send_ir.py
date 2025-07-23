"""Example script to demonstrate IR NEC communication with Free-WiLi."""

from freewili import FreeWili

with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
    roku_keyhome = bytes([0xBE, 0xEF, 00, 0xFF])
    print("Sending Roku Key Home IR command:", roku_keyhome)
    fw.send_ir(roku_keyhome).expect("Failed to send IR command")
print("Done.")
