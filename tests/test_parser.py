import pytest
from nyaa_scraper.parser import parse

CASES = [
    ("[SubsPlease] Attack on Titan - The Final Season - 01 [1080p][H.264][AAC]", 1, None, 1080),
    ("[Group] Attack on Titan Season 3 - 01 [1080p]", 1, 3, 1080),
    ("[Group] 86 - Eighty Six - 01 [1080p][x264]", 1, None, 1080),
    ("[Group] 009-1 - 01 [720p]", 1, None, 720),
    ("[TaigaSubs]_Toradora!_(2008)_-_01v2_-_Tiger_and_Dragon_[1280x720_H.264_FLAC][1234ABCD].mkv", 1, None, 720),
    ("[Group] Show - 1920x1080 x264", None, None, 1080),
    ("[Group] Show - 1440p AV1", None, None, 1440),
    ("[Group] Show - S02E03-E05 [BluRay][10-bit][DTS-HD][1080p]", 3, 2, 1080),
    ("[Group] One Piece - 1136 [WEB-DL][1080p]", None, None, 1080),
    ("[Group] Series - 01 ~ 12 [Batch][1080p]", 1, None, 1080),
    ("[Group] Naruto Shippuden - 220 [1080p]", 220, None, 1080),
    ("[Group] Show - 07.5 [720p]", 7.5, None, 720),
    ("[Group] Show - Episode 07 [1080p]", 7, None, 1080),
    ("[Group] Show - 1x08 [1080p]", 8, 1, 1080),
    ("[Group] Spirited Away (2001) [1080p][BluRay]", None, None, 1080),
    ("[Group] Show Movie 2 [2160p][HDR10]", None, None, 2160),
    ("[Group] Show [Dual Audio][English][Japanese][1080p] - 01", 1, None, 1080),
    ("[Group] Show - 01 [WEB-DL][H.265][10bit][HDR][EAC3 5.1][1080p]", 1, None, 1080),
    ("[Group] Show - 01 [HEVC][1920x1080][FLAC]", 1, None, 1080),
    ("[Group] Fate/stay night: Unlimited Blade Works - 12 [1080p]", 12, None, 1080),
]

@pytest.mark.parametrize("filename,episode,season,res_height", CASES)
def test_parser_cases(filename, episode, season, res_height):
    t = parse(filename, use_aniparse=False)
    if episode is not None:
        assert t.episode == episode
    if season is not None:
        assert t.season == season
    assert t.height == res_height


def test_numeric_titles_are_not_destroyed():
    t = parse("[G] 86 - Eighty Six - 01 [1080p]", use_aniparse=False)
    assert t.episode == 1
    assert "Eighty Six" in t.title


def test_dash_title_not_episode_range():
    t = parse("[G] 009-1 - 01 [720p]", use_aniparse=False)
    assert t.episode == 1
    assert "009-1" in t.title


def test_dimensions_are_supported():
    t = parse("[G] Show - 1280x720 [H.264]", use_aniparse=False)
    assert (t.width, t.height) == (1280, 720)
