-- Extend administrative audit to explicit global flora controls.
ALTER TABLE ecology_admin_operations
 DROP CONSTRAINT ecology_admin_operations_command_check;
ALTER TABLE ecology_admin_operations
 ADD CONSTRAINT ecology_admin_operations_command_check
 CHECK (command IN ('!nuke','!nuke-all','!genesis','!genesis-all',
                   '!nuke-all-flora','!genesis-all-flora'));
