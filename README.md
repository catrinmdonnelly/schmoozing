# Schmoozing

**Turn a pile of business cards into a researched pipeline.**

You have just got back from an event with a pocket full of cards. Now comes the tedious bit: typing them in, finding the right company, filling in the gaps, and deciding who is actually worth pursuing.

Schmoozing does it in one pass.

Photograph the cards. We will turn them into pipeline.

It reads the details, checks them against independent sources, researches the person and the business, and adds a clean, useful record to your CRM, with a verdict and a next action where it can.

So instead of a stack of cards waiting to be processed, you have a pipeline ready to work.

## Install

```
/plugin marketplace add catrinmdonnelly/schmoozing
/plugin install schmoozing@schmoozing
```

Or drop it in as a plain skill:

```bash
git clone https://github.com/catrinmdonnelly/schmoozing ~/.claude/skills/schmoozing
```

Then photograph a card and say **"scan this card"**.

Needs Python 3, which every Mac has. `gspread` and `google-auth` only if you send them to a Google Sheet.

## What happens to each card

1. **It reads the card.** Claude reads the image directly, so there is no OCR library and the photo is not uploaded anywhere. It copes with two-sided cards, QR codes, bilingual cards, generic inboxes, and the difference between a trading name and a registered one.
2. **It checks you have not met them before.** Searching your existing contacts first stops the same person going in three times across a year of events, and stops you emailing someone you archived last year.
3. **It checks the card against reality.** Phone against the company's own website, email domain against DNS, name spelling against the companies register, job title against their profile. A card is a printed claim, often years old.
4. **It researches the business.** What they sell and how an order actually reaches them, evidence of size and ownership, recent news, the person's LinkedIn.
5. **It gives a verdict.** Against your definition of a good contact, not a generic one. The verdict is allowed to be no.
6. **It writes one record** with a next action specific enough to act on, and the date it is owed.

## Why it is not a card scanner

**It tells you what it is not sure about.** Every record carries an `unverified` field naming what could not be read, could not be confirmed, or was inferred rather than printed. An uncertain email goes there with the reason, never in the email field, because a plausible wrong address looks correct forever. An empty `unverified` field is a claim that everything in that record was checked against a source.

**It learns.** Correct it once and the correction goes into a log it reads before every future run. Names it read wrong, verdicts you overruled, card layouts that caught it out. Being corrected twice for the same thing is what makes people abandon a tool.

**It knows where it cannot check.** UK companies get Companies House, which is free and definitive. The United States has no national register, so it uses general search, the state Secretary of State and SEC EDGAR, and marks size figures as claimed rather than filed. It will tell you a number is unproven instead of inventing confidence.

## Setup is three questions

The first time you use it, it asks:

1. **Where should the contacts land?** A Google Sheet, a CRM you already have a connector for, or nothing at all. With no answer it writes a CSV that imports anywhere, so it is useful before you have set anything up.
2. **What do you want to know about a contact?** It maps onto your existing columns and never renames them.
3. **Who is actually worth your time?** This is the one that matters. "Small businesses" produces verdicts worth nothing. Describe your good customer, and more usefully the ones who have never bought from you however promising they looked.

Then it connects to your answer to the first question there and then, writes a test record, shows it to you, and deletes it. Only after that does it touch a real card.

There is no list of supported CRMs, deliberately. If you have a connector attached for Notion, Airtable, HubSpot or anything else, it works the tool out at runtime: finds your databases, reads their real fields and types, maps onto your names, tests a write, and records what it learned so the next session starts where the last one finished.

## Honest limits

- **The verdict is only as good as your fit profile.** Write it properly and it earns its place. Leave it vague and this is a fancy OCR tool.
- **LinkedIn cannot be fetched**, so it works from what search results show and says so rather than pretending it read the profile.
- **Outside the UK, size and ownership are usually claimed rather than filed.** It attributes them instead of stating them.
- **Google Sheets setup needs your own Google Cloud console.** Fifteen minutes, walked through, and it cannot be automated away.
- **A connector destination cannot be duplicate-checked by the bundled script.** It says so loudly rather than returning an empty result that reads like "no duplicates found".

## What is in here

| Path | What |
|---|---|
| `SKILL.md` | The workflow Claude follows |
| `references/extraction.md` | Field list, confidence rules, and the card-reading traps |
| `references/research.md` | The research plan, the cross-check table, and what to do per country |
| `references/connect.md` | Connecting to each kind of destination and proving it works |
| `references/setup.md` | The three setup questions, and publishing this for someone else |
| `scripts/card_capture.py` | Duplicate check and the safe write |
| `scripts/uk_companies_house.py` | UK Companies House lookup. Optional, and UK only |

## Security

Two readable Python files and some markdown. No MCP server, no binaries, no telemetry, nothing phones home.

Nothing personal lives in this repo. Your destination, credentials, column mapping and fit profile all sit in a config file outside the skill folder, and no API key is stored here or printed back into the chat. Installing any plugin runs its code on your machine, so read the two scripts before you install this. They are short on purpose.

## Why it exists

I run an AI consultancy for small businesses, and the honest version of that job is noticing where someone is doing something repetitive by hand. Mine was business cards. Every event produced a pocketful, and the pocketful produced nothing, because the work was never the typing. It was the twenty minutes of research per card that decides whether a person is worth an email.

Built and tested on real cards from a real event, which is also how the bugs got found. One of them: Google Sheets reads a phone number printed as `+44 7700 900123` as a formula and stores `#ERROR!`, silently. If you are writing contact data into Sheets, check that one first.

**From a pocketful of cards to pipeline.**

## Licence

MIT. Do what you like with it.
