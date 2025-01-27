import adafruit_display_text.label
import board
import displayio
import framebufferio
import rgbmatrix
import terminalio
import requests
import asyncio
from math import sqrt

ciderUrl = "http://dry-mails-report.loca.lt/api/v1/playback"

displayio.release_displays()

matrix = rgbmatrix.RGBMatrix(
    width=64,
    height=32,
    bit_depth=1,
    rgb_pins=[board.D6, board.D5, board.D9, board.D11, board.D10, board.D12],
    addr_pins=[board.A5, board.A4, board.A3, board.A2],
    clock_pin=board.D13,
    latch_pin=board.D0,
    output_enable_pin=board.D1,
)
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
    loop = asyncio.get_event_loop()

    try:
        r1 = await loop.run_in_executor(None, requests.get, ciderUrl + "/is-playing")
        if r1.status_code != 200:
            return current_text

        if r1.json()["is_playing"]:
            r2 = await loop.run_in_executor(
                None, requests.get, ciderUrl + "/now-playing"
            )
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
    loop = asyncio.get_event_loop()
    try:
        r1 = await loop.run_in_executor(None, requests.get, ciderUrl + "/volume")
        if r1.status_code != 200:
            return current_volume

        if r1.json()["volume"] != current_volume:
            updatevolume(r1.json()["volume"])
            return r1.json()["volume"]
        else:
            return current_volume
    except Exception as e:
        print("Error:", e)
        return current_text


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
            current_volume = await updatevolume_async("0")
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
