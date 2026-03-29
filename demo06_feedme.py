from sam import SAM, VOICES
from time import sleep

sam = SAM(pin=0)

while True:
  sam.set_voice('robot')
  sam.say("Help! Feed me!")
  sleep(0.5)