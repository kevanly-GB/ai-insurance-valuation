# Team contribution guidelines

- Create a branch from `main` for each feature (for example `feature/claim-upload`).
- Keep related frontend, backend and database changes in the same pull request where practical.
- Describe the feature, relevant functional requirement(s), how it was tested, and any new environment variables in the pull request.
- Ask another team member to review before merging. Avoid force-pushing to `main`.
- Add tests for data validation, role-based access, claim ownership and AI-output handling.
- Use only synthetic test documents in this public repository; never commit real insurance documents or customer data.
- Do not commit `.env`, API tokens, AWS credentials, Terraform state or database dumps.
- Document architectural decisions and AWS configuration in `docs/architecture/` and `infrastructure/`.

The directories currently contain `.gitkeep` files where necessary because Git does not track empty directories. These placeholders can be removed when actual implementation files are added.
