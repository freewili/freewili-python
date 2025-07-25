"""Example script to load a FPGA file using FreeWili."""

from freewili import FreeWili

with FreeWili.find_first().expect("Failed to find FreeWili") as fw:
    print(f"Connected to {fw}")
    fw.load_fpga_from_file("i2c").expect("Failed to load i2c FPGA from file")
    print("FPGA loaded successfully.")
print("Goodbye!")
