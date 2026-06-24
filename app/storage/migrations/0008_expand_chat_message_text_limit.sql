ALTER TABLE chat_messages
    DROP CONSTRAINT IF EXISTS chat_messages_message_text_check;

ALTER TABLE chat_messages
    ADD CONSTRAINT chat_messages_message_text_check
    CHECK (char_length(message_text) <= 2000);
