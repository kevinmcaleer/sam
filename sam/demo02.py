from sam import SAM

sam = SAM(pin=0)
print(f" sam info - {sam.info()}")

# Robot voice: low pitch, narrow mouth
sam.set_pitch(40)
sam.set_mouth(150)
sam.set_throat(90)
sam.say("i am a robot")

# High-pitched voice
sam.set_pitch(96)
sam.set_mouth(128)
sam.set_throat(128)
sam.say("hello there")

