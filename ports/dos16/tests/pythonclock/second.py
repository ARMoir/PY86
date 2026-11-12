def setsecond(seconds, minute, clockchar):
     if (seconds % 2 == 0):

        if (minute == 0):
            clockchar[148] = "*"

        elif (minute ==1):  
            clockchar[37] = "*" 
        
        elif (minute ==2):
            clockchar[86] = "*" 
        
        elif (minute ==3):       
            clockchar[155] = "*"       

        elif (minute ==4):       
            clockchar[224] = "*"       

        elif (minute ==5):       
            clockchar[267] = "*"
        
        elif (minute ==6):       
            clockchar[263] = "*"
        
        elif (minute ==7):       
            clockchar[259] = "*"
        
        elif (minute ==8):       
            clockchar[210] = "*" 
        
        elif (minute ==9):   
            clockchar[141] = "*"
     
     return clockchar
