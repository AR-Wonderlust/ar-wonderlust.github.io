CREATE TABLE categories (
 code text PRIMARY KEY,
 name text NOT NULL,
 active boolean NOT NULL DEFAULT true
);
INSERT INTO categories(code,name) VALUES
 ('transfer','Transfer aeroportuario'),('traslado','Traslado'),
 ('alojamiento_yala','Alojamiento · Yala'),('alojamiento_carmen','Alojamiento · El Carmen'),
 ('alquiler_vehiculo','Alquiler de vehículo'),('actividad','Excursión / actividad'),
 ('ticket','Ticket por pasajero'),('paquete','Paquete'),('otro','Por clasificar');

CREATE TABLE enquiries (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 request_id uuid NOT NULL UNIQUE,
 code text GENERATED ALWAYS AS ('CON-' || lpad(id::text,8,'0')) STORED UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 channel text NOT NULL CHECK(channel IN ('web','whatsapp','telefono','presencial','agencia','otro')),
 name text NOT NULL DEFAULT '',
 contact text NOT NULL DEFAULT '',
 summary text NOT NULL CHECK(length(summary) BETWEEN 1 AND 6000),
 travel_start date,
 travel_end date,
 passengers integer CHECK(passengers BETWEEN 1 AND 500),
 status text NOT NULL DEFAULT 'nueva' CHECK(status IN ('nueva','contactada','presupuestada','aceptada','perdida','cerrada')),
 owner text NOT NULL DEFAULT '',
 next_action text NOT NULL DEFAULT '',
 follow_up_at timestamptz,
 loss_reason text NOT NULL DEFAULT '',
 version integer NOT NULL DEFAULT 1,
 CHECK(travel_end IS NULL OR travel_start IS NULL OR travel_end>=travel_start),
 CHECK(status<>'perdida' OR length(trim(loss_reason))>0)
);
CREATE INDEX enquiries_created_idx ON enquiries(created_at DESC);
CREATE INDEX enquiries_followup_idx ON enquiries(follow_up_at) WHERE status NOT IN ('perdida','cerrada','aceptada');
CREATE TABLE enquiry_categories (
 enquiry_id bigint REFERENCES enquiries(id) ON DELETE CASCADE,
 category_code text REFERENCES categories(code),
 PRIMARY KEY(enquiry_id,category_code)
);
CREATE TABLE audit_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 created_at timestamptz NOT NULL DEFAULT now(),
 actor text NOT NULL,
 action text NOT NULL,
 entity text NOT NULL,
 entity_id text NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE catalog_items (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id text,
 source_version text,
 source_url text NOT NULL DEFAULT '',
 title text NOT NULL,
 category_code text NOT NULL REFERENCES categories(code),
 content text NOT NULL CHECK(length(content) BETWEEN 1 AND 20000),
 starts_on date,
 ends_on date,
 permanent boolean NOT NULL DEFAULT false,
 status text NOT NULL DEFAULT 'pendiente' CHECK(status IN ('pendiente','aprobado','archivado')),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 approved_by text,
 approved_at timestamptz,
 version integer NOT NULL DEFAULT 1,
 UNIQUE(source_id,source_version),
 CHECK(ends_on IS NULL OR starts_on IS NULL OR ends_on>=starts_on),
 CHECK(status<>'aprobado' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL
   AND (permanent OR (starts_on IS NOT NULL AND ends_on IS NOT NULL))))
);
CREATE INDEX catalog_current_idx ON catalog_items(status, ends_on);
CREATE TABLE automation_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 created_at timestamptz NOT NULL DEFAULT now(),
 event_type text NOT NULL,
 entity_id bigint NOT NULL REFERENCES enquiries(id),
 processed_at timestamptz,
 lease_token uuid,
 lease_until timestamptz,
 attempts integer NOT NULL DEFAULT 0
);
CREATE INDEX automation_pending_idx ON automation_events(id) WHERE processed_at IS NULL;
