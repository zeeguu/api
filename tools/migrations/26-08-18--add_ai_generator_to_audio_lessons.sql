-- Record which model and prompt version produced each audio lesson script.
--
-- created_by has always been the literal 'claude-v1', so it cannot answer either
-- question. It matters because the Anthropic->DeepSeek fallback chain means the
-- configured model is not necessarily the model that served: scripts generated
-- while the Anthropic spend cap was reached were written by DeepSeek and recorded
-- as Claude. Nullable, so existing rows stay honest about not knowing.

ALTER TABLE audio_lesson_meaning
    ADD COLUMN ai_generator_id INT DEFAULT NULL,
    ADD CONSTRAINT fk_audio_lesson_meaning_ai_generator
        FOREIGN KEY (ai_generator_id) REFERENCES ai_generator (id);

ALTER TABLE audio_lesson_dialogue
    ADD COLUMN ai_generator_id INT DEFAULT NULL,
    ADD CONSTRAINT fk_audio_lesson_dialogue_ai_generator
        FOREIGN KEY (ai_generator_id) REFERENCES ai_generator (id);
