# Security Notes

This review covers frontend-facing upload behavior only. Backend validation, image processing, email delivery, routes, schemas, config, and environment handling were intentionally left unchanged.

- The upload UI validates PNG/JPG type and the 5 MB size limit before submission for immediate feedback. This is only a UX courtesy; the backend validator remains the security boundary.
- SVG uploads are not accepted or previewed by the client, avoiding raw SVG rendering paths in the browser UI.
- Local image previews use `URL.createObjectURL()` and revoke the object URL when a new file is selected or the page unloads.
- The frontend sends the existing multipart form fields, `recipient_email` and `file`, to the existing `/process` endpoint. No new endpoints or request/response shapes were introduced.
- No API keys, tokens, or client-exposed environment variables were added.
