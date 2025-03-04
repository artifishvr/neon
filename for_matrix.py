import adafruit_display_text.label
import board
import displayio
import framebufferio
import rgbmatrix
import terminalio
import asyncio
from math import sqrt
import os

import adafruit_connection_manager
import wifi
import adafruit_requests


ssid = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

# Initalize Wifi, Socket Pool, Request Session
pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
requests = adafruit_requests.Session(pool, ssl_context)
rssi = wifi.radio.ap_info.rssi

print(f"\nConnecting to {ssid}...")
print(f"Signal Strength: {rssi}")
try:
    # Connect to the Wi-Fi network
    wifi.radio.connect(ssid, password)
except OSError as e:
    print(f"❌ OSError: {e}")
print("✅ Wifi!")


ciderUrl = "http://cider-remote-ezurqs1yb57ilpkb4mja6ocv.loca.lt/api/v1/playback"

displayio.release_displays()

matrix = rgbmatrix.RGBMatrix(
    width=64, height=32, bit_depth=1,
    rgb_pins=[board.IO1, board.IO2, board.IO3, board.IO5, board.IO4, board.IO6],
    addr_pins=[board.IO8, board.IO7, board.IO10, board.IO9],
    clock_pin=board.IO12, latch_pin=board.IO11, output_enable_pin=board.IO13)

display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)

g = displayio.Group()
display.root_group = g

nowplayingline = adafruit_display_text.label.Label(
    terminalio.FONT, color=0xFFFFF, text="Loading..."
)
nowplayingline.x = 64  # Start offscreen to the right
nowplayingline.y = display.height // 2 - 8
g.append(nowplayingline)

volume = adafruit_display_text.label.Label(
    terminalio.FONT, color=0xFFFFF, text="■■■■■■■■■■"
)
volume.x = 0  # Start offscreen to the right
volume.y = 24
g.append(volume)

current_text = "Loading..."
keepingtrackorsomething = 0
waveform_step = 0
current_volume = "0"


def updatenowplaying(thetext) -> str:
    global nowplayingline
    nowplayingline.text = thetext
    nowplayingline.x = 64  # Reset to right edge
    return thetext


def updatevolume(newvolume) -> str:
    global volume
    volume_percent = int(sqrt(newvolume) * 10)  # undoes cider's volume curve :3c
    volume.text = "■" * volume_percent
    return newvolume


async def updateinfo(current_text: str) -> str:
    try:
        # Give control back to event loop momentarily
        await asyncio.sleep(0)
        
        # Make request directly - CircuitPython's requests are blocking
        # but this is fine in this context
        r1 = requests.get(ciderUrl + "/is-playing")
        if r1.status_code != 200:
            return current_text

        if r1.json()["is_playing"]:
            # Give control back to event loop again
            await asyncio.sleep(0)
            
            r2 = requests.get(ciderUrl + "/now-playing")
            if r2.status_code != 200:
                return current_text

            info = r2.json()["info"]
            newString = f'{info["name"]} - {info["artistName"]}'
            if newString != current_text:
                updatenowplaying(newString)
            return newString
        else:
            if current_text != "Nothing is Playing":
                updatenowplaying("Nothing is Playing")
            return "Nothing is Playing"
    except Exception as e:
        print("Error:", e)
        return current_text


async def updatevolume_async(current_volume: str) -> str:
    try:
        # Give control back to event loop momentarily
        await asyncio.sleep(0)
        
        # Make direct request
        r1 = requests.get(ciderUrl + "/volume")
        if r1.status_code != 200:
            return current_volume

        volume_data = r1.json()["volume"]
        if volume_data != current_volume:
            updatevolume(volume_data)
            return volume_data
        else:
            return current_volume
    except Exception as e:
        print("Error:", e)
        # Fixed bug: was returning current_text before
        return current_volume


async def scroll():
    while True:
        nowplayingline.x -= 1
        line_width = nowplayingline.bounding_box[2]
        if nowplayingline.x < -line_width:
            nowplayingline.x = display.width
        await asyncio.sleep(0.05)


async def maybeupdate():
    global keepingtrackorsomething, current_text, current_volume
    while True:
        keepingtrackorsomething += 1
        if keepingtrackorsomething >= 10:
            current_text = await updateinfo(current_text)
            current_volume = await updatevolume_async(current_volume)
            keepingtrackorsomething = 0
        await asyncio.sleep(1)


async def refreshdisplay():
    while True:
        display.refresh()
        await asyncio.sleep(0.1)


async def main():
    scroll_task = asyncio.create_task(scroll())
    update_task = asyncio.create_task(maybeupdate())
    refresh_task = asyncio.create_task(refreshdisplay())
    await asyncio.gather(scroll_task, update_task, refresh_task)


asyncio.run(main())