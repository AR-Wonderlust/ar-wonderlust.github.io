CREATE TABLE transport_rates (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 fingerprint text NOT NULL UNIQUE,
 snapshot jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE transport_quotes (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 request_id uuid NOT NULL UNIQUE,
 enquiry_id bigint NOT NULL REFERENCES enquiries(id),
 rate_id bigint NOT NULL REFERENCES transport_rates(id),
 payload jsonb NOT NULL,
 calculation jsonb NOT NULL,
 status text NOT NULL DEFAULT 'borrador' CHECK(status IN ('borrador','aprobado')),
 created_at timestamptz NOT NULL DEFAULT now(),
 approved_at timestamptz,
 approved_by text,
 CHECK(status <> 'aprobado' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);
