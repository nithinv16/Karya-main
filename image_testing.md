# Image Integration Testing Rules

- Always use base64-encoded images for all tests and requests.
- Accepted formats: JPEG, PNG, WEBP only. No SVG/BMP/HEIC.
- Do not upload blank, solid-color, or uniform-variance images. Every image must contain real visual features (objects, edges, textures, shadows).
- If image is not PNG/JPEG/WEBP, transcode to PNG or JPEG before upload; re-detect MIME after transformation.
- If the image is animated, extract the first frame only.
- Resize large images to reasonable bounds.

App-specific: Daily Report generation (`POST /api/reports/generate`) accepts `photo_ids` of files previously uploaded via `POST /api/files/upload`. Backend fetches photos from object storage, base64-encodes them and passes them to Claude Sonnet 4.6 as ImageContent.
