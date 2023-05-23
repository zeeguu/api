import numpy as np
import heapq
from .spacy_wrapper import SpacyWrapper
from .automatic_gec_tagging import DICTIONARY_UD_MAP

NOISE_PROBABILITIES_DEFAULT = {
    "PREP": 0.1,
    "VERB": 0.2,
    "NOUN": 0.15,
    "CONJ": 0.025,
    "PART": 0.025,
    "DET" : 0.15,
    "ADV" : 0.1,
    "PRON": 0.15,
    "ADJ" : 0.1,
}

MAP_NOISE_PROB = {k:i for i, k in enumerate(NOISE_PROBABILITIES_DEFAULT.keys())}
POS_ARRAY = np.array(list(NOISE_PROBABILITIES_DEFAULT.keys()))

class NoiseGenerator():
    def __init__(self, spacy_wrapper:SpacyWrapper, language:str, lemma_set:set, 
                 pos_confusion_set=None, word_confusion_set=None,
                 noise_probabilities=NOISE_PROBABILITIES_DEFAULT):
        """
            pos_confusion_set = Dictionary generated from confusion_set.pos_dictionary
            word_confusion_set = Could be a list of words or I would recommend the words the student as seen.
            noise_probabilities = Uses the default defined, but it could be tuned to students based on the feedback.
        """
        self.language = language
        self.lemma_set = lemma_set
        self.spacy_pipe = spacy_wrapper.spacy_pipe
        self.pos_confusion_set = pos_confusion_set
        self.word_confusion_set = word_confusion_set
        self.noise_probabilities = noise_probabilities

    def _select_words_based_on_sim(self, word_to_confuse, pos_pick, is_lemma=False, top_n=20):
        # Sample the Word List
        if is_lemma:
            candidate_words = list(self.pos_confusion_set.get(pos_pick).keys())
        else:
            candidate_words = list(self.pos_confusion_set.get(pos_pick)) 
        subset = np.random.choice(candidate_words, min(len(candidate_words), top_n), replace=False)
        heap = []
        for word in subset:
            if word == word_to_confuse.lemma_: continue
            # Heap is a Min implementation, 1.0 should be the first returned. 
            heapq.heappush(heap, (-self.spacy_pipe(str(word)).similarity(word_to_confuse), word))
        return heap
    
    def _compare_string(self, s1, s2):
        # Use lower to avoid casing comparisons
        return s1.lower() == s2.lower()
    
    def _get_random_word(self, student_words, number_of_words):
        """
            Returns confusion words, however, it prioritizes taking words
            from the student word list before random words from corpora.
        """
        random_confusion_words = []
        if len(student_words) > number_of_words:
            random_confusion_words = list(np.random.choice(number_of_words, 2, replace=False))
        else:
            random_confusion_words = student_words
        if len(random_confusion_words) < number_of_words:
            random_confusion_words += list(np.random.choice(self.word_confusion_set, number_of_words-len(random_confusion_words), replace=False))

        return random_confusion_words 
    
    def _conf_generate_confusion_words(self, sentence, number_of_words, student_words, verbose):
        og_split_sentence = self.spacy_pipe(sentence)
        # Get the probabilities 
        d_pos_map = dict()
        pos_prob_mask = np.zeros(len(MAP_NOISE_PROB), dtype=bool)
        # 
        for i, token in enumerate(og_split_sentence):
            if token.pos_ == "PROPN": continue # Do not consider PNOUNs
            pos_token = DICTIONARY_UD_MAP.get(token.pos_,token.pos_)
            if pos_token not in self.noise_probabilities: continue # Do not consider PUNCT for example.
            d_pos_map[pos_token] = d_pos_map.get(pos_token, []) + [i]
            pos_prob_mask[MAP_NOISE_PROB[pos_token]] = True
    
        # Available POS to pick
        pos_avl = POS_ARRAY[pos_prob_mask]
        # Adjusted probability based on the POS that are not present.
        list_noise_p_vals = np.array(list(self.noise_probabilities.values()))
        pos_probs = list_noise_p_vals[pos_prob_mask] + (list_noise_p_vals[~pos_prob_mask].sum()/pos_prob_mask.sum())
        if verbose: print(f"POS Probabilities: ", pos_probs)
        if len(pos_avl) == 0:
            if verbose: print(f"No POS were available, random word.")
            random_word = np.random.choice(len(og_split_sentence))
            random_word_pos = og_split_sentence[random_word].pos_
            pos_pick = DICTIONARY_UD_MAP.get(random_word_pos,random_word_pos)
            confusion_set = self._get_random_word(student_words, number_of_words)
            return list(confusion_set), pos_pick, random_word
        else: 
            pos_pick = np.random.choice(pos_avl, p=pos_probs)
            id_to_add = np.random.choice(d_pos_map[pos_pick])
        
        if verbose: print(f"POS picked: '{pos_pick}'")
            
        confusion_set = []
        # Updated it to the un-mapped POS
        t_confusion = og_split_sentence[id_to_add]
        if verbose: print(f"WORD picked: '{t_confusion}'")
        pos_pick = t_confusion.pos_
        if pos_pick in self.lemma_set:
            confusion_set = self.pos_confusion_set.get(pos_pick).get(t_confusion.lemma_, [])
            confusion_set = [conf_word for conf_word in confusion_set if not self._compare_string(conf_word, str(t_confusion))]
            if verbose: print(f"Confusion set: '{confusion_set}', in while.")
            if len(confusion_set) >= number_of_words:
                confusion_set = np.random.choice(confusion_set, number_of_words, replace=False)
            if confusion_set is None or len(confusion_set) < number_of_words:
                heap = self._select_words_based_on_sim(t_confusion, pos_pick, is_lemma=True)
                if verbose: print(heap)
                while len(confusion_set) < number_of_words:
                    word_to_add = heapq.heappop(heap)[-1]
                    if self._compare_string(word_to_add, str(t_confusion)): continue
                    if verbose: print(f"Word to add: '{word_to_add}', in while.")
                    confusion_extra_words = list(self.pos_confusion_set.get(pos_pick).get(word_to_add, []))
                    if word_to_add not in confusion_extra_words: confusion_extra_words += [word_to_add]
                    if verbose: print(f"Candidate Set: '{confusion_extra_words}', in while.")
                    confusion_extra_words = np.random.choice(confusion_extra_words, min(number_of_words-len(confusion_set), len(confusion_extra_words)), replace=False)
                    if verbose: print(f"words to add from: {confusion_extra_words}")
                    for c_word in confusion_extra_words:
                        if c_word not in confusion_set:
                            if verbose: print(f"Word added: {c_word}")
                            confusion_set.append(c_word)
        else:
            heap = self._select_words_based_on_sim(t_confusion, pos_pick, is_lemma=False)
            if verbose: print(f"Heap found for 't_confusion' : {heap}")
            while len(confusion_set) < number_of_words and len(heap) > 0:
                word_to_add = heapq.heappop(heap)[1]
                if word_to_add.lower() not in confusion_set:
                    confusion_set.append(word_to_add)
        
        result = {
            "confusion_words": list(confusion_set),
            "pos_picked" : pos_pick,
            "word_used" : str(t_confusion)
        }
        return result
    
    def generate_confusion_words(self, sentence, number_of_words=2, student_words=[], verbose=False):
        return self._conf_generate_confusion_words(sentence, number_of_words, student_words, verbose)
  
    def replace_sent_with_noise(self, sentence, number_of_mistakes=1, number_of_words=2, verbose=False):
        id_used = dict()
        # Try 5 times:
        sentence_doc = self.spacy_pipe(sentence)
        confusion_op = []
        for _ in range(5):
            if len(id_used) >= number_of_mistakes: break
            confusion_set, pos, id = self.generate_confusion_words(sentence, number_of_words, verbose=verbose)
            if id in id_used: continue
            if len(confusion_set) == 0: continue
            word_picked = np.random.choice(confusion_set)
            id_used[id] = word_picked
            # print(f"Confusion set: {confusion_set}, POS: {pos}, Word used: {word_picked}, Word Replaced: {sentence_doc[id]}")
            confusion_op.append((confusion_set, pos, word_picked, sentence_doc[id]))
        complete_sentence = [t.text + t.whitespace_ if i not in id_used else id_used[i] + t.whitespace_ for i, t in enumerate(sentence_doc)]

        wo_swap_p = np.random.random()
        if wo_swap_p < 0.05:
            w_i = np.random.choice(np.arange(1,len(complete_sentence)-2))
            if w_i+1 == len(complete_sentence):
                temp = complete_sentence[w_i]
                complete_sentence[w_i] = complete_sentence[w_i-1]
                complete_sentence[w_i-1] = temp
            else:
                temp = complete_sentence[w_i]
                complete_sentence[w_i] = complete_sentence[w_i+1]
                complete_sentence[w_i+1] = temp
            confusion_op.append(("WO", w_i))
        return "".join(complete_sentence), confusion_op

