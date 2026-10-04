# Deploy remoto sicuro - VitaSync Portal

## Prima del deploy
1. cp .env.production.template .env.production
2. Personalizza SECRET_KEY, INVITE_CODE, SMTP_*, CORS_ORIGINS, FRONTEND_URL
3. python backend/scripts/security_check.py --env-file .env.production
   Deve uscire senza ERRORI.

## Opzione A - Tailscale (raccomandata per famiglia)
- Installa Tailscale su server e dispositivi familiari.
- Nessun porto aperto verso internet: accesso solo dal tailnet.
- URL: http://IP-TAILSCALE:3001 (oppure HTTPS con tailscale cert).
- Vantaggi: zero esposizione pubblica, setup minimo.

## Opzione B - Cloudflare Tunnel + Access
- cloudflared tunnel create vitasync + route dns sul tuo dominio.
- Ingress verso http://localhost:3001.
- Cloudflare Access: policy Allow solo email familiari (2FA).
- Vantaggi: HTTPS automatico, accesso da qualsiasi browser.

## HTTPS e HSTS
HSTS va impostato sul terminatore TLS (Caddy/Nginx/Cloudflare), non nell'app:
- Caddy: header Strict-Transport-Security automatico con tls.
- Cloudflare: Edge -> HTTPS forzato + HSTS attivabile in dashboard.

## Checklist hardening
- REGISTRATION_MODE=invite_only e REQUIRE_INVITE_CODE=true
- DEV_AUTO_VERIFY_EMAIL=false, DEV_EXPOSE_VERIFICATION_LINK=false
- COOKIE_SECURE=true (solo con HTTPS)
- Backup giornalieri DB + storage, cifrati e off-site
- Restore drill periodico

## Rate limit
Attivi su login/register. Estensione a upload/extract/report/export
pianificata in Sprint 5.4b dopo verifica del pattern esistente.