"""Detect the genre of a whole script and the mood of each passage.

Offline lexicon scoring by default; if ANTHROPIC_API_KEY is set, Claude is
asked to label genre and per-passage moods (more accurate), with the lexicon
as fallback."""
import json
import re
from collections import Counter

import httpx

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL

MOODS = ["calm", "joyful", "sad", "suspense", "horror", "romantic", "epic",
         "mystery", "inspirational", "whimsical", "informative"]

LEXICON: dict[str, set[str]] = {
    "calm": {"quiet", "gentle", "soft", "peace", "peaceful", "still", "breeze", "meadow",
             "river", "silence", "slowly", "rest", "calm", "serene", "breathe", "moon",
             "morning", "garden", "meditate", "meditation", "relax", "sleep", "dream", "shanti"},
    "joyful": {"laugh", "laughed", "laughing", "smile", "smiled", "happy", "joy", "delight",
               "celebrate", "celebration", "party", "cheer", "fun", "bright", "sunny", "dance",
               "danced", "sing", "sang", "festival", "wonderful", "giggle", "hooray"},
    "sad": {"tears", "tear", "cried", "cry", "weep", "wept", "grief", "sorrow", "lonely",
            "alone", "loss", "lost", "died", "death", "funeral", "goodbye", "mourning",
            "heartbroken", "pain", "regret", "miss", "missed", "empty", "grave"},
    "suspense": {"suddenly", "footsteps", "breath", "heart", "pounding", "waited", "hide",
                 "hid", "escape", "chase", "run", "ran", "danger", "trap", "seconds",
                 "silent", "creak", "creaked", "behind", "watching", "tense", "gun", "knife"},
    "horror": {"blood", "scream", "screamed", "ghost", "corpse", "dead", "demon", "monster",
               "shadow", "shadows", "darkness", "terror", "horror", "haunted", "skull",
               "rotting", "evil", "curse", "cursed", "nightmare", "fear", "dread", "witch"},
    "romantic": {"love", "loved", "kiss", "kissed", "heart", "embrace", "darling", "beloved",
                 "lips", "tender", "longing", "desire", "passion", "romance", "wedding",
                 "eyes", "touch", "blush", "blushed", "sweetheart", "pyaar"},
    "epic": {"battle", "war", "army", "sword", "king", "kingdom", "queen", "hero", "glory",
             "warrior", "empire", "dragon", "legend", "victory", "fought", "charge",
             "thunder", "conquer", "destiny", "throne", "march", "shield", "fire"},
    "mystery": {"clue", "detective", "secret", "mystery", "strange", "puzzle", "murder",
                "inspector", "suspect", "evidence", "hidden", "letter", "key", "door",
                "unknown", "vanished", "disappeared", "riddle", "case", "investigate"},
    "inspirational": {"dream", "believe", "courage", "purpose", "success", "achieve",
                      "never", "give", "journey", "growth", "strength", "faith", "hope",
                      "discipline", "goal", "goals", "rise", "potential", "mindset",
                      "grateful", "gratitude", "soul", "spirit", "truth", "karma"},
    "whimsical": {"fairy", "magic", "magical", "bunny", "rabbit", "elf", "princess",
                  "giggled", "tiny", "little", "candy", "rainbow", "puppy", "kitten",
                  "once", "upon", "wizard", "talking", "teddy", "unicorn", "toy"},
    "informative": {"data", "research", "study", "percent", "results", "system",
                    "process", "method", "chapter", "figure", "table", "analysis",
                    "according", "therefore", "however", "example", "define",
                    "important", "information", "step", "steps", "first", "second"},
}

GENRE_MOOD = {  # genre -> default mood
    "fiction": "calm", "children": "whimsical", "horror": "horror", "thriller": "suspense",
    "romance": "romantic", "fantasy": "epic", "mystery": "mystery", "drama": "sad",
    "self-help": "inspirational", "spiritual": "calm", "non-fiction": "informative",
    "comedy": "joyful",
}
MOOD_GENRE = {"whimsical": "children", "horror": "horror", "suspense": "thriller",
              "romantic": "romance", "epic": "fantasy", "mystery": "mystery",
              "sad": "drama", "inspirational": "self-help", "informative": "non-fiction",
              "joyful": "comedy", "calm": "fiction"}

_word = re.compile(r"[a-zA-Z']+")


def detect_language(text: str) -> str:
    sample = text[:4000]
    deva = len(re.findall(r"[ऀ-ॿ]", sample))
    letters = len(re.findall(r"\w", sample)) or 1
    return "hi" if deva / letters > 0.3 else "en"


def score_moods(text: str) -> Counter:
    words = [w.lower() for w in _word.findall(text)]
    c = Counter()
    for w in words:
        forms = {w, w.rstrip("s"), re.sub(r"(ed|d|ing|ly)$", "", w), re.sub(r"(ed|ing)$", "e", w)}
        for mood, lex in LEXICON.items():
            if forms & lex:
                c[mood] += 1
    # punctuation cues
    c["suspense"] += text.count("...") * 0.5 + text.count("—") * 0.2
    c["joyful"] += text.count("!") * 0.3
    if '"' in text or "“" in text:
        c["calm"] += 0.2  # mild bias to narrative tone when there's dialogue
    return c


def detect_genre(text: str) -> str:
    c = score_moods(text[:60000])
    if not c:
        return "fiction"
    mood = c.most_common(1)[0][0]
    return MOOD_GENRE.get(mood, "fiction")


def passage_mood(text: str, genre: str) -> str:
    """Mood for one passage, biased toward the genre's home mood so the voice
    doesn't flip on a single stray word."""
    c = score_moods(text)
    base = GENRE_MOOD.get(genre, "calm")
    c[base] += 0.75
    mood, top = c.most_common(1)[0]
    return mood if top >= 1.5 else base


def split_passages(text: str, max_chars: int = 1200, min_chars: int = 100) -> list[str]:
    """Split text into narration passages. Each paragraph is its own passage
    (so voice and music can follow the mood); tiny paragraphs such as dialogue
    lines are merged, and huge ones are cut at sentence boundaries."""
    text = text.replace("\f", "\n\n")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    buf = ""
    for p in paras:
        pieces = [p]
        if len(p) > max_chars:
            pieces, cur = [], ""
            for s in re.split(r"(?<=[.!?।])\s+", p):
                if len(cur) + len(s) > max_chars and cur:
                    pieces.append(cur.strip())
                    cur = ""
                cur += s + " "
            if cur.strip():
                pieces.append(cur.strip())
        for piece in pieces:
            buf = f"{buf}\n\n{piece}" if buf else piece
            if len(buf) >= min_chars:
                out.append(buf)
                buf = ""
    if buf:
        if out and len(out[-1]) + len(buf) <= max_chars:
            out[-1] += "\n\n" + buf
        else:
            out.append(buf)
    return out


def _claude_label(passages: list[str]) -> tuple[str, list[str]] | None:
    if not ANTHROPIC_API_KEY or len(passages) > 400:
        return None
    numbered = "\n".join(f"[{i}] {p[:500]}" for i, p in enumerate(passages))
    prompt = (
        "Classify this text for audiobook narration. Return ONLY JSON: "
        '{"genre": one of ' + json.dumps(list(GENRE_MOOD)) +
        ', "moods": [one mood per passage, in order, from ' + json.dumps(MOODS) + "]}\n\n" + numbered)
    try:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
            "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
            "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        raw = r.json()["content"][0]["text"]
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        moods = [m if m in MOODS else "calm" for m in data.get("moods", [])]
        if len(moods) != len(passages):
            return None
        genre = data.get("genre") if data.get("genre") in GENRE_MOOD else "fiction"
        return genre, moods
    except Exception:
        return None


def analyse(text: str, genre: str | None = None, mood: str | None = None) -> dict:
    """Return {'language', 'genre', 'passages': [{'text','mood'}], 'engine'}."""
    passages = split_passages(text)
    lang = detect_language(text)
    engine = "lexicon"
    moods = None
    if not mood:
        labelled = _claude_label(passages)
        if labelled:
            g, moods = labelled
            genre = genre or g
            engine = "claude"
    genre = genre or detect_genre(text)
    if mood:
        moods = [mood] * len(passages)
    elif moods is None:
        moods = [passage_mood(p, genre) for p in passages]
        moods = _smooth(moods)
    return {"language": lang, "genre": genre, "engine": engine,
            "passages": [{"text": p, "mood": m} for p, m in zip(passages, moods)]}


def _smooth(moods: list[str]) -> list[str]:
    """Remove single-passage blips (A B A -> A A A) for a steadier listen."""
    m = moods[:]
    for i in range(1, len(m) - 1):
        if m[i - 1] == m[i + 1] != m[i]:
            m[i] = m[i - 1]
    return m
