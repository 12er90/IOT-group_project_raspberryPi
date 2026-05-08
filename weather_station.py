"""
╔══════════════════════════════════════════════════════════════════╗
║            🌦️  PiicoDev Weather Station  🌦️                     ║
║   BME280 + VEML6030 + PiicoDev LCD 1.3" + 5V Buzzer            ║
║   Raspberry Pi Weather Monitoring System                         ║
╚══════════════════════════════════════════════════════════════════╝

══════════════════════════════════════════════════════════════════
  HARDWARE REQUIRED
══════════════════════════════════════════════════════════════════

  1. Raspberry Pi (any model with GPIO, e.g. Pi 4, Pi 3, Pi Zero 2W)
  2. PiicoDev BME280    — Temperature, Humidity & Pressure sensor
  3. PiicoDev VEML6030  — Ambient Light sensor (lux)
  4. PiicoDev OLED SSD1306 LCD 1.3" (128x64 pixels)
  5. 5V Active Buzzer
  6. PiicoDev cables    — to daisy-chain the PiicoDev modules
  7. Jumper wires       — for connecting the buzzer to GPIO
  8. (Optional) NPN transistor (e.g. 2N2222) + 1kΩ resistor
     if your buzzer draws more current than the GPIO can supply


══════════════════════════════════════════════════════════════════
  RASPBERRY PI SETUP (Step by Step)
══════════════════════════════════════════════════════════════════

  STEP 1 — Enable I2C on your Raspberry Pi:
  ──────────────────────────────────────────
    Open a terminal and run:

        sudo raspi-config

    Then navigate to:
        Interface Options  -->  I2C  -->  Enable  -->  Yes

    Reboot when prompted:

        sudo reboot


  STEP 2 — Verify I2C is working (optional but recommended):
  ───────────────────────────────────────────────────────────
    After reboot, plug in your PiicoDev modules and run:

        sudo apt install -y i2c-tools
        i2cdetect -y 1

    You should see addresses like 0x10, 0x48, 0x77, 0x3D
    (these are VEML6030, BME280 alt, BME280, and LCD).


  STEP 3 — Create a Python virtual environment:
  ──────────────────────────────────────────────
    Newer Raspberry Pi OS (Bookworm) blocks system-wide pip installs.
    You MUST use a virtual environment:

        python3 -m venv ~/weather-env

    Activate it:

        source ~/weather-env/bin/activate

    Your terminal prompt should now start with (weather-env).


  STEP 4 — Install Python dependencies:
  ──────────────────────────────────────
    With the virtual environment activated, run:

        pip install PiicoDev RPi.GPIO


  STEP 5 — Copy the script to your Pi:
  ─────────────────────────────────────
    Save this file as weather_station.py in your home directory:

        /home/pi/weather_station.py

    (Or use scp / Thonny / USB drive to transfer it.)


  STEP 6 — Run the weather station:
  ─────────────────────────────────
    Make sure your virtual environment is activated, then:

        source ~/weather-env/bin/activate
        python3 weather_station.py

    Press Ctrl+C to stop.


══════════════════════════════════════════════════════════════════
  AUTO-START ON BOOT (Optional)
══════════════════════════════════════════════════════════════════

  To make the weather station start automatically when the Pi
  boots up, create a systemd service:

  1. Create the service file:

        sudo nano /etc/systemd/system/weather-station.service

  2. Paste this content (change 'pi' if your username differs):

        [Unit]
        Description=PiicoDev Weather Station
        After=multi-user.target

        [Service]
        Type=simple
        User=pi
        ExecStart=/home/pi/weather-env/bin/python3 /home/pi/weather_station.py
        Restart=on-failure
        RestartSec=5

        [Install]
        WantedBy=multi-user.target

  3. Enable and start the service:

        sudo systemctl daemon-reload
        sudo systemctl enable weather-station.service
        sudo systemctl start weather-station.service

  4. Check status:

        sudo systemctl status weather-station.service

  5. To stop it:

        sudo systemctl stop weather-station.service


══════════════════════════════════════════════════════════════════
  CONFIGURATION
══════════════════════════════════════════════════════════════════

  You can customise the following settings in the code below:

  - BUZZER_PIN     : Change the GPIO pin number (default: 17)
  - TEMP_HIGH/LOW  : Temperature alert thresholds (°C)
  - HUMIDITY_HIGH  : Humidity alert threshold (%)
  - PRESSURE_LOW   : Low pressure / storm alert (hPa)
  - LUX_HIGH       : Bright light alert (lux)
  - SCREEN_TIME    : Seconds each screen is shown (default: 3)
  - READ_INTERVAL  : Seconds between sensor readings (default: 2)


══════════════════════════════════════════════════════════════════
  TROUBLESHOOTING
══════════════════════════════════════════════════════════════════

  Problem: "ModuleNotFoundError: No module named 'PiicoDev_BME280'"
  Fix:     Make sure your venv is activated before running.
           Run: source ~/weather-env/bin/activate

  Problem: "externally-managed-environment" error with pip
  Fix:     Never use sudo pip. Always use a virtual environment.
           See Step 3 above.

  Problem: Sensors not detected / I2C errors
  Fix:     - Check cables are firmly plugged in.
           - Make sure I2C is enabled (Step 1).
           - Run i2cdetect -y 1 to verify addresses appear.

  Problem: Buzzer not making sound
  Fix:     - Confirm wiring (+) to GPIO 17, (-) to GND.
           - Test the pin:  python3 -c "import RPi.GPIO as G; \\
             G.setmode(G.BCM); G.setup(17,G.OUT); G.output(17,1)"
           - Use a transistor if the buzzer needs more current.

  Problem: LCD shows nothing
  Fix:     - Check I2C connection and that address 0x3D appears
             in i2cdetect output.
           - Try unplugging and re-plugging the PiicoDev cable.

══════════════════════════════════════════════════════════════════
"""

import time
import math
import json
import urllib.request
import urllib.error
from PiicoDev_BME280 import PiicoDev_BME280
from PiicoDev_VEML6030 import PiicoDev_VEML6030
from PiicoDev_SSD1306 import *
import RPi.GPIO as GPIO


# ─────────────────────────────────────────────
#  CONFIGURATION — Edit these to your liking
# ─────────────────────────────────────────────

BUZZER_PIN = 17          # BCM pin number for the buzzer

# Alert thresholds
TEMP_HIGH   = 40.0       # °C — buzzer alert if exceeded
TEMP_LOW    =  5.0       # °C — buzzer alert if below
HUMIDITY_HIGH = 85.0     # %  — buzzer alert if exceeded
PRESSURE_LOW  = 1000.0   # hPa — possible storm warning
LUX_HIGH   = 80000.0     # lux — very bright sun warning

# Display cycle time (seconds per screen)
SCREEN_TIME = 3.0

# How often to read sensors (seconds)
READ_INTERVAL = 2.0

# Buzzer beep duration
BEEP_SHORT = 0.1         # seconds
BEEP_LONG  = 0.3

# ─────────────────────────────────────────────
#  HTTP POST CONFIGURATION
# ─────────────────────────────────────────────
# Set your endpoint URL below. If left as "" the
# station will NOT send any HTTP POST requests.
# Example: "https://your-server.com/api/weather"

API_ENDPOINT = ""

# Optional: extra headers (e.g. API key, auth token)
# Add as many as you need. Leave empty {} if none.
API_HEADERS = {
    # "Authorization": "Bearer YOUR_TOKEN_HERE",
    # "X-Api-Key":     "YOUR_API_KEY_HERE",
}

# How often to send data to the endpoint (seconds)
POST_INTERVAL = 30.0

# Station identifier sent in the JSON payload
STATION_ID = "pi-weather-01"


# ─────────────────────────────────────────────
#  BUZZER SETUP
# ─────────────────────────────────────────────

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.output(BUZZER_PIN, GPIO.LOW)


def buzzer_beep(duration=BEEP_SHORT, count=1):
    """Activate buzzer for a short beep."""
    for i in range(count):
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        if i < count - 1:
            time.sleep(0.1)


def buzzer_alert(pattern="warning"):
    """Play different buzzer patterns for alerts."""
    if pattern == "warning":
        buzzer_beep(BEEP_SHORT, 3)
    elif pattern == "danger":
        buzzer_beep(BEEP_LONG, 2)
    elif pattern == "startup":
        buzzer_beep(0.05, 2)
    elif pattern == "info":
        buzzer_beep(0.05, 1)


# ─────────────────────────────────────────────
#  SENSOR INITIALISATION
# ─────────────────────────────────────────────

print("Initialising sensors...")

try:
    bme280 = PiicoDev_BME280()
    print("  ✓ BME280 (Temp/Humidity/Pressure)")
except Exception as e:
    print(f"  ✗ BME280 error: {e}")
    bme280 = None

try:
    veml6030 = PiicoDev_VEML6030()
    print("  ✓ VEML6030 (Light sensor)")
except Exception as e:
    print(f"  ✗ VEML6030 error: {e}")
    veml6030 = None

try:
    display = create_PiicoDev_SSD1306()
    print("  ✓ SSD1306 OLED 1.3\" LCD")
except Exception as e:
    print(f"  ✗ LCD error: {e}")
    display = None

buzzer_alert("startup")
print("Weather Station ready!\n")


# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────

def read_sensors():
    """Read all sensor data and return a dictionary."""
    data = {
        "temp":     None,
        "humidity": None,
        "pressure": None,
        "lux":      None,
    }

    if bme280:
        try:
            data["temp"]     = bme280.values()[0]   # °C
            data["pressure"] = bme280.values()[1]   # hPa
            data["humidity"] = bme280.values()[2]   # %
        except Exception as e:
            print(f"BME280 read error: {e}")

    if veml6030:
        try:
            data["lux"] = veml6030.read()           # lux
        except Exception as e:
            print(f"VEML6030 read error: {e}")

    return data


def get_weather_condition(data):
    """Determine a simple weather description from sensor data."""
    temp = data["temp"]
    humidity = data["humidity"]
    pressure = data["pressure"]
    lux = data["lux"]

    if temp is None:
        return "No Data"

    conditions = []

    # Temperature description
    if temp > 35:
        conditions.append("Hot!")
    elif temp > 25:
        conditions.append("Warm")
    elif temp > 15:
        conditions.append("Mild")
    elif temp > 5:
        conditions.append("Cool")
    else:
        conditions.append("Cold!")

    # Humidity hints
    if humidity is not None:
        if humidity > 80:
            conditions.append("Humid")
        elif humidity < 30:
            conditions.append("Dry")

    # Pressure hints
    if pressure is not None:
        if pressure < 1000:
            conditions.append("Storm?")
        elif pressure > 1025:
            conditions.append("Clear")

    # Light hints
    if lux is not None:
        if lux > 50000:
            conditions.append("Sunny")
        elif lux > 10000:
            conditions.append("Bright")
        elif lux > 500:
            conditions.append("Cloudy")
        elif lux > 10:
            conditions.append("Dim")
        else:
            conditions.append("Dark")

    return " / ".join(conditions[:3])


def get_comfort_index(temp, humidity):
    """Calculate a simple heat index / comfort level."""
    if temp is None or humidity is None:
        return "N/A"
    # Simplified heat index
    if temp < 15:
        return "Cold"
    elif temp < 20 and humidity < 60:
        return "Comfortable"
    elif temp < 27 and humidity < 65:
        return "Pleasant"
    elif temp < 32 and humidity < 70:
        return "Warm"
    elif temp < 35 or humidity > 75:
        return "Uncomfortable"
    else:
        return "Dangerous"


def check_alerts(data):
    """Check thresholds and trigger buzzer if needed."""
    alerts = []

    if data["temp"] is not None:
        if data["temp"] > TEMP_HIGH:
            alerts.append(f"HIGH TEMP: {data['temp']:.1f}C")
        elif data["temp"] < TEMP_LOW:
            alerts.append(f"LOW TEMP: {data['temp']:.1f}C")

    if data["humidity"] is not None:
        if data["humidity"] > HUMIDITY_HIGH:
            alerts.append(f"HIGH HUM: {data['humidity']:.0f}%")

    if data["pressure"] is not None:
        if data["pressure"] < PRESSURE_LOW:
            alerts.append(f"LOW PRES: {data['pressure']:.0f}hPa")

    if data["lux"] is not None:
        if data["lux"] > LUX_HIGH:
            alerts.append(f"BRIGHT: {data['lux']:.0f}lux")

    if alerts:
        buzzer_alert("warning")
        return alerts
    return []


def format_value(value, fmt=".1f", unit=""):
    """Safely format a sensor value or show '--'."""
    if value is None:
        return f"--{unit}"
    return f"{value:{fmt}}{unit}"


# ─────────────────────────────────────────────
#  HTTP POST — Send data to endpoint
# ─────────────────────────────────────────────

def send_data(data):
    """
    Send sensor data as JSON via HTTP POST.
    Returns (success: bool, message: str).
    Skips silently if API_ENDPOINT is empty.
    """
    if not API_ENDPOINT:
        return (False, "No endpoint")

    payload = {
        "station_id":  STATION_ID,
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "temperature": data["temp"],
        "humidity":    data["humidity"],
        "pressure":    data["pressure"],
        "lux":         data["lux"],
        "alerts":      check_alerts_silent(data),
    }

    json_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent":   "PiicoDev-WeatherStation/1.0",
    }
    headers.update(API_HEADERS)

    req = urllib.request.Request(
        API_ENDPOINT,
        data=json_bytes,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")[:200]
            print(f"  📡 POST {status} -> {API_ENDPOINT}")
            return (True, f"OK ({status})")
    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}"
        print(f"  ❌ POST failed: {msg}")
        return (False, msg)
    except urllib.error.URLError as e:
        msg = str(e.reason)[:40]
        print(f"  ❌ POST failed: {msg}")
        return (False, msg)
    except Exception as e:
        msg = str(e)[:40]
        print(f"  ❌ POST failed: {msg}")
        return (False, msg)


def check_alerts_silent(data):
    """Check thresholds without triggering buzzer (for JSON payload)."""
    alerts = []
    if data["temp"] is not None:
        if data["temp"] > TEMP_HIGH:
            alerts.append(f"HIGH_TEMP:{data['temp']:.1f}")
        elif data["temp"] < TEMP_LOW:
            alerts.append(f"LOW_TEMP:{data['temp']:.1f}")
    if data["humidity"] is not None and data["humidity"] > HUMIDITY_HIGH:
        alerts.append(f"HIGH_HUMIDITY:{data['humidity']:.0f}")
    if data["pressure"] is not None and data["pressure"] < PRESSURE_LOW:
        alerts.append(f"LOW_PRESSURE:{data['pressure']:.0f}")
    if data["lux"] is not None and data["lux"] > LUX_HIGH:
        alerts.append(f"HIGH_LUX:{data['lux']:.0f}")
    return alerts


# ─────────────────────────────────────────────
#  DISPLAY SCREENS
# ─────────────────────────────────────────────

def draw_header(display, title):
    """Draw a consistent header bar on the OLED."""
    display.fill_rect(0, 0, 128, 12, 1)
    display.text(title, 2, 2, 0)  # inverted text on white bar


def screen_overview(display, data):
    """Screen 1: Overview of all readings."""
    display.fill(0)
    draw_header(display, "WEATHER STATION")

    display.text(f"T: {format_value(data['temp'], '.1f', 'C')}", 4, 16, 1)
    display.text(f"H: {format_value(data['humidity'], '.0f', '%')}", 4, 28, 1)
    display.text(f"P: {format_value(data['pressure'], '.0f', 'hPa')}", 4, 40, 1)
    display.text(f"L: {format_value(data['lux'], '.0f', 'lux')}", 4, 52, 1)

    display.show()


def screen_temperature(display, data):
    """Screen 2: Detailed temperature view."""
    display.fill(0)
    draw_header(display, "TEMPERATURE")

    temp = data["temp"]
    if temp is not None:
        # Large temperature display
        temp_str = f"{temp:.1f} C"
        display.text(temp_str, 16, 20, 1)

        # Comfort level
        comfort = get_comfort_index(temp, data["humidity"])
        display.text(f"Feel: {comfort}", 4, 38, 1)

        # Simple bar graph (0-50°C range mapped to 0-120px)
        bar_w = max(0, min(120, int(temp * 120 / 50)))
        display.fill_rect(4, 54, bar_w, 8, 1)
        display.rect(4, 54, 120, 8, 1)
    else:
        display.text("Sensor Error", 16, 30, 1)

    display.show()


def screen_humidity(display, data):
    """Screen 3: Detailed humidity view."""
    display.fill(0)
    draw_header(display, "HUMIDITY")

    hum = data["humidity"]
    if hum is not None:
        hum_str = f"{hum:.1f} %"
        display.text(hum_str, 24, 20, 1)

        # Description
        if hum > 80:
            desc = "Very Humid"
        elif hum > 60:
            desc = "Moderate"
        elif hum > 40:
            desc = "Comfortable"
        elif hum > 20:
            desc = "Dry"
        else:
            desc = "Very Dry"
        display.text(desc, 24, 36, 1)

        # Bar graph (0-100%)
        bar_w = max(0, min(120, int(hum * 120 / 100)))
        display.fill_rect(4, 54, bar_w, 8, 1)
        display.rect(4, 54, 120, 8, 1)
    else:
        display.text("Sensor Error", 16, 30, 1)

    display.show()


def screen_pressure(display, data):
    """Screen 4: Barometric pressure."""
    display.fill(0)
    draw_header(display, "PRESSURE")

    pres = data["pressure"]
    if pres is not None:
        pres_str = f"{pres:.1f}"
        display.text(pres_str, 20, 18, 1)
        display.text("hPa", 80, 18, 1)

        # Trend description
        if pres > 1025:
            trend = "High - Clear"
        elif pres > 1015:
            trend = "Normal"
        elif pres > 1005:
            trend = "Low - Change"
        else:
            trend = "Storm Warning!"
        display.text(trend, 4, 36, 1)

        # Mini bar (950-1050 hPa range)
        bar_w = max(0, min(120, int((pres - 950) * 120 / 100)))
        display.fill_rect(4, 54, bar_w, 8, 1)
        display.rect(4, 54, 120, 8, 1)
    else:
        display.text("Sensor Error", 16, 30, 1)

    display.show()


def screen_light(display, data):
    """Screen 5: Ambient light level."""
    display.fill(0)
    draw_header(display, "LIGHT LEVEL")

    lux = data["lux"]
    if lux is not None:
        lux_str = f"{lux:.0f} lux"
        display.text(lux_str, 8, 20, 1)

        # Light description
        if lux > 50000:
            desc = "Direct Sun"
        elif lux > 10000:
            desc = "Daylight"
        elif lux > 1000:
            desc = "Overcast"
        elif lux > 100:
            desc = "Indoor"
        elif lux > 10:
            desc = "Dim"
        else:
            desc = "Dark / Night"
        display.text(desc, 8, 36, 1)

        # Log-scale bar (0-100000 lux)
        if lux > 0:
            log_val = math.log10(lux + 1) / 5.0  # log10(100000) = 5
            bar_w = max(0, min(120, int(log_val * 120)))
        else:
            bar_w = 0
        display.fill_rect(4, 54, bar_w, 8, 1)
        display.rect(4, 54, 120, 8, 1)
    else:
        display.text("Sensor Error", 16, 30, 1)

    display.show()


def screen_conditions(display, data):
    """Screen 6: Overall weather conditions summary."""
    display.fill(0)
    draw_header(display, "CONDITIONS")

    condition = get_weather_condition(data)
    # Word wrap the condition string if needed
    words = condition.split(" / ")
    y = 18
    for word in words[:4]:
        display.text(word, 8, y, 1)
        y += 14

    display.show()


def screen_post_status(display, success, message):
    """Screen 7: Show last HTTP POST result on LCD."""
    display.fill(0)
    draw_header(display, "DATA UPLOAD")

    if not API_ENDPOINT:
        display.text("No endpoint", 8, 24, 1)
        display.text("configured", 12, 38, 1)
    elif success:
        display.text("Sent OK", 28, 22, 1)
        display.text(message[:21], 4, 38, 1)
    else:
        display.text("Send FAILED", 16, 22, 1)
        display.text(message[:21], 4, 38, 1)

    display.text(time.strftime("%H:%M:%S"), 32, 54, 1)
    display.show()


# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────

def main():
    """Main weather station loop."""
    print("=" * 50)
    print("  PiicoDev Weather Station — Running")
    print(f"  POST endpoint: {API_ENDPOINT or '(disabled)'}")
    print(f"  POST interval: {POST_INTERVAL}s")
    print("  Press Ctrl+C to exit")
    print("=" * 50)

    # List of display screens to cycle through
    screens = [
        screen_overview,
        screen_temperature,
        screen_humidity,
        screen_pressure,
        screen_light,
        screen_conditions,
    ]

    screen_index = 0
    last_screen_change = time.time()
    last_read = 0
    last_post = 0            # track last POST time
    post_success = None      # None = never sent yet
    post_message = ""
    data = read_sensors()
    read_count = 0

    try:
        while True:
            now = time.time()

            # ── Read sensors at interval ──
            if now - last_read >= READ_INTERVAL:
                data = read_sensors()
                last_read = now
                read_count += 1

                # Print to console
                print(
                    f"[{read_count:>5}]  "
                    f"T={format_value(data['temp'], '.1f', '°C'):>8}  "
                    f"H={format_value(data['humidity'], '.0f', '%'):>5}  "
                    f"P={format_value(data['pressure'], '.0f', 'hPa'):>8}  "
                    f"L={format_value(data['lux'], '.0f', 'lux'):>9}"
                )

                # Check for alert conditions
                alerts = check_alerts(data)
                if alerts:
                    print(f"  ⚠ ALERTS: {', '.join(alerts)}")
                    if display:
                        screen_alert(display, alerts)
                        time.sleep(2)  # hold alert screen for 2s

            # ── HTTP POST at POST_INTERVAL ──
            if now - last_post >= POST_INTERVAL:
                if API_ENDPOINT:
                    post_success, post_message = send_data(data)
                    # Briefly show upload status on LCD
                    if display:
                        screen_post_status(display, post_success, post_message)
                        time.sleep(1)
                last_post = now

            # ── Cycle display screens ──
            if display and (now - last_screen_change >= SCREEN_TIME):
                screens[screen_index](display, data)
                screen_index = (screen_index + 1) % len(screens)
                last_screen_change = now

            time.sleep(0.1)  # small sleep to reduce CPU usage

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        if display:
            display.fill(0)
            display.text("Goodbye!", 28, 28, 1)
            display.show()
        buzzer_beep(0.05, 1)
        time.sleep(1)

    finally:
        if display:
            display.fill(0)
            display.show()
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.cleanup()
        print("Weather Station stopped. GPIO cleaned up.")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()
