# Privacy checklist iniziale — VitaSync Portal

## Obbligo prima di apertura a terzi

- [ ] Definire titolare del trattamento.
- [ ] Predisporre informativa privacy completa.
- [ ] Raccogliere consenso esplicito per dati sanitari.
- [ ] DPIA formale, non solo light.
- [ ] Valutazione legale/regolatoria.
- [ ] Provider hosting UE con DPA.
- [ ] Provider AI conforme o modello locale.
- [ ] Procedura data breach.
- [ ] Retention policy.
- [ ] Export dati.
- [ ] Cancellazione account effettiva.
- [ ] Audit log completo.
- [ ] Backup cifrati e test restore.
- [ ] HTTPS, HSTS, CSP.
- [ ] Rate limiting e anti-abuso.
- [ ] Email verification reale.
- [ ] Disable DEV_AUTO_VERIFY_EMAIL in produzione.
- [ ] COOKIE_SECURE=true in produzione.
- [ ] Registrazione beta/invite-only fino a conformità.

## Regola operativa

Non caricare referti reali con dati identificativi finché il sistema non è pronto.
Usare documenti sintetici o fortemente anonimizzati per sviluppo e test.