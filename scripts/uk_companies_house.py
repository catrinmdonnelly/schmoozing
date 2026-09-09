#!/usr/bin/env python3
"""Companies House lookup for a UK company on a business card.

UK ONLY, and optional. There is no equivalent script for anywhere else because
there is nothing equivalent to read: the United States has no national companies
register, and most other countries have one whose access ranges from free to
paid and awkward. Outside the UK the research falls back to general search, the
company's own site, and any free national or state register. See
references/research.md.

Without an API key the skill still works, it just relies on web research instead
of filings. With a key you get the things nobody at a networking event knows
about a business: real size band, who actually owns it, whether it is
independent or part of a group, and whether it is still trading.

Key resolution order:
    $COMPANIES_HOUSE_KEY
    $CH_API_KEY
    ~/.secrets/companies-house-key.txt
The key is never stored in this folder and never printed back into the chat.
A free key comes from https://developer.company-information.service.gov.uk/

Usage:
    python3 uk_companies_house.py "Acme Fabrications"
    python3 uk_companies_house.py --number 01234567
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://api.company-information.service.gov.uk'

KEY_FILES = [
    Path.home() / '.secrets' / 'companies-house-key.txt',
]

# Accounts type is the most reliable public size signal for a private company.
BANDS = {
    'micro-entity': 'micro, under £632k turnover',
    'micro entity': 'micro, under £632k turnover',
    'total-exemption-full': 'small, under £10.2m turnover (exempt from disclosing)',
    'total-exemption-small': 'small, under £10.2m turnover (exempt from disclosing)',
    'small': 'small, under £10.2m turnover',
    'small-full': 'small, under £10.2m turnover',
    'medium': 'medium, £10.2m to £36m turnover',
    'full': 'medium or large, £10.2m+ turnover, full accounts filed',
    'group': 'group accounts, so part of a wider structure',
    'audit-exemption-subsidiary': 'subsidiary of a group, audited at parent level',
    'dormant': 'dormant, not trading',
}


def api_key():
    for var in ('COMPANIES_HOUSE_KEY', 'CH_API_KEY'):
        if os.environ.get(var):
            return os.environ[var].strip()
    for path in KEY_FILES:
        if path.is_file():
            return path.read_text().strip()
    sys.exit('No Companies House API key found. Set $COMPANIES_HOUSE_KEY or '
             'save one at ~/.secrets/companies-house-key.txt. '
             'Free key: https://developer.company-information.service.gov.uk/')


def get(path, params=None):
    url = BASE + path + ('?' + urllib.parse.urlencode(params) if params else '')
    token = base64.b64encode(f'{api_key()}:'.encode()).decode()
    req = urllib.request.Request(url, headers={'Authorization': f'Basic {token}'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise


def profile_summary(number):
    prof = get(f'/company/{number}')
    if not prof:
        return {}
    accounts = (prof.get('accounts') or {}).get('last_accounts') or {}
    acc_type = (accounts.get('type') or '').lower()

    officers = get(f'/company/{number}/officers', {'items_per_page': 50})
    active = [o for o in (officers.get('items') or []) if not o.get('resigned_on')]
    resigned = [o for o in (officers.get('items') or []) if o.get('resigned_on')]

    pscs = get(f'/company/{number}/persons-with-significant-control',
               {'items_per_page': 25})
    psc_items = pscs.get('items') or []
    corporate_owner = any(p.get('kind', '').startswith('corporate')
                          for p in psc_items)

    return {
        'name': prof.get('company_name'),
        'number': number,
        'status': prof.get('company_status'),
        'incorporated': prof.get('date_of_creation'),
        'address': ', '.join(
            v for k, v in (prof.get('registered_office_address') or {}).items()
            if k in ('address_line_1', 'locality', 'postal_code') and v),
        'sic_codes': prof.get('sic_codes') or [],
        'accounts_type': acc_type,
        'size_signal': BANDS.get(acc_type, 'unknown from accounts type'),
        'last_accounts_to': accounts.get('period_end_on'),
        'next_accounts_due': (prof.get('accounts') or {}).get('next_due'),
        'active_officers': [
            {'name': o.get('name'), 'role': o.get('officer_role'),
             'appointed': o.get('appointed_on'),
             'occupation': o.get('occupation', '')}
            for o in active],
        'recent_resignations': [
            {'name': o.get('name'), 'resigned': o.get('resigned_on')}
            for o in sorted(resigned, key=lambda x: x.get('resigned_on') or '',
                            reverse=True)[:5]],
        'owners': [{'name': p.get('name'),
                    'kind': p.get('kind'),
                    'control': p.get('natures_of_control', [])}
                   for p in psc_items],
        'independent': not corporate_owner and bool(psc_items),
    }


def search(name, limit=5):
    res = get('/search/companies', {'q': name, 'items_per_page': limit})
    return [{'title': i.get('title'),
             'number': i.get('company_number'),
             'status': i.get('company_status'),
             'address': i.get('address_snippet')}
            for i in (res.get('items') or [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name', nargs='?')
    ap.add_argument('--number', help='look a known company number up directly')
    ap.add_argument('--all', action='store_true',
                    help='profile every search hit, not just the best one')
    args = ap.parse_args()

    if args.number:
        print(json.dumps(profile_summary(args.number), indent=2))
        return
    if not args.name:
        ap.error('give a company name or --number')

    hits = search(args.name)
    if not hits:
        print(json.dumps({'matches': [], 'note': 'nothing on Companies House '
                                                 'under that name'}, indent=2))
        return

    out = {'matches': hits}
    targets = hits if args.all else hits[:1]
    out['profiles'] = [profile_summary(h['number']) for h in targets
                       if h.get('number')]
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
