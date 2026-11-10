def setminute(minutes, clockchar):

    if(minutes >= 55):
        clockchar[52] = "M"
        clockchar[76] = "\\"
        clockchar[100] = "\\"

    elif(minutes >= 50):
        clockchar[73] = "M" 
        clockchar[97] = "\\"
        clockchar[122] = "\\"

    elif(minutes >= 45):
        clockchar[142] = "M"
        clockchar[143] = "-"
        clockchar[144] = "-" 
        clockchar[145] = "-"

    elif(minutes >= 40):
        clockchar[211] = "M"
        clockchar[189] = "/"
        clockchar[168] = "/"

    elif(minutes >= 35):
         clockchar[236] = "M"
         clockchar[214] = "/" 
         clockchar[192] = "/" 

    elif(minutes >= 30):
        clockchar[240] = "M"
        clockchar[217] = "|";
        clockchar[194] = "|" 

    elif(minutes >= 25):
        clockchar[244] = "M" 
        clockchar[220] = "\\" 
        clockchar[196] = "\\"

    elif(minutes >= 20):
        clockchar[223] = "M"
        clockchar[199] = "\\"
        clockchar[174] = "\\"

    elif(minutes >= 15):
        clockchar[154] = "M"
        clockchar[153] = "-"
        clockchar[152] = "-"
        clockchar[151] = "-"

    elif(minutes >= 10):
        clockchar[85] = "M"
        clockchar[107] = "/"
        clockchar[128] = "/"

    elif(minutes >= 5):
        clockchar[60] = "M"
        clockchar[82] = "/"
        clockchar[104] = "/"

    elif(minutes >= 0):
        clockchar[56] = "M"
        clockchar[79] = "|"
        clockchar[102] = "|" 

    return clockchar
