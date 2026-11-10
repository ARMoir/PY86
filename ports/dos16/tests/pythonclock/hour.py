def sethour(hours, clockchar):

    if (hours > 12):
        hours -= 12
    elif (hours == 0):
        hours = 12

    if (hours == 1):
        clockchar[82] = "H" 
        clockchar[104] = "/" 
        
    if (hours == 2):
        clockchar[107] = "H" 
        clockchar[128] = "/" 
        
    if (hours == 3):
        clockchar[153] = "H" 
        clockchar[152] = "-" 
        clockchar[151] = "-"     
        
    if (hours == 4):
        clockchar[199] = "H" 
        clockchar[174] = "\\" 

    if (hours == 5):
        clockchar[220] = "H" 
        clockchar[196] = "\\" 
        
    if (hours == 6):
        clockchar[217] = "H" 
        clockchar[194] = "|" 
        
    if (hours == 7):
        clockchar[214] = "H" 
        clockchar[192] = "/" 
        
    if (hours == 8):
        clockchar[189] = "H" 
        clockchar[168] = "/" 
        
    if (hours == 9):
        clockchar[143] = "H" 
        clockchar[144] = "-" 
        clockchar[145] = "-" 
        
    if (hours == 10):
        clockchar[97] = "H" 
        clockchar[122] = "\\" 
        
    if (hours == 11):
        clockchar[76] = "H" 
        clockchar[100] = "\\" 
        
    if (hours == 12):
        clockchar[79] = "H" 
        clockchar[102] = "|" 

    return clockchar
