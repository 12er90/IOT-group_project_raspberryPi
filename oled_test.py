from PiicoDev_SSD1306 import *
import time

display = create_PiicoDev_SSD1306()

# xoa man hinh
display.fill(0)

# dong 1: chu to
display.text("Hello!", 30, 10, 1)

# dong 2
display.text("OLED dang chay", 4, 30, 1)

# dong 3: dem so
display.text("Test OK :)", 20, 50, 1)

display.show()
time.sleep(3)

# dem so tu 0 den 99
count = 0
while True:
    display.fill(0)
    display.text("Dem:", 10, 10, 1)
    display.text(str(count), 50, 30, 1)
    display.show()
    count += 1
    time.sleep(1)
