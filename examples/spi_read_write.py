"""Example script to read and write SPI data using FreeWili."""

from freewili import FreeWili

fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    print(f"Connected to {fw}")
    while True:
        try:
            user_input = input("Enter data bytes seperated by spaces: ").strip().split(" ")
            data = bytes(int(x, 16) for x in user_input)
            print(f"Sending {len(data)} bytes: {data!r}")
            rx_data = fw.read_write_spi_data(data).expect("Failed to send SPI data")
            print(f"Received {len(rx_data)} bytes: {rx_data!r}")
        except (ValueError, KeyboardInterrupt):
            break
print("Goodbye!")
