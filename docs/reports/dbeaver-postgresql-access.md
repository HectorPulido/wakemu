# Local DBeaver PostgreSQL access

PostgreSQL is published from Docker on the same machine at `127.0.0.1:15432`. It remains attached to the internal service network and also uses the existing client-access network so Docker can publish the localhost port. No LAN or public binding is enabled.

Create a PostgreSQL connection in DBeaver with:

| Setting | Value |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `15432` |
| Database | `wakemu_runtime` |
| Username | `wakemu_inspector` |
| Password | Contents of `.runtime/local/secrets/dbeaver-password` |
| SSL | Disabled for this local connection |

The password file is private, mode `600`; do not commit it or copy it into documentation. The inspector can read all public tables but cannot update them or create roles/databases. Default privileges for tables created by `wakemu` grant inspector SELECT, including subsequently imported catalogs.

Press **Test Connection**, then open the `public` schema and inspect its tables. Refresh the schema after migrations create new tables. A connection from another machine requires a separately configured tunnel or network binding; `127.0.0.1` refers to this Mac only.

Validation: PostgreSQL healthy, localhost socket reachable, inspector password authentication succeeds, zero public tables lack SELECT, and inspector has no superuser/create-database/create-role permissions.
