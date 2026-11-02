ALTER TABLE whatsapp_events ADD COLUMN manual_category text REFERENCES categories(code);
CREATE TABLE passenger_requests (
 id uuid PRIMARY KEY,
 event_id text NOT NULL REFERENCES whatsapp_events(event_id),
 enquiry_id bigint NOT NULL REFERENCES enquiries(id),
 token_hash text NOT NULL UNIQUE,
 snapshot jsonb NOT NULL,
 response jsonb,
 status text NOT NULL DEFAULT 'awaiting' CHECK(status IN ('awaiting','received','reviewed','revoked')),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 submitted_at timestamptz,
 submission_id uuid,
 reviewed_at timestamptz,
 notice_status text NOT NULL DEFAULT 'not_required' CHECK(notice_status IN ('not_required','pending','sent','unknown','paused')),
 notice text NOT NULL DEFAULT '',
 last_attempt_at timestamptz
);
CREATE INDEX passenger_request_event_idx ON passenger_requests(event_id,created_at DESC);
CREATE UNIQUE INDEX passenger_request_one_pending_idx ON passenger_requests(event_id) WHERE status IN ('awaiting','received');
CREATE INDEX passenger_request_notice_idx ON passenger_requests(created_at) WHERE notice_status='pending';
