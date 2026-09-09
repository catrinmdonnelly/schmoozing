# Connecting to where they want the contacts

The answer to "where should these land" is not a preference to write down, it is a job to do now. Connect it, write a test row, show them the test row in their own tool, then delete it. Nobody should scan their first card wondering whether it went anywhere.

**Look before you ask.** Check what tools this session already has attached before offering options. If there is a Notion, Airtable, HubSpot or Google connector available, the connection is nearly free and you should lead with it. Offering someone a service account walkthrough when they already have the connector attached wastes their afternoon.

## Route 1, a connector is already attached

The best case, and increasingly the normal one.

**There is no list of supported CRMs here on purpose.** This skill is not going to ship an integration per tool and wait for the world to stop inventing them. Work the connector out at runtime, whatever it is, including one nobody has ever pointed this skill at before. The procedure below is the same for Notion, Airtable, HubSpot, Attio, Monday, Pipedrive or something that launched last week.

### Work it out, in this order

**1. Discover what is actually attached.** Look at the tools available in this session and find the ones that read and write records in the user's CRM. Judge them by what they do, not by their names. A tool called `create-page` may be exactly the row writer you need, and a tool with the CRM's name in it may only read analytics.

**2. Probe before you ask.** Use the connector's own listing or search capability to see what exists: databases, bases, tables, pipelines, boards. Then show the user that list and let them point at one. Asking a person for an internal ID is a failure of nerve. Never guess an ID and never invent one.

**3. Read the target's real schema.** Fetch the target and look at its actual fields, including their types. This is the step that decides whether the write succeeds:

- A plain text field takes anything.
- A select or status field usually rejects a value that is not already an option. Either use an existing option or create it deliberately, and say which you did.
- Date fields want a specific format, usually ISO.
- Email, phone and URL fields validate, so a malformed value fails the whole write rather than just that field.
- Relations and linked records need the id of the thing they point at, not its name.

**4. Map onto their names, not yours.** Their field called "Org" takes the company. Do not create a duplicate field called "Company" alongside it. Only add a field when there is genuinely nowhere for something important to go, and say so when you do.

**5. Test with one real write, then read it back.** A tool reporting success is not proof the record saved correctly. Fetch the record you just created, check the values actually landed in the right fields, show it to the user, then delete it.

**6. Write down what you learned.** This is the part that makes it stick. The config gets the destination, the tools that worked, and the quirks you discovered, so the next session does not re-derive any of it:

```json
"destination": {
  "type": "connector",
  "target": "Contacts database, id 24f1a...",
  "tool_hint": "notion create-pages, one page per contact",
  "learned": {
    "search_with": "notion search restricted to that database, query the email first",
    "field_types": "Status is a select with options New, Warm, Client. Met is a date, ISO only. Website is a URL field and rejects bare domains, so prefix https://",
    "gotchas": "Creating a page needs the data source id, not the page id of the database"
  }
}
```

`learned` is free text for the next run to read. Anything that cost you a failed attempt belongs in it.

### Duplicate checking on this route

The script cannot see inside someone else's CRM, so `card_capture.py check` will tell you it did not run. Do it yourself with the connector, and do it before every write: search the email first because it is the most reliable identifier, then the company name, then the person's name. Record how to search in `learned.search_with` so the next session does not have to work it out again.

### When the connector cannot write

Some connectors are read-only, and some fail on a field type you cannot satisfy. Do not fake it and do not keep retrying variations for twenty minutes. Tell the user what failed and in which field, then fall back to the CSV so their cards are still captured today, and note the blocker in the config so nobody repeats the attempt.

### What the script does here

`card_capture.py add` maps the card onto the configured columns and hands back a correct row, which you then write with the connector. That division is deliberate: the mapping, the fit verdict and the research are the same everywhere, and only the last inch differs by tool.

## Route 2, a Google Sheet

Fifteen minutes, and it needs their Google Cloud console, so you cannot do it for them. Walk them through it and stay with them.

1. **Create the sheet, or take a link to the one they use.** The sheet ID is the long string between `/d/` and `/edit`.
2. **Google Cloud.** Create a project, enable the Google Sheets API and the Google Drive API, create a service account, then create a JSON key for it and download it.
3. **Save the key** somewhere private, for example `~/.secrets/service-account.json`. Never in the skill folder, never in a repo.
4. **Share the sheet with the service account's email address, as Editor.** This is the step everyone misses. Without it you get a 403 that reads like a broken credential.
5. **Write the config**, mapping their existing headers exactly as spelled.
6. **Prove it**: `card_capture.py where` prints the workbook and the live headers. Then dry run a card, then write one real row and let them look at it.

If they do not have a Google account or do not want the console work, do not push it. Use route 3 and offer to move them later, which costs nothing because the CSV carries the same columns.

## Route 3, a CSV

The default when there is no CRM, no connector, or no appetite for setup. Nothing to connect. Cards append to `schmoozing-captures.csv` in the working directory, with the columns they asked for, and it imports into every CRM on the market.

Say plainly that this is a real option rather than a consolation prize. Someone who has been keeping cards in a drawer is better served by a file that exists today than by a spreadsheet integration they abandon halfway through.

## Route 4, a CRM with no connector attached

Their CRM has an API, but a client hand-rolled in the middle of someone's first session, tested against nothing, is worse than an honest limit. Offer, in this order:

1. Check whether a connector for it can be attached. That is route 1, it is always better, and route 1 does not care whether the tool is one this skill has seen before.
2. Export to CSV and import. Every CRM has a contacts import that maps columns, and the CSV already carries their field names.
3. Only build a direct integration if they ask for it and will test it with you. It means replacing `open_workbook` and `add` in `card_capture.py`, and keeping `check` doing a real duplicate search, which is the part that stops the same person going in three times over a year of events.

## Whatever the route

- Prove the connection with a real write before the first card, then remove the test row.
- Never invent an ID, a sheet, a database or a token. If you cannot see it, ask for it.
- Credentials live outside the skill folder, always, and never get printed back into the chat.
- Record what you connected to in the config so the next session does not ask again.
