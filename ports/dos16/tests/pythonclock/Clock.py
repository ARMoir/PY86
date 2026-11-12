import os
import time
import datetime

from face import *
from hour import *
from minute import *
from second import *

def split(frame):
    return [char for char in frame]

def clear():
    if os.name in ('nt','dos'):
        os.system("cls")
    elif os.name in ('linux','osx','posix'):
        print("\033[H\033[J") 
    else:
        print("\n") * 120

while True:   
    clockchar = ""
    clockstring = ""
    display = ""
   
    clockstring = setface()
    clockchar = split(clockstring)

    ctime = datetime.datetime.now()
    hours = ctime.hour
    minutes = ctime.minute
    seconds = ctime.second
    minute = minutes % 10

    clockchar = sethour(hours, clockchar)
    clockchar = setminute(minutes, clockchar)
    clockchar = setsecond(seconds, minute, clockchar)

    for val in clockchar: 
        display += val 

    print(display)
    time.sleep(1)
    clear()


