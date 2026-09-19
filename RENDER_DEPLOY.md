# Deploy LifeClip on Render

LifeClip deploys as one Docker web service plus PostgreSQL. The Docker image builds the React frontend, installs Tesseract OCR, starts FastAPI, and serves the frontend and `/api` from one HTTPS origin.

## Before deploying

1. Verify the application locally.
2. Commit and push this complete project to GitHub. Never commit `backend/.env`.
3. Keep the Cloudinary cloud name, API key and matching API secret ready.

## Create the Blueprint

1. Sign in to [Render](https://dashboard.render.com/).
2. Select **New → Blueprint**.
3. Connect the GitHub repository containing this project.
4. Render detects the root `render.yaml`.
5. Enter the three prompted secret values:
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`
6. Confirm creation of the `lifeclip` web service and `lifeclip-db` PostgreSQL database.
7. Wait for the Docker build and deploy to finish.

Do not create `VITE_API_URL` for this combined deployment. The frontend intentionally calls same-origin `/api`.

## Verify production

Open the service URL, then check:

```text
https://YOUR-SERVICE.onrender.com/api/health
```

The response should report:

- `status`: `ok`
- `database`: `ok`
- `cloudinary_configured`: `true`

Then upload one JPEG, PNG or WebP image and confirm it reaches Ready or Needs review.

## Operational notes

- Render's free web service may sleep after inactivity, so the first request can be slow.
- Free Render PostgreSQL databases expire after 30 days. Upgrade or migrate before expiry if data must persist.
- Render's web-service filesystem is ephemeral. `DATABASE_URL` therefore points at PostgreSQL instead of local SQLite.
- Cloudinary stores the images; PostgreSQL stores LifeClip records and extracted metadata.
- OCR analysis interrupted by a Render restart is marked Failed and can be retried honestly from the UI.
- Change `RETENTION_DAYS` in Render environment settings if 90 days is not desired. Use `0` to retain until explicit deletion.

## Updating the deployment

Push a new commit to the connected GitHub branch. Render automatically rebuilds and redeploys it. The database schema update is additive and runs during FastAPI startup.
