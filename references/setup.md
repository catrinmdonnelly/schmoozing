# Setting this up

Setup is a conversation, not a form. If there is no config, do not send the user off to write JSON. Ask them the questions below, write the file for them, and prove it works before any card is processed.

The skill folder itself holds no personal data. Everything that names a CRM, a credential or a business lives in a config file outside it. That is what makes it safe to publish and easy to hand to someone else.

## The three questions

**1. Where should the contacts land?**

This is the only question with no sensible default, so ask it first.

Their answer is a job to do immediately, not a preference to record. Connect it before the first card, following `references/connect.md`, and check what connectors this session already has before you offer anything.

| Their answer | What to do |
|---|---|
| "Notion, Airtable, HubSpot" and a connector for it is attached | Best case. Use the connector, list what you can see so they can point at the right database rather than typing an ID, map onto their existing fields, write a test row, show them, delete it |
| Same tools, no connector attached | Ask whether one can be attached first. Otherwise use the CSV and their tool's own contacts import, which every one of them has |
| "A Google Sheet I already use" | Ask for the link, read the live column headers, map onto what is already there. Never rename or reorder their columns. Then walk the service account setup with them |
| "I have a spreadsheet but it is a mess" | Read it anyway. Map what fits, add the missing columns at the end where nothing shifts |
| "I have not got one" | Offer to create one, or use the CSV. Do not make a spreadsheet the price of entry |
| They are not sure | Use the CSV. `schmoozing-captures.csv` appears in the working directory with the columns they asked for and imports anywhere. Moving to a sheet later costs nothing |

**2. What do they want to know about a contact?**

The default columns cover company, name, role, sector, location, email, phone, website, LinkedIn, source, date met, notes, fit and next action. Ask what they would add. People who go to a lot of events usually want the event name; recruiters want current employer and specialism; property people want area. Add their answer as a column rather than burying it in notes.

**3. Who is actually worth their time?**

This is the question that makes the skill worth having, and it is the one most people skip. Their answer becomes `fit_profile` in the config, and the model reads it as plain sentences, so it should read like briefing a new salesperson:

- Who is a good customer. Size, ownership, sector, and the problem being solved.
- The disqualifiers. The kinds of business that have never bought from them, however promising they looked.
- Whether referral routes and partners matter as much as prospects, and where those should go.

"Small businesses" produces a verdict worth nothing. "Owner-managed, ten to a hundred staff, where one named person spends hours a day on repetitive work" produces a verdict they can act on.

Also ask what country most of their contacts are in. It decides which sources the research can use, and it is in `research.country`.

## Pointing it at a Google Sheet

1. **Service account.** In Google Cloud, create a project, enable the Google Sheets API and the Google Drive API, create a service account, and download its JSON key. Save it somewhere private, for example `~/.secrets/service-account.json`, and never commit it.
2. **Share the sheet** with the service account's email address, as Editor. This is the step everyone forgets, and it fails with a 403 that reads like a credentials problem.
3. **Write the config** for them. `python3 scripts/card_capture.py init` drops the template, then fill it in from their answers. The sheet ID is the long string in the sheet URL between `/d/` and `/edit`.
4. **Map columns exactly** as they are spelled in the sheet, capitals and spaces included. A mapped column the sheet does not have is skipped with a warning, or added at the end when `create_missing_columns` is true. New columns always go at the end so nothing already in the sheet shifts.
5. **Prove it.** `python3 scripts/card_capture.py where` prints the workbook, the tab and the live headers. Then run the first real card with `--dry-run` and show them the mapped row before writing it.

Python needs `gspread` and `google-auth` for a sheet. Nothing else here needs a package.

## No sheet, no problem

Leave `destination` out of the config, or run with no config at all, and every card is appended to `schmoozing-captures.csv` in the working directory. That file imports into any CRM. The skill is useful on day one without a Google account, and the research is identical either way.

## A different CRM

Replace `open_workbook` and `add` in `scripts/card_capture.py` with calls to that CRM's API. Keep `check` doing a real duplicate search across everything, because that is the step that stops the same person being added three times across a year of events.

## Country, and the registry lookup

`scripts/uk_companies_house.py` is the only country-specific piece, and it is optional. It needs a free key from the [Companies House developer site](https://developer.company-information.service.gov.uk/), read from `$COMPANIES_HOUSE_KEY` or `~/.secrets/companies-house-key.txt`.

Outside the UK, there is nothing to install. The research falls back to general search, the company's own site, LinkedIn and, where they exist and are free, national or state registers. `references/research.md` says what to use where. Set `research.country` in the config so the model does not go hunting for filings that do not exist.

## Publishing this skill

The folder is already portable. Before sharing it, check three things:

- No config file was saved inside the skill folder. `config.example.json` is a template and holds no real IDs.
- No card images or captured CSVs are sitting in the folder.
- The scripts read credentials from environment variables and paths given at run time, and nothing is hardcoded.

Then publish the folder as it is. A new user answers three questions and is working.
