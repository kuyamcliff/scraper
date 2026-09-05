from nyaa_scraper.parser import parse

FILENAMES = [
    "[SubsPlease] One Piece - 1136 [1080p][WEB-DL][H.264][AAC]",
    "[EMBER] My Hero Academia - 168 [1080p][x265][10bit]",
    "[JudAs] Jujutsu Kaisen S02E23 [1080p][HEVC][10bit]",
    "[Erai-raws] Demon Slayer - Kimetsu no Yaiba - 06 [1080p][x264][AAC]",
    "[Group] Attack on Titan Final Season Part 2 - 12 [1080p]",
    "[Group] Naruto Shippuden 220 [1080p]",
    "[Group] Bleach 001~366 [Batch][1080p]",
    "[Group] Bleach S01E01-E20 [BluRay][1080p][FLAC]",
    "[Group] Frieren - S01E28 [WEB-DL][1080p]",
    "[Group] Frieren 28 [WEB-DL][1080p]",
    "[Group] Solo Leveling - 1x12 [1080p]",
    "[Group] 86 - Eighty Six - 01 [1080p]",
    "[Group] 009-1 - 01 [720p]",
    "[Group] The Melancholy of Haruhi Suzumiya (2006) - 01 [BluRay][1080p]",
    "[Group] Kaguya-sama: Love is War - 01 [1080p]",
    "[Group] Re:ZERO -Starting Life in Another World- 01 [1080p]",
    "[Group] Fate/stay night: Unlimited Blade Works - 12 [1080p]",
    "[Group] Oshi no Ko - 11 [WEB-DL][1080p][AAC]",
    "[Group] Spice and Wolf: MERCHANT MEETS THE WISE WOLF - 25 [1080p]",
    "[Group] Monogatari Series: Second Season - 26 [1080p]",
    "[Group] Sword Art Online II - S02E24 [1080p]",
    "[Group] Dragon Ball Z - 291 [480p]",
    "[Group] Dragon Ball Super - 131 [1080p]",
    "[Group] Hunter x Hunter - 148 [720p]",
    "[Group] Fullmetal Alchemist: Brotherhood - 64 [1080p]",
    "[Group] Steins;Gate - 23 [BluRay][1080p][10bit]",
    "[Group] Vinland Saga Season 2 - 24 [1080p][WEB-DL]",
    "[Group] Mob Psycho 100 III - 12 [1080p][WEB-DL]",
    "[Group] Chainsaw Man - Episode 12 [1080p]",
    "[Group] Spy x Family Part 2 - 13 [1080p]",
    "[Group] One Punch Man 02 [1080p]",
    "[Group] A Place Further than the Universe - 13 [1080p]",
    "[Group] Made in Abyss - S02E12 [1080p]",
    "[Group] Mushoku Tensei: Jobless Reincarnation - 23 [1080p]",
    "[Group] The Apothecary Diaries - 24 [1080p]",
    "[Group] Pluto - 08 [1080p][WEB-DL]",
    "[Group] Frieren Beyond Journey's End [Movie] [2160p][HDR10]",
    "[Group] Spirited Away (2001) [2160p][HDR]",
    "[Group] Your Name (2016) Remux [2160p][TrueHD]",
    "[Group] Akira - 01 [BluRay][1920x1080][H.264][DTS-HD]",
    "[Group] Ghost in the Shell - 01 [1920x1038][H.264]",
    "[Group] Show - 01 [1440p][AV1]",
    "[Group] Show - 01 [3840x2160][HEVC][10bit][HDR10+]",
    "[Group] Show - 01 [1280x720][H.264][FLAC]",
    "[Group] Show - 07.5 [720p]",
    "[Group] Show - S00E01 [1080p]",
    "[Group] Show - Special 01 [1080p]",
    "[Group] Show - OVA 02 [1080p]",
    "[Group] Show - ONA 03 [1080p]",
    "[Group] Show - Complete Series [1080p][BluRay]",
    "[Group] Show - Season 1 - Episode 01 [1080p]",
]


def test_mass_parse_smoke():
    results = [parse(x, use_aniparse=False) for x in FILENAMES]
    assert len(results) == len(FILENAMES)
    assert sum(bool(x.title) for x in results) >= 40
    assert sum(bool(x.resolution) for x in results) >= 40
    assert all(x.filename for x in results)
