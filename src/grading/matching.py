from thefuzz import fuzz
import unicodedata
from collections import Counter, defaultdict
from typing import List, Optional


def _normalize(s: str) -> tuple[str, List[int]]:
    out, mapping = [], []
    for i, ch in enumerate(unicodedata.normalize("NFKC", s).lower()):
        if ch.isspace():
            if out and out[-1] == " ":
                continue
            ch = " "
        out.append(ch)
        mapping.append(i)
    while out and out[0] == " ":
        out.pop(0); mapping.pop(0)
    while out and out[-1] == " ":
        out.pop();  mapping.pop()
    return "".join(out), mapping

def _ngrams(s: str, n: int = 3) -> List[str]:
    return [s[i:i+n] for i in range(len(s) - n + 1)]

# ───────────── main search ───────────────
def fuzzy_substring_pos(
    text: str,
    pattern: str,
    *,
    min_score: int = 60,          # 0‒100
    ngram_size: int = 3,
    max_offset: int = None,          # ± inserted/deleted chars allowed
    scorer = fuzz.ratio           # swap e.g. fuzz.token_sort_ratio
) -> Optional[int]:               # return start index or None
    """Return the *best* match's start index in the original text."""
    if max_offset is None:
        max_offset = len(pattern) // 3
    if not pattern:
        return None

    text_norm,  t_map = _normalize(text)
    pat_norm,   _     = _normalize(pattern)
    N, M = len(text_norm), len(pat_norm)
    if M == 0 or M - max_offset > N:
        return None

    # 1) n-gram inverted index on the text
    index: dict[str, List[int]] = defaultdict(list)
    if N >= ngram_size:
        for i in range(N - ngram_size + 1):
            index[text_norm[i:i+ngram_size]].append(i)

    # 2) vote for candidate *start* positions
    pat_ngrams = _ngrams(pat_norm, ngram_size)
    votes = Counter()
    for pat_offset, gram in enumerate(pat_ngrams):
        for pos_in_text in index.get(gram, ()):
            start_guess = pos_in_text - pat_offset
            if 0 <= start_guess < N:
                votes[start_guess] += 1

    if not votes:
        return None

    min_votes = max(len(pat_ngrams) - max_offset * ngram_size, 0)
    candidates = [p for p, c in votes.items() if c >= min_votes]
    if not candidates:                       # relax if threshold too strict
        candidates = [p for p, _ in votes.most_common(10)]

    # 3) evaluate *all* candidate windows, keep the best score
    best_score = -1
    best_start = None
    best_length = None
    lengths = range(max(M - max_offset, 1), M + max_offset + 1, 3)

    for start in candidates:
        for L in lengths:
            if start + L > N:
                continue
            window = text_norm[start:start + L]
            score = scorer(pat_norm, window)
            if score > best_score:
                best_score, best_start = score, start
                best_length = L
            # perfect score 100 → can’t improve further
            if best_score == 100:
                break
        if best_score == 100:
            break

    if best_score >= min_score:
        # return (t_map[best_start], best_score)  # ← uncomment to also get score
        return t_map[best_start], t_map[best_start + best_length - 1]
    return None