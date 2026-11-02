CREATE TABLE whatsapp_events (
 event_id text PRIMARY KEY,
 account_id uuid NOT NULL,
 group_id text NOT NULL,
 group_name text NOT NULL,
 sender_id text NOT NULL,
 message_id text NOT NULL,
 text text NOT NULL CHECK(length(text) BETWEEN 1 AND 5000),
 source_at timestamptz NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now(),
 processed_at timestamptz,
 classification text,
 enquiry_id bigint REFERENCES enquiries(id),
 draft text NOT NULL DEFAULT '',
 notice text NOT NULL DEFAULT '',
 delivery_status text NOT NULL DEFAULT 'pending' CHECK(delivery_status IN ('pending','sent','unknown','paused','not_required')),
 last_attempt_at timestamptz
);
CREATE INDEX whatsapp_pending_idx ON whatsapp_events(received_at) WHERE processed_at IS NULL;
CREATE INDEX whatsapp_delivery_idx ON whatsapp_events(received_at) WHERE delivery_status='pending' AND enquiry_id IS NOT NULL;
