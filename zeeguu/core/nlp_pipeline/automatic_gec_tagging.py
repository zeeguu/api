from .alignment_errant import ERRANT_Alignment
import regex as re
import numpy as np
import json
from rapidfuzz.fuzz import ratio
from .spacy_wrapper import SpacyWrapper

"""

Automatic GEC (Grammatical Error Correction) Tagging

Based on the ERRANT methodology, and using the alignment that ERRANT uses.

The labels are inspired by those used in ERRANT as well:
- M: Missing
- U: Unnecessary
- R: Replacement

However, the categories are based on the POS attached to either M or R:
 'PREP'
 'NOUN'
 'SPELL/MORPH': In case there is a similarity between lema and token >= 0.6 and len(token) > 2
 'VERB'
 'PUNCT'
 'DET'
 'WO' : If aligment returned word order.
 'ADV'
 'PRON'
 'FORM/MORPH' : In case the two tokens have the same POS or sim > 0.85, but do not have any unmatched modifier.
 'CONJ'
 'ADJ'
 OTHER': If POS is INTJ, NUM, X, SPACE, SYM

The labels are attributed in the following way:
1. If the tokens match, then C is used (correct)
2. If the ERRANT_Alignment returns a word swap operation, all words are tagged with WO
3. If insert, then an M: followed by the POS identified by spaCy
4. If delete, then U is used, no POS is used here to reduce the label space
5. If substitute, then:
 5.1. if the tokens are the same in lowercase, then return a SPELL/MORPH
 5.2. if tokens share the same DICTIONARY_UD_MAP and similarity above 0.85,
 then morphology dictionary is checked to identify where they are different.
 5.2.1. if they have the same lemma, but no Modifiers was found, mark as 'FORM/MORPH'
 5.2.2. If none of the above, but similarity above 0.6 and len of token > 2, then mark as
 'SPELL/MORPH'.
 5.2.3. If none of the above, then M:[POS_REF] is used.

Similarity:
- To avoid the use of language specific dictionaries, I implement a similarity metric based on
the token and lemma's retrieved from spaCy. The similarity is then calculated as follows:
 lemma_sim * (LEMMA_SIM_WEIGHT) + token_sim * (1-LEMMA_SIM_WEIGHT), where sim is given by
the normalized ratio of the Levenshtein distance.
If one of the lemmas > 5 it's a long word, and to avoid misclassifying long words, I reduce similarity
by the ratio of the minimum token length devided by the maximum token being compared.

Example 1 (plane vs airplane):
Lemma: plane vs airplane, Lev sim: 0.77
Token: plane vs airplane, Lev sim: 0.77
Ratio: 5/8 = 0.625
Final Sim: 0.48

Example 2 (where vs everywhere):
Token ERR: where | Token COR: everywhere, Token Sim: 0.67
Lemma ERR: where | Lemma COR: everywhere, Lemma Sim: 0.67 
Ratio: 5/10 = 0.5
Sim weighted: 0.33

This similarity is used in 2 ways:
 1. Determine if the word is a form of a verb or a noun, which should be modified in some way.
 This is done if the two words have a similarity above .7 and share the same POS. Resulting in 
 a modifier described below.
 2. If above 0.6, then the word is marked as either a 'SPELL/MORPH' as this indicates that the words
 were quite similar and it is likely to only necessitate small changes.

Modifiers (Properties checked in the morphology dictionary):
- Checked in the following order and if unmatched, then the modifier is added 
to the matched POS. Only the Reference/Correction labels are checked, if the 
error is missing, that is still marked.

 1. 'T': Tense
 2. 'G': Gender 
 3. 'P': Person
 4. 'N': Number
 5. 'C': Case

Finally, as this method is to be used for label prediction, there is the requirement
that the final list needs to have the same size as the word tokens in SENT_ERR.

To do this, the following merge operations are used:
 if M, then start Merge:
    if M:POS_1 == M:POS_2, then M:POS_1
    else M:OTHER
 these are then mapped to the previous token, or the starting one (if missing at start).
The intuition here, is since the learner will add a word, then a new alignment can be made, and then 
the other errors can be highlighted. 

"""
LEMMA_SIM_WEIGHT = 0.55
SWAP_WORDS = re.compile(r'T([0-9])')
PROPERTIES_TO_CHECK = ["Tense", "Gender", "Person", "Number", "Case"]
DICTIONARY_UD_MAP = {
    "ADP":"PREP",
    "CCONJ":"CONJ",
    "SCONJ":"CONJ",
    "PROPN":"NOUN",
    "AUX":"VERB",
    "INTJ":"OTHER",
    "X":"OTHER",
    "NUM":"OTHER",
    "SYM":"OTHER",
    "SPACE":"OTHER",
}

UD_TO_WORD_CLASS = {
    "PREP":"preposition",
    "CONJ":"conjunction",
    "NOUN":"noun",
    "VERB":"verb",
    "PART":"particle",
    "ADV":"adverb",
    "SPELL/MORPH": "spelling or morphology.",
    "FORM/MORPH": "form or morphology.",
    "ADJ":"adjective",
    "DET":"determinant",
    "PUNCT":"punctuation",
    "PRON":"pronoun",
    'T': "tense",
    'G': "gender",
    'P': "person",
    'N': "number",
    'C': "case",
}

class AutoGECTagging():
    def __init__(self, spacy_pipe:SpacyWrapper, language:str) -> None:
        
        self.language_pipe = language
        self.spacy_pipeline = spacy_pipe.spacy_pipe

    def word_lemma_token_sim(self, token_err, token_ref, verbose=False):
        lemma_ref_str = str(token_ref.lemma_).lower()
        lemma_err_str = str(token_err.lemma_).lower()
        token_ref_str = str(token_ref)
        token_err_str = str(token_err)
        lemma_sim = ratio(lemma_err_str, lemma_ref_str)/100 # (min(len(lemma_err_str), len(lemma_ref_str)) - distance(lemma_ref_str, lemma_err_str))/max(len(lemma_err_str), len(lemma_ref_str))
        token_sim = ratio(token_err_str, token_ref_str)/100 # (min(len(token_err_str), len(token_ref_str)) - distance(token_ref_str, token_err_str))/max(len(token_err_str), len(token_ref_str))
        sim_weighted = (LEMMA_SIM_WEIGHT * lemma_sim) + ((1-LEMMA_SIM_WEIGHT) * token_sim)
        if  max(len(lemma_err_str), len(lemma_ref_str)) > 5:
            if verbose: print("Using Penalizing")
            sim_weighted *= (min(len(token_ref_str), len(token_err_str))/max(len(token_ref_str), len(token_err_str))) # Penalizes Long Words
        if verbose:
            print(f"Token ERR: {token_err_str} | Token COR: {token_ref_str}")
            print(f"Lemma ERR: {lemma_err_str} | Lemma COR: {lemma_ref_str}")
            print(f"Lemma Sim: {lemma_sim:.2f} | Token Sim: {token_sim:.2f}")
            print(f"Sim weighted: {sim_weighted:.2f}")
        return sim_weighted
    
    def _merge_missing(self, og_labels, include_o_start_end, corrections_array=None):
        merge_labels = []
        corrections_merged = []
        label_i = 0
        label_j = label_i
        skip_next = False
        while(label_i < len(og_labels)):
            if include_o_start_end:
                label_i_cat, (i_s_err,i_e_err) = og_labels[label_i]
            else:
                label_i_cat = og_labels[label_i]

            if label_i_cat[0] == "M":
                modify_i_split = label_i_cat.split(":")[1]
                all_labels_same = True
                if include_o_start_end:
                    label_j_cat, (_,_) = og_labels[label_j]
                else:
                    label_j_cat = og_labels[label_j]
                while (label_j < len(og_labels) and label_j_cat[0] == "M"):
                    modify_j_split = label_j_cat.split(":")[1]
                    if modify_i_split != modify_j_split:
                        all_labels_same = False
                    label_j += 1
                    # Handle cases where there is the span targets.
                    if label_j >= len(og_labels): break # We have reached the end.
                    if include_o_start_end:
                        label_j_cat, (_,_) = og_labels[label_j]
                    else:
                        label_j_cat = og_labels[label_j]
                if len(merge_labels) == 0:
                    skip_next = True
                    if corrections_array is not None: corrections_merged.append(corrections_array[label_i]) 
                    if all_labels_same:
                        if not include_o_start_end: merge_labels.append(label_i_cat) 
                        else: merge_labels.append((label_i_cat, (i_s_err, i_e_err)))
                    else:
                        if not include_o_start_end: merge_labels.append("M:OTHER") 
                        else: merge_labels.append(("M:OTHER", (i_s_err, i_e_err))) 
                else:
                    if corrections_array is not None: corrections_merged[-1] += f" {corrections_array[label_i]}"
                    if all_labels_same:
                        if not include_o_start_end: merge_labels[-1] = (label_i_cat) 
                        else: merge_labels[-1] = ((label_i_cat, (i_s_err, i_e_err))) 
                    else:
                        if not include_o_start_end: merge_labels[-1] = ("M:OTHER") 
                        else: merge_labels[-1] = (("M:OTHER", (i_s_err, i_e_err))) 
                label_i = label_j
            else:
                # When we were missing something in the beggining, do not add label.
                if not skip_next:
                    merge_labels.append(og_labels[label_i])
                    if corrections_array is not None: corrections_merged.append(corrections_array[label_i]) 
                else:
                    skip_next = False  
                label_i += 1
                label_j = label_i
        # Set if the start_index is correct in last position
        if include_o_start_end and merge_labels[-1][0].split(":")[0] == "M":
            merge_labels[-1] = (merge_labels[-1][0], (len(merge_labels) - 1, len(merge_labels)))

        return merge_labels if corrections_array is None else (merge_labels, corrections_merged)

    def generate_labels(self, error_sentence, corr_sentence, merge_inserts=True, 
                        include_o_start_end=False, return_tokens=False,
                        return_err_pos=False, return_corr_pos=False,
                        return_alignment = False, 
                        return_corrections=False, verbose=False):
        
        def _include_start_end(operation, s_err, e_err, flag):
            return (operation, (s_err,e_err)) if flag else operation
        
        doc_err = self.spacy_pipeline(error_sentence)
        doc_corr = self.spacy_pipeline(corr_sentence)

        alignment = ERRANT_Alignment(doc_err, doc_corr)

        error = [token for token in doc_err]
        ref = [token for token in doc_corr]
        labels = []
        corrections = []
        alignment_map = {}
        for (case, start_err, end_err, start_ref, end_ref) in alignment.align_seq:
            alignment_map[(start_err, end_err)] = (start_ref, end_ref)
            match_swap = SWAP_WORDS.match(case)
            if case == 'M':
                labels.append(_include_start_end("C", start_err, end_err, include_o_start_end))
                corrections.append(str(ref[start_ref:end_ref][0]))
            elif match_swap:
                num_words = int(match_swap.group(1))
                for _ in range(num_words):
                    labels.append(_include_start_end("R:WO", start_err, end_err, include_o_start_end))
                corrections += [str(word) for word in ref[start_ref:end_ref]]
            elif case == "D":
                token_err = error[start_err:end_err][0]
                labels.append(_include_start_end("U", start_err, end_err, include_o_start_end))
                corrections.append("")
            elif case == "I":
                token_ref = ref[start_ref:end_ref][0]
                ref_pos_converted = DICTIONARY_UD_MAP.get(token_ref.pos_, token_ref.pos_)
                labels.append(_include_start_end(f"M:{ref_pos_converted}", start_err, end_err, include_o_start_end))
                corrections.append(str(token_ref))
            elif case == "S":
                token_ref = ref[start_ref:end_ref][0]
                token_err = error[start_err:end_err][0]
                corrections.append(str(token_ref))
                if str(token_ref).lower() == str(token_err).lower():
                    labels.append(_include_start_end(f"R:SPELL/MORPH", start_err, end_err, include_o_start_end))
                    continue
                ref_pos_converted = DICTIONARY_UD_MAP.get(token_ref.pos_, token_ref.pos_)
                sim_weighted = self.word_lemma_token_sim(token_err, token_ref, verbose)
                morph_ref = token_ref.morph.to_dict()
                morph_err = token_err.morph.to_dict()
                if verbose:
                    print("REF Morph dict: ", morph_ref)
                    print("ERR Morph dict: ", morph_err)
                if ((token_ref.pos_ == token_err.pos_ and sim_weighted > 0.85)
                    or token_err.lemma_ == token_ref.lemma_):
                    # Handle the different Cases:
                    # Check the Tense and Number
                    action_taken = False
                    for property in PROPERTIES_TO_CHECK:
                        # At first property stop
                        if property not in morph_ref:
                            continue
                        elif ((property in morph_ref and property in morph_err)
                            and morph_ref[property] != morph_err[property]):
                            labels.append(_include_start_end(f"R:{ref_pos_converted}:{property.upper()[:1]}", start_err, end_err, include_o_start_end))
                            action_taken = True
                            break
                    if action_taken:
                        continue
                    
                    if token_err.lemma_ == token_ref.lemma_:
                        labels.append(_include_start_end(f"R:FORM/MORPH", start_err, end_err, include_o_start_end))
                        continue

                if sim_weighted >= 0.6 and len(token_err) > 2:
                    labels.append(_include_start_end(f"R:SPELL/MORPH", start_err, end_err, include_o_start_end))
                else:
                    labels.append(_include_start_end(f"R:{ref_pos_converted}", start_err, end_err, include_o_start_end))
        assert len(labels) == len(corrections), f"{len(labels)} <> {len(corrections)}"
        results = {}
        if merge_inserts:
            if not return_corrections:
                merge_labels = self._merge_missing(labels, include_o_start_end)  
            else: 
                merge_labels, corrections = self._merge_missing(labels, include_o_start_end, corrections)
            assert len(error) == len(merge_labels), f"Length of ERR tokens vs merge labels does not match. {len(error)} vs {len(merge_labels)}"
            results["unmerged_labels"] = labels
            labels = merge_labels
        results["labels"] = labels
        if return_err_pos: results["err_s_tokens"] = error
        if return_corr_pos: results["corr_s_tokens"] = ref
        if return_alignment: results["alignment"] = alignment_map
        if return_tokens: results["return_tokens"] = ([t_e.text + t_e.whitespace_ for t_e in error], [t_c.text + t_c.whitespace_  for t_c in ref])
        if return_corrections: results["corrections"] = corrections
        return results
    
    def anottate_clues(self, word_dictionary_list, original_sentence):
        """
            Call from the ZeeGuu App to provide the feedback.
            It uses the generate_labels to annotate the errors, with merging and start positions.

            The start positions are then used to update the word properties list sent by the ZeeGuu app.
            The Feedback field is set based on the FEEDBACK_DICT defined in _write_feedback.
        """
        if type(word_dictionary_list) is str: word_dictionary_list = json.loads(word_dictionary_list)
        assert type(word_dictionary_list) is list, f"Input in the wrong format, it needs to be a list of JSON or a JSON string. Found: {type(word_dictionary_list)}"
        def _write_feedback(op, word, word_i, err_last_i, first_missing_before=None,
                            is_sent_shorter=False, err_pos=None, related_words=None):
            """

            """
            op_list = op.split(":")
            # Allow for feedback dict to be prepared.
            while len(op_list) < 3: op_list.append("")
            pos_feedback = UD_TO_WORD_CLASS.get(op_list[1],"")
            morph_feedback = UD_TO_WORD_CLASS.get(op_list[2],"")
            
            pos_is_correct = op_list[1] == err_pos
            related_words_feedback = "" if related_words is None else f" It might relate to '{','.join(related_words)}'."
            article = "a"
            if len(pos_feedback) > 0:
                article = "an" if pos_feedback[0] in "aeiou" else "a"

            FEEDBACK_DICT = {
                "U":[f"'{word}' is not in the right position.", 
                     f"'{word}' isn't correctly placed here."],
                "M":[f"There is something missing after '{word}'.",
                     f"Something is missing after '{word}'."],
                "M-F-Not-Complete":[f"You still need something after '{word}'."],
                "M-B":[f"There is something missing before '{word}'.",
                     f"Something is missing before '{word}'."],
                "R-WRONG":[f"You need to replace '{word}'.",
                           f"'{word}' needs to be replaced."],
                "R-WO":[f"'{word}' is not in the right order.",
                           f"'{word}' need to be re-ordered."],
                "POS":[f"It needs to be {article} {pos_feedback}.",
                       f"Use {article} {pos_feedback}."],
                "POS-CORRECT":[f"Use a different {pos_feedback}.",
                               f"Almost there, try a different {pos_feedback}."],
                "SPELL/MORPH":[f"Check the spelling or morphology for '{word}'.",
                               f"Either the spelling or morphology is not quite right for '{word}'."],
                "FORM/MORPH":[f"Check the form or morphology for '{word}'.",
                               f"Try a different form or morphology for '{word}'."],
                "R3":[f"'{word}' needs to change in {morph_feedback} to be correct.",
                      f"'{word}' doesn't have the correct {morph_feedback}.",]
            }

            if op_list[0] == "U":
                return np.random.choice(FEEDBACK_DICT["U"])
            elif op_list[0] == "M":
                if first_missing_before: feedback_message = np.random.choice(FEEDBACK_DICT["M-B"])
                elif word_i == err_last_i and is_sent_shorter: feedback_message = np.random.choice(FEEDBACK_DICT["M-F-Not-Complete"])
                else: feedback_message = np.random.choice(FEEDBACK_DICT["M"])
                if op_list[1] != "OTHER" and op_list[1] != "":
                    feedback_message += " " + np.random.choice(FEEDBACK_DICT["POS"])
                return feedback_message
            else:
                if op_list[2] != "": return np.random.choice(FEEDBACK_DICT["R3"]) + related_words_feedback
                if op_list[1] == "SPELL/MORPH": return np.random.choice(FEEDBACK_DICT["SPELL/MORPH"])
                if op_list[1] == "FORM/MORPH": return np.random.choice(FEEDBACK_DICT["FORM/MORPH"]) + related_words_feedback
                if op_list[1] == "OTHER": return np.random.choice(FEEDBACK_DICT["R-WRONG"]) + related_words_feedback
                if op_list[1] == "WO": return np.random.choice(FEEDBACK_DICT["R-WO"])
                if pos_is_correct: return np.random.choice(FEEDBACK_DICT["R-WRONG"]) + " " + np.random.choice(FEEDBACK_DICT["POS-CORRECT"]) + related_words_feedback
                return np.random.choice(FEEDBACK_DICT["R-WRONG"]) + " " + np.random.choice(FEEDBACK_DICT["POS"]) + related_words_feedback
        
        sentence_to_correct = " ".join([wProps["word"] for wProps in word_dictionary_list]) 
        annotated_errors = self.generate_labels(sentence_to_correct, original_sentence, include_o_start_end=True, return_tokens=True,
                                                return_err_pos=True, return_corr_pos=True, return_corrections=True, return_alignment=True)
        err = annotated_errors["return_tokens"][0]
        map_n_err_to_old_err = dict()
        # If the first is an error
        first_missing_before = False
        if ("M:" in annotated_errors["labels"][0][0] 
            and (0,0) in annotated_errors["alignment"]):
            first_missing_before = True

        if len(word_dictionary_list) != len(err):
            # Handle Cases where the tokenization wasn't the same.
            # The tokens in e_rr have a leading whitespace if they are tokenized
            # If we find cases where this isn't true, merge them.
            n_err = []
            n_corrections = []
            n_operations = []
            i_pos = 0
            prev_is_wo = False
            new_alignment = {}
            while i_pos < len(err):
                map_n_err_to_old_err[len(n_err)] = i_pos
                current_err = err[i_pos]
                operation, span = annotated_errors["labels"][i_pos]
                correction = annotated_errors["corrections"][i_pos]
                old_alignment = annotated_errors["alignment"][span]
                while (current_err.strip() != word_dictionary_list[len(n_err)]["word"]):
                    if i_pos != len(err)-1:
                        current_err += err[i_pos+1]
                        if operation == "C": operation = annotated_errors["labels"][i_pos+1][0]
                        correction += annotated_errors["corrections"][i_pos+1]
                        i_pos += 1
                n_err.append(current_err)
                if prev_is_wo and operation == "R:WO":
                    prev_op, (start, end) = n_operations[-1]
                    span = end - start
                    for i in range(1, min(len(n_err), span)+1):
                        n_operations[-i] = (prev_op, (start, len(n_err)))
                    new_alignment[(start, len(n_err))] = old_alignment
                    n_operations.append((operation, (start, len(n_err))))
                else:
                    n_operations.append((operation, (len(n_err)-1, len(n_err))))
                    new_alignment[(len(n_err)-1, len(n_err))] = old_alignment
                n_corrections.append(correction)
                if operation == "R:WO":
                    prev_is_wo = True
                else:
                    prev_is_wo = False
                i_pos += 1
            err = n_err
            annotated_errors["labels"] = n_operations
            annotated_errors["corrections"] = n_corrections
            annotated_errors["alignment"] = new_alignment
        
        # Check if the sentence is shorter (provide better feedback)
        is_sent_shorter = False
        if len(annotated_errors["corr_s_tokens"]) > len(annotated_errors["err_s_tokens"]): is_sent_shorter = True
        err_last_i = len(annotated_errors["err_s_tokens"]) - 1
        seen_wo_err = set()
        # Create a reverse map of the unmerged tokens
        # We keep the first Missing token as the feedback to give.
        unmerge_labels = {}
        for k, v in annotated_errors["unmerged_labels"]:
            if v not in unmerge_labels:
                unmerge_labels[v] = k 

        # Annotate the Feedback
        assert len(word_dictionary_list) == len(err), "Input words and corrected words do not match."
        for i, ((operation, (s_err,s_end))) in enumerate(annotated_errors["labels"]):
            token_err = annotated_errors["err_s_tokens"][map_n_err_to_old_err.get(s_err, s_err)]
            wProps = word_dictionary_list[i] 
            word_for_correction = wProps["word"]
            if operation == "C":
                wProps["isCorrect"] = True
                wProps["status"] = "correct"
                wProps["feedback"] = ""
                continue
            if (wProps["isInSentence"] and operation == "U"
                and wProps["word"] not in original_sentence
                and i+1 == len(annotated_errors["labels"])):
                # Attempt to fix case where words are marked as uncesseary because of
                # context cutoff.
                # In this situation, we don't know yet if it's correct.
                wProps["isCorrect"] = False
                wProps["status"] = ""
                wProps["feedback"] = ""
                continue
            if s_err in seen_wo_err: continue # Avoid Order errors. (Have the same start)
            if operation == "R:WO":
                seen_wo_err.add(s_err)
                word_for_correction = "".join(err[s_err:s_end]).strip()
                for j in range(s_err, s_end):
                    word_dictionary_list[j]["isCorrect"] = False
                    word_dictionary_list[j]["status"] = "incorrect"
                    word_dictionary_list[j]["error_type"] = "R:WO"
                    # This needs to be in otherwise if there was a previous feedback
                    # the word will be still put in the latest status.
                    word_dictionary_list[j]["feedback"] = ""

            # Handle the Dependency parser clues.
            related_words = None
            if "R:" in operation and operation != "R:WO":
                if token_err.text == token_err.head.text: related_words == [child for child in token_err.children]
                else: related_words = [token_err.head.text]
                # Avoid situations where the token is referring to itself.
                if related_words is not None:
                    related_words = [rel_token for rel_token in related_words if rel_token not in word_for_correction]
                    if len(related_words) == 0: related_words = None

            # Prepare the Properties in the Dictionary.
            wProps["pos"] = DICTIONARY_UD_MAP.get(token_err.pos_, token_err.pos_)
            if i == len(word_dictionary_list)-1 and (s_err,s_end) in unmerge_labels:
                # We check if the original operation was another error.
                if (unmerge_labels[(s_err,s_end)][:2] != "M:" 
                    and unmerge_labels[(s_err,s_end)][0] != "C"):
                    operation = unmerge_labels[(s_err,s_end)]
                    
            if (operation == "M:OTHER"):
                # Set the first label (from unmerged)
                operation = unmerge_labels.get((s_err,s_end), "M:OTHER")
                # Needs to check if there is 'C' means we have
                # a merge of 2 M, then we set to the first.
                if operation == "C":
                    if first_missing_before: operation = unmerge_labels.get((s_err,s_err), "M:OTHER")
                    else: operation = unmerge_labels.get((s_end, s_end), "M:OTHER")

            wProps["feedback"] = _write_feedback(operation, word_for_correction, word_i=i, err_last_i = err_last_i,
                                                 first_missing_before = first_missing_before,
                                                 is_sent_shorter=is_sent_shorter, err_pos=wProps["pos"], related_words=related_words)
            wProps["missBefore"] = True if first_missing_before else False
            wProps["error_type"] = operation
            if s_err != s_end and s_err != 0: wProps["correction"] = " ".join(annotated_errors["corrections"][s_err:s_end])
            else: wProps["correction"] = annotated_errors["corrections"][max(0, s_err-1)] # Avoid -1 (if s_err == 0)
            wProps["isCorrect"] = False
            # Only mark incorrect if not missing.
            # If it is missing, 
            if (operation[:2] == "M:"):
                # If the correction is in the correction, we know the token is correct
                # Otherwise we can't mark it incorrect.
                wProps["status"] = "correct" if wProps["word"] in wProps["correction"] else ""
            else:
                wProps["status"] = "incorrect"
        return word_dictionary_list
            