# NovaQ SaaS authentication implementation plan

1. Record the focused authentication and migration baseline; audit sessions, CSRF, roles, routing, settings, and current Alembic head.
2. Add revision `0003` with normalized verified users, nullable passwords, Google identities, and hashed authentication challenges; test fresh, upgrade, collision, and downgrade behavior on SQLite.
3. Add shared email normalization, public user serialization, session-response, challenge issue/consume, and email-delivery services.
4. Move authentication routes into an additive router and implement registration, verification, resend, forgot/reset, config, nonce, Google verification, identity resolution, and the shared NovaQ session response.
5. Update seeding, admin user creation, and Account password behavior to use normalization, verification, nullable-password rules, and explicit Google linking.
6. Add frontend auth APIs, AuthProvider Google session entry, public pages, fragment scrubbing, GIS button, Account authentication methods, routes, translations, and styling.
7. Add backend and frontend security/regression tests with fake email and Google verification; run focused suites after each layer.
8. Run the complete repository gates from the repository virtual environment and document environment/Google Console operations.
9. Report exact results and confirm the Analysis workspace and all analytical engines and ownership relationships were untouched.
