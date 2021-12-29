import argparse
import os
import requests

import pykakasi
kks = pykakasi.kakasi()

blank = "@"
after = lambda sep: lambda s: s.split(sep)[1]
before = lambda sep: lambda s: s.split(sep)[0]

def is_whistle(circle):
    """set of hitsounds must be exactly {whistle}"""
    content = circle.split(sep=',')
    hs = int(content[4])
    return hs == 2

def parse_interval(circles, daisuu):
    """
    parses the hitobjects of a .osu file for ishotyping intervals
    :param circles: list of hitcircles
    :param daisuu: expected number of nonempty lines
    :return: interval lengths and whether they're empty: [(int, bool)]
    """
    outputs = []
    lastt = 0
    num_lines = 0
    for circle in circles:
        try:
            # print(circle)
            [x, y, t, rest] = circle.split(sep=',', maxsplit=3)
            t = int(t)
        except ValueError:
            print('fuck osu')
            print(circles)
            return

        intvl = t - lastt
        lastt = t
        is_break = is_whistle(circle)
        num_lines += not is_break
        outputs.append((intvl, is_break))
    assert num_lines == daisuu, f"{num_lines} != {daisuu}"
    return outputs

def parse_xml(s):
    """
    parses an ishotyping xml file except for interval
    :param s: file contents
    :return:
        header: str content before daisuu tags
        daisuu: number of nonempty lines (NOT number in the file)
        nihongo: list of contents of <nihongoword> tags (no blanks)
        word: same for <word>
    """
    [header, s] = s.split("<saidaimondaisuu>")
    s = after("</saidaimondaisuu>")(s)

    nonempty = lambda s: s != blank

    nihongo_raw = s.split("</nihongoword>")
    s = nihongo_raw.pop()
    nihongo = list(filter(nonempty, map(after("<nihongoword>"), nihongo_raw)))

    word_raw = s.split("</word>")
    word_raw.pop()
    word = list(filter(nonempty, map(after("<word>"), word_raw)))

    # assert len(nihongo) == len(word)
    return header, len(nihongo), nihongo, word

def make_xml(header, nihongo, word, interval):
    """
    reconstructs ishotyping xml file
    uses interval to determine locations of blanks, and for daisuu
    :param header: str content before daisuu tags
    :param nihongo: list of contents of <nihongoword> tags (no blanks)
    :param word: same for <word>
    :param interval: desired timing intervals and whether they're empty: [(int, bool)]
    :return: reconstructed file contents
    """
    output = header.lstrip()
    daisuu = len(interval)
    output += f"<saidaimondaisuu>{daisuu}</saidaimondaisuu>"
    output += "\n    "

    nihongo_strs = []
    word_strs = []
    interval_strs = []
    for intvl, is_blank in interval:
        n, w = blank, blank
        if not is_blank:
            n, w = nihongo.pop(0), word.pop(0)
        nihongo_strs.append(f"<nihongoword>{n}</nihongoword>\n    ")
        word_strs.append(f"<word>{w}</word>\n    ")
        interval_strs.append(f"<interval>{intvl}</interval>")

    output += "".join(nihongo_strs)
    output += "".join(word_strs)
    output += "\n    ".join(interval_strs)
    output += "\n"
    output += "</musicXML>"
    output += "\n"
    return output

def scrape_lyrics(url):
    """
    finds lyrics from typing.twi1.me site
    :param url: such as https://typing.twi1.me/game/120064
    :return: list of lyric lines, list of furigana lines
    """
    r = requests.get(url)
    site_str = r.text
    site_str = before("""<div id="questionBoxTail">""") \
        (after("""<div class="questions blockQuestions">""")(site_str))
    questions = site_str.split("""<div class="question">""")[1:]

    def parse_question(question):
        """parses a single line of lyrics"""
        question = before("""</p>\n\t\t\t\t\t\t\t\t\t\t\t\t\t</div>""") \
            (after("""<p class="kana">""")(question))
        [word, nihongo] = question.split("""<p class="kanji">""")
        word = list(word)
        for i in range(len(word)):  # sub normal chars in for unicode fullwidth
            twi, fullwidth_twi = ord("!"), ord("！")
            if ord(word[i]) in range(fullwidth_twi, fullwidth_twi+94):
                word[i] = chr(ord(word[i]) + twi - fullwidth_twi)
        word = before("""</p>""")("".join(word))[1:-1]  # strip parens
        return nihongo, word
    questions = list(map(parse_question, questions))
    return [a for a,b in questions], [b for a,b in questions]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help="a typing.twi1.me page for lyrics (if using this, "
                                      "path doesn't need to be an existing .xml file)")
    parser.add_argument('--convert', dest='convert', action="store_const",
                        const=True, default=False,
                        help="autogenerate kana readings of japanese kanji lyrics "
                             "using pykakasi")
    parser.add_argument('-f', '--force', dest='force', action="store_const",
                        const=True, default=False,
                        help="force changes (i.e. do not make a backup even if "
                             "file already exists)")
    parser.add_argument('osupath', help="path to .osu file containing timings")
    parser.add_argument('path', help="path to output .xml file (which should contain "
                                     "lyrics if not using --url option)")

    args = parser.parse_args()
    path_osu = args.osupath
    path = args.path
    assert path_osu[-4:] == ".osu", f"argument {path_osu} not a .osu file"
    assert path[-4:] == ".xml", f"argument {path} not a .xml file"

    if os.path.exists(path):
        if not args.force:  # save backup
            print(f"saving backup copy of {path}...")
            with open(path, mode='r', encoding='UTF-8') as f:
                s = f.read()
            path_old = path[:-4] + "_old.xml"
            old_index = 1
            while os.path.exists(path_old):
                path_old = path[:-4] + f"_old_{old_index}.xml"
                old_index += 1
            with open(path_old, mode='w', encoding='UTF-8') as f_old:
                f_old.write(s)
            print(f"backup saved to {path_old}")
        else:
            print(f"overwriting existing content of {path} due to --force flag")

    if args.url:  # taking lyrics from provided typing.twi1.me page
        url = args.url
        nihongo, word = scrape_lyrics(url)
        header = """
    <?xml version='1.0' encoding='UTF-8' standalone='yes'?>
    <musicXML>
        """
        daisuu = len(word)
        print(f"found {daisuu} lines of lyrics from {url}")

    else:  # using lyrics already contained in destination .xml file
        assert os.path.exists(path)
        with open(path, mode='r', encoding='UTF-8') as f:
            s = f.read()
        header, daisuu, nihongo, word = parse_xml(s)
        print(f"found {daisuu} lines of lyrics in {path}")
        if args.convert:  # automatically convert kanji lyrics to kana
            print(f"automatically generating kana lyrics using pykakasi...")
            def to_kana(text):
                result = kks.convert(text)
                return "".join(item['hira'] for item in result)
            word = list(map(to_kana, nihongo))
        else:
            assert len(nihongo) == len(word)

    with open(path_osu, mode='r', encoding='UTF-8') as f:
        osu = f.read()
        [stuff, circles_str] = osu.split("[HitObjects]")
        circles = circles_str.split('\n')
        circles = list(filter(lambda x: x != '', circles))
        print(f"found {len(circles)} hitobjects in {path_osu}")

    interval = parse_interval(circles, daisuu)

    with open(path, mode='w', encoding='UTF-8') as f:
        f.write(make_xml(header, nihongo, word, interval))
    print(f"game file written to {path}")
