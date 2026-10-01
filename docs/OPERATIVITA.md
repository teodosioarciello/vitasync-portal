# VitaSync Portal - Operativita e sicurezza locale

Questo documento raccoglie le note operative minime per sviluppare e usare
in sicurezza locale VitaSync Portal prima di trattare dati sanitari reali.

## 1. Ambiente attuale

Ambiente di sviluppo locale:

- backend FastAPI in Docker;
- frontend Next.js in Docker;
- PostgreSQL 16 in Docker;
- Redis in Docker;
- storage locale dei file in `data/`;
- OCR locale con Tesseract;
- nessuna AI cloud attiva;
- telemetry Next.js disattivata via `NEXT_TELEMETRY_DISABLED=1`.

La telemetry Next.js e' anonima e, secondo la documentazione ufficiale, non
raccoglie variabili d'ambiente, percorsi file, contenuti, log o errori
serializzati. Tuttavia, in un progetto che puo' trattare dati sanitari,
tenerla spenta e' una scelta di privacy by design.

## 2. Segreti e configurazione

Prima di qualsiasi uso non puramente locale, verificare in `.env`:

- `SECRET_KEY` diversa dal default;
- `ENVIRONMENT=production` quando si va in produzione;
- `COOKIE_SECURE=true` se si usa HTTPS;
- SMTP reale solo se servono email vere;
- `DEV_AUTO_VERIFY_EMAIL=false` in produzione.

Il backend fallisce intenzionalmente all'avvio se `ENVIRONMENT=production`
e `SECRET_KEY` e' ancora il default.

## 3. Backup database

Lo script di backup e':

```powershell
.\scripts\backup-db.ps1
```

Esegue un `pg_dump` in formato custom dentro il container PostgreSQL,
verifica il dump con `pg_restore --list`, poi lo copia in:

```text
D:\RD\VitaSync\backups\db\vitasync-db-YYYYMMDD-HHMMSS.dump
```

Il backup include struttura e dati del DB. NON include i file fisici in
`data/`. Per un backup completo servono sia il dump DB sia la cartella
`data/` oppure uno snapshot/backup del volume/host.

### Backup completo codice + dati locali

Per uno snapshot di sviluppo si puo' usare una zip escludendo:

- `node_modules`;
- `.next`;
- `__pycache__`;
- `.venv` / `venv`;
- `.git`;
- eventualmente `data` se contiene documenti sensibili.

Se `data/` contiene referti reali, va trattata come dato sanitario e
cifrata/protetta.

## 4. Restore database

Attenzione: il restore sovrascrive il database corrente.

Procedura locale prudenziale:

```powershell
docker compose stop backend frontend

docker compose cp D:\RD\VitaSync\backups\db\vitasync-db-YYYYMMDD-HHMMSS.dump postgres:/tmp/restore.dump

docker compose exec -T postgres sh -lc "dropdb --if-exists -U vitasync vitasync"
docker compose exec -T postgres sh -lc "createdb -U vitasync vitasync"
docker compose exec -T postgres sh -lc "pg_restore -U vitasync -d vitasync /tmp/restore.dump"

docker compose exec -T postgres sh -lc "rm -f /tmp/restore.dump"

docker compose up -d backend frontend
```

Sostituisci il nome del file dump con quello reale.

## 5. Cancellazione documenti e retention

Dallo Sprint C-media Step 6A la cancellazione documento e' soft-delete:

- `DELETE /api/documents/{id}` sposta il documento nel cestino impostando `deleted_at`;
- il file fisico resta nello storage locale;
- le `lab_tests` collegate restano nel DB;
- le terapie collegate come ricetta restano collegate;
- il documento non compare piu' negli elenchi attivi, nella review, nell'estrazione, nei trend e nei valori laboratorio finche' e' nel cestino.

Endpoint cestino:

- `GET /api/documents/trash` elenca i documenti nel cestino;
- `POST /api/documents/{id}/restore` ripristina un documento dal cestino;
- `DELETE /api/documents/{id}/permanent` elimina definitivamente un documento gia' nel cestino, rimuovendo file, lab_tests e detachando le terapie.

L'eliminazione definitiva e' consentita solo su documenti gia' soft-deleted. Questo riduce il rischio di cancellazione accidentale, ma resta un hard delete irreversibile quando eseguito dal cestino.

### 5.1 Retention e purge manuale

Dallo Sprint C-media Step 7 esiste uno script manuale di retention/purge:

    docker compose exec backend python scripts/purge_expired_trash.py --days 30 --dry-run
    docker compose exec backend python scripts/purge_expired_trash.py --days 30

Default retention: 30 giorni.

Puoi configurarla:

- con environment variable:

    TRASH_RETENTION_DAYS=30

- oppure con parametro CLI:

    --days 30

Lo script elimina solo documenti con:

    deleted_at IS NOT NULL
    AND deleted_at <= now() - retention_days

Non tocca documenti attivi.

Per ogni documento purgato registra audit:

    action = document.retention_purge
    method = SYSTEM
    path = scripts/purge_expired_trash.py
    user_id = null
    extra = document_id=...;patient_id=...;uploaded_by_user_id=...;deleted_at=...;file_existed=...

`user_id` e' nullo perche' l'azione e' di sistema, non di un utente autenticato.

Prima di eseguire purge su dati reali:

- backup DB recente;
- eventuale backup `data/`;
- dry-run preliminare;
- verifica che i documenti candidabili siano effettivamente solo quelli attesi.

### 5.2 Report retention sicuro e scheduler

Dallo Sprint C-media Step 8 esiste uno script di solo report:

    docker compose exec backend python scripts/report_retention_trash.py --days 30

Oppure, da host:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\retention-report.ps1 -Days 30

Questo script:

- elenca i documenti nel cestino oltre la retention;
- NON elimina documenti;
- NON elimina file;
- NON tocca lab_tests;
- registra audit:

    action = document.retention_report
    method = SYSTEM
    path = scripts/report_retention_trash.py
    user_id = null
    extra = days=...;candidates=...;oldest_deleted_at=...;candidate_document_ids=...;truncated=...

La schedulerazione sicura consigliata e' solo il report. Esempio con Task Scheduler Windows:

    schtasks /Create /TN "VitaSync Retention Report" /TR "powershell -NoProfile -ExecutionPolicy Bypass -File D:\RD\VitaSync\vitasync-portal\scripts\retention-report.ps1 -Days 30" /SC DAILY /ST 03:15 /F

Per rimuovere l'activity schedulata:

    schtasks /Delete /TN "VitaSync Retention Report" /F

Policy operativa:

- lo scheduler puo' eseguire solo `retention-report.ps1`;
- la purge definitiva resta manuale;
- prima di ogni purge reale eseguire backup DB e dry-run;
- non schedulare `purge_expired_trash.py` senza una revisione esplicita della policy.

Futura evoluzione possibile:

- scheduler con approvazione umana;
- UI “Svuota cestino”;
- retention differenziata per paziente/tenant;
- notifiche prima della purge definitiva.

## 6. Audit log

La tabella `audit_logs` registra azioni sensibili:

- login/register/logout;
- upload documento;
- extract documento;
- confirm-all lab tests;
- patch lab test;
- delete documento;
- create/update medicine;
- create/update therapy;
- create/update reminder.

In questo step l'`user_id` viene associato alle azioni sensibili su
documenti e lab-test. Per login, medicinali, terapie e promemoria l'audit
esiste ma `user_id` puo' ancora essere nullo.

Query utile:

```sql
select action, method, path, status_code, user_id, created_at
from audit_logs
order by created_at desc
limit 50;
```

Filtrare cancellazioni documento:

```sql
select action, method, path, status_code, user_id, created_at
from audit_logs
where action = 'document.delete'
order by created_at desc
limit 20;
```

## 7. Upload sicuri

Gli upload accettano solo:

- PDF;
- JPEG;
- PNG.

La validazione usa magic byte, non solo estensione/MIME dichiarato.
Limite attuale: 25 MB.

File HEIC/TIFF non sono ancora supportati.

## 8. OCR e limiti

L'OCR e' locale con Tesseract, lingue `ita` e `eng`.

Limiti noti:

- foto mosse/inclinate/scarsamente illuminate possono produrre errori;
- tabelle complesse possono essere interpretate male;
- alcune confusioni OCR sono mitigate da normalizzazione hardening, ma non
  eliminate;
- la review utente resta obbligatoria prima di considerare un valore
  confermato.

## 9. Dati reali

Prima di caricare dati sanitari reali, anche solo personali, completare
almeno:

- hardening produzione;
- backup affidabili e testati;
- policy cancellazione/retention;
- audit piu' completo;
- valutazione hosting e responsible disclosure;
- informativa privacy/termini adeguata.

Finche' il progetto e' in sviluppo, usare fixture sintetiche.

<!-- CLEANUP-TEST-DATA-SECTION -->
## Igiene dati di test

Durante gli sprint di sviluppo sono stati creati diversi dati di test:
documenti fixture, medicinali di test, terapie di test, promemoria di test,
lab-test sintetici e file in `data/documents/_fixtures`.

Per mantenere pulito l'ambiente di sviluppo esiste uno script dedicato:

    docker compose exec backend python scripts/cleanup_test_data.py

Questo comando esegue solo un **dry-run**: elenca cosa verrebbe eliminato,
ma non elimina nulla.

Per eliminare realmente i dati di test transienti riconosciuti dai pattern:

    docker compose exec backend python scripts/cleanup_test_data.py --execute

I seed/demo fixtures canonici (lab-report-synthetic, ocr-lab-report-synthetic, ocr-synonyms-synthetic, promemoria fixture, terapia sintetica di test) NON vengono eliminati di default. Per includerli:

    docker compose exec backend python scripts/cleanup_test_data.py --include-seed-fixtures --dry-run
    docker compose exec backend python scripts/cleanup_test_data.py --include-seed-fixtures --execute

La script elimina solo entita' che corrispondono a pattern di test noti, ad esempio:

- titoli documento che iniziano con `TEST C-media`, `TEST retention`, `TEST trend`, `CLEANUP TEST`;
- storage key in `_fixtures/test-...`, `_fixtures/trend-trash-...`, `_fixtures/retention-...`, `_fixtures/cleanup-test-...`;
- medicinali/terapie/promemoria con note o titoli di test;
- lab-test con codici/nomi di test;
- file orfanti in `data/documents/_fixtures` corrispondenti ai pattern di test.

Importante:

- lo script **non elimina audit log**;
- lo script **non elimina utenti/pazienti**;
- lo script **non tocca dati che non corrispondono ai pattern**;
- prima di usare `--execute` su dati reali o semi-realii, fare backup DB e verificare il dry-run.

Test deterministico:

    docker compose exec backend python scripts/test_cleanup_test_data.py

Il test crea entita' di test ed entita' di controllo, verifica che il dry-run
non elimini nulla e che l'esecuzione elimini solo le entita' di test.

Dopo un cleanup reale, se servono dati demo, e' possibile rilanciare i seed:

    docker compose exec backend python scripts/seed_fixture.py
    docker compose exec backend python scripts/seed_ocr_fixture.py
    docker compose exec backend python scripts/seed_ocr_synonyms_fixture.py
