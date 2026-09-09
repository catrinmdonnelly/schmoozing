#!/usr/bin/env python3
"""Write a scanned business card into a CRM destination, safely.

The reading of the card is done by the model, not by this script. This script
does the three mechanical jobs that are easy to get wrong by hand:

  1. `check`  looks the person and the company up across every tab of the
              destination first, so a card that is already on file, already a
              client, or explicitly archived as do-not-contact is caught before
              anything is written.
  2. `add`    writes the row by matching the live header row by NAME, never by
              position, so a column inserted in the sheet later cannot shift the
              data into the wrong columns.
  3. `init`   drops an example config next to you so a new user can point the
              skill at their own destination.

Usage:
    python3 card_capture.py check --company "Acme Ltd" --email jo@acme.co.uk
    python3 card_capture.py add --json card.json [--dry-run]
    python3 card_capture.py add --json cards.json --multi
    python3 card_capture.py init [--path ./schmoozing.config.json]

Config resolution order:
    $SCHMOOZING_CONFIG
    ./.schmoozing.json
    ./schmoozing.config.json
    ~/.config/schmoozing/config.json
    no config found -> CSV fallback at ./schmoozing-captures.csv

See references/config.example.json for the schema.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG = SKILL_DIR / 'references' / 'config.example.json'

CONFIG_CANDIDATES = [
    Path('.schmoozing.json'),
    Path('schmoozing.config.json'),
    Path.home() / '.config' / 'schmoozing' / 'config.json',
]

CSV_FALLBACK = Path('schmoozing-captures.csv')
CSV_FIELDS = ['captured', 'company', 'name', 'job_title', 'email', 'phone',
              'website', 'linkedin', 'location', 'sector', 'event', 'notes',
              'fit', 'unverified']

LEARNED_KINDS = ('correction', 'verdict', 'extraction', 'connector', 'fit',
                 'process')


# ---------------------------------------------------------------- config


def load_config(explicit=None):
    """Return (config_dict, path_or_None). No config is a valid state."""
    paths = []
    if explicit:
        paths.append(Path(explicit).expanduser())
    elif os.environ.get('SCHMOOZING_CONFIG'):
        paths.append(Path(os.environ['SCHMOOZING_CONFIG']).expanduser())
    paths.extend(CONFIG_CANDIDATES)

    for p in paths:
        if p.is_file():
            with open(p) as fh:
                return json.load(fh), p
    if explicit:
        sys.exit(f'Config not found: {explicit}')
    return None, None


def _expand(p):
    return Path(str(p)).expanduser()


# ---------------------------------------------------------------- learning


def learned_path(cfg_path=None):
    """The learning log lives beside the config, so it moves with the user."""
    if cfg_path:
        return Path(cfg_path).expanduser().parent / 'schmoozing-learned.jsonl'
    return Path.home() / '.config' / 'schmoozing' / 'schmoozing-learned.jsonl'


def learn_add(cfg_path, kind, note, subject=None):
    """Append one lesson. Appending only, because history is the point.

    A skill that is corrected and forgets is a skill that gets corrected again
    next month. Every entry here is something a run got wrong, or something a
    run had to work out the hard way.
    """
    if kind not in LEARNED_KINDS:
        sys.exit(f'kind must be one of {", ".join(LEARNED_KINDS)}')
    path = learned_path(cfg_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {'date': date.today().isoformat(), 'kind': kind,
             'subject': subject or '', 'note': note}
    with open(path, 'a') as fh:
        fh.write(json.dumps(entry) + '\n')
    print(f'Recorded a {kind} lesson in {path}')
    return entry


def _print_learned_count(cfg_path):
    """`where` runs at the start of a session, so it is where to surface this."""
    entries = learn_list(cfg_path, limit=10000)
    if entries:
        print(f'Lessons on file: {len(entries)}. Read them with "learn" before '
              'processing cards.')


def learn_list(cfg_path, limit=30, kind=None):
    path = learned_path(cfg_path)
    if not path.exists():
        return []
    entries = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue                      # a bad line must not kill the run
            if kind and entry.get('kind') != kind:
                continue
            entries.append(entry)
    return entries[-limit:]


# ---------------------------------------------------------------- sheet access


def retry(fn, tries=5, first_wait=2):
    """Google's API drops connections often enough to matter mid-batch.

    A dropped connection halfway through a stack of cards is the worst case,
    because it is not obvious afterwards which rows made it in. Retrying with a
    widening gap turns nearly all of those into a pause instead.
    """
    import time
    wait = first_wait
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as exc:
            transient = any(word in type(exc).__name__ for word in
                            ('Connection', 'Timeout', 'Protocol', 'Remote')) \
                or 'Connection aborted' in str(exc) \
                or 'RemoteDisconnected' in str(exc) \
                or getattr(getattr(exc, 'response', None), 'status_code', 0) in (429, 500, 502, 503)
            if not transient or attempt == tries:
                raise
            print(f'  Network hiccup ({type(exc).__name__}), retrying in {wait}s '
                  f'[{attempt}/{tries - 1}]', file=sys.stderr)
            time.sleep(wait)
            wait *= 2


_WORKBOOK = None


def _missing_gspread_message():
    """A machine often has several Pythons and only one of them has gspread."""
    import shutil
    import subprocess

    candidates = ['/opt/homebrew/bin/python3', '/usr/local/bin/python3',
                  shutil.which('python3.13'), shutil.which('python3.12'),
                  shutil.which('python3.11'), shutil.which('python3')]
    for path in candidates:
        if not path or path == sys.executable or not Path(path).exists():
            continue
        try:
            probe = subprocess.run([path, '-c', 'import gspread'],
                                   capture_output=True, timeout=20)
        except Exception:
            continue
        if probe.returncode == 0:
            args = ' '.join(sys.argv[1:])
            return (f'This interpreter ({sys.executable}) has no gspread, but '
                    f'{path} does. Re-run with:\n\n'
                    f'  {path} {Path(__file__).resolve()} {args}\n')
    return ('gspread and google-auth are needed for a google_sheet destination. '
            'Install them with "pip install gspread google-auth", or remove '
            '"destination" from the config to fall back to CSV.')


def open_workbook(cfg):
    """Opened once per run, so a batch of cards is one connection, not one each."""
    global _WORKBOOK
    if _WORKBOOK is not None:
        return _WORKBOOK
    dest = cfg['destination']
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        sys.exit(_missing_gspread_message())
    scopes = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/drive']
    key = _expand(dest.get('credentials', ''))
    if not dest.get('credentials'):
        sys.exit('The config has a google_sheet destination but no '
                 '"credentials" path to a service account JSON key.')
    if not key.is_file():
        sys.exit(f'No service account key at {key}. Check the "credentials" '
                 'path in the config. The key is the JSON file downloaded from '
                 'Google Cloud, and the sheet must be shared with the service '
                 "account's email address as Editor.")
    try:
        creds = Credentials.from_service_account_file(str(key), scopes=scopes)
    except ValueError as exc:
        sys.exit(f'{key} is not a usable service account key: {exc}')
    _WORKBOOK = retry(lambda: gspread.authorize(creds).open_by_key(dest['sheet_id']))
    return _WORKBOOK


def _norm(value):
    return ' '.join(str(value or '').lower().split())


def _company_key(value):
    """Company names differ by suffix and punctuation more than by substance."""
    text = _norm(value)
    for junk in [' limited', ' ltd.', ' ltd', ' plc', ' llp', ' & co', ' group',
                 ',', '.', "'", '(', ')']:
        text = text.replace(junk, ' ')
    return ' '.join(text.split())


# ---------------------------------------------------------------- check


# Columns that identify who a row is about. A match in one of these is a real
# duplicate. A match anywhere else in the row is only a mention, which is worth
# reading but is not the same person on file twice.
IDENTITY_HEADERS = ('company', 'contact', 'name', 'person', 'client', 'account',
                    'organisation', 'organization', 'email', 'website', 'domain',
                    'linkedin', 'phone', 'mobile')


def _identity_columns(headers):
    return [i for i, h in enumerate(headers)
            if any(k in h.lower() for k in IDENTITY_HEADERS)]


def check(cfg, company=None, email=None, name=None, domain=None):
    """Search the destination for an existing record. Returns a list of hits.

    A CSV user gets the same duplicate check as a spreadsheet user, because
    adding the same person three times over a year of events is the failure this
    step exists to prevent, and it does not care where the rows live.
    """
    warn_tabs = {t.lower() for t in (cfg or {}).get('warn_tabs', [])}
    skip_tabs = {t.lower() for t in (cfg or {}).get('skip_tabs', [])}
    hits = []

    needles = {
        'company': _company_key(company) if company else None,
        'email': _norm(email) if email else None,
        'name': _norm(name) if name else None,
        'domain': _norm(domain).replace('www.', '') if domain else None,
    }

    def matches(text):
        found = []
        plain, as_company = _norm(text), _company_key(text)
        if needles['email'] and needles['email'] in plain:
            found.append('email')
        if needles['company'] and len(needles['company']) > 3 \
                and needles['company'] in as_company:
            found.append('company')
        if needles['name'] and len(needles['name']) > 5 and needles['name'] in plain:
            found.append('name')
        if needles['domain'] and len(needles['domain']) > 5 \
                and needles['domain'] in plain:
            found.append('domain')
        return found

    def scan(title, rows):
        if not rows:
            return
        headers = [h.strip() for h in rows[0]]
        id_cols = _identity_columns(headers)
        for n, row in enumerate(rows[1:], start=2):
            id_text = ' '.join(row[i] for i in id_cols if i < len(row))
            matched = matches(id_text) if id_cols else []
            strength = 'record'
            if not matched:
                matched = matches(' '.join(row))
                strength = 'mention'
            if not matched:
                continue
            record = {h: (row[i] if i < len(row) else '')
                      for i, h in enumerate(headers) if h}
            hits.append({
                'tab': title,
                'row': n,
                'strength': strength,
                'matched_on': matched,
                'warn': title.lower() in warn_tabs,
                'record': {k: v for k, v in record.items() if v},
            })

    kind = ((cfg or {}).get('destination') or {}).get('type', 'csv')

    if kind == 'connector':
        # The script cannot see inside someone else's CRM. Say so loudly rather
        # than returning an empty list, which reads as "no duplicates found".
        return [{'tab': 'connector', 'row': 0, 'strength': 'unknown',
                 'matched_on': [], 'warn': True,
                 'record': {'note': 'Duplicate check not run. This destination '
                                    'is reached through a connector, so search '
                                    'it with that tool before writing.'}}]

    if kind == 'google_sheet':
        wb = open_workbook(cfg)
        for ws in wb.worksheets():
            if ws.title.lower() in skip_tabs:
                continue
            try:
                rows = retry(lambda: ws.get_all_values())
            except Exception as exc:                   # a tab can be huge or odd
                print(f'  (skipped tab {ws.title}: {exc})', file=sys.stderr)
                continue
            scan(ws.title, rows)
    elif CSV_FALLBACK.exists():
        with open(CSV_FALLBACK, newline='') as fh:
            scan(CSV_FALLBACK.name, list(csv.reader(fh)))

    hits.sort(key=lambda h: (not h['warn'], h['strength'] != 'record'))
    return hits


# ---------------------------------------------------------------- add


def build_row(headers, card, cfg):
    """Map card fields onto the live header row, by header name."""
    mapping = cfg.get('columns', {})
    defaults = cfg.get('defaults', {})
    values = [''] * len(headers)
    unmapped = []

    for header, field in mapping.items():
        if header not in headers:
            unmapped.append(header)
            continue
        value = card.get(field, '')
        if isinstance(value, list):
            value = ' | '.join(str(v) for v in value if v)
        values[headers.index(header)] = str(value or '')

    for header, value in defaults.items():
        if header in headers and not values[headers.index(header)]:
            values[headers.index(header)] = str(value)

    return values, unmapped


def add_columns(ws, headers, missing):
    """Append new headers at the END so nothing positional shifts."""
    start = len(headers) + 1
    if start + len(missing) - 1 > ws.col_count:
        ws.add_cols(start + len(missing) - 1 - ws.col_count)
    ws.update(
        values=[missing],
        range_name=f'{_a1_col(start)}1:{_a1_col(start + len(missing) - 1)}1',
    )
    return headers + missing


# Google rejects the whole write if any one cell is over 50,000 characters.
CELL_LIMIT = 49_900


def sheet_safe(values):
    """Make values survive Google Sheets exactly as they were read off the card.

    Two things bite here. A leading +, =, - or @ makes Sheets evaluate the cell,
    which turned a card printing "+44 7700 900123" into #ERROR!, silently. A
    leading apostrophe forces text and is not part of the value when the cell is
    read back, so the number survives as printed.

    And one oversized cell fails the entire row, losing every other field with
    it. A truncated note that says it was truncated beats no record at all.
    """
    out = []
    for v in values:
        text = '' if v is None else str(v)
        if len(text) > CELL_LIMIT:
            text = text[:CELL_LIMIT] + ' [TRUNCATED, too long for one cell]'
        out.append("'" + text if _needs_quoting(text) else text)
    return out


# Digits and the punctuation people print phone numbers with, nothing else.
_NUMERICISH = re.compile(r'[0-9 ()+\-./]+')


def _needs_quoting(text):
    if text[:1] in ('=', '+', '-', '@'):
        return True
    # "07700900123" became 7939508778 and "0000" became 0. A leading zero on a
    # number is never decoration on a business card, it is part of the number.
    return bool(text[:1] == '0' and _NUMERICISH.fullmatch(text))


def _a1_col(n):
    out = ''
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def add(cfg, card, dry_run=False):
    # No config, or a config that names no destination, both mean CSV. Someone
    # with no CRM should still get their cards filed on day one.
    if not cfg or not cfg.get('destination'):
        return add_csv(cfg, card, dry_run)

    dest = cfg['destination']
    kind = dest.get('type', 'google_sheet')

    if kind == 'csv':
        return add_csv(cfg, card, dry_run)

    if kind == 'connector':
        # Notion, Airtable, HubSpot and the rest are reached through the
        # connector the user already has attached, not through a client bundled
        # in here. The script's job is to hand over a correctly mapped row, and
        # the caller does the write with the tool named in the config.
        headers = list((cfg.get('columns') or {}).keys())
        values, _ = build_row(headers, card, cfg)
        row = dict(zip(headers, values))
        print(json.dumps(row, indent=2))
        target = dest.get('target', 'the configured target')
        print(f'  Mapped row ready. Write it to {target} with '
              f'{dest.get("tool_hint", "the connector for this destination")}.')
        return row

    if kind != 'google_sheet':
        sys.exit(f'Unknown destination type {kind!r}. Use "google_sheet", "csv" '
                 'or "connector".')

    wb = open_workbook(cfg)
    ws = retry(lambda: wb.worksheet(dest['worksheet']))
    headers = [h.strip() for h in retry(lambda: ws.row_values(1))]

    values, missing = build_row(headers, card, cfg)
    if missing:
        if not cfg.get('create_missing_columns', False):
            print(f'  Config maps columns the sheet does not have: {missing}. '
                  f'They were not written. Set create_missing_columns to add them.')
        elif dry_run:
            print(f'  DRY RUN would add columns at the end: {missing}')
        else:
            headers = add_columns(ws, headers, missing)
            values, _ = build_row(headers, card, cfg)
            print(f'  Added columns at the end: {missing}')

    if dry_run:
        print(json.dumps(dict(zip(headers, values)), indent=2))
        print(f'  DRY RUN, nothing written to "{dest["worksheet"]}".')
        return None

    safe = sheet_safe(values)
    if dest.get('insert_at', 'top') == 'top':
        retry(lambda: ws.insert_row(safe, index=2,
                                    value_input_option='USER_ENTERED'))
        row_no = 2
    else:
        retry(lambda: ws.append_row(safe, value_input_option='USER_ENTERED',
                                    table_range=f'A1:{_a1_col(len(headers))}1'))
        row_no = len(retry(lambda: ws.get_all_values()))

    print(f'  Written to "{dest["worksheet"]}" row {row_no}.')
    return row_no


def csv_headers(cfg):
    """The CSV takes its shape from the config's columns, when there is one.

    A file whose headers match what the user asked for imports into their CRM
    later without a second mapping exercise.
    """
    if CSV_FALLBACK.exists():
        with open(CSV_FALLBACK, newline='') as fh:
            existing = next(csv.reader(fh), [])
        if existing:
            return existing
    if cfg and cfg.get('columns'):
        heads = list(cfg['columns'].keys())
        for header in (cfg.get('defaults') or {}):
            if header not in heads:
                heads.append(header)
        return heads
    return CSV_FIELDS


def add_csv(cfg, card, dry_run=False):
    headers = csv_headers(cfg)
    if cfg and cfg.get('columns'):
        values, _ = build_row(headers, card, cfg)
        row = dict(zip(headers, values))
    else:
        row = {k: card.get(k, '') for k in headers}
        if 'captured' in headers:
            row['captured'] = row.get('captured') or date.today().isoformat()

    if dry_run:
        print(json.dumps(row, indent=2))
        print(f'  DRY RUN, nothing written to {CSV_FALLBACK}.')
        return None

    new = not CSV_FALLBACK.exists()
    with open(CSV_FALLBACK, 'a', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction='ignore')
        if new:
            writer.writeheader()
        writer.writerow(row)
    if not cfg:
        why = 'No config found, so the card was'
    elif (cfg.get('destination') or {}).get('type') == 'csv':
        why = 'Card'
    else:
        why = 'No destination configured, so the card was'
    print(f'  {why} appended to {CSV_FALLBACK}.')
    return None


# ---------------------------------------------------------------- cli


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command',
                    choices=['check', 'add', 'init', 'where', 'learn'])
    ap.add_argument('--config')
    ap.add_argument('--company')
    ap.add_argument('--email')
    ap.add_argument('--name')
    ap.add_argument('--domain')
    ap.add_argument('--json', help='path to a card JSON file, or - for stdin')
    ap.add_argument('--multi', action='store_true',
                    help='the JSON holds a list of cards, not one card')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--path', default='schmoozing.config.json')
    ap.add_argument('--note', help='learn: what was got wrong, and what is right')
    ap.add_argument('--kind', help=f'learn: one of {", ".join(LEARNED_KINDS)}')
    ap.add_argument('--subject', help='learn: the person, company or card it came from')
    ap.add_argument('--limit', type=int, default=30, help='learn: how many to list')
    args = ap.parse_args()

    if args.command == 'init':
        target = Path(args.path).expanduser()
        if target.exists():
            sys.exit(f'{target} already exists, not overwriting it.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(EXAMPLE_CONFIG.read_text())
        print(f'Wrote {target}. Edit it, then run "card_capture.py where" to confirm.')
        return

    cfg, cfg_path = load_config(args.config)

    if args.command == 'learn':
        if args.note:
            learn_add(cfg_path, args.kind or 'correction', args.note, args.subject)
            return
        entries = learn_list(cfg_path, args.limit, args.kind)
        if not entries:
            print(f'Nothing learned yet. The log will be at '
                  f'{learned_path(cfg_path)}')
            return
        for e in entries:
            subject = f' [{e["subject"]}]' if e.get('subject') else ''
            print(f'{e["date"]}  {e["kind"]}{subject}: {e["note"]}')
        return

    if args.command == 'where':
        if not cfg:
            print('No config found. Cards will go to '
                  f'{CSV_FALLBACK.resolve()} as CSV.')
            _print_learned_count(cfg_path)
            return
        print(f'Config: {cfg_path}')
        country = (cfg.get('research') or {}).get('country', 'not set')
        dest = cfg.get('destination') or {}
        kind = dest.get('type', 'csv' if not dest else 'google_sheet')

        if kind == 'csv':
            reason = '' if dest else ' (no destination in the config)'
            print(f'Destination: CSV at {CSV_FALLBACK.resolve()}{reason}')
            print(f'Columns: {csv_headers(cfg)}')
            print(f'Research country: {country}')
            _print_learned_count(cfg_path)
            return

        if kind == 'connector':
            print(f'Destination: connector, target {dest.get("target", "not set")}')
            print(f'Write with: {dest.get("tool_hint", "not set")}')
            print(f'Columns: {list((cfg.get("columns") or {}).keys())}')
            print(f'Research country: {country}')
            print('Note: duplicate checking and writing both go through that '
                  'connector, not through this script.')
            if dest.get('learned'):
                print(f'Learned about this destination: '
                      f'{json.dumps(dest["learned"], indent=2)}')
            _print_learned_count(cfg_path)
            return

        print(f'Destination: {kind} {dest.get("sheet_id", "")} '
              f'tab "{dest.get("worksheet", "")}"')
        wb = open_workbook(cfg)
        ws = retry(lambda: wb.worksheet(dest['worksheet']))
        print(f'Workbook: {wb.title}')
        print(f'Live headers: {retry(lambda: ws.row_values(1))}')
        print(f'Research country: {country}')
        _print_learned_count(cfg_path)
        return

    if args.command == 'check':
        if not any([args.company, args.email, args.name, args.domain]):
            # An empty result here would read as "no duplicates found", which is
            # the most dangerous wrong answer this script can give.
            sys.exit('check needs something to look for: --company, --email, '
                     '--name or --domain. Nothing was searched.')
        hits = check(cfg, args.company, args.email, args.name, args.domain)
        print(json.dumps(hits, indent=2))
        if any(h['warn'] for h in hits):
            print('\nWARNING: a match sits in a tab flagged in warn_tabs. '
                  'Read it before contacting anyone.', file=sys.stderr)
        return

    if args.command == 'add':
        if not args.json:
            sys.exit('add needs --json')
        try:
            raw = (sys.stdin.read() if args.json == '-'
                   else Path(args.json).read_text())
        except FileNotFoundError:
            sys.exit(f'No card file at {args.json}. Write the card JSON first, '
                     'or pass - to read it from stdin.')
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            sys.exit(f'{args.json} is not valid JSON: {exc}. Nothing was '
                     'written. Fix the file and run it again.')

        cards = payload if args.multi else [payload]
        if not isinstance(cards, list):
            sys.exit('--multi expects a JSON list of cards.')
        if any(not isinstance(c, dict) for c in cards):
            sys.exit('Every card must be a JSON object. Did you mean --multi?')

        written = 0
        for card in cards:
            label = f'{card.get("name", "?")} at {card.get("company", "?")}'
            # A row with no company and no person is not a contact, and once it
            # is in a CRM nobody can tell what it was meant to be.
            if not card.get('company') and not card.get('name'):
                print(f'SKIPPED, no company and no name: {json.dumps(card)[:80]}',
                      file=sys.stderr)
                continue
            print(f'{label}:')
            add(cfg, card, args.dry_run)
            written += 1

        if written < len(cards):
            print(f'\n{len(cards) - written} of {len(cards)} cards were skipped. '
                  'See the lines above.', file=sys.stderr)


if __name__ == '__main__':
    main()
