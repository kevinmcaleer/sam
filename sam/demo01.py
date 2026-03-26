from sam import SAM

sam = SAM(pin=0)

text = "Red, Yellow, Green, Brown, Blue, Black, Purple"
print(sam.text_to_phonemes(text))
sam.say(text)


sam.stop()
