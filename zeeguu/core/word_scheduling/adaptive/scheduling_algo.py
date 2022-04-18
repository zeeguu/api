

# information needed for selecting words to practice 
"""
- nextDueDate = when the user should practice this again
- coolingInterval = how much will they have to wait till they see this word again
"""


""" **** nextDueDate *** """

""" 
    Rule #1: when a new word is saved, nextDueDate is null; 
    
    - that way we know that it has not been practiced yet;
    - we can use this info to pull that word up when we need 
    to insert new words in the study
"""

    # scenario 1:
    # - a user has translated 100 words; then they have 
    # two minutes of practice; they practice 10 words
    # - next day they open the exercises again; what 
    # do we want to present them with? old words or 
    # new ones?
    #   - well, if they started learning some words we
    #   should prioritize those; but once they're done
    #   with the things they should study for the day
    #   we can go and catch up with older words...


""" **** coolingInterval *** """

# scenarios
# - user sees a word for the first time, gets it correct
# currentCoolingInterval is set to 1 - we plan to practice
# tomorrow; he got it wrong; we set it to 1min - would be
# good to remind them sooner about it

# - user sees 

"""
    Rule #2: currentCoolingInterval should be used in prioritizing 

    # things that are due with a smaller coolingInterval 

"""


# the scheduler is called when a new word is saved
# or after an exercise is being done;

# if we want to add awareness of difficulty levels for
# exercises, then get words to study should be called
# with the difficulty in mind 
# e.g.  an exercise session that plans to have 3 recognize, 3 audio, and 3 recall
# should make this explicit; such that we don't get very difficult words in 
# recall... although maybe we can simply let the randomization 
# do it's job for now; and ensure 


from datetime import datetime, timedelta

from numpy import number
from zeeguu.core.model.word_to_study import WordToStudy
from zeeguu.core.model import Bookmark, UserWord
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import exists
from sqlalchemy.sql.expression import func


def getWordsToStudy(user, numberOfWords):
    """
        :param: number of words -- how many words to be studied
        the system should be fast enough such as to allow for 
        a query for 

        :param: language - a user might be studying in multiple
        languages; let the algo choose which language is the 
        user interested in
    """
    # to think about

    # - what happens if they have added a lot of words but they
    # have practiced very little? all their due words are studied
    # and now we have to schedule a new word: do we select one 
    # that has high frequency but was first studied two weeks ago?
    # or one that has lower frequency but was seen today? 
    # ... we could ask them? 
    # ... we could prioritize by frequency
    
    # - we promise to prioritize starred words; how do we exactly
    # do that? 
    #   - i guess in two situations:
    #     1. we need to schedule a new word that has not been 
    #        rehearsed yet; we look at the starred ones and 
    #        select one from them; if there's frequency, go with that
    #        else go with (shortness of word/expression as a proxy?)
    #        what if in this way we never get to schedule frequent ones?
    #        well, we promised to schedule starred; so we should do that
    #     2. we have a bunch of words that are due today or before today
    #        we schedule starred ones first, and then non-starred; 
    #        if they don't get to do any non-starred; that's ok; they'll
    #        hopefully do them next time
   
    _now = datetime.now()
    due_words = WordToStudy.query
    due_words = due_words.filter(WordToStudy.user_id == user.id).filter(WordToStudy.language_id==user.learned_language_id)
    due_words = due_words.filter(WordToStudy.nextDueDate<_now)
    due_words = due_words.limit(numberOfWords).all()

    stillNecessary = numberOfWords - len(due_words)
    new_words = []
    if stillNecessary > 0:
        # we need to add other words to study
        # try first to get the starred words first

        new_words = Bookmark.query.filter_by(user_id=user.id).filter_by(learned=False).filter_by(starred=True)
        new_words = new_words.filter(Bookmark.fit_for_study==True)
        new_words = new_words.join(UserWord, Bookmark.origin_id == UserWord.id)
        new_words = new_words.filter( ~exists().where(WordToStudy.bookmark_id==Bookmark.id))
        new_words = new_words.filter(UserWord.language_id == user.learned_language_id)
        new_words = new_words.order_by(Bookmark.starred, func.length(UserWord.word))

        new_words = new_words.filter_by(language_id=user.learned_language_id).limit(stillNecessary).all()

    stillNecessary = numberOfWords - len(due_words) - len(new_words)

    if stillNecessary > 0:
        # we can bring some more words
        # we can go with unstarred 
        pass
    
    due_bookmarks = [dw.bookmark for dw in due_words]
    print("DUE: ")
    print(due_bookmarks)
    print("NEW:")
    print(new_words)

    return due_bookmarks + new_words


# scenario 2:
# - a user starts with 


def updateSchedulingInfo(session, bookmark, outcome):

    # to think about
    # - what do we do this is the first time a user
    # did a correct exercise, but it was not in
    # the WordsToStudy yet? 
    # 

    _now = datetime.now()

    try:
        word_to_study = WordToStudy.find(bookmark)
        
        # if we continue here, it means that we're not seeing this word
        # for the first time
        if outcome == 'C': 
            word_to_study.coolingInterval = word_to_study.coolingInterval * 2 if word_to_study.coolingInterval > 0 else 1
            word_to_study.consecutiveCorrects = word_to_study.consecutiveCorrects +1 
        else:
            # to think about
            # resetting is too harsh (especially if, one has a typo? or it's a high difficulty exercise?)
            word_to_study.coolingInterval = 0
            word_to_study.consecutiveCorrects = 0 
            
        word_to_study.nextDueDate = _now + timedelta(days=word_to_study.coolingInterval)
    
    except NoResultFound:
        # The first time we've seen this word
        word_to_study = WordToStudy(bookmark.user, bookmark)
        if outcome == 'C': 
            word_to_study.coolingInterval = 1
            word_to_study.consecutiveCorrects = 1
        else: 
            word_to_study.coolingInterval = 0
            word_to_study.consecutiveCorrects = 0

        word_to_study.nextDueDate = _now + timedelta(days=word_to_study.coolingInterval)
    
    session.add(word_to_study)
    session.commit()

