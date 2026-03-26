"""
SAM Reciter: English text to phoneme conversion.
Ported from reciter.c / ReciterTabs.h in the original SAM source.

This implements the rule-based text-to-phoneme engine. Rules have the form:
    prefix(match)suffix=phonemes
where prefix/suffix can use special wildcard characters:
    ' ' = non-alphabetic
    '#' = vowel (A E I O U Y)
    '.' = voiced consonant (B D G J L M N R V W Z)
    '&' = sibilant (S C G Z X J CH SH)
    '@' = T S R D L Z N J TH CH SH (dental/alveolar)
    '^' = consonant
    '+' = E I Y (front vowel)
    ':' = B D G J L M N R V W Z (voiced cons)
    '%' = suffix check (ER, ES, ED, ELY, EFUL, ING)
"""

# Character flags for reciter rule matching
# Indexed by ASCII value 0-127
# Bit flags:
#   0x01 = numeric
#   0x02 = alphabetic or apostrophe
#   0x04 = vowel or Y
#   0x08 = consonant  (not vowel, is alpha)
#   0x10 = voiced consonant
#   0x20 = sibilant/affricate
#   0x40 = used for rule set 2
CHAR_FLAGS = bytearray(128)

def _init_char_flags():
    global CHAR_FLAGS
    # Digits
    for c in '0123456789':
        CHAR_FLAGS[ord(c)] = 0x01
    # Vowels (also alphabetic)
    for c in 'AEIOUY':
        CHAR_FLAGS[ord(c)] = 0x06  # alpha + vowel
    # Consonants
    for c in 'BCDFGHJKLMNPQRSTVWXZ':
        CHAR_FLAGS[ord(c)] = 0x0A  # alpha + consonant
    # Voiced consonants: B D G J L M N R V W Z
    for c in 'BDGJLMNRVWZ':
        CHAR_FLAGS[ord(c)] |= 0x10
    # Sibilants: S C G Z X J
    for c in 'SCGZXJ':
        CHAR_FLAGS[ord(c)] |= 0x20
    # Apostrophe is "alphabetic"
    CHAR_FLAGS[ord("'")] = 0x02

_init_char_flags()

def _is_alpha(c):
    return CHAR_FLAGS[ord(c) & 0x7F] & 0x02 if c else False

def _is_vowel(c):
    return CHAR_FLAGS[ord(c) & 0x7F] & 0x04 if c else False

def _is_consonant(c):
    return CHAR_FLAGS[ord(c) & 0x7F] & 0x08 if c else False

def _is_voiced(c):
    return CHAR_FLAGS[ord(c) & 0x7F] & 0x10 if c else False


# ============================================================================
# The English text-to-phoneme rules
# Format: "prefix(match)suffix=phonemes"
# Rules are grouped by starting letter. Within a group, rules are tried
# in order; first match wins.
# ============================================================================

# Number pronunciation
RULES_NUM = [
    "(0)=ZIY4ROW ",
    "(1)=WAH4N ",
    "(2)=TUW4 ",
    "(3)=THRIY4 ",
    "(4)=FOH4R ",
    "(5)=FAY4V ",
    "(6)=SIH4KS ",
    "(7)=SEH4VUN ",
    "(8)=EY4T ",
    "(9)=NAY4N ",
]

# Punctuation and special characters
RULES_PUNCT = [
    "( )= ",
    "(!)=.",
    "(\")=-AH5NKWOWT-",
    "(#)= NAH4MBER",
    "($)= DAA4LER",
    "(%)= PERSEH4NT",
    "(&)= AEND",
    "(')=",
    "(()=",
    "())=",
    "(*)= AE4STERIHSK",
    "(+)= PLAH4S",
    "(,)=,",
    " (-) =-",
    "(-)=",
    "(.)=.",
    "(/)= SLAE4SH",
    "(:)=.",
    "(;)=.",
    "(<)= LEH4S DHAEN",
    "(=)= IY4KWULZ",
    "(>)= GREY4TER DHAEN",
    "(?)=?",
    "(@)= AE6T",
    "(^)= KAE4RIHT",
]

RULES_A = [
    " (A.)=EH4Y. ",
    "(A) =AH",
    " (ARE) =AAR",
    " (AR)O=AXR",
    "(AR)#=EH4R",
    " ^(AS)#=EY4S",
    "(A)WA=AX",
    "(AW)=AO5",
    " :(ANY)=EH4NIY",
    "(A)^+#=EY5",
    "#:(ALLY)=ULIY",
    " (AL)#=UL",
    "(AGAIN)=AXGEH4N",
    "#:(AG)E=IHJ",
    "(A)^+:#=AE",
    " :(A)^+ =EY4",
    "(A)^%=EY",
    " (ARR)=AXR",
    "(ARR)=AE4R",
    " ^(AR) =AA5R",
    "(AR)=AA5R",
    "(AIR)=EH4R",
    "(AI)=EY4",
    "(AY)=EY5",
    "(AU)=AO4",
    "#:(AL) =UL",
    "#:(ALS) =ULZ",
    "(ALK)=AO4K",
    "(AL)^=AOL",
    " :(ABLE)=EY4BUL",
    "(ABLE)=AXBUL",
    "(ANG)+= EY4NJ",
    "(A)=AE",
]

RULES_B = [
    " (B) =BIY4",
    " (BE) =BIH",
    " (BE)^#=BIH",
    "(BEING)=BIY4IHNX",
    " (BOTH) =BOW4TH",
    " (BUS)#=BIH4Z",
    "(BUIL)=BIH4L",
    "(B)=B",
]

RULES_C = [
    " (C) =SIY4",
    " (CH)^=K",
    "^E(CH)=K",
    "(CHA)R#=KEH5",
    "(CH)=CH",
    " S(CI)#=SAY4",
    "(CI)A=SH",
    "(CI)O=SH",
    "(CI)EN=SH",
    "(C)+=S",
    "(CK)=K",
    "(COM)%=KAHM",
    "(C)=K",
]

RULES_D = [
    " (D) =DIY4",
    " (DR.) =DAA4KTER",
    "#:(DED) =DIHD",
    ".E(D) =D",
    "#^:E(D) =T",
    " (DE)^#=DIH",
    " (DO) =DUW",
    " (DOES)=DAHZ",
    " (DOING)=DUW4IHNX",
    " (DON'T)=DOW4NT",
    "(DG)E=J",
    "(D)=D",
]

RULES_E = [
    " (E) =IY4",
    "#:(E) =",
    "':^(E) =",
    " :(E) =IY",
    "#(ED) =D",
    "#:(E)D =",
    "(EV)ER=EH4V",
    "(E)^%=IY4",
    "(ERI)#=IY4RIY",
    "(ERI)=EH4RIH",
    "#:(ER)#=ER",
    "(ER)#=EHR",
    "(ER)=ER",
    " (EVEN)=IYVEHN",
    "#:(E)N=",
    "(E)^+=IY",
    "(EW)=YUW",
    "(EY)=EY",
    "(EU)=YUW5",
    "(EIGH)=EY4",
    "(EI)=IY4",
    " (EYE)=AY4",
    "(EE)=IY4",
    "(EARL)=ER5L",
    "(EAR)^=ER5",
    "(EAD)=EHD",
    "#:(EA) =IYAX",
    "(EA)SU=EH5",
    "(EA)=IY5",
    " (EX)#=IHGZ",
    "(E)=EH",
]

RULES_F = [
    " (F) =EH4F",
    "(FUL)=FUHL",
    "(FRIEND)=FREH5ND",
    "(FATHER)=FAA4DHER",
    "(F)F=",
    "(F)=F",
]

RULES_G = [
    " (G) =JIY4",
    "(GIV)=GIH5V",
    " (G)I^=G",
    "(GE)T=GEH5",
    "SU(GGES)=GJEH4S",
    "(GG)=G",
    " B#(G)=G",
    "(G)+=J",
    "(GREAT)=GREY4T",
    "(GON)E=GAO5N",
    "#(GH)=",
    " (GN)=N",
    "(G)=G",
]

RULES_H = [
    " (H) =EY4CH",
    " (HAV)=/HAE6V",
    " (HERE)=/HIYR",
    " (HOUR)=AW5ER",
    "(HOW)=/HAW4",
    "(H)#=/H",
    "(H)=",
]

RULES_I = [
    " (IN)=IHN",
    " (I) =AY4",
    "(I) =AY",
    "(IN)D=AY5N",
    "SEM(I)=IY",
    " ANT(I)=AY",
    "(IER)=IYER",
    "#:R(IED) =IYD",
    "(IED) =AY5D",
    "(IEN)=IYEHN",
    "(IE)T=AY4EH",
    " :(I)%=AY",
    "(I)%=IY",
    "(IE)=IY4",
    "(I)^+:#=IH",
    "(IR)#=AYR",
    "(IZ)%=AY4Z",
    "(IS)%=AY4Z",
    "(I)D%=AY",
    "+^(I)^+=IH",
    "(I)T%=AY",
    "#:^(I)^+=IH",
    "(I)^+=AY",
    "(IR)=ER",
    "(IGH)=AY4",
    "(ILD)=AY5LD",
    "(IGN) =AY4N",
    "(IGN)^=AY4N",
    "(IGN)%=AY4N",
    "(IQUE)=IY4K",
    "(I)=IH",
]

RULES_J = [
    " (J) =JEY4",
    "(J)=J",
]

RULES_K = [
    " (K) =KEY4",
    " (K)N=",
    "(K)=K",
]

RULES_L = [
    " (L) =EH4L",
    "(LO)C#=LOW",
    "L(L)=",
    "#^:(L)%=UL",
    "(LEAD)=LIYD",
    "(LAUGH)=LAE4F",
    "(L)=L",
]

RULES_M = [
    " (M) =EH4M",
    " (MR.) =MIH4STER",
    " (MS.)=MIH5Z",
    " (MRS.) =MIH4SIHZ",
    "(MOV)=MUW4V",
    "(MACHIN)=MAHSHIY5N",
    "M(M)=",
    "(M)=M",
]

RULES_N = [
    " (N) =EH4N",
    "E(NG)+=NJ",
    "(NG)R=NXG",
    "(NG)#=NXG",
    "(NGL)%=NXGUL",
    "(NG)=NX",
    "(NK)=NXK",
    " (NOW) =NAW4",
    "N(N)=",
    "(NON)E=NAH4N",
    "(N)=N",
]

RULES_O = [
    " (O) =OH4",
    "(OF) =AHV",
    " (OH) =OW5",
    "(OROUGH)=ER4OW",
    "#:(OR) =ER",
    "#:(ORS) =ERZ",
    "(OR)=AOR",
    " (ONE)=WAHN",
    "(OW)=OW",
    " (OVER)=OW5VER",
    "(OV)=AH4V",
    "(O)^%=OW5",
    "(O)^EN=OW",
    "(O)^I#=OW5",
    "(OL)D=OW4L",
    "(OUGHT)=AO5T",
    "(OUGH)=AH5F",
    " (OU)=AW",
    "H(OU)S#=AW4",
    "(OUS)=AXS",
    "(OUR)=OHR",
    "(OULD)=UH5D",
    "(OU)^L=AH5",
    "(OUP)=UW5P",
    "(OU)=AW",
    "(OY)=OY",
    "(OING)=OW4IHNX",
    "(OI)=OY5",
    "(OOR)=OH5R",
    "(OOK)=UH5K",
    "(OOD)=UH5D",
    "(OO)=UW5",
    "(O)E=OW",
    "(O) =OW",
    "(OA)=OW4",
    " (ONLY)=OW4NLIY",
    " (ONCE)=WAH4NS",
    "(ON'T)=OW4NT",
    "C(O)N=AA",
    "(O)NG=AO",
    " :^(O)N=AH",
    "I(ON)=UN",
    "#:(ON) =UN",
    "#^(ON)=UN",
    "(O)ST =OW",
    "(OF)^=AO4F",
    "(OTHER)=AH5DHER",
    "(OSS) =AO5S",
    "#:^(OM)=AHM",
    "(O)=AA",
]

RULES_P = [
    " (P) =PIY4",
    "(PH)=F",
    "(PEOP)=PIY5P",
    "(POW)=PAW4",
    "(PUT) =PUHT",
    "(P)P=",
    "(P)S=",
    "(P)N=",
    "(PROF.)=PROHFEH4SER",
    "(P)=P",
]

RULES_Q = [
    " (Q) =KYUW4",
    "(QUAR)=KWOH5R",
    "(QU)=KW",
    "(Q)=K",
]

RULES_R = [
    " (R) =AA5R",
    " (RE)^#=RIY",
    "(R)R=",
    "(R)=R",
]

RULES_S = [
    " (S) =EH4S",
    "(SH)=SH",
    "#(SION)=ZHUN",
    "(SOME)=SAHM",
    "#(SUR)#=ZHUH4R",
    "(SUR)#=SHUH4R",
    "#(SU)#=ZHUW",
    "#(SSU)#=SHUW",
    "#(SED) =ZD",
    "#(S)#=Z",
    "(SAID)=SEHD",
    "^(SION)=SHUN",
    "(S)S=",
    ".(S) =Z",
    "#:.E(S) =Z",
    "#:^#(S) =S",
    "U(S) =S",
    " :#(S) =Z",
    " (SCH)=SK",
    "(S)C+=",
    "#(SM)=ZUM",
    "#(SN)'=ZUN",
    "(S)=S",
]

RULES_T = [
    " (T) =TIY4",
    " (THE) #=DHIY",
    " (THE) =DHAX",
    "(TO) =TUX",
    " (THAT)=DHAET",
    " (THIS) =DHIHS",
    " (THEY)=DHEY",
    " (THERE)=DHEHR",
    "(THER)=DHER",
    "(THEIR)=DHEHR",
    " (THAN) =DHAEN",
    " (THEM) =DHEHM",
    "(THESE) =DHIYZ",
    " (THEN)=DHEHN",
    "(THROUGH)=THRUW4",
    "(THOSE)=DHOWZ",
    "(THOUGH) =DHOW",
    "(THUS)=DHAH4S",
    "(TH)=TH",
    "#:(TED) =TIHD",
    "S(TI)#N=CH",
    "(TI)O=SH",
    "(TI)A=SH",
    "(TIEN)=SHUN",
    "(TUR)#=CHER",
    "(TU)A=CHUW",
    " (TWO)=TUW",
    "(T)T=",
    "(T)=T",
]

RULES_U = [
    " (U) =YUW4",
    " (UN)I=YUWN",
    " (UN)=AHN",
    " (UPON)=AXPAON",
    "@(UR)#=UH4R",
    "(UR)#=YUH4R",
    "(UR)=ER",
    "(U)^ =AH",
    "(U)^^=AH5",
    "(UY)=AY5",
    " G(U)#=",
    "G(U)%=",
    "G(U)#=W",
    "#N(U)=YUW",
    "@(U)=UW",
    "(U)=YUW",
]

RULES_V = [
    " (V) =VIY4",
    "(VIEW)=VYUW5",
    "(V)=V",
]

RULES_W = [
    " (W) =DAH4BULYUW",
    " (WERE)=WER",
    "(WA)S=WAH",
    "(WA)T=WAH",
    "(WHERE)=WHEHR",
    "(WHAT)=WHAHT",
    "(WHOL)=/HOWL",
    "(WHO)=/HUW",
    "(WH)=WH",
    "(WAR)=WOHR",
    "(WOR)^=WER",
    "(WR)=R",
    "(W)=W",
]

RULES_X = [
    " (X) =EH4KR",
    " (X)=Z",
    "(X)=KS",
]

RULES_Y = [
    " (Y) =WAY4",
    "(YOUNG)=YAHNX",
    " (YOUR)=YOHR",
    " (YOU)=YUW",
    " (YES)=YEHS",
    " (Y)=Y",
    "(Y)=IH",
]

RULES_Z = [
    " (Z) =ZIY4",
    "(Z)=Z",
]

# Exception dictionary: words the rules get wrong.
# Maps uppercase word to phoneme output.
# Add entries here for any word SAM mispronounces.
EXCEPTIONS = {
    'ROBOT': 'ROW4BAHT',
    'ROBOTS': 'ROW4BAHTS',
    'ROBOTIC': 'ROW4BAH4TIK',
    'MICRO': 'MAY4KROW',
    'PYTHON': 'PAY4THAHN',
    'PICO': 'PIY4KOW',
    'DATA': 'DEY4TAH',
    'COMPUTER': 'KAHMPYUW4TER',
    'AUDIO': 'AO4DIYOW',
    'VIDEO': 'VIH4DIYOW',
    'MOTOR': 'MOW4TER',
    'MOTORS': 'MOW4TERZ',
    'TOTAL': 'TOW4TUL',
    'PROGRAM': 'PROW4GRAEM',
    'PHOTO': 'FOW4TOW',
    'SOLAR': 'SOW4LER',
    'SONAR': 'SOW4NAHR',
    'MOBILE': 'MOW4BIYL',
    'HOTEL': 'HOWTEH4L',
    'TROPHY': 'TROW4FIY',
    'GLOBAL': 'GLOW4BUL',
    'LOCAL': 'LOW4KUL',
    'FOCAL': 'FOW4KUL',
    'VOCAL': 'VOW4KUL',
    'LOCATE': 'LOW4KEYT',
    'POLAR': 'POW4LER',
    'MOMENT': 'MOW4MEHNT',
    'OPEN': 'OW4PUN',
    'OVER': 'OW4VER',
    'OCEAN': 'OW4SHUN',
    'ONLY': 'OW4NLIY',
    'BONUS': 'BOW4NUHS',
    'FOCUS': 'FOW4KUHS',
    'NOTICE': 'NOW4TIHS',
    'MOTION': 'MOW4SHUN',
    'NOTION': 'NOW4SHUN',
    'POTION': 'POW4SHUN',
    'FROZEN': 'FROW4ZUN',
    'BROKEN': 'BROW4KUN',
    'SPOKEN': 'SPOW4KUN',
    'WOKEN': 'WOW4KUN',
    'TOKEN': 'TOW4KUN',
    'CHOSEN': 'CHOW4ZUN',
    'VOLTAGE': 'VOW4LTIHJ',
    'SERVO': 'SER4VOW',
    'SENSOR': 'SEH4NSER',
    'LED': 'EH4LIYDIY4',
    'GPIO': 'JIY4PIY4AY4OW4',
    'WIFI': 'WAY4FAY',
    'UART': 'YUW4AA4RT',
    'SPI': 'EH4SPIY4AY4',
}

# All rules indexed by letter
ALL_RULES = {
    ' ': RULES_PUNCT,
    'A': RULES_A, 'B': RULES_B, 'C': RULES_C, 'D': RULES_D,
    'E': RULES_E, 'F': RULES_F, 'G': RULES_G, 'H': RULES_H,
    'I': RULES_I, 'J': RULES_J, 'K': RULES_K, 'L': RULES_L,
    'M': RULES_M, 'N': RULES_N, 'O': RULES_O, 'P': RULES_P,
    'Q': RULES_Q, 'R': RULES_R, 'S': RULES_S, 'T': RULES_T,
    'U': RULES_U, 'V': RULES_V, 'W': RULES_W, 'X': RULES_X,
    'Y': RULES_Y, 'Z': RULES_Z,
}


def _parse_rule(rule_str):
    """Parse a rule string into (prefix, match, suffix, replacement)."""
    # Find the parentheses
    lp = rule_str.index('(')
    rp = rule_str.index(')')
    eq = rule_str.index('=')
    prefix = rule_str[:lp]
    match = rule_str[lp+1:rp]
    suffix = rule_str[rp+1:eq]
    replacement = rule_str[eq+1:]
    return prefix, match, suffix, replacement


def _match_prefix(text, pos, prefix):
    """
    Check if the prefix pattern matches the text before position pos.
    Scans prefix right-to-left, text right-to-left from pos-1.
    """
    tpos = pos - 1
    for i in range(len(prefix) - 1, -1, -1):
        p = prefix[i]
        if p == ' ':
            # Must be non-alphabetic
            if tpos < 0:
                continue
            c = text[tpos]
            if _is_alpha(c):
                return False
            tpos -= 1
        elif p == '#':
            # Must be a vowel
            if tpos < 0:
                return False
            if not _is_vowel(text[tpos]):
                return False
            tpos -= 1
        elif p == '.':
            # Must be voiced consonant
            if tpos < 0:
                return False
            if not _is_voiced(text[tpos]):
                return False
            tpos -= 1
        elif p == '&':
            # Must be sibilant (S C G Z X J)
            if tpos < 0:
                return False
            if text[tpos] not in 'SCGZXJ':
                return False
            tpos -= 1
        elif p == '@':
            # Must be one of: T S R D L Z N J TH CH SH
            if tpos < 0:
                return False
            if text[tpos] not in 'TSRDLZNJ':
                return False
            tpos -= 1
        elif p == '^':
            # Must be consonant
            if tpos < 0:
                return False
            if not _is_consonant(text[tpos]):
                return False
            tpos -= 1
        elif p == '+':
            # Must be E I or Y
            if tpos < 0:
                return False
            if text[tpos] not in 'EIY':
                return False
            tpos -= 1
        elif p == ':':
            # Walk through zero or more consonants
            while tpos >= 0 and _is_consonant(text[tpos]):
                tpos -= 1
        else:
            # Literal match
            if tpos < 0:
                return False
            if text[tpos] != p:
                return False
            tpos -= 1
    return True


def _match_suffix(text, pos, suffix):
    """
    Check if the suffix pattern matches the text starting at position pos.
    Scans suffix left-to-right, text left-to-right from pos.
    """
    tpos = pos
    for i in range(len(suffix)):
        s = suffix[i]
        if s == ' ':
            if tpos >= len(text):
                continue
            c = text[tpos]
            if _is_alpha(c):
                return False
            tpos += 1
        elif s == '#':
            if tpos >= len(text):
                return False
            if not _is_vowel(text[tpos]):
                return False
            tpos += 1
        elif s == '.':
            if tpos >= len(text):
                return False
            if not _is_voiced(text[tpos]):
                return False
            tpos += 1
        elif s == '&':
            if tpos >= len(text):
                return False
            if text[tpos] not in 'SCGZXJ':
                return False
            tpos += 1
        elif s == '@':
            if tpos >= len(text):
                return False
            if text[tpos] not in 'TSRDLZNJ':
                return False
            tpos += 1
        elif s == '^':
            if tpos >= len(text):
                return False
            if not _is_consonant(text[tpos]):
                return False
            tpos += 1
        elif s == '+':
            if tpos >= len(text):
                return False
            if text[tpos] not in 'EIY':
                return False
            tpos += 1
        elif s == ':':
            while tpos < len(text) and _is_consonant(text[tpos]):
                tpos += 1
        elif s == '%':
            # Check for: ING, ER, ES, ED, ELY, EFUL, ENESS
            rest = text[tpos:]
            if rest.startswith('ING'):
                tpos += 3
            elif rest.startswith('ER'):
                tpos += 2
            elif rest.startswith('ES'):
                tpos += 2
            elif rest.startswith('ED'):
                tpos += 2
            elif rest.startswith('ELY'):
                tpos += 3
            elif rest.startswith('EFUL'):
                tpos += 4
            elif rest.startswith('ENESS'):
                tpos += 5
            else:
                return False
        else:
            # Literal
            if tpos >= len(text):
                return False
            if text[tpos] != s:
                return False
            tpos += 1
    return True


def text_to_phonemes(text):
    """
    Convert English text to SAM phoneme string.

    Args:
        text: English text string

    Returns:
        Phoneme string suitable for SAM's phoneme parser
    """
    # Normalize: uppercase, add boundary spaces
    text = ' ' + text.upper() + ' '
    output = []
    pos = 1  # Skip leading space

    while pos < len(text) - 1:
        ch = text[pos]

        # Check exception dictionary for whole words
        if ch.isalpha():
            # Find the end of this word
            wend = pos
            while wend < len(text) and text[wend].isalpha():
                wend += 1
            word = text[pos:wend]
            if word in EXCEPTIONS:
                output.append(EXCEPTIONS[word])
                pos = wend
                continue

        # Handle digits
        if ch.isdigit():
            rules = ALL_RULES.get(' ', RULES_PUNCT)
            # Use number rules
            for rule in RULES_NUM:
                prefix, match, suffix, replacement = _parse_rule(rule)
                if match == ch:
                    output.append(replacement)
                    pos += 1
                    break
            else:
                pos += 1
            continue

        # Handle non-alpha characters
        if not ch.isalpha():
            if ch == ' ':
                output.append(' ')
                pos += 1
                continue
            # Try punctuation rules
            rules = RULES_PUNCT
            found = False
            for rule in rules:
                prefix, match, suffix, replacement = _parse_rule(rule)
                if text[pos:pos+len(match)] == match:
                    if _match_prefix(text, pos, prefix) and \
                       _match_suffix(text, pos + len(match), suffix):
                        output.append(replacement)
                        pos += len(match)
                        found = True
                        break
            if not found:
                pos += 1
            continue

        # Get rules for this letter
        rules = ALL_RULES.get(ch)
        if rules is None:
            pos += 1
            continue

        found = False
        for rule in rules:
            prefix, match, suffix, replacement = _parse_rule(rule)

            # Check if match fits at current position
            end_pos = pos + len(match)
            if end_pos > len(text):
                continue
            if text[pos:end_pos] != match:
                continue

            # Check prefix
            if not _match_prefix(text, pos, prefix):
                continue

            # Check suffix
            if not _match_suffix(text, end_pos, suffix):
                continue

            # Rule matches!
            output.append(replacement)
            pos += len(match)
            found = True
            break

        if not found:
            # No rule matched, skip character
            pos += 1

    return ''.join(output)
