-- Cached AI explanations of a selected word or phrase in its sentence, behind
-- the Explain option in the translation menu.
--
-- Cacheable because the explanation is generated at temperature 0 from nothing
-- but (selection, sentence, languages, level): same inputs, same text. Sentences
-- are shared between readers of an article, so one learner's lookup serves the
-- next, saving a Sonnet call and the wait.
--
-- The sentence is keyed by sha256 rather than by value: article sentences are
-- longer than MySQL will index. The full text is kept in its own column so a
-- cached explanation can still be read and judged by a person.
--
-- Deliberately not keyed by user: the inputs are a word and a published
-- sentence, nothing personal, and keying by user would discard most of the
-- benefit.
CREATE TABLE selection_explanation (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,

    selection VARCHAR(255) NOT NULL,

    context_hash VARCHAR(64) NOT NULL,
    context TEXT NOT NULL,

    language_id INT NOT NULL,
    native_language_id INT NOT NULL,

    cefr_level VARCHAR(2) NOT NULL,

    explanation TEXT NOT NULL,

    created DATETIME NOT NULL,

    CONSTRAINT unique_selection_explanation
        UNIQUE (selection, context_hash, language_id, native_language_id, cefr_level),

    CONSTRAINT fk_selection_explanation_language
        FOREIGN KEY (language_id) REFERENCES language (id),
    CONSTRAINT fk_selection_explanation_native_language
        FOREIGN KEY (native_language_id) REFERENCES language (id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
