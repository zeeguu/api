import heapq
import numpy as np
from .spacy_wrapper import SpacyWrapper

class ContextReducer():
    @classmethod
    def get_similar_sentences(cls, nlp_pipe:SpacyWrapper, sentence:str, article:str, max_length:int = 15):
        sentences = nlp_pipe.get_sent_list(article)
        short_sentences_in_article = [sent for sent in sentences if len(nlp_pipe.tokenize_sentence(sent)) <= max_length]
        
        context_doc = nlp_pipe.get_doc(sentence)
        heap = []
        for f_sent in short_sentences_in_article:
            sent_doc = nlp_pipe.get_doc(f_sent)
            heapq.heappush(heap, (context_doc.similarity(sent_doc), f_sent))
        
        most_similar_sent = heapq.nlargest(1, heap)[0][1]
        top_10_results = heapq.nlargest(10, heap)

        result_json = {
            "top_1_sent": most_similar_sent,
            "top_10_sents_w_sim": top_10_results
        }

        return result_json
    
    @classmethod
    def reduce_context_for_bookmark(cls, nlp_pipe:SpacyWrapper, sentence:str, bookmark:str, max_length:int = 15):
        def filter_non_consecutive(l, bookmark_word_i):
            sub_continuous_list = []
            current_sub_list = [l[0]]
            for i in range(1, len(l)):
                # Assumes elements are sorted.
                if np.abs(current_sub_list[-1]-l[i]) == 1:
                    current_sub_list.append(l[i])
                else:
                    sub_continuous_list.append([]+current_sub_list)
                    current_sub_list = [l[i]]
            sub_continuous_list.append([]+current_sub_list)
            for sub_l in sub_continuous_list:
                if bookmark_word_i in sub_l:
                    return sub_l
            return "Error"
    
        def get_context_for_word_heap(doc, bookmark, max_context=max_length):
            token_to_i = {str(token): token.i for token in doc}
            start_i = token_to_i[bookmark.split()[-1]]
            heap = []
            counter = 0
            heapq.heappush(heap, (counter, start_i))
            new_sub_context = []
            context_no_punct = 0
            while(len(heap) != 0):
                if context_no_punct > max_context:
                    break
                _, current_i = heapq.heappop(heap)
                if current_i in new_sub_context:
                    continue
                new_sub_context.append(current_i)
                children_to_add = doc[current_i].children
                children_to_add = [token.i for token in children_to_add]
                for c_i in children_to_add:
                    counter += 1
                    heapq.heappush(heap, (counter, doc[c_i].i))
                counter += 1
                heapq.heappush(heap, (counter, doc[current_i].head.i))
                new_sub_context = list(set(new_sub_context))
                context_no_punct = len([doc[i] for i in new_sub_context if doc[i].pos_ != "PUNCT"])
            new_sub_context.sort()
            filtered_new_context = filter_non_consecutive(new_sub_context, start_i)
            new_sent = "".join([doc[i].text_with_ws for i in filtered_new_context]).strip()
            return new_sent
        
        doc = nlp_pipe.get_doc(sentence)
        smaller_context = get_context_for_word_heap(doc, bookmark, max_length)
        
        return smaller_context