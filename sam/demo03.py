from sam import SAM, VOICES

sam = SAM(pin=0)

for name in VOICES:                                                           
  sam.set_voice(name)                                   
  sam.say("I am " + name) 
