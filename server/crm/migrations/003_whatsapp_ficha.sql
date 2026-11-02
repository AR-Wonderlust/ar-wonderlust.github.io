ALTER TABLE whatsapp_events ADD COLUMN sender_name text NOT NULL DEFAULT '';
ALTER TABLE whatsapp_events ADD COLUMN sender_phone text NOT NULL DEFAULT '';
ALTER TABLE whatsapp_events ADD COLUMN phone_source text NOT NULL DEFAULT '';
ALTER TABLE whatsapp_events ADD COLUMN ficha jsonb;
ALTER TABLE whatsapp_events ADD COLUMN ficha_version integer NOT NULL DEFAULT 1;
ALTER TABLE whatsapp_events ADD COLUMN ficha_updated_at timestamptz;
