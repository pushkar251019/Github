# SweepGuard: hidden device detector

A free, open-source counter-surveillance web app. It runs on your phone in the browser, needs no install or account, and sends no data anywhere. You can add it to your home screen and it works offline.

| Tool | What it finds | Works on |
|---|---|---|
| Magnetic | Powered electronics and batteries in walls, chargers, smoke detectors | Chrome Android |
| Lens finder | Pinhole camera lenses (retro-reflection glint, using the torch) | Android + iPhone |
| IR / night-vision | Infrared LEDs on cameras that film in the dark | Android + iPhone |
| Bluetooth | AirTag/Find My, Tile, SmartTag, Chipolo, ESP32/Nordic DIY chips, unnamed devices, with signal strength | Chrome Android/desktop |
| RF buzz | 217 Hz GSM/SIM-bug interference and 18–22 kHz ultrasonic beacons | Android + iPhone |
| Checklist | A guided physical search, saved on the device | All |

**Limits:** a phone has no wideband radio receiver, so no app can directly detect every wireless mic (analog VHF/UHF bugs, or recorders that don't transmit). For a full RF sweep, use an RTL-SDR dongle (~$30) with SDR++ or `rtl_power`.

Run it locally with `python3 -m http.server` in this folder. The camera, mic and sensors need HTTPS or localhost.
