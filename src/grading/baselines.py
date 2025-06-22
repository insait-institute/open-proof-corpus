import re
import random
class VerifierBaseline():
    def __init__(self, strategy, **kwargs):
        self.strategy = strategy
        if strategy == 'naive':
            self.verifier = SimpleBaseline(**kwargs)
        else:
            raise NotImplementedError(f'Baseline with strategy {strategy} is not supported')
        
    def run_queries(self, queries):
        return [(i, self.verifier.verify(text['solution']), {"cost": 0, "input_tokens": 0, "output_tokens": 0}) for i, text in enumerate(queries)]

class SimpleBaseline():
    def __init__(self, length_threshold, keyword_list, discrete, **kwargs):
        self.length_threshold = length_threshold
        self.keyword_list = keyword_list
        self.discrete = discrete

    def verify(self, text):
        if len(text) < self.length_threshold:
            return 'Text is too short to be correct. \\boxed{incorrect}' if self.discrete else 'Text is too short to be correct. \\boxed{0}'
        normalized_text = re.sub(r"[^\w\s]", "", text).lower()
        text_words = set(normalized_text.split())
        normalized_words = [re.sub(r"[^\w\s]", "", w).lower() for w in self.keyword_list]
        for w in normalized_words:
            if w in text_words:
                return f'Text contains forbidden keyword {w}. \\boxed{{incorrect}}' if self.discrete else f'Text contains forbidden keyword {w}. \\boxed{{0}}'
        if random.randint(0, 1) == 0:
            return 'Randomly guessed \\boxed{correct}' if self.discrete else 'Randomly guessed \\boxed{100}'
        else:
            return 'Randomly guessed \\boxed{incorrect}' if self.discrete else 'Randomly guessed \\boxed{0}'
