-- Regional stat snapshots share the bounded ecology proposal transport.
ALTER TABLE ecology_service_proposals
    DROP CONSTRAINT ecology_service_proposals_domain_check;
ALTER TABLE ecology_service_proposals
    ADD CONSTRAINT ecology_service_proposals_domain_check
    CHECK (domain IN ('plants','mobs','weather','population','bonuses'));
