from __future__ import annotations

import tiktoken


class TokenBudget:
    def __init__(self, name: str = "cl100k_base"):
        self.encoding = tiktoken.get_encoding(name)
        self.name = name

    def count(self, text: str) -> int:
        # Source may contain literal special-token strings; never treat them as
        # tokenizer control codes or instructions.
        return len(self.encoding.encode_ordinary(text))

    def fit_end(self, text: str, start: int, end: int, limit: int) -> int:
        low, high = start, min(end, start + max(1, limit) * 24)
        while low < high:
            middle = (low + high + 1) // 2
            if self.count(text[start:middle]) <= limit:
                low = middle
            else:
                high = middle - 1
        if low == start:
            raise ValueError("Token budget cannot fit one Unicode character")
        return low

    def bounded_context(self, text: str, limit: int) -> tuple[str, bool]:
        if self.count(text) <= limit:
            return text, False
        if limit == 0:
            return "", bool(text)
        end = self.fit_end(text, 0, len(text), limit)
        return text[:end], True

    def windows(self, text: str, start: int, end: int, limit: int, overlap: int):
        while start < end:
            stop = self.fit_end(text, start, end, limit)
            if stop < end:
                # Prefer a newline or whitespace near the end, retaining every
                # character. Fall back to a Unicode boundary for very long lines.
                lower = start + (stop - start) // 2
                newline = text.rfind("\n", lower, stop)
                space = text.rfind(" ", lower, stop)
                if newline >= lower:
                    candidate = newline + 1
                elif space >= lower:
                    candidate = space + 1
                else:
                    candidate = stop
                if self.count(text[start:candidate]) <= limit:
                    stop = candidate
            yield start, stop
            if stop == end:
                return
            if overlap == 0:
                start = stop
                continue
            low, high = start + 1, stop
            while low < high:
                middle = (low + high) // 2
                if self.count(text[middle:stop]) <= overlap:
                    high = middle
                else:
                    low = middle + 1
            # Align overlap to a line start if possible and always advance.
            newline = text.find("\n", low, stop)
            candidate = newline + 1 if newline >= 0 else low
            # A shorter BPE suffix can have more tokens at its new boundary.
            while candidate < stop and self.count(text[candidate:stop]) > overlap:
                candidate += 1
            start = candidate
