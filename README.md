# Randy Kleckner — Portfolio

A responsive, dependency-free static portfolio highlighting Apple technical operations experience, AI-assisted analytics platform development, and technical projects.

## Preview

Run `npm run dev`, then visit http://127.0.0.1:4173. Python 3 is required for the preview server. Run `npm run check` to check JavaScript syntax.

## Content and design

- `index.html`: page copy, navigation, project details, and GitHub links.
- `styles.css`: responsive layout, typography, diagrams, and reduced-motion support.
- `script.js`: current copyright year.
- `assets/favicon.svg`: site icon.

Local preview requires no package installation. `npm run build` copies only public assets to `dist/` for deployment. Google Fonts is optional; the site falls back to locally available sans-serif fonts.

Content is based on the supplied August 2026 résumé, including Apple roles, project scope, dated usage figures, education, and certifications. Development is described as AI-assisted and grounded in operations and business analysis. The analytics graphic is explicitly illustrative, not an internal screenshot. The résumé is presented as an accessible HTML section; the original Pages document, phone number, and internal source data are not included. The University of Iowa entry does not imply a completed degree; the UMGC degree is marked in progress, expected 2027.

## GitHub

The local repository's `origin` is https://github.com/randykleckner/randykleckner-portfolio.git. Cloudflare Workers Builds is connected to `main`, with deploy command `npx wrangler deploy`. `wrangler.jsonc` runs the static build and serves `dist/`. The existing R2 binding is preserved; the portfolio does not expose the bucket or provide email access.

## Incoming job email

`worker/index.mjs` accepts only `randy@randykleckner.com` and stores bounded raw MIME messages in the existing `randy-job-mail` R2 bucket under `inbox/<sha256>.eml`. The `job-mail-inbound` binding name is retained exactly from the dashboard and accessed with bracket notation. HTTP requests serve static portfolio assets only; no HTTP route lists or returns email objects. A Cloudflare Email Routing address rule must point to this Worker before delivery works. R2 must remain private. Run `npm test` for storage, size, recipient, and HTTP isolation checks.
