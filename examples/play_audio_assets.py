"""Example script to play audio on the FreeWili."""

import time

from freewili import FreeWili

# https://docs.freewili.com/downloads/FwROMAudioAssets.pdf
AUDIO_NAMES = (
    "1",
    "10",
    "2",
    "3",
    "4",
    "42",
    "5",
    "6",
    "7",
    "8",
    "9",
    "About",
    "AllYourBases",
    "beephigh",
    "ChooseYourDestiny",
    "click",
    "daisy",
    "DaveICantDoThat",
    "DefCon",
    "Dominating",
    "DoOrDoNot",
    "DoubleKill",
    "EndOfLine",
    "Engage",
    "Excellent",
    "ExcuseMe",
    "FearIsTheMindKiller",
    "FreeWilli",
    "GodLike",
    "GoodJob",
    "GPIO",
    "GUI",
    "GUISettings",
    "GUITerminal",
    "HackMe",
    "HangTough",
    "HaveACupcake",
    "HolyShit",
    "I2C",
    "IllBeBack",
    "ImThinking",
    "Infinity",
    "Invalid",
    "IR",
    "ItsTime",
    "KillingSpree",
    "LudacrisKill",
    "MegaKill",
    "Minus",
    "MonsterKill",
    "MultiKill",
    "No",
    "NoWay",
    "NoWayWithLaugh",
    "Orca",
    "palebluedot",
    "PinOut",
    "PlansWithinPlans",
    "Plus",
    "Point",
    "PorqueNo",
    "Radios",
    "Rampage",
    "Revenge",
    "ScanMeHarder",
    "Scripts",
    "Settings",
    "shame",
    "ShutUpWesely",
    "SmileAndBeHappy",
    "Sorry",
    "SoSayWeAll",
    "SPI",
    "Sweet",
    "Tasty",
    "Terminal",
    "ThanksForAllTheFish",
    "tom",
    "UART",
    "UltraKill",
    "UnstopableWind",
    "unstoppable",
    "UserError",
    "VivaLosVegas",
    "WarWarNeverChanges",
    "Welcome",
    "WhaleEver",
    "WhaleThankU",
    "What",
    "WickedSick",
    "Yes",
)

fw = FreeWili.find_first().expect("Failed to find FreeWili")
with fw:
    print(f"Connected to FreeWili {fw}")
    print("type 'list' to see audio assets or 'exit' to quit.")
    while True:
        try:
            user_input = input("Enter to play audio asset (1-{}): ".format(len(AUDIO_NAMES)))
            value = int(user_input) - 1  # Convert to zero-based index
            print(f"\tPlaying: {AUDIO_NAMES[value]}")  # Fixed index here
            fw.play_audio_asset(value).expect("Failed to play audio asset")
            time.sleep(1)  # Give some time for the audio to play, playing is async
        except ValueError:
            if user_input.lower() == "list":
                for i, name in enumerate(AUDIO_NAMES, start=1):
                    print(f"\t{i}: {name}")
                continue
            print("Goodbye!")
            break
    print("Done.")
