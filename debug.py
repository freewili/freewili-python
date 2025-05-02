import time
from freewili import FreeWili
from freewili.serial_util import IOMenuCommand
from freewili.types import FreeWiliProcessorType


device = FreeWili.find_first().expect("Failed to find a FreeWili")
print(device)
#device.stay_open = True
device.open().expect("Failed to open")
# for _ in range(10):
#     for led_num in range(7):
#         resp = device.set_board_leds(led_num, 10, 10, led_num * 2).expect("Failed to set LED")
#         print("On:", led_num, resp.success)
#     for led_num in range(7):
#         resp = device.set_board_leds(led_num, 0, 0, 0).expect("Failed to set LED")
#         print("Off:", led_num, resp.success)
# resp = device.run_script("test.wasm").expect("Failed to run script")
# print("Response: ", resp)
# for _ in range(10):
#     #resp = device.set_board_leds(0, 10, 10, 10).expect("Failed to set LED")
#     #print("On:", 0, resp.success)
#     print(device.get_io().expect("Failed to get IO"))
#     print(device.set_io(25, IOMenuCommand.High).expect("Failed to set IO high"))
#     #time.sleep(0.1)
#     print(device.set_io(25, IOMenuCommand.Low).expect("Failed to set IO low"))
#resp = device.send_file("test.txt", "/scripts/test.txt", FreeWiliProcessorType.Main).expect("Failed to send file")
#print(resp)
#resp = device.get_file("/scripts/test.txt", "test.txt", FreeWiliProcessorType.Main).expect("Failed to get file")
#print(resp)
#print(device.reset_to_uf2_bootloader(FreeWiliProcessorType.Main))
print(device.main_serial.get_app_info())
device.close()
print("Done.")