from sam import SAM                                                           
  
sam = SAM(pin=0)                                                              
                                                        
# Note-to-pitch mapping (lower value = higher note)                           
N = {
  'C3':96, 'D3':86, 'E3':76, 'F3':72, 'G3':64, 'A3':57, 'B3':51,            
  'C4':48, 'D4':43, 'E4':38, 'F4':36, 'G4':32, 'A4':28,                     
  'R':0,                                                                    
}                                                                             
                                                                            
# "Daisy Bell" in 3/4 waltz time                                              
# Each tuple: (pitch, phonemes, beats)
daisy_bell = [                                                                
  # "Daisy, Daisy,"                                     
  (N['G3'], 'DEY4',  1.5),                                                  
  (N['E3'], 'ZIY',   1.5),                                                  
  (N['C3'], 'DEY4',  1.5),                                                  
  (N['C3'], 'ZIY',   1.5),                                                  
                                                                            
  # "give me your answer do,"                                               
  (N['D3'], 'GIH4V', 1),                                                    
  (N['E3'], 'MIY4',  1),                                                    
  (N['F3'], 'YOHR',  1),                                
  (N['E3'], 'AE4N',  1.5),                                                  
  (N['D3'], 'SER',   0.5),                                                  
  (N['C3'], 'DUW4',  2),                                                    
  (N['R'],  '',      1),                                                    
                                                                            
  # "I'm half crazy,"                                                       
  (N['E3'], 'AY4M',  1.5),                                                  
  (N['F3'], 'HAE4F', 1.5),                                                  
  (N['G3'], 'KREY4', 1.5),
  (N['G3'], 'ZIY4',  1.5),                                                  
                                                        
  # "all for the love of you."                                              
  (N['A3'], 'AOL',   1),                                
  (N['G3'], 'FOHR',  1),                                                    
  (N['F3'], 'DHAX',  1),                                                    
  (N['E3'], 'LAH4V', 1),
  (N['D3'], 'AHV',   0.5),                                                  
  (N['C3'], 'YUW4',  2.5),                              
]                                                                             
                                                        
sam.sing(daisy_bell, bpm=80)     
