-- Operator metadata is separate from native game and combat authority.
CREATE TABLE admin_map_metadata (
    map_id integer PRIMARY KEY,
    name text NOT NULL DEFAULT '',
    notes text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE admin_panel_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operator text NOT NULL,
    action text NOT NULL,
    target text NOT NULL,
    before_data jsonb,
    after_data jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX admin_panel_audit_created ON admin_panel_audit(created_at DESC);
