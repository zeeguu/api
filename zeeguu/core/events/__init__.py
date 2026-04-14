from blinker import signal

# Events related to the badges module
word_translated = signal("word_translated")
exercise_correct = signal("exercise_correct")
audio_lesson_completed = signal("audio_lesson_completed")
streak_changed = signal("streak_changed")
word_learned = signal("word_learned")
article_read = signal("article_read")
friendship_changed = signal("friendship_changed")

# Events related to the friendship module
friend_streak_changed = signal("friend_streak_changed")
