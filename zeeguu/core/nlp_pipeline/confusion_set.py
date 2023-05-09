import regex as re
import numpy as np
import copy
import os
import json
import pickle
from .spacy_wrapper import SpacyWrapper
from scipy.special import softmax
import string


"""
    Class to generate the confusion words for ZeeGuu
"""
LEMMA_CONFUSION_SET = set(["VERB","AUX", "NOUN", "ADJ", "DET"])
SUPPORTED_SAVE_OBJ = set(["json","pkl"])

POS_PROBS = {
    "danish": "morphologizer",
    "english": "tagger",
    "german": "tagger"
}

class ConfusionSet():
    """
        Class to create the confusion set for the ZeeGuu OrderWords exercise.

        Stores the number of counts for different words according to their POS and Lemmas, given the classes
        defined in LEMMA_CONFUSION_SET and POS_CONFUSION_SET.

        The Softmax probabilities can be used to filter out cases where model has low probability assigned (0-1).
            Suggestion: 0.8 - 0.9
        
        The minimum/maximum sentence size can be defined.
            Suggestion: [4, 20], however, since the Application already has a restraint on context size, the max can
            be set to np.inf to ignore this limit.
        
        The minimum number of a word ocurring within the dictionary as a certain POS can be used to filter the dictionary.
            Suggestion: 2, meaning that the word appears at least twice. For larger datasets, this value can be higher.

    """
    def __init__(self, spacy_wrapper:SpacyWrapper, language:str, filter_sentence_size=True, min_sent_size=4, max_sent_size=20, 
                            prob_filter=0.8, pos_min_count = 2, unnecessary_POS=set(["PROPN", "X", "INTJ", "SPACE", "PUNCT", "SYM", "NUM"]), 
                            verbose=False) -> None:
        
        assert language in POS_PROBS, f"Language '{language}' is not supported, please use one of the following:{list(POS_PROBS.keys())}"
        self.language = language
        self.unnecessary_POS = unnecessary_POS
        self.spacy_wrapper = spacy_wrapper
        self.nlp = self.spacy_wrapper.spacy_pipe
        self.filter_sentence_size = filter_sentence_size
        self.min_sent_size = min_sent_size
        self.max_sent_size = max_sent_size
        self.prob_filter = prob_filter
        self.pos_min_count = pos_min_count
        self.verbose = verbose
        self.count_dictionary = dict()
        self.pos_dictionary = dict()
        self.word_list = set()
        self.char_list = set()
    
    def string_to_sents(self, article_string):
        """
            Takes in a string and uses spaCy to return a list of sentences.
        """
        tokenized_sents = self.nlp(article_string)
        sentences_in_line = [str(sent).strip() for sent in tokenized_sents.sents]
        return sentences_in_line

    def remove_punctuation(s):
        # https://stackoverflow.com/questions/265960/best-way-to-strip-punctuation-from-a-string
        return s.translate(None, string.punctuation)
    
    def update_confusion_sets(self, line_list, reset_counts=False):
        """
            Updates the current pos_dictionary based on the line_list.

            If reset_counts is set to True, then the count dictionary will be reset.
            This means that all words that do not fit the criteria of min_counts will be removed.

            line_list:list, a list of sentences. Can be obtained with the method string_sents.
        """
        if reset_counts: self.count_dictionary = dict()
        self.create_confusion_sets(line_list, self.pos_dictionary, self.word_list, self.char_list)
        return self.pos_dictionary
 
    def create_confusion_sets(self, line_list, 
                                pos_confusion_set = {},
                                word_confusion_set = set(),
                                char_confusion_set = set()):
        """
            This option overwrites the current status saved on the class.

            Use this with the first time use or to re-build the dictionaries. 
        """
        sentence_list = []
        pos_confusion_set = {}
        word_confusion_set = set()
        char_confusion_set = set()
        # I decide to only keep the lowercase tokens for the confusion set.
        chars_accepted = re.compile(r'[a-ø]')
        # Filter Words with more than 2 instances of number/punctuation
        string_punct = string.punctuation
        string_numbers =  string.digits

        for line in line_list:
            tokenized_sents = self.nlp(line)
            sentences_in_line = [str(sent).strip() for sent in tokenized_sents.sents]
            for sent in sentences_in_line:
                tokenized_sent = self.nlp(sent)
                # Do not consider small or very long sentences
                # Still collect the words seen for a more complete confusion set. [4, 20]
                if self.filter_sentence_size:
                    if (len(tokenized_sent) >= self.min_sent_size 
                        and len(tokenized_sent) <= self.max_sent_size):
                        sentence_list.append(sent)
                else:
                    sentence_list.append(sent)
                
                # Get the Softmax Probabilities
                prob = np.max(softmax(self.nlp.get_pipe(POS_PROBS[self.language]).model.predict([tokenized_sent])[0], 1), 1)

                for t_i, token in enumerate(tokenized_sent):
                    # Remove if prediction for POS is low.
                    if prob[t_i] < self.prob_filter: continue

                    # Both lemmas and tokens are filtered from punctuation 
                    token_string = str(token).lower()
                    num_count = len([c for c in token_string if (c in string_numbers)])
                    symb_count = len([c for c in token_string if (c in string_punct)])
                    # Ignore if there is numbers
                    if num_count > 0: continue
                    # Ignore if there is 2 punct and it's not a punct POS.
                    if token.pos_ != "PUNCT" and symb_count > 1 or symb_count == len(token_string): continue
                    # Due to possible parsing errors, check if last or start token is punct
                    if token_string[0] in string_punct: token_string = token_string[1:]
                    if token_string[-1] in string_punct: token_string = token_string[:-1]
                    
                    word_confusion_set.add(token_string)
                    if token.pos_ in LEMMA_CONFUSION_SET:
                        # Handle case where there is no dictionary yet
                        if token.pos_ not in pos_confusion_set:
                            pos_confusion_set[token.pos_] = dict()
                        lemma_str = token.lemma_.lower()
                        self.count_dictionary[token.pos_] = self.count_dictionary.get(token.pos_, dict())
                        self.count_dictionary[token.pos_][lemma_str] = self.count_dictionary[token.pos_].get(lemma_str, 0) + 1
                        if lemma_str in pos_confusion_set[token.pos_]:
                            pos_confusion_set[token.pos_][lemma_str].add(token_string)
                        else:
                            pos_confusion_set[token.pos_][lemma_str] = set([token_string])
                    else:
                        # Count Dictionary 
                        self.count_dictionary[token.pos_] = self.count_dictionary.get(token.pos_, dict())
                        self.count_dictionary[token.pos_][token_string] = self.count_dictionary[token.pos_].get(token_string, 0) + 1
                        # Keep counts of the number of times the word shows up
                        if token.pos_ in pos_confusion_set:
                            pos_confusion_set[token.pos_].append(token_string)
                        else:
                            pos_confusion_set[token.pos_] = [token_string]

                    for c in str(token):
                        if chars_accepted.match(c):
                            char_confusion_set.add(c)
                

        # Transform the sets into lists so they can be sampled
        for pos, value_i in pos_confusion_set.items():
            if pos in LEMMA_CONFUSION_SET:
                for lemma, value_j in pos_confusion_set[pos].items():
                    pos_confusion_set[pos][lemma] = list(value_j)
            else:
                # Filter Any Items that is below the threshold count:
                filter_dict = copy.deepcopy(self.count_dictionary[pos])
                for t, count in self.count_dictionary[pos].items():
                    # Handle Case in Lemma Words
                    if count < self.pos_min_count:
                        filter_dict.pop(t)
                        if self.verbose: print(f"Deleted '{t}', as a POS {pos}")
                pos_confusion_set[pos] = list(filter_dict.keys())

        self.pos_dictionary = pos_confusion_set
        self.word_list = word_confusion_set
        self.char_list = char_confusion_set
        return sentence_list

    def filter_pos_dictionary(self, dictionary_to_filter, min_lemma_len=1, ignore_pos=set()):
        def dict_array_to_list(d, min_lemma_len=1):
            # Converts from np arrays to lists so they can be 
            # outputed as a json file.
            return {k:list(v) for k, v in d.items() if len(v) > min_lemma_len}
        

        if self.language == "english":
            # if Language is English determinants shouldn't be filtered.
            ignore_pos = set(["DET"])

        to_json_pos_confusion_set = dict()
        for k, v in dictionary_to_filter.items():
            if k in self.unnecessary_POS: continue
            if type(v) is dict:
                if k in ignore_pos:
                    to_json_pos_confusion_set[k] = dict_array_to_list(v, 0)
                else:
                    to_json_pos_confusion_set[k] = dict_array_to_list(v, min_lemma_len)
            else:
                to_json_pos_confusion_set[k] = list(v)
            if self.verbose: print(k, " ", len(to_json_pos_confusion_set[k]))

        return to_json_pos_confusion_set
    
    def get_filter_dictionary(self, min_lemma_len=1, ignore_pos=set()):
        """
            Returns a filtered POS dictionary
        """
        new_pos_dictionary = dict()
        for pos, value_i in self.pos_dictionary.items():
            if pos in LEMMA_CONFUSION_SET:
                new_pos_dictionary[pos] = value_i
            else:
                filter_dict = copy.deepcopy(self.count_dictionary[pos])
                for t, count in self.count_dictionary[pos].items():
                    # Handle Case in Lemma Words
                    if count < self.pos_min_count:
                        filter_dict.pop(t)
                        if self.verbose: print(f"Deleted '{t}', as a POS {pos}")
                new_pos_dictionary[pos] = list(filter_dict.keys())

        new_pos_dictionary = self.filter_pos_dictionary(new_pos_dictionary, min_lemma_len, ignore_pos=ignore_pos)
        return new_pos_dictionary

    def save_json_confusion_dictionary(self, filename, dictionary):
        """
            Saves the dictionary with the specific name as a json file.
        """
        with open(f"{filename}.json", "w", encoding="utf-8") as f:
            json.dump(dictionary, f)

    def save_confusionset_state(self, filepath, filetype="json", save_filtered_pos=False):
        assert filetype in SUPPORTED_SAVE_OBJ, f"Filetype needs to be in {SUPPORTED_SAVE_OBJ} got: 'filetype'"
        if filetype == "json":
            json_object = {
                    "language" : self.language ,
                    "unnecessary_POS" : list(self.unnecessary_POS),
                    "filter_sentence_size" : self.filter_sentence_size,
                    "min_sent_size"  : self.min_sent_size,
                    "max_sent_size" : self.max_sent_size,
                    "prob_filter" : self.prob_filter,
                    "pos_min_count" : self.pos_min_count,
                    "verbose" : self.verbose,
                    "count_dictionary"  : f"{filepath}_count", 
                    "pos_dictionary" : f"{filepath}_pos" ,
                    "word_list" : list(self.word_list),
                    "char_list" : list(self.char_list) ,
            }
            self.save_json_confusion_dictionary(json_object["count_dictionary"], self.count_dictionary)
            self.save_json_confusion_dictionary(json_object["pos_dictionary"], self.pos_dictionary)
            self.save_json_confusion_dictionary(f"{filepath}", json_object)

        elif filetype == "pkl":
            with open(f"{filepath}.pkl", "wb") as f:
                pickle.dump(self, f)
    
    def load_confusionset_state(self, filepath):
        assert ".json" in filepath or ".pkl" in filepath, f"Unsupported file extension. Found: '{filepath}'"
        if ".json" in filepath:
            json_state = dict()
            json_count = dict()
            json_pos = dict()
            with open(f"{filepath}", "r", encoding="utf-8") as f:
                json_state = json.load(f)
            # Remove the final extension
            path_to_file = os.sep.join(filepath.split(os.sep)[:-1])
            count_path = os.path.join(path_to_file, json_state["count_dictionary"] + ".json")
            pos_path = os.path.join(path_to_file, json_state["pos_dictionary"] + ".json")
            with open(count_path, "r", encoding="utf-8") as f:
                json_count = json.load(f)
            with open(pos_path, "r", encoding="utf-8") as f:
                json_pos = json.load(f)

            self.language = json_state["language"]
            self.unnecessary_POS = set(json_state["unnecessary_POS"])
            self.filter_sentence_size = json_state["filter_sentence_size"]
            self.min_sent_size = json_state["min_sent_size"]
            self.max_sent_size = json_state["max_sent_size"]
            self.prob_filter = json_state["prob_filter"]
            self.pos_min_count = json_state["pos_min_count"]
            self.verbose = json_state["verbose"]
            self.count_dictionary = json_count
            self.pos_dictionary = json_pos
            self.word_list = set(json_state["word_list"])
            self.char_list = set(json_state["char_list"])

        elif ".pkl" in filepath:
            with open(f"{filepath}", "rb") as f:
                self = pickle.load(f)
