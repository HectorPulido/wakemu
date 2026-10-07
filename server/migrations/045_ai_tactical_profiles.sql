-- Tactical difficulty changes search/utility, never actor damage or resources.
CREATE TABLE ai_policy_versions (
    profile text NOT NULL CHECK (profile ~ '^[a-z][a-z0-9_]{0,63}$'),
    version integer NOT NULL CHECK (version > 0),
    policy jsonb NOT NULL CHECK (jsonb_typeof(policy) = 'object'),
    forecast_limits jsonb NOT NULL CHECK (jsonb_typeof(forecast_limits) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile, version)
);
INSERT INTO ai_policy_versions(profile,version,policy,forecast_limits)
VALUES ('normal',1,'{}','{"max_previews":48,"budget_ms":150,"depth":2}');

CREATE TABLE ai_policy_active (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    profile text NOT NULL,
    version integer NOT NULL,
    FOREIGN KEY (profile,version) REFERENCES ai_policy_versions(profile,version)
);
INSERT INTO ai_policy_active(singleton,profile,version) VALUES (true,'normal',1);

CREATE TABLE monster_ai_profiles (
    monster_reference integer PRIMARY KEY CHECK (monster_reference > 0),
    profile text NOT NULL,
    version integer NOT NULL,
    FOREIGN KEY (profile,version) REFERENCES ai_policy_versions(profile,version)
);
